# 03 — Schema Design & Appropriateness

**Proyecto:** Estimación del potencial solar en techos de municipios PDET — UPME
**Entrega:** Semana 1
**Componente:** *Schema Design & Appropriateness*

---

## 1. Resumen del diseño

Tres colecciones MongoDB:

- `municipalities` — polígonos PDET (170 documentos).
- `buildings` — huellas de edificios de las fuentes Microsoft y Google.
- `municipality_stats` — resultados agregados (se popula en Semana 4).

Todas las geometrías se almacenan como **GeoJSON** en EPSG:4326. Cada colección
tiene un validador `$jsonSchema` y al menos un índice `2dsphere`.

## 2. Por qué MongoDB es apropiado

El requisito del proyecto exige *NoSQL solutions, enabling scalable storage,
efficient querying, and flexible spatial operations* (Project.pdf, §1). La
siguiente tabla evalúa las opciones NoSQL más relevantes contra los requisitos
reales del proyecto:

| Requisito del proyecto | MongoDB 7 | Cassandra | Redis | Couchbase | DynamoDB |
|---|---|---|---|---|---|
| GeoJSON nativo | ✅ Sí | ❌ No | ⚠️ Solo *geo-sets* sobre puntos | ⚠️ Limitado | ❌ No |
| Índice geoespacial 2D/3D sobre polígonos | ✅ `2dsphere` | ❌ | ❌ (sólo puntos) | ⚠️ | ❌ |
| `$geoIntersects`, `$geoWithin`, `$geoNear` | ✅ | ❌ | ⚠️ Sólo *radius* | ⚠️ | ❌ |
| Agregaciones complejas (`$group`, `$lookup`) | ✅ Pipeline | ⚠️ Vía Spark | ❌ | ✅ N1QL | ⚠️ Limitado |
| Esquema flexible (heterogeneidad MS vs Google) | ✅ Documentos JSON | ⚠️ Rígido | — | ✅ | ✅ |
| Escala horizontal (*sharding*) | ✅ por *shard key* | ✅ | ⚠️ | ✅ | ✅ |
| Comunidad y curva de aprendizaje | ✅ Madura | Media | Alta | Media | Atado a AWS |
| Costo y portabilidad | ✅ Open Source | ✅ | ✅ | Comercial | Cerrado |

**Conclusión:** MongoDB es la única opción que cubre los tres requisitos críticos
del problema (GeoJSON nativo + índice sobre polígonos + agregaciones espaciales)
con licencia libre y sin atarse a un proveedor cloud. PostGIS (relacional) sería
técnicamente superior para geoespacial, pero **viola el requisito NoSQL**.

## 3. Detalle de cada colección

### 3.1 `municipalities`

**Propósito:** servir como referencia espacial autoritativa para resolver
"qué municipio contiene esta huella".

**Documento canónico:**

```json
{
  "_id": ObjectId("..."),
  "divipola": "05001",
  "mpio_cnmbr": "Medellín",
  "dpto_ccdgo": "05",
  "dpto_cnmbr": "Antioquia",
  "is_pdet": true,
  "pdet_subregion": "Bajo Cauca y Nordeste Antioqueño",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[-75.65, 6.20], [-75.50, 6.20], [-75.50, 6.35],
                     [-75.65, 6.35], [-75.65, 6.20]]]
  },
  "area_km2": 380.64,
  "bbox": [-75.65, 6.20, -75.50, 6.35],
  "source": { "name": "DANE-MGN", "version": "MGN2025" },
  "ingested_at": ISODate("2026-05-15T14:00:00Z")
}
```

**Índices:**

| Índice | Tipo | Razón |
|---|---|---|
| `{ divipola: 1 }` | `unique` | Clave funcional, evita duplicados |
| `{ geometry: "2dsphere" }` | espacial | `$geoIntersects`, `$geoWithin` |
| `{ pdet_subregion: 1 }` | simple | Agrupaciones por subregión en el reporte |

### 3.2 `buildings`

**Propósito:** almacenar huellas de edificios de las dos fuentes elegidas, ya
acotadas al territorio PDET y enriquecidas con su `municipality_divipola`.

**Documento canónico (Microsoft):**

