# 01 — Implementation Plan

**Proyecto:** Estimación del potencial solar en techos de municipios PDET — UPME
**Entrega:** Semana 1
**Componente:** *Implementation Plan*

---

## 1. Contexto y alcance

UPME requiere una metodología reproducible para **(i) contar las edificaciones**
existentes en cada municipio PDET y **(ii) estimar el área total de techo apta**
para la instalación de paneles solares, comparando los resultados de al menos dos
fuentes abiertas de *building footprints* y usando obligatoriamente una
infraestructura **NoSQL**.

El alcance de esta Entrega 1 se limita a establecer el cimiento técnico:

| Dentro del alcance | Fuera del alcance |
|---|---|
| Elección del motor NoSQL | Carga masiva de huellas (Semana 3) |
| Modelado de datos | Pipelines de agregación final (Semana 4) |
| Diseño de colecciones e índices | Visualizaciones y reporte final (Semana 5) |
| Validadores `$jsonSchema` | Filtrado de techos por inclinación/sombra |
| Plan de carga e ingesta | Recomendaciones operativas para UPME |

## 2. Objetivos de la entrega

1. Definir el motor NoSQL y justificar su idoneidad frente a los requisitos
   geoespaciales del proyecto.
2. Especificar las colecciones, los campos y los tipos de dato que se usarán a
   lo largo de las cinco semanas del proyecto.
3. Entregar los validadores formales (`$jsonSchema`) y el script de
   inicialización de índices que serán aplicados al instanciar la base.
4. Documentar el flujo de datos *end-to-end* para que la entrega de la Semana 2
   (carga de fronteras PDET) y la Semana 3 (carga de huellas) puedan ejecutarse
   sin re-trabajo de modelado.

## 3. Stack tecnológico

| Capa | Tecnología | Versión objetivo | Rol |
|---|---|---|---|
| Base de datos | **MongoDB Community** | 7.0 LTS | Almacenamiento NoSQL e indexación geoespacial |
| Cliente / shell | `mongosh` | ≥ 2.2 | Administración, índices, validadores |
| Driver | `pymongo` | ≥ 4.8 | Conexión desde scripts Python |
| Procesamiento geoespacial | `geopandas`, `shapely`, `pyproj` | últimas estables | Lectura, reproyección, validación de geometrías |
| Lectura de fuentes | `pyarrow`, `fiona`, `requests` | últimas estables | Parquet/GeoParquet, Shapefile, descargas |
| Notebooks | Jupyter | — | EDA y reportes intermedios |
| Control de versiones | Git + GitHub | — | Repositorio del grupo (requisito del proyecto) |
| Despliegue local | Docker + `docker-compose` | — | MongoDB reproducible en cualquier máquina |
| Orquestación opcional | Makefile / `invoke` | — | Comandos estandarizados (`make init`, `make load`) |

> **Por qué MongoDB y no otra NoSQL:** la decisión se argumenta en detalle en
> `03_Schema_Design.md` §2. En resumen: es la única familia NoSQL de propósito
> general con soporte de primera clase para GeoJSON, índices `2dsphere`,
> operadores `$geoIntersects`/`$geoWithin`/`$geoNear` y agregaciones espaciales,
> que son exactamente las operaciones que pide el problema.

## 4. Arquitectura lógica

```
                ┌────────────────────────────────────────────────┐
                │              Fuentes externas                  │
                │  ┌──────────────┐ ┌──────────────┐ ┌─────────┐ │
                │  │ DANE / MGN   │ │ MS Buildings │ │ Google  │ │
                │  │ (Shapefile)  │ │ (GeoParquet) │ │ OpenBld │ │
                │  └──────┬───────┘ └──────┬───────┘ └────┬────┘ │
                └─────────┼────────────────┼──────────────┼──────┘
                          │                │              │
                          ▼                ▼              ▼
                  ┌───────────────────────────────────────────┐
                  │   Capa de ingesta (Python + GeoPandas)    │
                  │  - Validación de geometrías               │
                  │  - Filtrado espacial por bbox PDET        │
                  │  - Reproyección a EPSG:4326 (GeoJSON)     │
                  │  - Cálculo de área en EPSG:9377 (CTM12)   │
                  └────────────────────┬──────────────────────┘
                                       │ pymongo (bulk_write)
                                       ▼
                  ┌───────────────────────────────────────────┐
                  │          MongoDB 7 — base `upme_solar`    │
                  │  ┌─────────────────┐  ┌──────────────────┐│
                  │  │ municipalities  │  │ buildings        ││
                  │  │  (170 docs)     │  │  (millones docs) ││
                  │  │  2dsphere(geom) │  │  2dsphere(geom)  ││
                  │  │                 │  │  idx(source,muni)││
                  │  └─────────────────┘  └──────────────────┘│
                  │  ┌─────────────────────────────────────┐  │
                  │  │ municipality_stats (resultados W4)  │  │
                  │  └─────────────────────────────────────┘  │
                  └────────────────────┬──────────────────────┘
                                       │
                                       ▼
                  ┌───────────────────────────────────────────┐
                  │   Capa de análisis (Jupyter + pymongo)    │
                  │  - Agregaciones $geoIntersects            │
                  │  - Conteos y sumas por municipio          │
                  │  - Mapas y tablas para el reporte final   │
                  └───────────────────────────────────────────┘
```

