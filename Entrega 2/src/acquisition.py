"""Adquisición y verificación de la fuente MGN."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


_CHUNK = 4 * 1024 * 1024  # 4 MB

EXPECTED_FIELDS = {"dpto_ccdgo", "mpio_ccdgo", "mpio_cdpmp", "mpio_cnmbr", "dpto_cnmbr"}


@dataclass
class AcquisitionReport:
    file: Path
    exists: bool = False
    size_bytes: int = 0
    sha256: Optional[str] = None
    has_expected_layer: bool = False
    has_expected_fields: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.exists
            and self.size_bytes > 0
            and self.sha256 is not None
            and self.has_expected_layer
            and self.has_expected_fields
            and not self.errors
        )


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def verify_mgn(
    zip_path: Path,
    expected_sha256: Optional[str] = None,
    min_size: int = 3_000_000_000,
    max_size: int = 4_000_000_000,
    layer_hint: str = "MGN_ADM_MPIO_GRAFICO",
) -> AcquisitionReport:
    """Verifica el ZIP del MGN sin descomprimirlo a disco."""
    report = AcquisitionReport(file=zip_path)

    if not zip_path.exists():
        report.errors.append(f"No existe: {zip_path}")
        return report
    report.exists = True

    report.size_bytes = zip_path.stat().st_size
    if not (min_size <= report.size_bytes <= max_size):
        report.errors.append(
            f"Tamaño fuera de rango esperado: {report.size_bytes} bytes"
        )

    report.sha256 = sha256_of(zip_path)
    if expected_sha256 and report.sha256 != expected_sha256:
        report.errors.append(
            f"SHA-256 no coincide. Esperado {expected_sha256}, "
            f"obtenido {report.sha256}"
        )

    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            report.has_expected_layer = any(layer_hint in n for n in names)
            if not report.has_expected_layer:
                report.errors.append(
                    f"Capa {layer_hint!r} no encontrada en el ZIP"
                )
    except zipfile.BadZipFile as exc:
        report.errors.append(f"ZIP corrupto: {exc}")
        return report

    # Validación profunda de campos: se hace al abrir el shapefile con
    # geopandas en `integrity.py`. Aquí solo marcamos preliminar.
    report.has_expected_fields = report.has_expected_layer

    return report
