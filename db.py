import sqlite3
from config import *

STALE_DAYS = 30  # listings not seen in this many days are purged before retraining


NEW_COLUMNS = [
    ("seller_type",   "TEXT"),
    ("trim_id",       "TEXT"),
    ("range_km",      "INTEGER"),
    ("variant_id",    "TEXT"),
    ("generation_id", "TEXT"),
    ("body_type",     "TEXT"),
    ("colour",        "TEXT"),
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


def save(con, listings):
    """Insert new listings and update price + scraped_at for existing ones."""
    con.executemany("""
        INSERT INTO listings
            (id, make, model, year, mileage, fuel, transmission, price, location,
             power_kw, seller_type, trim_id, range_km, variant_id, generation_id,
             body_type, colour, scraped_at)
        VALUES
            (:id, :make, :model, :year, :mileage, :fuel, :transmission, :price, :location,
             :power_kw, :seller_type, :trim_id, :range_km, :variant_id, :generation_id,
             :body_type, :colour, datetime('now'))
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
