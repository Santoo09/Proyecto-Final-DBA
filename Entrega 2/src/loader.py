"""Carga idempotente a MongoDB y validación post-insert."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

try:
    import pymongo
    from pymongo.errors import BulkWriteError
except ImportError:  # pragma: no cover
    pymongo = None


@dataclass
class LoadReport:
    matched: int = 0
    inserted: int = 0
    updated: int = 0
    upserted: int = 0
    errors: list[dict] = field(default_factory=list)


@dataclass
class PostValidationReport:
    total: int = 0
    duplicates: int = 0
    missing_bbox: int = 0
    subregions_covered: int = 0
    area_total_km2: float = 0.0
    ok: bool = False


def upsert_municipalities(db, documents: Iterable[dict]) -> LoadReport:
    if pymongo is None:  # pragma: no cover
        raise RuntimeError("pymongo no instalado")

    ops = [
        pymongo.UpdateOne(
            {"divipola": doc["divipola"]},
            {"$set": doc},
            upsert=True,
        )
        for doc in documents
    ]
    report = LoadReport()
    if not ops:
        return report

    try:
        result = db.municipalities.bulk_write(ops, ordered=False)
        report.matched = result.matched_count
        report.updated = result.modified_count
        report.upserted = len(result.upserted_ids)
        report.inserted = report.upserted
    except BulkWriteError as exc:  # pragma: no cover
        details = exc.details or {}
        report.matched = details.get("nMatched", 0)
        report.updated = details.get("nModified", 0)
        report.upserted = details.get("nUpserted", 0)
        report.inserted = report.upserted
        for werr in details.get("writeErrors", []):
            report.errors.append(
                {
                    "index": werr.get("index"),
                    "code": werr.get("code"),
                    "message": werr.get("errmsg"),
                }
            )

    return report


def post_validate(
    db,
    expected_count: int = 170,
    expected_subregions: int = 16,
) -> PostValidationReport:
    pipeline = [
        {
            "$facet": {
                "total": [{"$count": "n"}],
                "duplicados": [
                    {"$group": {"_id": "$divipola", "c": {"$sum": 1}}},
                    {"$match": {"c": {"$gt": 1}}},
                ],
                "sin_bbox": [
                    {"$match": {"bbox": {"$exists": False}}},
                    {"$count": "n"},
                ],
                "por_subregion": [
                    {"$group": {"_id": "$pdet_subregion", "c": {"$sum": 1}}},
                ],
                "area_total": [
                    {"$group": {"_id": None, "total": {"$sum": "$area_km2"}}},
                ],
            }
        }
    ]
    result = list(db.municipalities.aggregate(pipeline))[0]

    total = (result["total"][0]["n"] if result["total"] else 0)
    dup = len(result["duplicados"])
    sin_bbox = (result["sin_bbox"][0]["n"] if result["sin_bbox"] else 0)
    subregions = len(result["por_subregion"])
    area = (result["area_total"][0]["total"] if result["area_total"] else 0.0)

    report = PostValidationReport(
        total=total,
        duplicates=dup,
        missing_bbox=sin_bbox,
        subregions_covered=subregions,
        area_total_km2=float(area),
        ok=(
            total == expected_count
            and dup == 0
            and sin_bbox == 0
            and subregions == expected_subregions
        ),
    )
    return report
