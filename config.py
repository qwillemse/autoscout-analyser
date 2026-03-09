import os
from datetime import datetime

# In production (Railway), set DB_PATH and MODEL_PATH env vars to point to a
# persistent volume (e.g. /data/cars.db, /data/pipeline.joblib).
# Locally they default to files next to this script.
_here = os.path.dirname(__file__)
DB_PATH    = os.environ.get("DB_PATH",    os.path.join(_here, "cars.db"))
MODEL_PATH = os.environ.get("MODEL_PATH", os.path.join(_here, "pipeline.joblib"))
HEADERS = {"User-Agent": "Mozilla/5.0"}
BASE_URL = "https://www.autoscout24.nl/lst/{make}"

MAKES = [
    # High volume (original 15)
    "volkswagen", "bmw", "mercedes-benz", "audi", "ford",
    "toyota", "opel", "renault", "peugeot", "skoda",
    "hyundai", "kia", "seat", "honda", "volvo",
    # Expanded (NL market top sellers)
    "nissan", "mazda", "fiat", "dacia", "mini",
    "citroen", "suzuki", "mitsubishi", "jeep", "land-rover",
    "porsche", "tesla", "alfa-romeo", "subaru", "lexus",
    "cupra", "smart", "ds", "dodge", "chevrolet",
    # EV / newer brands with NL presence
    "polestar", "mg",
]

# Year bands used to split scraping queries and bypass AutoScout24's per-search
# result cap (200 pages = 4,000 listings per query).
# Older years are sparse so get wider bands; 2015+ are 1-year bands because
# popular makes (VW, BMW, Mercedes) can easily exceed 4,000 listings per year.
_current = datetime.now().year
YEAR_BANDS = (
    [(None, 2012), (2013, 2014)]          # pre-2015: wider bands, fewer listings
    + [(y, y) for y in range(2015, _current)]  # 2015 to last full year: 1 year each
    + [(_current, None)]                  # current year onwards
)


# to avoid outliers and focus on typical cars, we set some reasonable filters
PARAMS = {
    "cy": "NL",
    "kmto": 250000,       # exclude >250k km — outliers, essentially sold for parts
    "fregfrom": 2005,     # exclude pre-2005 — collectibles, completely different market
    "pricefrom": 500,
    "priceto": 150000,    # raised from 75k — captures Porsche, AMG, M-series, RS etc.
    "sort": "standard",
    "desc": 0,
}