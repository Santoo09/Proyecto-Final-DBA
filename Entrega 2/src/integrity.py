"""Validación, reparación y normalización de geometrías."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

try:
    import geopandas as gpd
    from shapely.geometry import mapping, Polygon, MultiPolygon
    from shapely.geometry.polygon import orient
    from shapely.validation import make_valid
except ImportError:  # pragma: no cover
    gpd = None  # permite que los tests unitarios corran sin geopandas


def _orient_ccw(geom):
    """Orienta el anillo exterior CCW y los huecos CW (requisito de MongoDB 2dsphere)."""
    if geom.geom_type == "Polygon":
        return orient(geom, sign=1.0)
    if geom.geom_type == "MultiPolygon":
        return MultiPolygon([orient(p, sign=1.0) for p in geom.geoms])
    return geom


@dataclass
class RepairRecord:
    divipola: str
    action: str
    delta_area_km2: float
    delta_area_pct: float


@dataclass
class IntegrityReport:
    total_in_pdet: int = 0
    valid_geom: int = 0
    repaired: int = 0
    rejected: int = 0
    repairs: list[RepairRecord] = field(default_factory=list)
    rejected_ids: list[str] = field(default_factory=list)
    area_total_km2: float = 0.0


def _is_in_colombia_bbox(bounds: tuple[float, float, float, float]) -> bool:
    minx, miny, maxx, maxy = bounds
    return -82 <= minx and maxx <= -66 and -5 <= miny and maxy <= 13


def build_documents(
    gdf,                                # GeoDataFrame ya filtrado a PDET
    decreto_index: dict[str, dict],     # {divipola: {pdet_subregion, ...}}
    source_meta: dict,
    run_id,                             # ObjectId del registro en ingest_runs
    simplify_tolerance_deg: float = 0.001,
    area_tolerance_pct: float = 0.01,
    crs_metric: str = "EPSG:9377",
) -> tuple[list[dict], IntegrityReport]:
    """Convierte un GeoDataFrame de polígonos MGN a documentos MongoDB válidos.

    Espera que `gdf` ya esté en EPSG:4326 y filtrado a los 170 PDET.
    """
    if gpd is None:  # pragma: no cover
        raise RuntimeError("geopandas no instalado")

    report = IntegrityReport(total_in_pdet=len(gdf))

    gdf_metric = gdf.to_crs(crs_metric)

    documents: list[dict] = []
    now = datetime.now(timezone.utc)

    for (idx, row), (_, row_m) in zip(gdf.iterrows(), gdf_metric.iterrows()):
        divipola: str = row["divipola"]
        geom = row.geometry
        geom_m = row_m.geometry

        area_before_km2 = geom_m.area / 1e6
        action: Optional[str] = None

        if not geom.is_valid:
            repaired = make_valid(geom)
            repaired_m = make_valid(geom_m)
            new_area = repaired_m.area / 1e6
            delta = new_area - area_before_km2
            pct = abs(delta) / max(area_before_km2, 1e-9)

            if pct > area_tolerance_pct:
                report.rejected += 1
                report.rejected_ids.append(divipola)
                continue

            geom = repaired
            area_before_km2 = new_area
            action = "make_valid"
            report.repaired += 1
            report.repairs.append(
                RepairRecord(
                    divipola=divipola,
                    action=action,
                    delta_area_km2=round(delta, 6),
                    delta_area_pct=round(pct, 6),
                )
            )
        else:
            report.valid_geom += 1

        if geom.is_empty or area_before_km2 <= 0:
            report.rejected += 1
            report.rejected_ids.append(divipola)
            continue

        if not _is_in_colombia_bbox(geom.bounds):
            report.rejected += 1
            report.rejected_ids.append(divipola)
            continue

        # MongoDB 2dsphere exige anillos exteriores en sentido antihorario.
        # Los shapefiles del DANE (y muchos otros) vienen en CW, lo que provoca
        # que $geoIntersects con puntos interiores retorne vacío. Reorientamos
        # explícitamente antes de serializar a GeoJSON.
        geom = _orient_ccw(geom)
        simplified = _orient_ccw(
            geom.simplify(simplify_tolerance_deg, preserve_topology=True)
        )
        minx, miny, maxx, maxy = geom.bounds

        decreto_info = decreto_index[divipola]

        doc = {
            "divipola": divipola,
            "mpio_cnmbr": row["mpio_cnmbr"],
            "dpto_ccdgo": row["dpto_ccdgo"],
            "dpto_cnmbr": row["dpto_cnmbr"],
            "is_pdet": True,
            "pdet_subregion": decreto_info["pdet_subregion"],
            "geometry": mapping(geom),
            "geometry_simplified": mapping(simplified),
            "area_km2": float(area_before_km2),
            "bbox": [float(minx), float(miny), float(maxx), float(maxy)],
            "source": {
                "name": "DANE-MGN",
                "version": source_meta["mgn_version"],
                "file_sha256": source_meta["sha256"],
                "downloaded_at": source_meta["downloaded_at"],
                "ingest_run_id": run_id,
            },
            "ingested_at": now,
        }
        documents.append(doc)
        report.area_total_km2 += area_before_km2

    return documents, report
