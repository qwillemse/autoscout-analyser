import sqlite3
from config import DB_PATH

STALE_DAYS = 30  # listings not seen in this many days are purged before retraining


NEW_COLUMNS = [
    ("seller_type",   "TEXT"),
    ("trim_id",       "TEXT"),
    ("range_km",      "INTEGER"),
    ("variant_id",    "TEXT"),
    ("generation_id", "TEXT"),
    ("body_type",     "TEXT"),
    ("colour",        "TEXT"),
    ("country",       "TEXT DEFAULT 'NL'"),
]


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            make TEXT,
            model TEXT,
            year INTEGER,
            mileage INTEGER,
            fuel TEXT,
            transmission TEXT,
            price INTEGER,
            location TEXT,
            power_kw INTEGER,
            scraped_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Non-destructive migration: add new columns if they don't exist yet
    for col, typedef in NEW_COLUMNS:
        try:
            con.execute(f"ALTER TABLE listings ADD COLUMN {col} {typedef}")
        except sqlite3.OperationalError:
            pass  # column already exists
    con.commit()
    return con


def _ensure_price_history(con):
    """Create price_history table if it doesn't exist."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            listing_id TEXT,
            price INTEGER,
            scraped_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (listing_id, scraped_at)
        )
    """)
    con.commit()


def track_price_changes(con, listings):
    """Record price changes before upserting new data."""
    _ensure_price_history(con)
    ids = [l["id"] for l in listings]
    if not ids:
        return
    # Fetch current prices for these listings
    placeholders = ",".join("?" * len(ids))
    rows = con.execute(
        f"SELECT id, price FROM listings WHERE id IN ({placeholders})", ids
    ).fetchall()
    old_prices = {row[0]: row[1] for row in rows}

    changes = []
    for l in listings:
        old = old_prices.get(l["id"])
        if old is not None and old != l["price"]:
            # Price changed — record the OLD price (current one will be overwritten)
            changes.append((l["id"], old))
    if changes:
        con.executemany(
            "INSERT OR IGNORE INTO price_history (listing_id, price) VALUES (?, ?)",
            changes,
        )
        con.commit()
        print(f"Tracked {len(changes)} price changes")


def save(con, listings):
    """Insert new listings and update price + scraped_at for existing ones."""
    con.executemany("""
        INSERT INTO listings
            (id, make, model, year, mileage, fuel, transmission, price, location,
             power_kw, seller_type, trim_id, range_km, variant_id, generation_id,
             body_type, colour, country, scraped_at)
        VALUES
            (:id, :make, :model, :year, :mileage, :fuel, :transmission, :price, :location,
             :power_kw, :seller_type, :trim_id, :range_km, :variant_id, :generation_id,
             :body_type, :colour, :country, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            price         = excluded.price,
            mileage       = excluded.mileage,
            seller_type   = excluded.seller_type,
            trim_id       = excluded.trim_id,
            range_km      = excluded.range_km,
            variant_id    = excluded.variant_id,
            generation_id = excluded.generation_id,
            body_type     = excluded.body_type,
            colour        = excluded.colour,
            country       = excluded.country,
            scraped_at    = excluded.scraped_at
    """, listings)
    con.commit()


def purge_stale(con):
    """Remove listings not seen in the last STALE_DAYS days (likely sold)."""
    cur = con.execute(f"""
        DELETE FROM listings
        WHERE scraped_at < datetime('now', '-{STALE_DAYS} days')
    """)
    con.commit()
    print(f"Purged {cur.rowcount} stale listings")