```json
{
  "_id": ObjectId("..."),
  "source": "microsoft",
  "source_id": "021132330_487",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[-75.561, 6.243], [-75.561, 6.244],
                     [-75.560, 6.244], [-75.560, 6.243], [-75.561, 6.243]]]
  },
  "centroid": { "type": "Point", "coordinates": [-75.5605, 6.2435] },
  "area_m2": 112.4,
  "confidence": null,
  "height_m": 7.2,
  "municipality_divipola": "05001",
  "ingested_at": ISODate("2026-05-22T14:00:00Z"),
  "ingest_batch": "ms-2026w03-01"
}
```

**Índices:**

| Índice | Tipo | Razón |
|---|---|---|
| `{ geometry: "2dsphere" }` | espacial | Consultas espaciales puntuales |
| `{ municipality_divipola: 1, source: 1 }` | compuesto | Conteo y suma por (municipio, fuente) en O(idx) |
| `{ municipality_divipola: 1, area_m2: 1 }` | compuesto | Filtros por umbral de área dentro de un municipio |
| `{ source: 1, ingest_batch: 1 }` | compuesto | Auditoría y reintentos selectivos |

> **Nota sobre sharding (futuro):** si la carga supera el nodo único, la *shard
> key* recomendada es `{ municipality_divipola: 1, _id: 1 }`. Distribuye por
> municipio (uniforme entre los 170 PDET) y mantiene localidad para las
> agregaciones del reporte.

### 3.3 `municipality_stats`

**Propósito:** resultados agregados para alimentar el reporte y las visualizaciones.

**Documento canónico:**

```json
{
  "_id": "05001:microsoft",
  "divipola": "05001",
  "mpio_cnmbr": "Medellín",
  "source": "microsoft",
  "building_count": 218450,
  "total_roof_area_m2": 21845300.5,
  "mean_roof_area_m2": 100.0,
  "median_roof_area_m2": 86.3,
  "coverage_ratio": 0.0574,
  "computed_at": ISODate("2026-06-05T14:00:00Z")
}
```

**Índices:**

| Índice | Tipo | Razón |
|---|---|---|
| `_id` (compuesto string) | implícito único | Garantiza unicidad por (mpio, fuente) |
| `{ divipola: 1 }` | simple | *Lookups* desde el reporte |
| `{ source: 1, total_roof_area_m2: -1 }` | compuesto | Rankings por fuente |

## 4. Validadores `$jsonSchema`

Cada colección se crea con un validador estricto. El detalle formal está en
`schemas/*.schema.json`. Aquí un extracto representativo (`buildings`):

```js
db.createCollection("buildings", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["source", "geometry", "centroid", "area_m2",
                 "municipality_divipola", "ingested_at", "ingest_batch"],
      properties: {
        source: { enum: ["microsoft", "google", "tum"] },
        source_id: { bsonType: ["string", "null"] },
        geometry: {
          bsonType: "object",
          required: ["type", "coordinates"],
          properties: {
            type: { enum: ["Polygon", "MultiPolygon"] },
            coordinates: { bsonType: "array" }
          }
        },
        centroid: {
          bsonType: "object",
          required: ["type", "coordinates"],
          properties: {
            type: { enum: ["Point"] },
            coordinates: { bsonType: "array", minItems: 2, maxItems: 2 }
          }
        },
        area_m2: { bsonType: "double", minimum: 0 },
        confidence: { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
        height_m: { bsonType: ["double", "null"], minimum: 0 },
        municipality_divipola: { bsonType: "string", pattern: "^[0-9]{5}$" },
        ingested_at: { bsonType: "date" },
        ingest_batch: { bsonType: "string" }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});
```

`validationAction: "error"` impide insertar documentos malformados, lo cual es
crítico cuando se cargan millones de registros por lote.

## 5. Justificación de las decisiones clave

### 5.1 Denormalización de `municipality_divipola` en `buildings`

**Decisión:** almacenar la pertenencia municipal en cada huella, calculada en ingesta.

**Trade-off:** se gana en velocidad de consulta a costa de:

- ~5 bytes adicionales por documento (despreciable a escala del proyecto).
- Recalcular el campo si cambia el MGN (esperable cada ~2 años — bajo).

