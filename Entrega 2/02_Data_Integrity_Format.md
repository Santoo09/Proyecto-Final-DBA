# 02 — Data Integrity & Format

**Criterio de evaluación 2 de 4 — Entrega 2**

---

## 1. De Shapefile a GeoJSON: transformaciones aplicadas

| Paso | Operación | Librería | Razón |
|---|---|---|---|
| 1 | Lectura `MGN_MPIO_POLITICO.shp` | `geopandas.read_file` | Soporte nativo de SRC, atributos y geometrías |
| 2 | Normalización de texto | `str.strip().encode('utf-8')` | Eliminar caracteres invisibles del shapefile |
| 3 | Construcción del `divipola` | `dpto_ccdgo + mpio_ccdgo` con `zfill` | Clave única estable |
| 4 | Filtro por lista PDET | `gdf[gdf.divipola.isin(decreto_set)]` | Reducir de ~1.122 a 170 municipios |
| 5 | Reproyección a EPSG:4326 | `gdf.to_crs(4326)` | Requisito de MongoDB `2dsphere` |
| 6 | Validación de topología | `shapely.is_valid` | Detectar auto-intersecciones |
| 7 | Reparación si aplica | `shapely.make_valid` | Corrige sin perder área significativa |
| 8 | Cálculo de área | reproyectar a EPSG:9377 y `.area / 1e6` | Métrica fiel (error < 0,02%) |
| 9 | Simplificación LOD | `shapely.simplify(tolerance=0.001, preserve_topology=True)` | ~100 m de tolerancia para render rápido |
| 10 | Cálculo de `bbox` | `geometry.bounds` | Pre-filtros sin tocar la geometría densa |
| 11 | Serialización a GeoJSON | `mapping(geom)` (shapely) | Formato exigido por MongoDB |

## 1.1 Reorientación de anillos (winding order)

MongoDB `2dsphere` exige que los **anillos exteriores** estén en **sentido
antihorario (CCW)** y los huecos en sentido horario. Los shapefiles del DANE
(y la mayoría de shapefiles de fuentes oficiales) almacenan en el orden
opuesto, lo que hace que el motor interprete el polígono como "el resto del
planeta menos el polígono" y `$geoIntersects` con un punto interior devuelva
vacío.

El módulo `integrity.py` aplica `shapely.geometry.polygon.orient(geom, sign=1)`
a cada geometría justo antes de serializar a GeoJSON. Este paso es **silencioso
pero crítico**: sin él, la base se carga "exitosamente" pero ninguna consulta
espacial funciona.

## 2. Almacenamiento dual de la geometría

Esta entrega introduce un campo nuevo en el documento de municipio:

```json
{
  "geometry":            { "type": "MultiPolygon", "coordinates": [ ... ] },  // fiel
  "geometry_simplified": { "type": "MultiPolygon", "coordinates": [ ... ] },  // ~100 m
}
```

### Justificación

| Aspecto | `geometry` (fiel) | `geometry_simplified` (LOD) |
|---|---|---|
| Uso | Cálculos espaciales precisos (Semanas 3-4) | Mapas web, *diffs* visuales, comparación de fuentes |
| Tolerancia Douglas-Peucker | 0 | ~0,001° (~100 m al ecuador) |
| Tamaño relativo | 100% | 5%–15% |
| Topología | Conservada | Conservada (`preserve_topology=True`) |
| Indexada con `2dsphere` | Sí | No (no se consulta espacialmente) |

