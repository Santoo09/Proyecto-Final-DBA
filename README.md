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

## 6. Estado de la entrega

- [x] Implementation Plan
- [x] Data Modeling
- [x] Schema Design & Appropriateness
- [x] JSON Schemas de validación
- [x] Documentos de ejemplo
- [x] Script de inicialización de índices
