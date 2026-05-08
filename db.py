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
    # Lifecycle tracking for the resell dashboard. first_seen is set on initial
    # INSERT and never updated; last_seen refreshes on every upsert.
    ("first_seen",    "TEXT"),
    ("last_seen",     "TEXT"),
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
    # Backfill first_seen/last_seen from scraped_at for rows added before the
    # lifecycle columns existed. Idempotent; only fills NULLs.
    con.execute("UPDATE listings SET first_seen = scraped_at WHERE first_seen IS NULL")
    con.execute("UPDATE listings SET last_seen  = scraped_at WHERE last_seen  IS NULL")
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
    """Insert new listings and update price + last_seen for existing ones."""
    con.executemany("""
        INSERT INTO listings
            (id, make, model, year, mileage, fuel, transmission, price, location,
             power_kw, seller_type, trim_id, range_km, variant_id, generation_id,
             body_type, colour, country, scraped_at, first_seen, last_seen)
        VALUES
            (:id, :make, :model, :year, :mileage, :fuel, :transmission, :price, :location,
             :power_kw, :seller_type, :trim_id, :range_km, :variant_id, :generation_id,
             :body_type, :colour, :country, datetime('now'), datetime('now'), datetime('now'))
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
            scraped_at    = excluded.scraped_at,
            last_seen     = excluded.last_seen
    """, listings)
    con.commit()


def purge_stale_legacy(con):
    """DEPRECATED: kept for back-compat but no longer called from main.py.

    The resell dashboard relies on first_seen / last_seen to track listing
    lifecycles, so we no longer delete stale rows. Disk cost is trivial (~140MB
    for 676k listings) and growth is bounded by the live AutoScout market.
    """
    cur = con.execute(f"""
        DELETE FROM listings
        WHERE scraped_at < datetime('now', '-{STALE_DAYS} days')
    """)
    con.commit()
    print(f"Purged {cur.rowcount} stale listings")
