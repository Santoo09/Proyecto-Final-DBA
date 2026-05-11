# Entrega 1 — NoSQL Database Schema Design and Implementation Plan

**Curso:** Database Administration
**Proyecto Final:** Estimación del Potencial Solar en Techos de Municipios PDET de Colombia
**Cliente:** UPME — Unidad de Planeación Minero Energética

---

## 1. Objetivo de la entrega

Definir las bases técnicas del proyecto mediante el diseño e implementación inicial de
una solución NoSQL que permita almacenar, indexar y consultar de forma eficiente
los datos geoespaciales requeridos para estimar el área de techos aptos para paneles
solares en municipios PDET.

Esta entrega cubre los tres componentes exigidos en el documento del proyecto
(`Project.pdf`, sección 3.1, ítem 1):

1. **Implementation Plan** — Plan de implementación.
2. **Data Modeling** — Modelado de datos.
3. **Schema Design & Appropriateness** — Diseño del esquema y justificación.

## 2. Estructura de la entrega

```
Entrega1/
├── README.md                            # Este archivo — índice y resumen
├── 01_Implementation_Plan.md            # Plan de implementación
├── 02_Data_Modeling.md                  # Modelado conceptual y lógico de datos
├── 03_Schema_Design.md                  # Diseño del esquema NoSQL y justificación
├── schemas/
│   ├── municipalities.schema.json       # JSON Schema — colección municipalities
│   ├── buildings.schema.json            # JSON Schema — colección buildings
│   ├── municipality_stats.schema.json   # JSON Schema — colección de resultados
│   └── init_indexes.js                  # Script mongosh para crear índices
├── examples/
│   ├── municipality_example.json        # Documento ejemplo (municipio PDET)
│   ├── building_ms_example.json         # Documento ejemplo (Microsoft Buildings)
│   ├── building_google_example.json     # Documento ejemplo (Google Open Buildings)
│   └── municipality_stats_example.json  # Documento ejemplo (resultado agregado)
└── diagrams/
    └── architecture.md                  # Diagrama de arquitectura (texto/ASCII)
```

## 3. Resumen ejecutivo

- **Motor NoSQL seleccionado:** MongoDB 7.x (Community Edition).
- **Justificación corta:** soporte nativo de GeoJSON, índice geoespacial `2dsphere`
  sobre el elipsoide WGS84, agregaciones espaciales en pipeline (`$geoIntersects`,
  `$geoWithin`, `$geoNear`), modelo de documentos flexible para esquemas
  heterogéneos entre las tres fuentes de huellas de edificios, y capacidad de
  *sharding* por clave geográfica cuando el volumen lo requiera.
- **Datasets seleccionados:** (a) Microsoft Building Footprints y (b) Google Open
  Buildings v3. La tercera fuente (GlobalBuildingAtlas) queda documentada como
  opcional, ya que el documento del proyecto permite escoger al menos dos.
- **Capa de fronteras administrativas:** Marco Geoestadístico Nacional (MGN) del
  DANE — nivel municipal, filtrado a los 170 municipios PDET.
- **Sistema de coordenadas de almacenamiento:** EPSG:4326 (WGS84) en GeoJSON,
  exigido por el índice `2dsphere`. Para cálculos métricos (áreas) se reproyectará
  *on-the-fly* a la proyección oficial colombiana **EPSG:9377** (CTM12).

## 4. Cómo leer esta entrega

1. Empezar por [`01_Implementation_Plan.md`](01_Implementation_Plan.md) para
   entender el alcance, la arquitectura y el cronograma.
2. Continuar con [`02_Data_Modeling.md`](02_Data_Modeling.md) para ver el
   modelado conceptual y lógico de las entidades.
3. Cerrar con [`03_Schema_Design.md`](03_Schema_Design.md), donde se justifica
   por qué la propuesta es apropiada para los requerimientos de UPME.
4. Los archivos `schemas/*.json` son las definiciones formales (JSON Schema Draft
   2020-12) que se aplicarán como `$jsonSchema` validators en MongoDB.
5. Los archivos `examples/*.json` son documentos sintéticos que ilustran el
   formato real que tendrán las colecciones tras la carga.

## 5. Equipo y contribuciones

| Miembro | Responsabilidad principal en Entrega 1 |
|---|---|
| Santiago Suárez Gómez | Implementation Plan, cronograma, arquitectura, Data Modeling — fuentes externas y mapeos |
| Julian Esteban Barrera Rueda | Schema Design, JSON Schemas y validadores, Documentos de ejemplo, índices y script de init |



# Entrega 2 — PDET Municipality Boundaries Dataset Integration

**Curso:** Database Administration
**Proyecto Final:** Estimación del Potencial Solar en Techos de Municipios PDET — UPME

---

## 1. Objetivo de la entrega

Cargar y verificar el dataset de fronteras municipales del **Marco Geoestadístico
Nacional (MGN)** del DANE en la base NoSQL diseñada en la Entrega 1, dejando
poblada la colección `municipalities` **únicamente con los 170 municipios PDET**
oficiales del Decreto 893 de 2017, con geometrías validadas e indexadas
espacialmente.

