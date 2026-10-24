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

## Planned (later phases)

| Data | Source | Used for | Notes |
|---|---|---|---|
| Landsat Collection 2 | Earth Search STAC | Longer history (pre-2017) | Optional |
| Crop type per pixel/year | USDA Cropland Data Layer (CDL) | Crop-type + recommendation labels | Public domain (USDA) |
| County yields | USDA NASS Quick Stats API | Yield labels, baselines | Free API key required |
| Daily weather history | NASA POWER, Open-Meteo archive | Climate features | Check Open-Meteo rate limits |
| Weather forecast | Open-Meteo / NOAA NWS API | Alerts | NWS requires a User-Agent header |
| Soil properties | USDA SSURGO (Soil Data Access), ISRIC SoilGrids | Recommendation features | SoilGrids: CC-BY 4.0 |
| Elevation | Copernicus DEM (Earth Search) | Slope / drainage | Free |
| Leaf disease images | PlantVillage, PlantDoc (+ FieldPlant) | Disease classifier | Check each dataset's license before redistribution |
| Agronomy knowledge | Texas A&M AgriLife Extension, USDA pubs | Advisor RAG corpus | **Check each site's terms before scraping** |

## Attribution block (for the app footer / docs)

> Contains modified Copernicus Sentinel data. Crop labels courtesy of the USDA National Agricultural
> Statistics Service Cropland Data Layer. Soil data from USDA NRCS SSURGO and ISRIC SoilGrids.
