"""Cruce DIVIPOLA: Decreto 893 (CSV) vs MGN (GeoDataFrame)."""

from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class DecretoEntry:
    divipola: str
    mpio_cnmbr: str
    dpto_cnmbr: str
    pdet_subregion: str


@dataclass
class CrosscheckReport:
    expected_count: int
    decreto_count: int
    mgn_pdet_count: int
    missing_in_mgn: list[str] = field(default_factory=list)
    extra_in_mgn: list[str] = field(default_factory=list)
    name_mismatches: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.decreto_count == self.expected_count
            and not self.missing_in_mgn
        )


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    ).lower().strip()


def load_decreto(path: Path) -> list[DecretoEntry]:
    entries: list[DecretoEntry] = []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            entries.append(
                DecretoEntry(
                    divipola=row["divipola"].strip().zfill(5),
                    mpio_cnmbr=row["mpio_cnmbr_decreto"].strip(),
                    dpto_cnmbr=row["dpto_cnmbr"].strip(),
                    pdet_subregion=row["pdet_subregion"].strip(),
                )
            )
    return entries


def run_crosscheck(
    decreto: list[DecretoEntry],
    mgn_records: Iterable[dict],
    expected_count: int = 170,
) -> CrosscheckReport:
    """`mgn_records` es un iterable de dicts con al menos `divipola` y `mpio_cnmbr`."""
    decreto_by_div = {e.divipola: e for e in decreto}
    mgn_by_div = {r["divipola"]: r for r in mgn_records}

    pdet_set = set(decreto_by_div) & set(mgn_by_div)
    missing = sorted(set(decreto_by_div) - set(mgn_by_div))
    extra: list[str] = []  # MGN tiene 1.122 municipios; "sobrantes" no aplica aquí

    mismatches: list[dict] = []
    for div in sorted(pdet_set):
        d_name = _strip_accents(decreto_by_div[div].mpio_cnmbr)
        m_name = _strip_accents(mgn_by_div[div]["mpio_cnmbr"])
        if d_name != m_name:
            mismatches.append(
                {
                    "divipola": div,
                    "decreto": decreto_by_div[div].mpio_cnmbr,
                    "mgn": mgn_by_div[div]["mpio_cnmbr"],
                }
            )

    return CrosscheckReport(
        expected_count=expected_count,
        decreto_count=len(decreto_by_div),
        mgn_pdet_count=len(pdet_set),
        missing_in_mgn=missing,
        extra_in_mgn=extra,
        name_mismatches=mismatches,
    )