## 5. Plan de implementación por semana

| Semana | Hito | Salida concreta |
|---|---|---|
| **1** | **NoSQL Schema & Plan** *(esta entrega)* | Esta carpeta `Entrega1/` |
| 2 | Carga de municipios PDET (DANE/MGN) | Colección `municipalities` poblada con 170 documentos y defendida en clase |
| 3 | Carga de huellas (MS + Google) | Colección `buildings` con dos fuentes, índice espacial activo y reporte EDA |
| 4 | Workflow reproducible | Notebooks que generan conteos y áreas por municipio para cada fuente |
| 5 | Reporte técnico final | PDF con metodología, resultados, mapas y recomendaciones |

## 6. Plan operativo de esta entrega (Semana 1)

### 6.1 Preparación del entorno

1. Levantar MongoDB local vía Docker:
   ```bash
   docker run -d --name mongo-upme -p 27017:27017 \
              -v mongo_upme_data:/data/db mongo:7
   ```
2. Crear entorno Python con las dependencias declaradas en §3.
3. Configurar el repo del grupo con la estructura propuesta en `README.md`.

### 6.2 Aplicación del esquema

1. Ejecutar `mongosh < schemas/init_indexes.js` para:
   - crear la base `upme_solar`,
   - crear las tres colecciones con sus validadores `$jsonSchema`,
   - construir los índices `2dsphere` y los compuestos auxiliares.
2. Verificar con `db.getCollectionInfos()` que los validadores quedaron activos.

### 6.3 Pruebas mínimas de aceptación

| Prueba | Comando | Resultado esperado |
|---|---|---|
| Inserción válida de municipio | `db.municipalities.insertOne(<example>)` | Documento aceptado |
| Inserción inválida (sin `mpio_cnmbr`) | `insertOne` sin el campo | Error de validación |
| Consulta espacial básica | `$geoIntersects` con un punto en Bogotá | Devuelve el municipio correspondiente cuando exista |
| Inserción de edificio MS y Google | Dos documentos con `source` distinto | Ambos aceptados, índice compuesto los diferencia |

## 7. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Volumen de huellas excede memoria local | Alta | Alto | Filtrar por *bounding box* de PDET antes de cargar; carga por *chunks* con `bulk_write(ordered=False)` |
| Geometrías inválidas (auto-intersección) | Media | Alto | Validar y reparar con `shapely.make_valid` antes de insertar; MongoDB rechaza polígonos inválidos en `2dsphere` |
| Diferencias de CRS entre fuentes | Alta | Medio | Reproyección obligatoria a EPSG:4326 para almacenamiento y a EPSG:9377 para cálculo de áreas |
| Duplicados entre Microsoft y Google | Media | Medio | Mantener `source` como discriminador y trabajar las métricas por fuente; el reporte comparará, no fusionará |
| Diferencias de versión de MGN | Baja | Medio | Fijar la versión MGN2025 en el documento de modelado y registrar el `version_mgn` en cada municipio |
| Inactividad de un miembro del equipo | Media | Alto | Tablero de tareas con asignación clara y commits frecuentes desde el día 1 (requisito explícito del proyecto) |

## 8. Criterios de aceptación de la Entrega 1

La entrega se considera completa si:

- [x] La base `upme_solar` puede crearse desde cero ejecutando un único script.
- [x] Las tres colecciones tienen validadores `$jsonSchema` activos.
- [x] Existen índices `2dsphere` sobre los campos geométricos.
- [x] Los documentos de ejemplo provistos pasan la validación al insertarse.
- [x] La documentación de las secciones *Implementation Plan*, *Data Modeling*
      y *Schema Design & Appropriateness* está en el repositorio y referenciada
      desde el `README.md`.

## 9. Próximos pasos (preparación Semana 2)

1. Descargar `MGN2025-Colombia` desde el Geoportal del DANE.
2. Cruzar el listado oficial de 170 municipios PDET (Decreto 893 de 2017) contra
   los códigos DIVIPOLA del MGN.
3. Cargar los polígonos municipales como documentos en la colección
   `municipalities` siguiendo el esquema definido en esta entrega.
4. Preparar la defensa en clase con: conteo de municipios cargados, validación
   de geometrías y un mapa estático de cobertura.
