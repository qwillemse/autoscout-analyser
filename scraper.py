import json
import re

from bs4 import BeautifulSoup
import requests

from config import PARAMS, HEADERS
from countries import get_country_config

# ── Normalize fuel/transmission across languages ─────────────────────────────
FUEL_MAP = {
    # DE
    "Benzin": "Benzine", "Elektro": "Elektrisch", "Elektro/Benzin": "Elektro/Benzine",
    "Elektro/Diesel": "Elektro/Diesel", "Autogas (LPG)": "LPG", "Erdgas (CNG)": "CNG",
    "Wasserstoff": "Waterstof", "Sonstige": "Overig",
    # BE
    "Elektrisch/Benzine": "Elektro/Benzine", "Elektrisch/Diesel": "Elektro/Diesel",
    "Andere": "Overig",
    # FR
    "Essence": "Benzine", "Électrique": "Elektrisch", "Électrique/Essence": "Elektro/Benzine",
    "Électrique/Diesel": "Elektro/Diesel", "Hydrogène": "Waterstof", "Autres": "Overig",
    # IT
    "Benzina": "Benzine", "Elettrica": "Elektrisch", "Elettrica/Benzina": "Elektro/Benzine",
    "Elettrica/Diesel": "Elektro/Diesel", "Idrogeno": "Waterstof", "Altro": "Overig",
    # ES
    "Gasolina": "Benzine", "Eléctrico": "Elektrisch", "Eléctrico/Gasolina": "Elektro/Benzine",
    "Eléctrico/Diésel": "Elektro/Diesel", "Hidrógeno": "Waterstof", "Otros": "Overig",
}

TRANSMISSION_MAP = {
    # DE
    "Automatik": "Automatisch", "Schaltgetriebe": "Handgeschakeld", "Halbautomatik": "Half/Semi-automaat",
    # BE
    "Manueel": "Handgeschakeld", "Halfautomaat": "Half/Semi-automaat",
    # FR
    "Automatique": "Automatisch", "Manuelle": "Handgeschakeld", "Semi-automatique": "Half/Semi-automaat",
    # IT
    "Automatico": "Automatisch", "Manuale": "Handgeschakeld", "Semiautomatico": "Half/Semi-automaat",
    # ES
    "Automático": "Automatisch", "Manual": "Handgeschakeld", "Semiautomático": "Half/Semi-automaat",
}

def normalize_fuel(raw): return FUEL_MAP.get(raw, raw)
def normalize_transmission(raw): return TRANSMISSION_MAP.get(raw, raw)



def scrape_page(make: str, page: int, country: str = "NL",
                year_from: int = None, year_to: int = None):
    cfg = get_country_config(country)
    prefix = cfg.get("search_prefix", "")
    url = f"https://{cfg['domain']}{prefix}/lst/{make}"
    params = {**PARAMS, "page": page}
    if cfg.get("cy"):
        params["cy"] = cfg["cy"]
    if year_from:
        params["fregfrom"] = year_from
    if year_to:
        params["fregto"] = year_to
    r = requests.get(url, headers=HEADERS, params=params)
    soup = BeautifulSoup(r.text, "html.parser")

    # AutoScout24 puts listing data in a __NEXT_DATA__ JSON blob
    script = soup.find("script", {"id": "__NEXT_DATA__"})
    if not script:
        print(f"No data on page {page}")
        return []

    data = json.loads(script.string)

    # Stop early if we've gone past the last page (AutoScout24 wraps back to
    # page 1 instead of returning empty, so we must check explicitly).
    total_pages = data.get("props", {}).get("pageProps", {}).get("numberOfPages", 0)
    if total_pages and page > total_pages:
        return []

    try:
        listings_raw = data["props"]["pageProps"]["listings"]
    except KeyError:
        print(f"Unexpected structure on page {page}")
        return []

    # Use flexible label matching for power/range across languages
    power_labels = cfg["power_labels"]
    range_labels = cfg["range_labels"]

    results = []
    for item in listings_raw:
        try:
            price = int(item["tracking"]["price"])
            item_make = item["vehicle"]["make"]
            model = item["vehicle"]["model"]
            year = int(item["tracking"]["firstRegistration"].split("-")[-1])
            mileage = int(item["tracking"]["mileage"])
        except (KeyError, TypeError, ValueError):
            continue  # skip if core fields missing

        # Extract IDs from modelTaxonomy e.g. "[make_id:74, variant_id:210, trim_id:621]"
        taxonomy = item.get("tracking", {}).get("modelTaxonomy", "") or ""
        def _tax(key):
            m = re.search(rf"{key}:(\d+)", taxonomy)
            return m.group(1) if m else None

        trim_id       = _tax("trim_id")
        variant_id    = _tax("variant_id")
        generation_id = _tax("generation_id")

        # Extract fields from vehicleDetails list (language-aware)
        power_kw = range_km = None
        for detail in item.get("vehicleDetails", []):
            label = detail.get("ariaLabel", "")
            detail_data = detail.get("data", "") or ""
            # Power: match configured labels, or fallback to "kW" in label/data
            if any(pl in label for pl in power_labels) or "kW" in label or "kW" in detail_data:
                try:
                    power_kw = int(re.search(r"(\d+)\s*kW", detail_data).group(1))
                except (AttributeError, ValueError):
                    pass
            # Range: match any configured label
            elif any(rl in label for rl in range_labels):
                try:
                    range_km = int(re.search(r"(\d[\d.]*)", detail_data).group(1).replace(".", ""))
                except (AttributeError, ValueError):
                    pass

        seller_type = item.get("seller", {}).get("type")
        body_type = item.get("vehicle", {}).get("variant")
        colour = item.get("vehicle", {}).get("colour")

        results.append({
            "id": item["id"],
            "make": item_make,
            "model": model,
            "year": year,
            "mileage": mileage,
            "fuel": normalize_fuel(item.get("vehicle", {}).get("fuel")),
            "transmission": normalize_transmission(item.get("vehicle", {}).get("transmission")),
            "price": price,
            "location": item.get("location", {}).get("city"),
            "power_kw": power_kw,
            "range_km": range_km,
            "trim_id": trim_id,
            "variant_id": variant_id,
            "generation_id": generation_id,
            "body_type": body_type,
            "colour": colour,
            "seller_type": seller_type,
            "country": country,
        })

    return results
