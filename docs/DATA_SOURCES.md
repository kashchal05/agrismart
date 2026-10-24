# Data Sources

All data used by Agrismart 2.0 is free. This file tracks each source, what it is used for, and its
license / attribution requirements. **Verify current limits and terms before relying on any source
in production.**

## Currently used (de-risk phase)

### Sentinel-2 Level-2A imagery
- **Access:** [Earth Search STAC API](https://earth-search.aws.element84.com/v1), collection
  `sentinel-2-c1-l2a`. Catalog by Element 84 over the AWS Open Data Sentinel-2 COGs.
- **Resolution / cadence:** 10 m (visible/NIR), new scene roughly every 5 days.
- **Region:** data lives in AWS `us-west-2` (deploy there to avoid egress cost).
- **Used for:** field health (NDVI/EVI/NDWI), crop-type features, yield features.
- **License:** Copernicus Sentinel data, free and open under the
  [Copernicus / ESA terms](https://sentinels.copernicus.eu/web/sentinel/terms-conditions).
  Attribution: "Contains modified Copernicus Sentinel data [year]".
- **Cost:** reads are anonymous and free; windowed COG reads keep transfer minimal.

### USDA Cropland Data Layer (CDL) — crop labels
- **Access:** CropScape `GetCDLValue` point API (`nassgeodata.gmu.edu`); coordinates in Albers EA
  (EPSG:5070). Returns the crop grown at a pixel for a given year.
- **Used for:** Module B training labels (the crop actually grown at each sampled point).
- **License:** public domain (USDA NASS). Attribution appreciated.

### ISRIC SoilGrids — soil properties
- **Access:** `rest.isric.org/soilgrids/v2.0/properties/query` point API. Clay/sand/silt, pH,
  organic carbon, CEC, bulk density, nitrogen at several depths.
- **Used for:** Module B soil features.
- **License:** CC-BY 4.0. Attribution: ISRIC — World Soil Information.
- **Note:** ~2s/query; be gentle with concurrency (the dataset builder backs off on 429).

### NASA POWER — climate normals
- **Access:** `power.larc.nasa.gov/api/temporal/climatology/point`. Long-term monthly normals for
  precipitation and temperature.
- **Used for:** Module B climate features (annual/seasonal rainfall, temperature, GDD, frost-free).
- **License:** free and open (NASA). No key required.

## Planned (later phases)

| Data | Source | Used for | Notes |
|---|---|---|---|
| Landsat Collection 2 | Earth Search STAC | Longer history (pre-2017) | Optional |
| County yields | USDA NASS Quick Stats API | Yield labels, baselines | Free API key required |
| Weather forecast | Open-Meteo / NOAA NWS API | Alerts | NWS requires a User-Agent header |
| USDA SSURGO | Soil Data Access | Higher-res US soil (vs SoilGrids) | Free |
| Elevation | Copernicus DEM (Earth Search) | Slope / drainage | Free |
| Leaf disease images | PlantVillage, PlantDoc (+ FieldPlant) | Disease classifier | Check each dataset's license before redistribution |
| Agronomy knowledge | Texas A&M AgriLife Extension, USDA pubs | Advisor RAG corpus | **Check each site's terms before scraping** |

## Attribution block (for the app footer / docs)

> Contains modified Copernicus Sentinel data. Crop labels courtesy of the USDA National Agricultural
> Statistics Service Cropland Data Layer. Soil data from USDA NRCS SSURGO and ISRIC SoilGrids.
