# 02 — Data Modeling

**Proyecto:** Estimación del potencial solar en techos de municipios PDET — UPME
**Entrega:** Semana 1
**Componente:** *Data Modeling*

---

## 1. Enfoque

El proyecto no es transaccional: la base se carga por lotes desde fuentes
externas, se consulta principalmente con agregaciones espaciales y produce
resultados resumidos por municipio. Por lo tanto, el modelado privilegia:

- **Documentos auto-contenidos** (sin *joins*), respetando la filosofía NoSQL.
- **Geometrías como GeoJSON nativo** para aprovechar el índice `2dsphere`.
- **Metadatos de procedencia** (`source`, `version`, `ingested_at`) embebidos
  en cada documento para garantizar trazabilidad y comparabilidad entre fuentes.
- **Identificadores estables y oficiales** (DIVIPOLA del DANE) para los
  municipios, garantizando interoperabilidad con futuros datasets.

## 2. Modelo conceptual

Tres entidades, relacionadas espacialmente (no por claves foráneas):

```
┌──────────────────────┐        contiene espacialmente        ┌──────────────────────┐
│   Municipality       │◄────────────────────────────────────►│      Building        │
│   (PDET, 170 docs)   │   ($geoIntersects / $geoWithin)      │  (huella, MS/Google) │
└──────────┬───────────┘                                      └──────────────────────┘
           │
           │ agrega resultados a
           ▼
┌──────────────────────┐
│ MunicipalityStats    │
│  (1 doc por mpio×    │
│   fuente)            │
└──────────────────────┘
```

Notas:

- La relación *Municipality → Building* es **espacial**, no por clave foránea.
  El operador `$geoIntersects` de MongoDB es quien la resuelve en tiempo de
  consulta. Esto es deliberado: las huellas pueden cargarse antes que los
  municipios y viceversa sin romper integridad referencial.
- `MunicipalityStats` se calcula en la Semana 4 y se almacena para acelerar el
  reporte final. Es un *materialized view* manual: una tupla por (municipio,
  fuente).

## 3. Fuentes de datos

### 3.1 DANE — Marco Geoestadístico Nacional (MGN)

| Atributo | Valor |
|---|---|
| Origen | Geoportal DANE, descarga `MGN2025-Colombia` |
| Formato original | Shapefile (`.shp`) y GeoPackage (`.gpkg`) |
| Sistema de referencia | EPSG:4686 (MAGNA-SIRGAS) en el archivo original |
| Nivel a usar | Municipal (`MGN_MPIO_POLITICO`) |
| Volumen | ~1.122 municipios totales; **170 PDET** tras filtrar |
| Licencia | Datos abiertos del Estado colombiano |

Campos relevantes del shapefile original:

| Campo MGN | Tipo | Descripción |
|---|---|---|
| `dpto_ccdgo` | str(2) | Código DIVIPOLA del departamento |
| `mpio_ccdgo` | str(3) | Código DIVIPOLA del municipio (sin departamento) |
| `dpto_cnmbr` | str | Nombre del departamento |
| `mpio_cnmbr` | str | Nombre del municipio |
| `mpio_crslc` | str | Categoría rural/urbano |
| `mpio_narea` | num | Área en km² (referencial, recalcularemos) |
| `geometry`   | Polygon/MultiPolygon | Frontera política |

El listado oficial de **170 municipios PDET** se cruzará por el código
DIVIPOLA completo (concatenación `dpto_ccdgo || mpio_ccdgo`, 5 dígitos).

### 3.2 Microsoft Building Footprints

| Atributo | Valor |
|---|---|
| Origen | Microsoft Planetary Computer, dataset `ms-buildings` |
| Formato | GeoParquet particionado por *quadkey* |
| CRS | EPSG:4326 (WGS84) |
| Cobertura mundial | ~999 millones de huellas |
| Atributos | `geometry` (Polygon), `quadkey`, `confidence` (opcional), `height` (opcional, solo algunas zonas) |
| Licencia | ODbL |

### 3.3 Google Open Buildings v3

| Atributo | Valor |
|---|---|
| Origen | Google Research, *Open Buildings* |
| Formato | CSV.GZ o GeoParquet por celda S2 |
| CRS | EPSG:4326 (WGS84) |
| Cobertura | América Latina incluida — ~1.800 millones de huellas |
| Atributos | `latitude`, `longitude`, `area_in_meters`, `confidence`, `geometry` (Polygon WKT), `full_plus_code` |
| Licencia | CC BY-4.0 + ODbL v1.0 |

### 3.4 (Opcional) GlobalBuildingAtlas — TUM

Documentada como reserva. No se incluye en el alcance de carga porque el
proyecto exige *al menos dos* fuentes y MS + Google son las que mejor cubren el
territorio colombiano con metadatos consistentes.

