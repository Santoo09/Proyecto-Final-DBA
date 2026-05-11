# 01 — Data Acquisition & Verification

**Criterio de evaluación 1 de 4 — Entrega 2**

---

## 1. Fuentes oficiales utilizadas

| # | Fuente | Propósito | Versión / Fecha |
|---|---|---|---|
| 1 | **DANE — Marco Geoestadístico Nacional (MGN)** | Polígonos municipales | `MGN2025-Colombia` |
| 2 | **Decreto 893 de 2017** (Presidencia de la República) | Lista oficial de 170 municipios PDET | 28 de mayo de 2017 |
| 3 | **Agencia de Renovación del Territorio (ART)** | Catálogo de 16 subregiones PDET | Última actualización ART |

> Las tres fuentes son de uso público y se citan en el reporte final (Semana 5).

### 1.1 URLs canónicas

| Fuente | URL |
|---|---|
| MGN — Geoportal DANE (descarga) | https://geoportal.dane.gov.co/servicios/descarga-y-metadatos/datos-geoestadisticos/?cod=111 |
| MGN — Manual de usuario v2.0 | https://geoportal.dane.gov.co/descargas/descarga_mgn/Manual_MGN.pdf |
| Decreto 893 de 2017 (DAFP) | https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=82111 |
| ART — Programas PDET | https://www.renovacionterritorio.gov.co/ |

## 2. Procedimiento de adquisición

### 2.1 MGN (Marco Geoestadístico Nacional)

1. Acceder al Geoportal DANE → sección *Geoestadísticos* → producto `MGN2025-Colombia, Todos los niveles geográficos, ZIP, 1.5 GB`.
2. Descargar el ZIP a `data/raw/MGN2025-Colombia.zip`.
3. Calcular SHA-256 local y compararlo con el valor publicado por DANE.
4. Descomprimir y conservar el directorio `MGN_MPIO_POLITICO/` (capa municipal en SRC EPSG:4686).

> **Por qué SHA-256 y no MD5:** SHA-256 es el algoritmo recomendado por NIST
> SP 800-131A para integridad de archivos. La diferencia de costo es despreciable
> y elimina el riesgo de colisiones conocidas en MD5.

### 2.2 Decreto 893 de 2017

El listado de 170 municipios PDET se transcribe del **Anexo I** del Decreto y se
versiona en este repositorio como [`data/pdet_decreto_893.csv`](data/pdet_decreto_893.csv).
Cada fila contiene:

```
divipola,mpio_cnmbr_decreto,dpto_cnmbr,pdet_subregion
```

> El campo `mpio_cnmbr_decreto` se conserva separado de `mpio_cnmbr` del MGN
> porque los nombres pueden diferir en tildes, espacios o nomenclatura
> histórica. El cruce se hace por `divipola` (numérico, estable), no por nombre.

## 3. Verificación automatizada (módulo `acquisition.py`)

El script implementa cuatro chequeos secuenciales. Si alguno falla, la
ejecución aborta y el manifest queda marcado como `status: "failed_verification"`.

| Chequeo | Implementación | Acción si falla |
|---|---|---|
| 1. Existencia del archivo | `Path(...).exists()` | Aborta con mensaje guía de descarga |
| 2. Tamaño esperado (~1.5 GB ±10%) | `os.path.getsize()` | Advierte; permite `--force` |
| 3. Checksum SHA-256 del ZIP | `hashlib.sha256` por chunks de 4 MB | Aborta sin reintento |
| 4. Estructura del shapefile | `fiona.listlayers` + verificación de campos `dpto_ccdgo`, `mpio_ccdgo`, `mpio_cnmbr` | Aborta |

Resultado: un objeto `AcquisitionReport` que se persiste en el documento de
auditoría de la corrida.

## 4. Cruce DIVIPOLA: MGN vs Decreto 893 (módulo `crosscheck.py`)

Antes de cualquier carga se ejecuta el cruce:

```
set_decreto  = {divipola ∈ CSV oficial}              # 170 esperados
set_mgn_pdet = {divipola ∈ MGN ∩ set_decreto}        # presentes en MGN

faltantes = set_decreto − set_mgn_pdet               # debe ser ∅
sobrantes = set_mgn_pdet − set_decreto               # debe ser ∅
```

Reglas:

- Si `|set_decreto| ≠ 170` → error duro (el CSV está corrupto).
- Si `faltantes ≠ ∅` → error duro (el MGN no contiene un municipio PDET).
- Si los nombres difieren (Levenshtein > 3) → *warning* registrado en el manifest.

El reporte del cruce queda en el campo `crosscheck` del documento de
`ingest_runs` y también en el scorecard de la Semana 5.

## 5. Trazabilidad: campo `source` en cada documento

Cada documento de `municipalities` incluye:

```json
"source": {
  "name": "DANE-MGN",
  "version": "MGN2025",
  "file_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "downloaded_at": "2026-05-15T12:30:00Z",
  "ingest_run_id": "ObjectId(...)"
}
```

El `ingest_run_id` referencia el documento en `ingest_runs`, cerrando el bucle
de auditoría: dado cualquier municipio, se puede saber **exactamente** de qué
corrida y qué archivo viene.

## 6. Aceptación del criterio

- [x] Las tres fuentes oficiales están documentadas con URL canónica.
- [x] La descarga del MGN se verifica vía SHA-256.
- [x] El listado PDET es del Decreto 893 (no inferido ni heurístico).
- [x] El cruce MGN ↔ Decreto bloquea la carga ante cualquier inconsistencia.
- [x] La trazabilidad queda persistida en cada documento y en `ingest_runs`.
