"""Configuración central de la Entrega 2."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Config:
    mongo_uri: str = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    db_name: str = os.environ.get("MONGO_DB", "upme_solar")

    raw_dir: Path = ROOT / "data" / "raw"
    decreto_csv: Path = ROOT / "data" / "pdet_decreto_893.csv"
    manifests_dir: Path = ROOT / "manifests"
    reports_dir: Path = ROOT / "reports"

    # Nombre real del archivo descargado del Geoportal DANE.
    mgn_zip_name: str = "MGN2025_00_COLOMBIA.zip"
    # Nombre de la capa dentro del ZIP (subcadena que se busca).
    mgn_layer: str = "MGN_ADM_MPIO_GRAFICO"
    mgn_version: str = "MGN2025"

    crs_storage: str = "EPSG:4326"
    crs_metric: str = "EPSG:9377"

    expected_pdet_count: int = 170
    simplify_tolerance_deg: float = 0.001
    area_tolerance_pct: float = 0.01

    tool_version: str = "0.2.0"

    @property
    def mgn_zip_path(self) -> Path:
        """Localiza el ZIP del MGN.

        Orden de búsqueda:
          1. `data/raw/<nombre>` dentro de Entrega2 (ubicación canónica).
          2. Raíz del proyecto (un nivel arriba de Entrega2), por si el equipo
             dejó el archivo en la carpeta padre por su tamaño (3.4 GB).
          3. Variable de entorno `MGN_ZIP_PATH` si está definida.
        """
        env_override = os.environ.get("MGN_ZIP_PATH")
        if env_override:
            return Path(env_override)

        canonical = self.raw_dir / self.mgn_zip_name
        if canonical.exists():
            return canonical

        parent = ROOT.parent / self.mgn_zip_name
        if parent.exists():
            return parent

        return canonical  # devuelve la ubicación canónica para el mensaje de error


CONFIG = Config()
