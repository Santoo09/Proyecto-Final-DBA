// =============================================================================
// extend_for_w2.js
//
// Extiende el esquema de la Entrega 1 con:
//   1) Campo opcional `geometry_simplified` en `municipalities`.
//   2) Campos opcionales `file_sha256`, `downloaded_at`, `ingest_run_id`
//      dentro del subdocumento `source` de `municipalities`.
//   3) Nueva colección `ingest_runs` con su validador e índices.
//
// Idempotente. Se ejecuta DESPUÉS de Entrega1/schemas/init_indexes.js.
// =============================================================================

const DB_NAME = "upme_solar";
db = db.getSiblingDB(DB_NAME);

print(`>> Extendiendo esquema W2 en '${DB_NAME}'...`);

// -----------------------------------------------------------------------------
// 1) municipalities v2 — extiende v1 sin romper compatibilidad
// -----------------------------------------------------------------------------
const municipalitiesValidatorV2 = {
  $jsonSchema: {
    bsonType: "object",
    required: [
      "divipola", "mpio_cnmbr", "dpto_ccdgo", "dpto_cnmbr",
      "is_pdet", "pdet_subregion", "geometry", "area_km2",
      "bbox", "source", "ingested_at"
    ],
    properties: {
      divipola:       { bsonType: "string", pattern: "^[0-9]{5}$" },
      mpio_cnmbr:     { bsonType: "string", minLength: 1 },
      dpto_ccdgo:     { bsonType: "string", pattern: "^[0-9]{2}$" },
      dpto_cnmbr:     { bsonType: "string", minLength: 1 },
      is_pdet:        { bsonType: "bool", enum: [true] },
      pdet_subregion: { bsonType: "string", minLength: 1 },
      geometry: {
        bsonType: "object",
        required: ["type", "coordinates"],
        properties: {
          type:        { enum: ["Polygon", "MultiPolygon"] },
          coordinates: { bsonType: "array" }
        }
      },
      // === NUEVO en v2: campo opcional para LOD ===
      geometry_simplified: {
        bsonType: "object",
        required: ["type", "coordinates"],
        properties: {
          type:        { enum: ["Polygon", "MultiPolygon"] },
          coordinates: { bsonType: "array" }
        }
      },
      area_km2: { bsonType: "double", minimum: 0 },
      bbox: {
        bsonType: "array",
        minItems: 4, maxItems: 4,
        items: { bsonType: "double" }
      },
      source: {
        bsonType: "object",
        required: ["name", "version"],
        properties: {
          name:          { bsonType: "string" },
          version:       { bsonType: "string" },
          // === NUEVO en v2: trazabilidad de la corrida ===
          file_sha256:   { bsonType: "string", pattern: "^[a-f0-9]{64}$" },
          downloaded_at: { bsonType: "date" },
          ingest_run_id: { bsonType: ["objectId", "string"] }
        }
      },
      ingested_at: { bsonType: "date" }
    }
  }
};

db.runCommand({
  collMod: "municipalities",
  validator: municipalitiesValidatorV2,
  validationLevel: "strict",
  validationAction: "error"
});
print("   - 'municipalities' actualizada a esquema v2.");

// -----------------------------------------------------------------------------
// 2) ingest_runs — colección de auditoría
// -----------------------------------------------------------------------------
const ingestRunsValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: ["entrega", "tool_version", "started_at", "status"],
    properties: {
      entrega:      { bsonType: "string" },
      tool_version: { bsonType: "string" },
      started_at:   { bsonType: "date" },
      finished_at:  { bsonType: ["date", "null"] },
      duration_seconds: { bsonType: ["double", "int", "null"] },
      status: {
        enum: [
          "running",
          "aborted",
          "failed_verification",
          "failed_post_validation",
          "success"
        ]
      },
      source: {
        bsonType: "object",
        properties: {
          file:          { bsonType: "string" },
          size_bytes:    { bsonType: ["int", "long"] },
          sha256:        { bsonType: ["string", "null"] },
          mgn_version:   { bsonType: "string" },
          downloaded_at: { bsonType: "date" }
        }
      },
      crosscheck:      { bsonType: "object" },
      integrity:       { bsonType: "object" },
      load:            { bsonType: "object" },
      post_validation: { bsonType: "object" },
      performance_ms:  { bsonType: "object" },
      errors:          { bsonType: "array" },
      manifest_path:   { bsonType: "string" }
    }
  }
};

if (!db.getCollectionNames().includes("ingest_runs")) {
  db.createCollection("ingest_runs", {
    validator: ingestRunsValidator,
    validationLevel: "moderate",          // permite escribir intermedios
    validationAction: "error"
  });
  print("   - Coleccion 'ingest_runs' creada.");
} else {
  db.runCommand({
    collMod: "ingest_runs",
    validator: ingestRunsValidator,
    validationLevel: "moderate",
    validationAction: "error"
  });
  print("   - Validador de 'ingest_runs' actualizado.");
}

db.ingest_runs.createIndex({ started_at: -1 }, { name: "by_started_desc" });
db.ingest_runs.createIndex({ entrega: 1, status: 1 }, { name: "by_entrega_status" });
print("   - Indices de 'ingest_runs' OK.");

print("\n>> Resumen final:");
db.getCollectionInfos().forEach(c => print(`   - ${c.name}`));
print(">> Listo.");
