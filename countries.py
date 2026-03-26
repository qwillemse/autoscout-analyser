# Per-country configuration for AutoScout24 scraping and extension.
# All countries use the same site structure (Next.js, /_next/data/ SPA nav)
# but differ in TLD, URL paths, and localized labels.

COUNTRIES = {
    "NL": {
        "domain": "www.autoscout24.nl",
        "cy": "NL",
        "search_prefix": "",  # no language prefix needed
        "detail_paths": ["/aanbod/*", "/auto/*"],
        "power_labels": ["Vermogen kW (PK)"],
        "range_labels": ["actieradius"],
        "equipment_heading": ["Opties"],
        "owner_keywords": ["eigenaar", "owner"],
        "locale": "nl-NL",
        "lang": "Dutch",
        "inspection_name": "APK",
    },
    "BE": {
        "domain": "www.autoscout24.be",
        "cy": None,  # .be domain already filters; cy param causes 0 results
        "search_prefix": "/nl",  # Belgium needs language prefix
        "detail_paths": ["/nl/aanbod/*", "/fr/annonce/*", "/nl/auto/*", "/fr/auto/*",
                         "/aanbod/*", "/annonce/*", "/auto/*"],
        "power_labels": ["Vermogen kW (PK)", "Puissance kW (CH)"],
        "range_labels": ["actieradius", "autonomie"],
        "equipment_heading": ["Opties", "Options", "Équipement"],
        "owner_keywords": ["eigenaar", "propriétaire", "owner"],
        "locale": "nl-BE",
        "lang": "Dutch/French",
        "inspection_name": "contrôle technique",
    },
    "DE": {
        "domain": "www.autoscout24.de",
        "cy": "D",
        "search_prefix": "",
        "detail_paths": ["/angebot/*"],
        "power_labels": ["Leistung"],
        "range_labels": ["Reichweite"],
        "equipment_heading": ["Ausstattung"],
        "owner_keywords": ["Vorbesitzer", "Halter", "Fahrzeughalter"],
        "locale": "de-DE",
        "lang": "German",
        "inspection_name": "TÜV/HU",
    },
    "AT": {
        "domain": "www.autoscout24.at",
        "cy": "A",
        "search_prefix": "",
        "detail_paths": ["/angebot/*"],
        "power_labels": ["Leistung"],
        "range_labels": ["Reichweite"],
        "equipment_heading": ["Ausstattung"],
        "owner_keywords": ["Vorbesitzer", "Halter"],
        "locale": "de-AT",
        "lang": "German",
        "inspection_name": "§57a (Pickerl)",
    },
    "FR": {
        "domain": "www.autoscout24.fr",
        "cy": "F",
        "search_prefix": "",
        "detail_paths": ["/annonce/*", "/auto/*"],
        "power_labels": ["Puissance kW (CH)"],
        "range_labels": ["autonomie"],
        "equipment_heading": ["Équipement", "Options"],
        "owner_keywords": ["propriétaire"],
        "locale": "fr-FR",
        "lang": "French",
        "inspection_name": "contrôle technique",
    },
    "IT": {
        "domain": "www.autoscout24.it",
        "cy": "I",
        "search_prefix": "",
        "detail_paths": ["/annuncio/*", "/auto/*"],
        "power_labels": ["Potenza kW (CV)"],
        "range_labels": ["autonomia"],
        "equipment_heading": ["Dotazione", "Optional"],
        "owner_keywords": ["proprietario"],
        "locale": "it-IT",
        "lang": "Italian",
        "inspection_name": "revisione",
    },
    "ES": {
        "domain": "www.autoscout24.es",
        "cy": "E",
        "search_prefix": "",
        "detail_paths": ["/anuncio/*", "/auto/*"],
        "power_labels": ["Potencia kW (CV)"],
        "range_labels": ["autonomía"],
        "equipment_heading": ["Equipamiento", "Opciones"],
        "owner_keywords": ["propietario"],
        "locale": "es-ES",
        "lang": "Spanish",
        "inspection_name": "ITV",
    },
    "LU": {
        "domain": "www.autoscout24.lu",
        "cy": "L",
        "search_prefix": "",
        "detail_paths": ["/annonce/*", "/auto/*"],
        "power_labels": ["Puissance kW (CH)", "Leistung"],
        "range_labels": ["autonomie", "Reichweite"],
        "equipment_heading": ["Équipement", "Options", "Ausstattung"],
        "owner_keywords": ["propriétaire", "Vorbesitzer"],
        "locale": "fr-LU",
        "lang": "French/German",
        "inspection_name": "contrôle technique",
    },
}

# All country codes
ALL_COUNTRY_CODES = list(COUNTRIES.keys())

# All domains for extension manifest
ALL_DOMAINS = [c["domain"] for c in COUNTRIES.values()]

def get_country_config(country_code: str) -> dict:
    """Get config for a country code (case-insensitive)."""
    return COUNTRIES[country_code.upper()]

def country_from_domain(domain: str) -> str:
    """Map a domain like 'www.autoscout24.de' to country code 'DE'."""
    for code, cfg in COUNTRIES.items():
        if cfg["domain"] == domain:
            return code
    return "NL"  # fallback
