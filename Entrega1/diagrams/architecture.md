# Arquitectura — diagrama de referencia

## Flujo end-to-end

```
                      ┌───────────────────────────────────────────┐
                      │              FUENTES EXTERNAS             │
                      ├───────────────────────────────────────────┤
                      │                                           │
   DANE Geoportal ───►│  MGN_MPIO_POLITICO  (shapefile, EPSG:4686)│
                      │                                           │
   MS Planetary ────► │  ms-buildings       (GeoParquet, 4326)    │
                      │                                           │
   Google Research ─► │  open-buildings v3  (CSV/Parquet, 4326)   │
                      └─────────────────────┬─────────────────────┘
                                            │
                                            ▼
                ┌─────────────────────────────────────────────────────┐
                │             CAPA DE INGESTA (Python)                │
                │  geopandas · shapely · pyproj · pyarrow · pymongo   │
                │                                                     │
                │  1. Lectura por chunks                              │
                │  2. Reproyeccion a EPSG:4326 (almacenamiento)       │
                │  3. Calculo de area en EPSG:9377 (CTM12)            │
                │  4. shapely.make_valid + sjoin con municipalities   │
                │  5. bulk_write(ordered=False) a MongoDB             │
                └─────────────────────┬───────────────────────────────┘
                                      │
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │                MongoDB 7 — base `upme_solar`                │
       │                                                             │
       │   ┌─────────────────────┐    ┌────────────────────────────┐ │
       │   │   municipalities    │    │         buildings          │ │
       │   │   (170 docs)        │    │   (millones de docs)       │ │
       │   │                     │    │                            │ │
       │   │   - divipola (uq)   │    │   - source                 │ │
       │   │   - geometry        │    │   - geometry               │ │
       │   │   - 2dsphere idx    │    │   - centroid               │ │
       │   └─────────────────────┘    │   - municipality_divipola  │ │
       │                              │   - 2dsphere idx           │ │
       │                              │   - (muni,source) idx      │ │
       │                              └────────────────────────────┘ │
       │                                                             │
       │            ┌────────────────────────────────────┐           │
       │            │       municipality_stats           │           │
       │            │   (170 x N_fuentes — Semana 4)     │           │
       │            └────────────────────────────────────┘           │
       └────────────────────────┬────────────────────────────────────┘
                                │
                                ▼
                ┌─────────────────────────────────────┐
                │       CAPA DE ANALISIS              │
                │  Jupyter + pymongo + matplotlib     │
                │                                     │
                │  - $geoIntersects / $geoWithin      │
                │  - $group por divipola, source      │
                │  - Mapas (folium / geopandas)       │
                │  - Reporte tecnico final            │
                └─────────────────────────────────────┘
```

## Modelo de datos (ER conceptual)

```
   ┌────────────────────────────┐
   │     municipalities         │
   │ ─────────────────────────  │
   │ * divipola  (uq)           │
   │   mpio_cnmbr               │
   │   pdet_subregion           │
   │   geometry  (Polygon)      │
   │   area_km2                 │
   └─────────────┬──────────────┘
                 │ 1
                 │
                 │ N (relacion espacial — no FK)
                 │
   ┌─────────────┴──────────────┐
   │       buildings            │
   │ ─────────────────────────  │
   │ * _id                      │
   │   source                   │
   │   geometry  (Polygon)      │
   │   centroid  (Point)        │
   │   area_m2                  │
   │   municipality_divipola ───┘  (denormalizado, resuelto en ingesta)
   └────────────────────────────┘

                 │ agrega a
                 ▼
   ┌────────────────────────────┐
   │   municipality_stats       │
   │ ─────────────────────────  │
   │ * _id = "divipola:source"  │
   │   building_count           │
   │   total_roof_area_m2       │
   │   coverage_ratio           │
   └────────────────────────────┘
```