> **Por qué no almacenar dos colecciones separadas:** ambas geometrías describen
> la misma entidad y se consultan juntas (e.g. "muéstrame el polígono del
> municipio X — simplificado en la UI, fiel en el cálculo"). El patrón MongoDB
> de *embed-related-data* aplica directamente.

### Hallazgo: los polígonos del MGN saturan `$geoIntersects` como operando

Al validar la consulta polígono-vs-polígono (Q4 — vecinos PDET de un municipio
dado), descubrimos que MongoDB **trunca silenciosamente** los polígonos
complejos usados como operando de la consulta. Promedios reales en este
dataset:

| Métrica | `geometry` | `geometry_simplified` |
|---|---:|---:|
| Vértices promedio | 8.910 | 374 |
| Vértices máximo | 51.716 | 2.423 |
| Razón de compresión | — | **23,8×** |

Con polígonos de miles de vértices como operando, `$geoIntersects` devuelve
menos resultados de los esperados (sin error, sin warning). La mitigación
adoptada es:

- el polígono fiel (`geometry`) se mantiene como **target** indexado en `2dsphere`;
- el polígono simplificado (`geometry_simplified`) se usa como **operando** de
  las consultas polígono-vs-polígono.

Esto convierte el almacenamiento dual de LOD de un "nice to have" a un
**requisito funcional** para que las consultas de la Semana 4 (huellas
intersectadas con municipios) sean correctas.

## 3. Validación en tres capas

### Capa 1 — Pre-insert (Python)

Antes de construir cualquier documento, `integrity.py` aplica:

| Regla | Acción si falla |
|---|---|
| `geometry.is_valid` | Reparar con `make_valid`; si la nueva geometría pierde > 1% de área, descartar |
| `geometry.area > 0` | Descartar |
| `geometry.geom_type ∈ {Polygon, MultiPolygon}` | Descartar |
| Coordenadas con `lon ∈ [-82, -66]`, `lat ∈ [-5, 13]` | Descartar (fuera de Colombia) |
| Centroide cae dentro del polígono | *Warning*; aceptar si el polígono es complejo |
| `area_km2` recalculado coincide con `mpio_narea` del MGN dentro de ±5% | *Warning* — diferencia esperada por método de cálculo |

### Capa 2 — Insert (MongoDB `$jsonSchema`)

El validador (heredado de la Entrega 1, extendido) rechaza:

- Documentos sin campos obligatorios.
- `divipola` con patrón distinto a `^[0-9]{5}$`.
- `geometry.type` fuera de `{"Polygon", "MultiPolygon"}`.
- `is_pdet` distinto de `true`.
- `pdet_subregion` fuera del enum de 16 subregiones.

Y MongoDB rechaza al construir el índice `2dsphere`:

- Coordenadas con `lon ∉ [-180, 180]` o `lat ∉ [-90, 90]`.
- Anillos sin cierre.
- Polígonos con superficie nula.

### Capa 3 — Post-insert (agregación)

Tras la carga, `loader.py` ejecuta una pipeline de verificación:

```js
db.municipalities.aggregate([
  { $facet: {
      total:          [{ $count: "n" }],
      duplicados:     [{ $group: { _id: "$divipola", c: { $sum: 1 } } },
                       { $match: { c: { $gt: 1 } } }],
      sin_bbox:       [{ $match: { bbox: { $exists: false } } }, { $count: "n" }],
      por_subregion:  [{ $group: { _id: "$pdet_subregion", c: { $sum: 1 } } }],
      area_total:     [{ $group: { _id: null, total: { $sum: "$area_km2" } } }]
  }}
])
```

Salidas esperadas:

- `total.n == 170`
- `duplicados == []`
- `sin_bbox.n == 0`
- `por_subregion` cubre las **16** subregiones del catálogo ART
- `area_total ≈ 90.000 km²` (suma de áreas PDET, valor de referencia)

Si alguno falla, la corrida se marca `status: "failed_post_validation"` y los
documentos quedan en `validationLevel: "strict"` pero la corrida no se considera
exitosa.

## 4. Reparación de geometrías — política

| Caso detectado | Frecuencia esperada | Política |
|---|---|---|
| Auto-intersección menor (cuello) | Alta en municipios costeros | `make_valid` y aceptar |
| Anillo duplicado | Baja | `make_valid` y aceptar |
| MultiPolygon con isla < 100 m² | Media | Conservar (es real) |
| Pérdida de área > 1% tras reparar | Muy baja | Rechazar y reportar al docente |
| Geometría vacía tras reparar | Muy baja | Rechazar |

Cada reparación queda registrada en el manifest con:

```json
{
  "divipola": "27077",
  "action": "make_valid",
  "delta_area_km2": -0.0034,
  "delta_area_pct": -0.0009
}
```

## 5. Sistema de coordenadas — política de proyecciones

| Operación | CRS | Justificación |
|---|---|---|
| Almacenamiento e índice `2dsphere` | EPSG:4326 (WGS84) | Único soportado por MongoDB |
| Cálculo de áreas y longitudes | EPSG:9377 (CTM12 — Colombia) | Proyección oficial nacional (Res. IGAC 471/2020) |
| Visualización web | EPSG:3857 (Web Mercator) | Estándar de tiles |

La reproyección se hace *on-the-fly* con `pyproj`; nunca se almacenan dos
versiones de la misma geometría en CRS distintos.

## 6. Aceptación del criterio

- [x] La cadena Shapefile → GeoJSON queda documentada paso a paso.
- [x] Cada geometría se valida y, si aplica, se repara con política explícita.
- [x] La validación tiene tres capas independientes (Python, Mongo schema, agregación post).
- [x] El almacenamiento dual `geometry` / `geometry_simplified` está justificado.
- [x] Las decisiones de CRS están alineadas con la normatividad colombiana.