## 2. Mapeo al rubric del PDF

| Criterio del PDF | Documento que lo cubre |
|---|---|
| Data Acquisition & Verification | [`01_Data_Acquisition_Verification.md`](01_Data_Acquisition_Verification.md) |
| Data Integrity & Format | [`02_Data_Integrity_Format.md`](02_Data_Integrity_Format.md) |
| NoSQL Spatial Integration | [`03_NoSQL_Spatial_Integration.md`](03_NoSQL_Spatial_Integration.md) |
| Documentation of Process | [`04_Process_Documentation.md`](04_Process_Documentation.md) |

## 3. Estructura del entregable

```
Entrega2/
├── README.md
├── 01_Data_Acquisition_Verification.md    # Criterio 1
├── 02_Data_Integrity_Format.md            # Criterio 2
├── 03_NoSQL_Spatial_Integration.md        # Criterio 3
├── 04_Process_Documentation.md            # Criterio 4
├── requirements.txt
├── .gitignore
│
├── data/
│   ├── README.md                          # instrucciones de descarga del MGN
│   └── pdet_decreto_893.csv               # 170 PDET oficiales (lista ART)
│
├── schemas/
│   └── extend_for_w2.js                   # esquema + índice 2dsphere
│
├── src/                                   # pipeline de carga
│   ├── __init__.py
│   ├── config.py
│   ├── acquisition.py                     # verificación SHA-256 del MGN
│   ├── crosscheck.py                      # cruce DIVIPOLA vs Decreto 893
│   ├── integrity.py                       # validación, reorientación, LOD
│   ├── loader.py                          # bulk_write idempotente
│   ├── audit.py                           # registro en ingest_runs
│   └── cli.py                             # CLI: ingest / verify / audit
│
└── manifests/
    └── 2026-05-11T19-25-36Z.json          # evidencia de la corrida exitosa
```

## 4. Equipo y contribuciones

| Miembro | Responsabilidad principal en Entrega 2 |
|---|---|
| Santiago Suárez Gómez | Data Integrity & Format + Documentation of Process |
| Julian Esteban Barrera Rueda | Data Acquisition & Verification + NoSQL Spatial Integration |

## 5. Cómo ejecutar

### Pre-requisitos
- MongoDB 7+ en `localhost:27017`
  (`docker run -d -p 27017:27017 mongo:7`).
- Python 3.10+ con `pip install -r requirements.txt`.
- `MGN2025_00_COLOMBIA.zip` descargado del Geoportal DANE
  (ver [`data/README.md`](data/README.md)).

### Aplicar el esquema
```bash
mongosh "mongodb://localhost:27017" --file schemas/extend_for_w2.js
```

### Correr el pipeline
```bash
python -m src.cli ingest \
  --sha256 4c7d2f2c8860fcd25eb70e8710289035aba51389100eed4c4a6dd6e81d36cbc0
```

Salida esperada:
```
Status:   success
Manifest: manifests/<timestamp>.json
```

### Ver corridas registradas
```bash
python -m src.cli audit --limit 5
```

## 6. Resultado de la corrida (evidencia)

Manifest: [`manifests/2026-05-11T19-25-36Z.json`](manifests/2026-05-11T19-25-36Z.json)

| Métrica | Valor |
|---|---:|
| `status` | `success` |
| Municipios cargados | **170** |
| Subregiones cubiertas | **16** |
| Área total PDET (km²) | **389.182,04** |
| Duración end-to-end | **17 s** |
| Geometrías reparadas | 0 |
| Errores de carga | 0 |

## 7. Consultas de verificación

```js
// Q1 — Conteo
db.municipalities.countDocuments({ is_pdet: true })  // → 170

// Q2 — Subregiones
db.municipalities.aggregate([
  { $group: { _id: "$pdet_subregion", n: { $sum: 1 } } },
  { $sort: { n: -1 } }
])  // → 16 subregiones

// Q3 — Punto en municipio PDET
db.municipalities.findOne(
  { geometry: { $geoIntersects: { $geometry:
      { type: "Point", coordinates: [-78.5, 1.8] } } } },
  { divipola: 1, mpio_cnmbr: 1, _id: 0 }
)  // → { divipola: "52835", mpio_cnmbr: "San Andrés De Tumaco" }

// Q4 — Vecinos PDET de Apartadó (usar geometry_simplified como operando)
const apt = db.municipalities.findOne({ divipola: "05045" });
db.municipalities.find(
  { geometry: { $geoIntersects: { $geometry: apt.geometry_simplified } },
    divipola: { $ne: "05045" } },
  { divipola: 1, mpio_cnmbr: 1, _id: 0 }
).toArray()
// → Carepa, Tierralta, Turbo, Valencia

// Q5 — Última corrida exitosa
db.ingest_runs.find({ entrega: "W2", status: "success" })
              .sort({ finished_at: -1 }).limit(1).pretty()
```

