import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import MAKES, YEAR_BANDS
from countries import ALL_COUNTRY_CODES
from db import init_db, save, track_price_changes, purge_stale
from scraper import scrape_page
from train import retrain

# AutoScout24 caps at 200 pages per search query. The scraper also breaks
# naturally when a page returns no listings, so this is a hard ceiling.
PAGES_PER_BAND = 200
MAX_WORKERS    = 5    # parallel make-scrapers; be polite to the server


def scrape_make(make: str, country: str = "NL", max_pages: int = PAGES_PER_BAND) -> list[dict]:
    """Scrape all year bands for one make in one country. Returns a flat list of listings."""
    all_listings = []
    for year_from, year_to in YEAR_BANDS:
        band_label = (str(year_from) if year_from == year_to
                      else f"{year_from or '≤'}-{year_to or '≥'}")
        for page in range(1, max_pages + 1):
            listings = scrape_page(make, page, country=country,
                                   year_from=year_from, year_to=year_to)
            if not listings:
                break
            all_listings.extend(listings)
            print(f"  {make} [{country}] [{band_label}] p{page}: {len(listings)} listings")
            time.sleep(1.5)
    return all_listings


def scrape_all(con, countries: list[str] = None, max_pages: int = PAGES_PER_BAND):
    """Scrape all makes for given countries in parallel, save to DB as results come in."""
    if countries is None:
        countries = ["NL"]

    for country in countries:
        print(f"\n{'='*60}")
        print(f"Scraping {country}...")
        print(f"{'='*60}")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(scrape_make, make, country, max_pages): make
                       for make in MAKES}
            for future in as_completed(futures):
                make = futures[future]
                try:
                    listings = future.result()
                    if listings:
                        track_price_changes(con, listings)
                        save(con, listings)
                        print(f"✓ {make} [{country}]: {len(listings)} saved")
                    else:
                        print(f"✗ {make} [{country}]: 0 listings")
                except Exception as exc:
                    print(f"✗ {make} [{country}]: error – {exc}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scrape", action="store_true", help="Scrape and purge only, no retraining")
    parser.add_argument("--train",  action="store_true", help="Retrain only, no scraping")
    parser.add_argument("--pages",  type=int, default=PAGES_PER_BAND, help="Max pages per year band per make")
    parser.add_argument("--countries", nargs="+", default=None,
                        help=f"Country codes to scrape (default: all). Options: {', '.join(ALL_COUNTRY_CODES)}")
    args = parser.parse_args()

    if args.train:
        retrain()
    elif args.scrape:
        con = init_db()
        scrape_all(con, args.countries, args.pages)
        purge_stale(con)
    else:
        con = init_db()
        scrape_all(con, args.countries, args.pages)
        purge_stale(con)
        retrain()
