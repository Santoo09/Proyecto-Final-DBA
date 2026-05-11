# 04 — Process Documentation

**Criterio de evaluación 4 de 4 — Entrega 2**

---

## 1. Pipeline reproducible

```
   ┌────────────────────────────────────────────────────────────────┐
   │                       make ingest                              │
   └───────────────────────────┬────────────────────────────────────┘
                               │
                               ▼
     ┌──────────────────────────────────────────────────────────┐
     │ 1. acquisition.verify(MGN.zip)                           │
     │    - existencia                                          │
     │    - tamaño en rango                                     │
     │    - SHA-256 esperado                                    │
     │    - capas del shapefile                                 │
     │    output → AcquisitionReport                            │
     └──────────────────────────┬───────────────────────────────┘
                                │ (si falla → status=failed_verification)
                                ▼
     ┌──────────────────────────────────────────────────────────┐
     │ 2. crosscheck.run(decreto_csv, mgn_gdf)                  │
     │    - faltantes, sobrantes, name_mismatches               │
     │    output → CrosscheckReport                             │
     └──────────────────────────┬───────────────────────────────┘
                                │ (si faltantes ≠ ∅ → aborta)
                                ▼
     ┌──────────────────────────────────────────────────────────┐
     │ 3. integrity.process(gdf_pdet)                           │
     │    - reproyección 4686 → 4326                            │
     │    - is_valid / make_valid                               │
     │    - cálculo de area_km2 en EPSG:9377                    │
     │    - simplify para LOD                                   │
     │    output → list[MunicipalityDoc]                        │
     └──────────────────────────┬───────────────────────────────┘
                                │
                                ▼
     ┌──────────────────────────────────────────────────────────┐
     │ 4. loader.upsert(docs)                                   │
     │    - bulk_write(UpdateOne upsert, ordered=False)         │
     │    - errores → ingest_runs.errors                        │
     │    output → InsertReport                                 │
     └──────────────────────────┬───────────────────────────────┘
                                │
                                ▼
     ┌──────────────────────────────────────────────────────────┐
     │ 5. loader.post_validate()                                │
     │    - $facet (total, dup, sin_bbox, por_subregion, area)  │
     │    output → PostValidationReport                         │
     └──────────────────────────┬───────────────────────────────┘
                                │
                                ▼
     ┌──────────────────────────────────────────────────────────┐
     │ 6. audit.finalize(run_id, all_reports)                   │
     │    - escribe ingest_runs.<this>                          │
     │    - escribe manifests/<timestamp>.json                  │
     └──────────────────────────┬───────────────────────────────┘
                                │
                                ▼
     ┌──────────────────────────────────────────────────────────┐
     │ 7. scorecard.generate(run_id)                            │
     │    - reports/quality_scorecard_<timestamp>.md            │
     └──────────────────────────────────────────────────────────┘
```

## 2. Bitácora de decisiones (ADR resumido)

| ID | Decisión | Alternativa descartada | Razón |
|---|---|---|---|
| ADR-W2-01 | Cruce DIVIPOLA contra CSV oficial Decreto 893 | Inferir PDET desde un atributo del MGN | El MGN no marca PDET; cualquier atributo derivado sería heurístico |
| ADR-W2-02 | Almacenar `geometry_simplified` además de `geometry` | Calcular simplificación en cada render | Las vistas web y los *diffs* son repetitivos; pre-calcular cuesta una vez |
| ADR-W2-03 | Colección `ingest_runs` (no archivo `.log`) | Solo logs en stdout/archivo | La auditoría debe vivir en la misma fuente de verdad que los datos |
| ADR-W2-04 | `UpdateOne(upsert=True)` en vez de `insert_many` | `insert_many` + `drop_collection` previo | Idempotencia y resistencia a fallos parciales |
| ADR-W2-05 | EPSG:9377 (CTM12) para áreas | EPSG:3116 (origen Bogotá) | Resolución IGAC 471/2020 establece CTM12 como SRC oficial nacional |
| ADR-W2-06 | Validación en 3 capas | Solo `$jsonSchema` | Las reglas de negocio (cuenta = 170, 16 subregiones) no caben en JSON Schema |
| ADR-W2-07 | Tolerancia ~100 m para `simplify` | Sin tolerancia o 1 km | 100 m preserva forma reconocible para municipios urbanos pequeños |