## 4. Modelo lógico — entidades

### 4.1 `municipalities`

Un documento por municipio PDET.

| Campo | Tipo lógico | Obligatorio | Notas |
|---|---|---|---|
| `_id` | ObjectId | sí | Generado por Mongo |
| `divipola` | string(5) | sí | PK funcional. Ej. `"05001"` (Medellín). Único. |
| `mpio_cnmbr` | string | sí | Nombre del municipio |
| `dpto_ccdgo` | string(2) | sí | Código del departamento |
| `dpto_cnmbr` | string | sí | Nombre del departamento |
| `is_pdet` | bool | sí | Siempre `true` en esta colección (se mantiene por claridad) |
| `pdet_subregion` | string | sí | Una de las 16 subregiones PDET (ej. `"Catatumbo"`) |
| `geometry` | GeoJSON `Polygon`/`MultiPolygon` | sí | EPSG:4326 (WGS84) |
| `area_km2` | double | sí | Calculada en EPSG:9377 para precisión métrica |
| `bbox` | array[4] de double | sí | `[minLon, minLat, maxLon, maxLat]` — útil para *pre-filtering* |
| `source` | object | sí | `{ "name": "DANE-MGN", "version": "MGN2025" }` |
| `ingested_at` | datetime | sí | Marca de tiempo UTC |

### 4.2 `buildings`

Un documento por huella de edificio. Se cargarán **únicamente** las huellas que
intersectan los 170 polígonos PDET (filtrado en ingesta).

| Campo | Tipo lógico | Obligatorio | Notas |
|---|---|---|---|
| `_id` | ObjectId | sí | Generado por Mongo |
| `source` | string enum | sí | `"microsoft"` \| `"google"` \| `"tum"` |
| `source_id` | string | no | ID original cuando exista (ej. `quadkey` o `full_plus_code`) |
| `geometry` | GeoJSON `Polygon` | sí | EPSG:4326 — la huella propiamente dicha |
| `centroid` | GeoJSON `Point` | sí | Pre-calculado para `$geoNear` y filtros rápidos |
| `area_m2` | double | sí | Calculada en EPSG:9377 (CTM12) |
| `confidence` | double [0..1] | no | Sólo cuando la fuente lo reporta |
| `height_m` | double | no | Sólo MS/TUM cuando esté disponible |
| `municipality_divipola` | string(5) | sí | DIVIPOLA del municipio que contiene el centroide. Asignado en ingesta para acelerar agregaciones. |
| `ingested_at` | datetime | sí | UTC |
| `ingest_batch` | string | sí | ID del lote de carga (auditoría) |

> El campo `municipality_divipola` **denormaliza** la pertenencia espacial. Aunque
> MongoDB puede resolverla en cada consulta con `$geoIntersects`, calcularla
> una vez en ingesta evita repetir esa operación costosa en cada agregación
> de la Semana 4. Es el clásico *trade-off* NoSQL: espacio en disco a cambio
> de velocidad de consulta.

### 4.3 `municipality_stats`

Resultados agregados — una fila por (municipio, fuente). Se popula en Semana 4.

| Campo | Tipo lógico | Obligatorio | Notas |
|---|---|---|---|
| `_id` | string | sí | Compuesto: `"<divipola>:<source>"` (ej. `"05001:microsoft"`) |
| `divipola` | string(5) | sí | |
| `mpio_cnmbr` | string | sí | Denormalizado para legibilidad del reporte |
| `source` | string enum | sí | |
| `building_count` | int | sí | Conteo total de huellas |
| `total_roof_area_m2` | double | sí | Suma de `area_m2` |
| `mean_roof_area_m2` | double | sí | |
| `median_roof_area_m2` | double | sí | |
| `coverage_ratio` | double | sí | `total_roof_area_m2 / (area_km2 * 1e6)` |
| `computed_at` | datetime | sí | |

## 5. Mapeo fuente → documento

### 5.1 DANE/MGN → `municipalities`

| Campo destino | Origen | Transformación |
|---|---|---|
| `divipola` | `dpto_ccdgo + mpio_ccdgo` | Concatenación, *zero-padding* |
| `mpio_cnmbr`, `dpto_cnmbr`, `dpto_ccdgo` | Directo | Normalización a UTF-8, *trim* |
| `is_pdet` | Cruce contra lista oficial PDET (170 mpios) | `true` si DIVIPOLA está en la lista; si no, el municipio se descarta |
| `pdet_subregion` | Cruce contra catálogo PDET (16 subregiones) | *Lookup* en tabla auxiliar |
| `geometry` | `geometry` del shapefile | Reproyección EPSG:4686 → EPSG:4326; `shapely.make_valid` |
| `area_km2` | Recalculado | Reproyectar a EPSG:9377 (CTM12), `.area / 1e6` |
| `bbox` | Calculado | `geom.bounds` en EPSG:4326 |
| `source`, `ingested_at` | Constantes | — |