**Por qué es correcto en NoSQL:** MongoDB privilegia *embed-and-query* sobre
*join-and-filter*. Hacer `$geoIntersects` sobre 10M+ huellas por cada agregación
de la Semana 4 sería prohibitivo; resolverlo una vez en ingesta lo convierte en
un filtro por igualdad sobre un índice B-tree.

### 5.2 Documentos separados por fuente, no fusionados

**Decisión:** cada huella conserva su `source` y se almacena en la misma
colección, sin intentar deduplicar entre MS y Google.

**Por qué:** el objetivo del proyecto (Project.pdf, §2) es **comparar** las
fuentes, no fusionarlas. Una deduplicación introduciría sesgo y borraría
diferencias que UPME quiere medir.

### 5.3 `centroid` pre-calculado

**Decisión:** almacenar el centroide aunque sea derivable del polígono.

**Por qué:** muchas consultas espaciales (`$geoNear`, *spatial joins*) son más
eficientes sobre puntos. Calcular centroides por cada consulta sobre 10M
documentos sería costoso; pre-calcularlos cuesta una vez en ingesta.

### 5.4 GeoJSON en EPSG:4326 como única representación almacenada

**Decisión:** no se almacena geometría reproyectada a CTM12; sólo el área
métrica resultante.

**Por qué:** MongoDB sólo soporta `2dsphere` sobre WGS84. Almacenar dos
geometrías duplicaría el tamaño de la colección sin valor adicional.

### 5.5 No usar `$lookup` para resolver municipio en consultas

**Decisión:** las agregaciones de la Semana 4 leen directamente
`municipality_divipola` ya denormalizado; no se hace `$lookup` desde `buildings`
hacia `municipalities`.

**Por qué:** `$lookup` en MongoDB es funcional pero costoso cuando la colección
izquierda es grande. Con la denormalización, las agregaciones reducen a
`$match + $group`, que MongoDB ejecuta sobre el índice compuesto sin
materializar documentos.

## 6. Apropiabilidad frente a los requisitos del cliente

| Requisito UPME (Project.pdf) | Cómo lo cubre el diseño |
|---|---|
| "Contar edificios por municipio PDET" | `$match + $group` por `municipality_divipola` — milisegundos por municipio |
| "Estimar área total de techos por municipio" | Suma de `area_m2` agrupada (`$sum`) sobre índice compuesto |
| "Comparar fuentes" | Campo `source` discriminador + `municipality_stats` con clave `(mpio, fuente)` |
| "Solución NoSQL escalable" | MongoDB con plan de *sharding* documentado y *shard key* identificada |
| "Operaciones espaciales flexibles" | Índice `2dsphere` + operadores `$geoIntersects`/`$geoWithin`/`$geoNear` disponibles |
| "Metodología reproducible" | Script `init_indexes.js` + validadores + documentos de ejemplo permiten re-crear la base desde cero |

## 7. Limitaciones reconocidas

- **No filtra techos por aptitud solar.** El diseño cuenta y suma *área de
  huella*, no área *apta* (sin sombra, con orientación correcta). El
  refinamiento por irradiancia queda fuera del alcance documentado del proyecto
  y, en caso de incluirse, se modelaría como un campo adicional `suitable_area_m2`
  sin tocar el resto del esquema.
- **MongoDB Community no soporta geometrías 3D.** El campo `height_m` se
  almacena pero no se indexa espacialmente en 3D; análisis volumétrico tendría
  que hacerse en una etapa de post-proceso.
- **Sharding no se activa en esta entrega.** Está documentado y se mantiene
  como opción si la Semana 3 muestra que un nodo único no escala.

## 8. Checklist final del diseño

- [x] Tres colecciones definidas con propósito claro y disjunto.
- [x] GeoJSON en EPSG:4326 como representación canónica.
- [x] Índices `2dsphere` sobre todos los campos espaciales relevantes.
- [x] Índices compuestos que cubren las consultas críticas sin escaneo de colección.
- [x] Validadores `$jsonSchema` que protegen la integridad estructural.
- [x] Trazabilidad: cada documento conserva `source`, `version`, `ingested_at`.
- [x] Denormalización justificada y acotada (`municipality_divipola`, `centroid`).
- [x] Plan de escala documentado (*shard key* identificada).
- [x] Limitaciones explícitas (sin doble engaño al cliente).
