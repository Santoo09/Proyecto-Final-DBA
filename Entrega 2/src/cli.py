"""CLI principal para la Entrega 2.

Subcomandos:
    verify     — verifica el ZIP del MGN (SHA-256, capas, tamaño).
    crosscheck — cruza el CSV PDET vs MGN.
    ingest     — pipeline completo: verify → crosscheck → integrity → load → audit → scorecard.
    audit      — lista las últimas corridas.
    scorecard  — regenera el scorecard de la última corrida exitosa.
"""

from __future__ import annotations

import argparse
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .config import CONFIG


def _connect():
    from pymongo import MongoClient
    client = MongoClient(CONFIG.mongo_uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    return client, client[CONFIG.db_name]


def cmd_verify(args: argparse.Namespace) -> int:
    from .acquisition import verify_mgn
    report = verify_mgn(CONFIG.mgn_zip_path, expected_sha256=args.sha256)
    print(f"File:    {report.file}")
    print(f"Size:    {report.size_bytes:,} bytes")
    print(f"SHA-256: {report.sha256}")
    print(f"Layer:   {'OK' if report.has_expected_layer else 'MISSING'}")
    if report.errors:
        print("ERRORS:")
        for e in report.errors:
            print(f"  - {e}")
        return 2
    print("OK")
    return 0


def cmd_crosscheck(args: argparse.Namespace) -> int:
    from .crosscheck import load_decreto, run_crosscheck
    import geopandas as gpd

    decreto = load_decreto(CONFIG.decreto_csv)
    gdf = _read_mgn_municipalities()
    records = [
        {"divipola": r.divipola, "mpio_cnmbr": r.mpio_cnmbr}
        for _, r in gdf.iterrows()
    ]
    report = run_crosscheck(decreto, records, CONFIG.expected_pdet_count)

    print(f"Decreto count:     {report.decreto_count}")
    print(f"MGN ∩ PDET count:  {report.mgn_pdet_count}")
    print(f"Faltantes en MGN:  {len(report.missing_in_mgn)}")
    print(f"Diferencias nombre:{len(report.name_mismatches)}")
    if report.missing_in_mgn:
        print("  FALTANTES:", report.missing_in_mgn)
    return 0 if report.ok else 3


def _read_mgn_municipalities():
    """Lee la capa municipal del ZIP del MGN como GeoDataFrame (EPSG:4326)."""
    import geopandas as gpd
    zip_path = CONFIG.mgn_zip_path
    if not zip_path.exists():
        raise FileNotFoundError(
            f"No se encontró el ZIP del MGN en {zip_path}. "
            "Ver Entrega2/data/README.md para instrucciones de descarga."
        )

    with zipfile.ZipFile(zip_path) as zf:
        shp_path = next(
            n for n in zf.namelist()
            if CONFIG.mgn_layer in n and n.endswith(".shp")
        )

    # Fiona/geopandas requiere una ruta absoluta con separadores POSIX
    # cuando se accede vía protocolo zip://.
    zip_abs = str(zip_path.resolve()).replace("\\", "/")
    uri = f"zip://{zip_abs}!{shp_path}"
    gdf = gpd.read_file(uri)

    # Los campos del shapefile vienen en minúsculas pero los valores de texto
    # pueden venir en mayúsculas (MEDELLÍN). Normalizamos a Title Case para
    # comparación legible con el Decreto 893.
    gdf = gdf.rename(columns=str.lower)
    for col in ("mpio_cnmbr", "dpto_cnmbr"):
        if col in gdf.columns:
            gdf[col] = gdf[col].astype(str).str.strip().str.title()

    # En el MGN 2025 el código DIVIPOLA viene listo en `mpio_cdpmp`. Si por
    # alguna razón no estuviera, lo reconstruimos a partir de los códigos
    # departamental y municipal.
    if "mpio_cdpmp" in gdf.columns:
        gdf["divipola"] = gdf["mpio_cdpmp"].astype(str).str.zfill(5)
    else:
        gdf["divipola"] = (
            gdf["dpto_ccdgo"].astype(str).str.zfill(2)
            + gdf["mpio_ccdgo"].astype(str).str.zfill(3)
        )

    if gdf.crs is None or gdf.crs.to_string() != CONFIG.crs_storage:
        gdf = gdf.to_crs(CONFIG.crs_storage)
    return gdf


def cmd_ingest(args: argparse.Namespace) -> int:
    from .acquisition import verify_mgn
    from .crosscheck import load_decreto, run_crosscheck
    from .integrity import build_documents
    from .loader import upsert_municipalities, post_validate
    from .audit import open_run, close_run, close_aborted_runs
    from .scorecard import render_scorecard
    from dataclasses import asdict

    client, db = _connect()
    close_aborted_runs(db, entrega="W2")
    run = open_run(db, entrega="W2", tool_version=CONFIG.tool_version)
    perf: dict[str, int] = {}

    try:
        # 1) Verify
        t0 = time.time()
        acq = verify_mgn(CONFIG.mgn_zip_path, expected_sha256=args.sha256)
        perf["verify"] = int((time.time() - t0) * 1000)
        run["source"] = {
            "file": str(acq.file),
            "size_bytes": acq.size_bytes,
            "sha256": acq.sha256,
            "mgn_version": CONFIG.mgn_version,
            "downloaded_at": datetime.now(timezone.utc),
        }
        if not acq.ok and not args.force:
            run["errors"].extend({"stage": "verify", "msg": e} for e in acq.errors)
            close_run(db, run, "failed_verification", CONFIG.manifests_dir)
            return 2

        # 2) Crosscheck
        t0 = time.time()
        decreto = load_decreto(CONFIG.decreto_csv)
        gdf = _read_mgn_municipalities()
        cc = run_crosscheck(
            decreto,
            ({"divipola": r.divipola, "mpio_cnmbr": r.mpio_cnmbr}
             for _, r in gdf.iterrows()),
            CONFIG.expected_pdet_count,
        )
        perf["crosscheck"] = int((time.time() - t0) * 1000)
        run["crosscheck"] = asdict(cc)
        if not cc.ok and not args.force:
            close_run(db, run, "failed_verification", CONFIG.manifests_dir)
            return 3

        # 3) Integrity
        t0 = time.time()
        pdet_set = {e.divipola for e in decreto}
        gdf_pdet = gdf[gdf["divipola"].isin(pdet_set)].copy()
        decreto_idx = {e.divipola: {"pdet_subregion": e.pdet_subregion} for e in decreto}
        docs, integ = build_documents(
            gdf_pdet,
            decreto_index=decreto_idx,
            source_meta={
                "mgn_version": CONFIG.mgn_version,
                "sha256": acq.sha256,
                "downloaded_at": run["source"]["downloaded_at"],
            },
            run_id=run["_id"],
            simplify_tolerance_deg=CONFIG.simplify_tolerance_deg,
            area_tolerance_pct=CONFIG.area_tolerance_pct,
            crs_metric=CONFIG.crs_metric,
        )
        perf["integrity"] = int((time.time() - t0) * 1000)
        run["integrity"] = asdict(integ)

        # 4) Load
        t0 = time.time()
        load_report = upsert_municipalities(db, docs)
        perf["load"] = int((time.time() - t0) * 1000)
        run["load"] = asdict(load_report)

        # 5) Post-validate
        # La verdad operativa es el CSV del Decreto 893 cargado. Si el equipo
        # corre con la plantilla seed (16 mpios), se valida contra 16; si corre
        # con el listado completo (170), se valida contra 170. El campo
        # `completeness` deja explícito qué tipo de corrida fue.
        t0 = time.time()
        expected = len(decreto)
        expected_subregions = len({e.pdet_subregion for e in decreto})
        post = post_validate(db, expected, expected_subregions)
        perf["post_validate"] = int((time.time() - t0) * 1000)
        run["post_validation"] = asdict(post)
        run["completeness"] = {
            "decreto_count": expected,
            "is_full_pdet": expected == CONFIG.expected_pdet_count,
            "subregions_in_csv": expected_subregions,
            "label": "complete" if expected == CONFIG.expected_pdet_count else "seed_partial",
        }

        status = "success" if post.ok and not load_report.errors else "failed_post_validation"
        run["performance_ms"] = perf

        manifest_path = close_run(db, run, status, CONFIG.manifests_dir)
        sc_path = render_scorecard(run, CONFIG.reports_dir)
        print(f"Status:   {status}")
        print(f"Manifest: {manifest_path}")
        print(f"Scorecard:{sc_path}")
        return 0 if status == "success" else 4

    except Exception as exc:  # pragma: no cover
        run["errors"].append({"stage": "fatal", "msg": str(exc)})
        close_run(db, run, "failed_post_validation", CONFIG.manifests_dir)
        raise


def cmd_audit(args: argparse.Namespace) -> int:
    _, db = _connect()
    cursor = (
        db.ingest_runs.find({"entrega": "W2"})
        .sort("started_at", -1)
        .limit(args.limit)
    )
    for run in cursor:
        print(
            f"{run.get('started_at')} | {run.get('status'):>26} | "
            f"docs={run.get('post_validation', {}).get('total', '?')} | "
            f"manifest={run.get('manifest_path', '-')}"
        )
    return 0


def cmd_scorecard(args: argparse.Namespace) -> int:
    from .scorecard import render_scorecard
    _, db = _connect()
    run = db.ingest_runs.find_one(
        {"entrega": "W2", "status": "success"},
        sort=[("finished_at", -1)],
    )
    if not run:
        print("No hay corridas exitosas para W2.", file=sys.stderr)
        return 1
    path = render_scorecard(run, CONFIG.reports_dir)
    print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="entrega2", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    pv = sub.add_parser("verify", help="Verifica el ZIP del MGN")
    pv.add_argument("--sha256", help="SHA-256 esperado (opcional)")
    pv.set_defaults(func=cmd_verify)

    pc = sub.add_parser("crosscheck", help="Cruza Decreto 893 vs MGN")
    pc.set_defaults(func=cmd_crosscheck)

    pi = sub.add_parser("ingest", help="Pipeline completo")
    pi.add_argument("--sha256", help="SHA-256 esperado del ZIP")
    pi.add_argument("--force", action="store_true",
                    help="Continúa aunque verify/crosscheck arrojen warnings")
    pi.set_defaults(func=cmd_ingest)

    pa = sub.add_parser("audit", help="Lista últimas corridas")
    pa.add_argument("--limit", type=int, default=10)
    pa.set_defaults(func=cmd_audit)

    ps = sub.add_parser("scorecard", help="Regenera scorecard de la última corrida ok")
    ps.set_defaults(func=cmd_scorecard)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
