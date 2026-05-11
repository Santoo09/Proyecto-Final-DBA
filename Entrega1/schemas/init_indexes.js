// =============================================================================
// init_indexes.js
//
// Crea la base `upme_solar`, sus tres colecciones con validadores
// $jsonSchema y los indices requeridos por el diseno (Entrega 1).
//
// Uso:
//   mongosh "mongodb://localhost:27017" --file schemas/init_indexes.js
//
// Idempotente: se puede correr varias veces sin error.
// =============================================================================

const DB_NAME = "upme_solar";
db = db.getSiblingDB(DB_NAME);

print(`>> Inicializando base '${DB_NAME}'...`);

// -----------------------------------------------------------------------------
// 1) municipalities
// -----------------------------------------------------------------------------
const municipalitiesValidator = {
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
          name:    { bsonType: "string" },
          version: { bsonType: "string" }
        }
      },
      ingested_at: { bsonType: "date" }
    }
  }
};

if (!db.getCollectionNames().includes("municipalities")) {
  db.createCollection("municipalities", {
    validator: municipalitiesValidator,
    validationLevel: "strict",
    validationAction: "error"
  });
  print("   - Coleccion 'municipalities' creada.");
} else {
  db.runCommand({ collMod: "municipalities", validator: municipalitiesValidator });
  print("   - Validador de 'municipalities' actualizado.");
}

db.municipalities.createIndex({ divipola: 1 },  { unique: true, name: "uq_divipola" });
db.municipalities.createIndex({ geometry: "2dsphere" }, { name: "geo_municipality" });
db.municipalities.createIndex({ pdet_subregion: 1 },    { name: "by_subregion" });
print("   - Indices de 'municipalities' OK.");

// -----------------------------------------------------------------------------
// 2) buildings
// -----------------------------------------------------------------------------
const buildingsValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: [
      "source", "geometry", "centroid", "area_m2",
      "municipality_divipola", "ingested_at", "ingest_batch"
    ],
    properties: {
      source:    { enum: ["microsoft", "google", "tum"] },
      source_id: { bsonType: ["string", "null"] },
      geometry: {
        bsonType: "object",
        required: ["type", "coordinates"],
        properties: {
          type:        { enum: ["Polygon", "MultiPolygon"] },
          coordinates: { bsonType: "array" }
        }
      },
      centroid: {
        bsonType: "object",
        required: ["type", "coordinates"],
        properties: {
          type:        { enum: ["Point"] },
          coordinates: { bsonType: "array", minItems: 2, maxItems: 2 }
        }
      },
      area_m2:    { bsonType: "double", minimum: 0 },
      confidence: { bsonType: ["double", "null"], minimum: 0, maximum: 1 },
      height_m:   { bsonType: ["double", "null"], minimum: 0 },
      municipality_divipola: { bsonType: "string", pattern: "^[0-9]{5}$" },
      ingested_at:  { bsonType: "date" },
      ingest_batch: { bsonType: "string", minLength: 1 }
    }
  }
};

if (!db.getCollectionNames().includes("buildings")) {
  db.createCollection("buildings", {
    validator: buildingsValidator,
    validationLevel: "strict",
    validationAction: "error"
  });
  print("   - Coleccion 'buildings' creada.");
} else {
  db.runCommand({ collMod: "buildings", validator: buildingsValidator });
  print("   - Validador de 'buildings' actualizado.");
}

db.buildings.createIndex({ geometry: "2dsphere" }, { name: "geo_building" });
db.buildings.createIndex(
  { municipality_divipola: 1, source: 1 },
  { name: "by_muni_source" }
);
db.buildings.createIndex(
  { municipality_divipola: 1, area_m2: 1 },
  { name: "by_muni_area" }
);
db.buildings.createIndex(
  { source: 1, ingest_batch: 1 },
  { name: "by_source_batch" }
);
print("   - Indices de 'buildings' OK.");

// -----------------------------------------------------------------------------
// 3) municipality_stats
// -----------------------------------------------------------------------------
const statsValidator = {
  $jsonSchema: {
    bsonType: "object",
    required: [
      "_id", "divipola", "mpio_cnmbr", "source",
      "building_count", "total_roof_area_m2",
      "mean_roof_area_m2", "median_roof_area_m2",
      "coverage_ratio", "computed_at"
    ],
    properties: {
      _id:        { bsonType: "string", pattern: "^[0-9]{5}:(microsoft|google|tum)$" },
      divipola:   { bsonType: "string", pattern: "^[0-9]{5}$" },
      mpio_cnmbr: { bsonType: "string", minLength: 1 },
      source:     { enum: ["microsoft", "google", "tum"] },
      building_count:        { bsonType: "int",    minimum: 0 },
      total_roof_area_m2:    { bsonType: "double", minimum: 0 },
      mean_roof_area_m2:     { bsonType: "double", minimum: 0 },
      median_roof_area_m2:   { bsonType: "double", minimum: 0 },
      coverage_ratio:        { bsonType: "double", minimum: 0, maximum: 1 },
      computed_at:           { bsonType: "date" }
    }
  }
};

if (!db.getCollectionNames().includes("municipality_stats")) {
  db.createCollection("municipality_stats", {
    validator: statsValidator,
    validationLevel: "strict",
    validationAction: "error"
  });
  print("   - Coleccion 'municipality_stats' creada.");
} else {
  db.runCommand({ collMod: "municipality_stats", validator: statsValidator });
  print("   - Validador de 'municipality_stats' actualizado.");
}

db.municipality_stats.createIndex({ divipola: 1 }, { name: "by_divipola" });
db.municipality_stats.createIndex(
  { source: 1, total_roof_area_m2: -1 },
  { name: "ranking_by_source" }
);
print("   - Indices de 'municipality_stats' OK.");

// -----------------------------------------------------------------------------
// Resumen
// -----------------------------------------------------------------------------
print("\n>> Resumen final:");
db.getCollectionInfos().forEach(c => {
  print(`   - ${c.name}  (validationAction: ${c.options.validationAction || "n/a"})`);
});
print(">> Listo.");
