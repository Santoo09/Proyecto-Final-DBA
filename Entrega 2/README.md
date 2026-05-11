# Entrega 2 — PDET Municipality Boundaries Dataset Integration

**Curso:** Database Administration
**Proyecto Final:** Estimación del Potencial Solar en Techos de Municipios PDET — UPME
**Defensa:** Semana 2 — antes de las 2:00 pm en clase

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

## 7. Consultas de verificación (para la defensa)

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