Cada ADR puede consultarse en el commit que lo introduce (mensaje del commit
incluye el ID `ADR-W2-XX`).

## 3. Manifest por corrida

Ejemplo (`manifests/2026-05-15T14-22-31Z.json`):

```json
{
  "run_id": "664e0a1f1b9e5f8c8a9b4d22",
  "entrega": "W2",
  "tool_version": "0.2.0",
  "started_at": "2026-05-15T14:22:31Z",
  "finished_at": "2026-05-15T14:22:38Z",
  "duration_seconds": 7.2,
  "status": "success",
  "source": {
    "file": "data/raw/MGN2025-Colombia.zip",
    "size_bytes": 1602347188,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "mgn_version": "MGN2025"
  },
  "decreto_csv": {
    "file": "data/pdet_decreto_893.csv",
    "rows": 170,
    "sha256": "..."
  },
  "crosscheck": {
    "missing_in_mgn": [],
    "extra_in_mgn": [],
    "name_mismatches": [
      { "divipola": "27077", "mgn": "Bajo Baudo", "decreto": "Bajo Baudó" }
    ]
  },
  "integrity": {
    "total_in_pdet": 170,
    "valid_geom": 168,
    "repaired": 2,
    "rejected": 0,
    "area_total_km2": 92143.7
  },
  "load": {
    "matched": 0,
    "inserted": 170,
    "updated": 0,
    "errors": 0
  },
  "post_validation": {
    "total": 170,
    "duplicates": 0,
    "missing_bbox": 0,
    "subregions_covered": 16,
    "area_total_km2": 92143.7
  },
  "performance_ms": {
    "verify": 312,
    "crosscheck": 41,
    "integrity": 4880,
    "load": 1654,
    "post_validate": 22,
    "scorecard": 198
  }
}
```

El manifest es el **artefacto auditable** que UPME podría exigir para replicar
el resultado.

## 4. Reglas de versionamiento

- Tag Git: `entrega-2-vX.Y.Z` al cerrar la entrega.
- `tool_version` se incrementa en cada cambio que afecte la salida (campo
  nuevo, regla de validación, política de reparación).
- El esquema MongoDB se versiona con `schemas/municipalities.vN.schema.json`.
  Esta entrega introduce la v2; la v1 sigue documentada en `Entrega1/`.

## 5. Repositorio de evidencias para la defensa

| Artefacto | Ubicación |
|---|---|
| Manifests de las corridas exitosas | `manifests/*.json` |
| Scorecards generados | `reports/quality_scorecard_*.md` |
| Output de pytest (en CI o local) | log del comando `make test` |
| Capturas de pantalla del shell de Mongo con Q1-Q5 | `reports/screenshots/` (opcional) |
| Diff de geometría reparada (antes/después) | Se documenta en el scorecard |

## 6. Lecciones identificadas (para la Semana 3)

1. La diferencia entre `mpio_narea` (MGN) y nuestro `area_km2` (CTM12) es
   típicamente < 0,2%; la usaremos como límite de aceptación al cargar huellas.
2. El cuello de botella esperado en la Semana 3 no será MongoDB sino la
   reproyección masiva. Investigar `pyproj.Transformer.transform` con `always_xy=True`
   y `geopandas.GeoSeries.to_crs(crs, always_xy=True)`.
3. La auditoría con `ingest_runs` debe extenderse a los lotes de huellas
   (`buildings`). Agregar el campo `ingest_run_id` también allí.

## 7. Aceptación del criterio

- [x] El pipeline está documentado paso a paso y es reproducible con un solo comando (`make ingest`).
- [x] Cada decisión técnica relevante tiene su ADR.
- [x] Cada corrida deja manifest + documento en `ingest_runs` + scorecard.
- [x] Las lecciones para la siguiente semana quedan registradas, evitando que el conocimiento se pierda entre integrantes.
