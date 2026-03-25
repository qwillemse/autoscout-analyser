import json
import re

from bs4 import BeautifulSoup
import requests

from config import BASE_URL, PARAMS, HEADERS



def scrape_page(make: str, page: int, year_from: int = None, year_to: int = None):
    url = BASE_URL.format(make=make)
    params = {**PARAMS, "page": page}
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
        variant_id    = _tax("variant_id")    # body-type variant within a model line
        generation_id = _tax("generation_id") # model generation (e.g. Golf Mk7 vs Mk8)

        # Extract fields from vehicleDetails list
        power_kw = range_km = None
        for detail in item.get("vehicleDetails", []):
            label = detail.get("ariaLabel", "")
            data  = detail.get("data", "") or ""
            if label == "Vermogen kW (PK)":
                try:
                    power_kw = int(data.split(" kW")[0])
                except (ValueError, IndexError):
                    pass
            elif label == "actieradius":
                try:
                    range_km = int(data.split(" km")[0])
                except (ValueError, IndexError):
                    pass

        # Seller type: "private" or "dealer" / "professional"
        seller_type = item.get("seller", {}).get("type")

        # Body type: "Limousine", "Combi", "SUV/Crossover", "Hatchback", etc.
        body_type = item.get("vehicle", {}).get("variant")

        # Colour: "Wit", "Zwart", "Grijs", "Zilver", "Blauw", "Rood", etc.
        colour = item.get("vehicle", {}).get("colour")

        results.append({
            "id": item["id"],
            "make": item_make,
            "model": model,
            "year": year,
            "mileage": mileage,
            "fuel": item.get("vehicle", {}).get("fuel"),
            "transmission": item.get("vehicle", {}).get("transmission"),
            "price": price,
            "location": item.get("location", {}).get("city"),
            "power_kw": power_kw,
            "range_km": range_km,
            "trim_id": trim_id,
            "variant_id": variant_id,
            "generation_id": generation_id,
            "body_type": body_type,
            "colour":    colour,
            "seller_type": seller_type,
        })

    return results