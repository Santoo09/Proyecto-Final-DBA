# Datos de la Entrega 2

Esta carpeta contiene los insumos versionados (`pdet_decreto_893.csv`) e
**instrucciones** para obtener los datos pesados que **no** se commitean al
repositorio.

## 1. `pdet_decreto_893.csv` (versionado)

Listado oficial completo de los **170 municipios PDET** organizados en las
**16 subregiones** del Decreto 893 de 2017.

| Campo | Tipo | Notas |
|---|---|---|
| `divipola` | str(5) | Clave de cruce contra el MGN |
| `mpio_cnmbr_decreto` | str | Nombre tal como aparece en el documento ART |
| `dpto_cnmbr` | str | Departamento |
| `pdet_subregion` | str | Una de las 16 subregiones PDET (ART) |

### Fuente

El listado fue derivado del archivo Excel oficial publicado por la
**Agencia de Renovación del Territorio (ART)**:

> https://centralpdet.renovacionterritorio.gov.co/wp-content/uploads/2022/01/MunicipiosPDET.xlsx

La conversión se hizo con el script `scripts/build_decreto_csv.py` (incluido en
esta carpeta para reproducibilidad). El cruce contra el MGN se valida
automáticamente en cada corrida con `src/crosscheck.py`.

### Distribución por subregión

| # | Subregión | Municipios |
|---|---|---:|
| 1 | Alto Patía y Norte del Cauca | 24 |
| 2 | Arauca | 4 |
| 3 | Bajo Cauca y Nordeste Antioqueño | 13 |
| 4 | Catatumbo | 8 |
| 5 | Chocó | 14 |
| 6 | Cuenca del Caguán y Piedemonte Caqueteño | 17 |
| 7 | Macarena - Guaviare | 12 |
| 8 | Montes de María | 15 |
| 9 | Pacífico Medio | 4 |
| 10 | Pacífico y Frontera Nariñense | 11 |
| 11 | Putumayo | 9 |
| 12 | Sierra Nevada - Perijá - Zona Bananera | 15 |
| 13 | Sur de Bolívar | 7 |
| 14 | Sur de Córdoba | 5 |
| 15 | Sur del Tolima | 4 |
| 16 | Urabá Antioqueño | 8 |
| **Total** | | **170** |

## 2. `raw/MGN2025-Colombia.zip` (NO versionado, ~1.5 GB)

Descarga manual desde el Geoportal DANE:

1. Ir a https://geoportal.dane.gov.co/servicios/descarga-y-metadatos/datos-geoestadisticos/?cod=111
2. Seleccionar **"Versión MGN2025-Colombia. Todos los niveles geográficos, 2025, ZIP, 1.5 GB"**.
3. Descargar y guardar en `data/raw/MGN2025-Colombia.zip`.
4. Registrar el SHA-256 en el `README.md` del repo del equipo y en el manifest.

El `.gitignore` de la raíz excluye `data/raw/` para evitar subir gigabytes a git.

## 3. Comprobación rápida

```bash
# Hash del shapefile descargado
sha256sum data/raw/MGN2025-Colombia.zip

# Verificación con la CLI
python -m src.cli verify --sha256 <hash_publicado_por_dane>
```

## 4. Versionado de fuente

| Fuente | Versión | Última actualización |
|---|---|---|
| MGN | MGN2025 | 2025-01 (DANE) |
| Decreto 893 | 28 de mayo de 2017 | Sin modificaciones materiales (al 2026-05) |
| Subregiones PDET | ART vigente | Catálogo de 16 subregiones |
