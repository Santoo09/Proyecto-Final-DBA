"""Auditoría: colección `ingest_runs` y manifests JSON locales."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat().replace("+00:00", "Z")
    if isinstance(obj, Path):
        return str(obj)
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "binary"):  # bson.ObjectId
        return str(obj)
    raise TypeError(f"No serializable: {type(obj).__name__}")


def open_run(db, entrega: str, tool_version: str) -> dict:
    """Crea un documento `ingest_runs` con status `running`. Devuelve el doc con `_id`."""
    doc = {
        "entrega": entrega,
        "tool_version": tool_version,
        "started_at": datetime.now(timezone.utc),
        "finished_at": None,
        "status": "running",
        "source": {},
        "crosscheck": {},
        "integrity": {},
        "load": {},
        "post_validation": {},
        "performance_ms": {},
        "errors": [],
    }
    result = db.ingest_runs.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def close_run(db, run_doc: dict, status: str, manifests_dir: Path) -> Path:
    """Cierra la corrida en Mongo y escribe el manifest JSON local."""
    run_doc["finished_at"] = datetime.now(timezone.utc)
    run_doc["status"] = status
    duration = (run_doc["finished_at"] - run_doc["started_at"]).total_seconds()
    run_doc["duration_seconds"] = round(duration, 3)

    db.ingest_runs.update_one(
        {"_id": run_doc["_id"]},
        {
            "$set": {
                k: v for k, v in run_doc.items() if k != "_id"
            }
        },
    )

    manifests_dir.mkdir(parents=True, exist_ok=True)
    ts = run_doc["started_at"].strftime("%Y-%m-%dT%H-%M-%SZ")
    manifest_path = manifests_dir / f"{ts}.json"
    run_doc["manifest_path"] = str(manifest_path)

    with manifest_path.open("w", encoding="utf-8") as fh:
        json.dump(run_doc, fh, ensure_ascii=False, indent=2, default=_json_default)

    db.ingest_runs.update_one(
        {"_id": run_doc["_id"]},
        {"$set": {"manifest_path": run_doc["manifest_path"]}},
    )
    return manifest_path


def close_aborted_runs(db, entrega: str) -> int:
    """Cierra como 'aborted' las corridas anteriores que quedaron 'running'."""
    result = db.ingest_runs.update_many(
        {"entrega": entrega, "status": "running"},
        {
            "$set": {
                "status": "aborted",
                "finished_at": datetime.now(timezone.utc),
            }
        },
    )
    return result.modified_count
