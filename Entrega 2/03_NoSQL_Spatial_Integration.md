# 03 — NoSQL Spatial Integration

**Criterio de evaluación 3 de 4 — Entrega 2**

---

## 1. Estado de la base al cierre de la Semana 2

| Colección | Documentos | Origen | Estado tras esta entrega |
|---|---|---|---|
| `municipalities` | **170** | DANE/MGN ∩ Decreto 893/2017 | Cargada, indexada y validada |
| `ingest_runs` | ≥ 1 | Cada corrida del cargador | Auditoría activa |
| `buildings` | 0 | (Semana 3) | Sólo esquema e índices |
| `municipality_stats` | 0 | (Semana 4) | Sólo esquema |

## 2. Extensión del esquema (v1 → v2)

La Entrega 1 definió el esquema base. Esta entrega lo amplía sin romper
compatibilidad: se añaden campos **opcionales** y una colección nueva
(`ingest_runs`).

### 2.1 Nuevos campos en `municipalities`

```json
{
  "geometry_simplified": { "type": "MultiPolygon", "coordinates": [ ... ] },
  "source": {
    "name": "DANE-MGN",
    "version": "MGN2025",
    "file_sha256": "<sha256>",
    "downloaded_at": "<ISO-8601>",
    "ingest_run_id": "<ObjectId de ingest_runs>"
  }
}
```

`source` pasa de tener 2 campos (Entrega 1) a 5. Compatible: los documentos
viejos siguen siendo válidos porque los campos nuevos son opcionales en el
`$jsonSchema` v2.

### 2.2 Nueva colección `ingest_runs`

| Campo | Tipo | Descripción |
|---|---|---|
| `_id` | ObjectId | — |
| `entrega` | string | `"W2"` (planificado para `"W3"` también) |
| `started_at` / `finished_at` | date | UTC |
| `status` | enum | `"success" \| "failed_verification" \| "failed_post_validation" \| "running"` |
| `source_file` | string | Ruta relativa del shapefile |
| `source_sha256` | string | Checksum SHA-256 del archivo |
| `mgn_version` | string | `"MGN2025"` |
| `counts` | object | `{ expected: 170, inserted: int, updated: int, skipped: int, repaired: int }` |
| `crosscheck` | object | `{ missing_in_mgn: [], extra_in_mgn: [], name_mismatches: [] }` |
| `post_validation` | object | Resultados de la *facet* de Capa 3 |
| `errors` | array | Errores con `divipola` y mensaje |
| `manifest_path` | string | Ruta al manifest JSON local |

Aplicación del cambio: `schemas/extend_for_w2.js` (idempotente).

## 3. Estrategia de carga: idempotencia + bulk

### 3.1 Idempotencia

La carga **siempre** usa `UpdateOne(..., upsert=True)` con filtro `{divipola: X}`.
Resultado:

- Primera corrida: inserta los 170 documentos.
- Segunda corrida (sin cambios): 170 *matched*, 0 *modified*.
- Si MGN se actualiza: sólo los municipios con geometría distinta se *modify*.

Esto permite re-correr con seguridad y soporta `--resume` ante fallos.

### 3.2 Bulk write

```python
operations = [
    pymongo.UpdateOne({"divipola": doc["divipola"]}, {"$set": doc}, upsert=True)
    for doc in documents
]
result = collection.bulk_write(operations, ordered=False)
```

`ordered=False` permite que MongoDB siga insertando aunque algún documento
falle por validación, y devuelve los errores agregados. Los errores se
transcriben a `ingest_runs.errors`.

### 3.3 Manejo de fallos parciales

| Escenario | Comportamiento |
|---|---|
| 1 documento falla el `$jsonSchema` | Otros 169 se insertan; el fallo va a `errors`; `status = "failed_post_validation"` |
| Conexión a Mongo cae a mitad | El cargador relanza; con upsert no hay duplicados |
| El cargador se interrumpe (Ctrl+C) | `ingest_runs.status` queda en `"running"`; el siguiente arranque lo cierra como `"aborted"` |

## 4. Índices activos

Heredados de la Entrega 1 (`schemas/init_indexes.js`):

```js
db.municipalities.createIndex({ divipola: 1 },         { unique: true });
db.municipalities.createIndex({ geometry: "2dsphere" });
db.municipalities.createIndex({ pdet_subregion: 1 });
```

Añadido en esta entrega para acelerar la auditoría temporal:

```js
db.ingest_runs.createIndex({ started_at: -1 });
db.ingest_runs.createIndex({ entrega: 1, status: 1 });
```

> **Por qué no se indexa `geometry_simplified`:** ese campo nunca se consulta
> espacialmente; sólo se lee al renderizar mapas o exportar GeoJSON ligero.
> Indexarlo costaría espacio (≈ otro 2dsphere completo) sin valor.

## 5. Consultas funcionales validadas

La carga se considera exitosa solo si las siguientes consultas devuelven el
resultado esperado:

### Q1 — Conteo total

```js
db.municipalities.countDocuments({ is_pdet: true })
// → 170
```

### Q2 — Cobertura por subregión

```js
db.municipalities.aggregate([
  { $group: { _id: "$pdet_subregion", n: { $sum: 1 } } },
  { $sort: { n: -1 } }
])
// → 16 subregiones, suma de n = 170
```

### Q3 — Punto en municipio (operación clave para Semana 3)

```js
db.municipalities.findOne({
  geometry: {
    $geoIntersects: {
      $geometry: { type: "Point", coordinates: [-75.5605, 6.2435] }
    }
  }
}, { divipola: 1, mpio_cnmbr: 1 })
// → ej. { divipola: "05001", mpio_cnmbr: "Medellín" }
```

### Q4 — Vecinos de un municipio (sanity check)

```js
const target = db.municipalities.findOne({ divipola: "05031" });
db.municipalities.find({
  geometry: { $geoIntersects: { $geometry: target.geometry } },
  divipola: { $ne: target.divipola }
}).count()
// → entre 3 y 8 (depende del municipio)
```

### Q5 — Última corrida exitosa

```js
db.ingest_runs.find({ entrega: "W2", status: "success" })
              .sort({ finished_at: -1 }).limit(1)
```

## 6. Métricas de desempeño esperadas

Sobre máquina típica (16 GB RAM, SSD), MongoDB local:

| Operación | Tiempo objetivo |
|---|---|
| Carga completa de 170 docs | < 5 s |
| Construcción `2dsphere` desde cero | < 2 s |
| `$geoIntersects` puntual (Q3) | < 20 ms |
| Agregación por subregión (Q2) | < 50 ms |

Estas métricas se registran en cada corrida en `ingest_runs.performance` y
deben usarse como línea base para la Semana 3, donde el volumen crece a millones.

## 7. Aceptación del criterio

- [x] La extensión del esquema v1 → v2 es retrocompatible.
- [x] La carga es idempotente y soporta re-corridas seguras.
- [x] Hay índice `2dsphere` y se valida con consultas reales.
- [x] La colección `ingest_runs` deja trazabilidad de cada corrida.
- [x] Las cinco consultas funcionales (Q1–Q5) se demuestran en la defensa.
