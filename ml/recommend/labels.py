"""USDA Cropland Data Layer (CDL) class codes -> crop names, and which count as crops.

Full CDL legend: https://www.nass.usda.gov/Research_and_Science/Cropland/metadata/
We keep the agricultural crop classes that are meaningful to *recommend* and drop land uses
that are not plantable decisions (developed, water, forest, wetland, barren, grassland/pasture,
fallow). Rare crops are kept only if they clear a per-class sample floor at train time.
"""

# CDL code -> crop label, for classes we treat as recommendable crops.
CROP_CLASSES: dict[int, str] = {
    1: "Corn",
    2: "Cotton",
    3: "Rice",
    4: "Sorghum",
    5: "Soybeans",
    6: "Sunflower",
    10: "Peanuts",
    12: "Sweet Corn",
    13: "Pop or Orn Corn",
    21: "Barley",
    22: "Durum Wheat",
    23: "Spring Wheat",
    24: "Winter Wheat",
    25: "Other Small Grains",
    27: "Rye",
    28: "Oats",
    29: "Millet",
    31: "Canola",
    33: "Safflower",
    36: "Alfalfa",
    37: "Other Hay/Non Alfalfa",
    41: "Sugarbeets",
    42: "Dry Beans",
    43: "Potatoes",
    53: "Peas",
    57: "Herbs",
    58: "Clover/Wildflowers",
    225: "Winter Wheat/Corn",
    226: "Oats/Corn",
    228: "Winter Wheat/Sorghum",
    237: "Barley/Corn",
}

# Double-crop CDL codes collapsed to a primary crop so classes don't fragment.
DOUBLECROP_REMAP: dict[int, int] = {
    225: 24,  # Winter Wheat/Corn -> Winter Wheat
    226: 28,  # Oats/Corn -> Oats
    228: 24,  # Winter Wheat/Sorghum -> Winter Wheat
    237: 21,  # Barley/Corn -> Barley
    12: 1,    # Sweet Corn -> Corn
    13: 1,    # Pop/Orn Corn -> Corn
    22: 24,   # Durum Wheat -> Winter Wheat (both wheat)
}


def is_crop(code: int) -> bool:
    return code in CROP_CLASSES


def crop_name(code: int) -> str:
    code = DOUBLECROP_REMAP.get(code, code)
    return CROP_CLASSES.get(code, f"Unknown({code})")


def canonical_code(code: int) -> int:
    """Map a raw CDL code to the canonical crop code used as the label."""
    return DOUBLECROP_REMAP.get(code, code)