### 5.2 Microsoft Buildings → `buildings`

| Campo destino | Origen | Transformación |
|---|---|---|
| `source` | constante `"microsoft"` | — |
| `source_id` | `quadkey + idx` | Concatenación |
| `geometry` | Columna `geometry` | Validar y simplificar tolerancia 1e-7 (opcional) |
| `centroid` | Calculado | `shapely.centroid` en EPSG:4326 |
| `area_m2` | Calculado | Polígono reproyectado a EPSG:9377 → `.area` |
| `height_m` | Columna `height` cuando exista | `null` si no |
| `municipality_divipola` | *Spatial join* con `municipalities` | `sjoin` por `within` |

### 5.3 Google Open Buildings → `buildings`

| Campo destino | Origen | Transformación |
|---|---|---|
| `source` | constante `"google"` | — |
| `source_id` | `full_plus_code` | Directo |
| `geometry` | WKT en columna `geometry` | `shapely.wkt.loads` |
| `centroid` | `latitude` + `longitude` | Construir `Point(lon, lat)` |
| `area_m2` | `area_in_meters` cuando exista, si no calcular | Validar contra valor reportado (±1%) |
| `confidence` | `confidence` | Directo |
| `municipality_divipola` | *Spatial join* | igual que MS |

## 6. Reglas de calidad y validación

| Regla | Capa | Acción si falla |
|---|---|---|
| Geometría con auto-intersección | Ingesta | `shapely.make_valid`; si persiste, descartar y registrar |
| `area_m2 <= 0` | Ingesta | Descartar — huella corrupta |
| `area_m2 > 50.000 m²` | Ingesta | Marcar como *outlier*; no descartar (puede ser bodega/aeropuerto) |
| Centroide fuera del *bbox* del municipio asignado | Ingesta | Recalcular *spatial join*; descartar si sigue inconsistente |
| Documento sin `divipola` (`municipalities`) | MongoDB | Rechazado por `$jsonSchema` |
| `source` no en enum | MongoDB | Rechazado por `$jsonSchema` |
| `coordinates` fuera de rango lon/lat | MongoDB | Rechazado por `2dsphere` al construir índice |

## 7. Volumetría estimada

| Colección | Documentos estimados | Tamaño por doc (aprox.) | Total |
|---|---|---|---|
| `municipalities` | 170 | ~30–80 KB (geometría densa) | ~8 MB |
| `buildings` | 8–15 millones (huellas dentro de PDET) | ~250 B (con índice) | ~3–4 GB |
| `municipality_stats` | 340 (170 × 2 fuentes) | < 1 KB | < 1 MB |

> El volumen efectivo dependerá del prefiltrado por *bounding box* y de cuántos
> municipios PDET sean cubiertos por cada dataset. La cifra de 8–15 M es una
> cota conservadora basada en la densidad rural de los municipios PDET.

## 8. Consideraciones de proyección (CRS)

| Operación | CRS exigido | Razón |
|---|---|---|
| Almacenamiento e índice `2dsphere` | EPSG:4326 | Requisito de MongoDB para geometrías GeoJSON |
| Cálculo de áreas en m² | EPSG:9377 (CTM12) | Proyección oficial colombiana, conserva áreas con error < 0,02% |
| Visualización / mapas | EPSG:3857 o EPSG:4326 | Compatible con web maps |

La conversión 4326 ↔ 9377 se hace en la capa de ingesta con `pyproj`, no se
almacenan duplicados de geometría.

## 9. Consultas que el modelo debe soportar

Estas son las consultas que el modelo está optimizado para resolver eficientemente
y que aparecen en las entregas posteriores:

1. *"Para un municipio PDET dado, ¿cuántas huellas hay y cuál es su área total?"*
   → Filtro `municipality_divipola = X` + agregación. **No requiere operador
   geoespacial** gracias a la denormalización.

2. *"¿Cuál es el área total de techos en cada subregión PDET?"*
   → `$group` por `pdet_subregion` sobre `municipality_stats`.

3. *"Dado un punto (lon, lat), ¿en qué municipio PDET cae?"*
   → `$geoIntersects` sobre `municipalities.geometry`.

4. *"Comparar conteo MS vs Google por municipio."*
   → `$pivot` sobre `municipality_stats` por `source`.

5. *"Edificios con área de techo > 100 m² en el municipio X."*
   → Filtro compuesto: `municipality_divipola = X` + `area_m2 > 100`. Usa índice
   compuesto `(municipality_divipola, area_m2)`.
