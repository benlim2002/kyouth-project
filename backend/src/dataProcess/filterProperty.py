import sqlite3
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "data.db"


def get_connection():
    if not DB_PATH.exists():
        logging.error(f"FILTER | ❌ Database not found at {DB_PATH}")
        return None
    return sqlite3.connect(DB_PATH)


def filter_properties(budget: float, state: str, property_type: str) -> list[dict]:
    """
    Filter properties from DB based on budget, state and property type.
    Only returns enriched rows (amenities is not null).
    Returns a list of dicts.
    """
    conn = get_connection()
    if not conn:
        return []

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            township,
            area,
            state,
            tenure,
            type,
            median_price,
            median_psf,
            transactions,
            amenities,
            growth_potential,
            tags,
            summary
        FROM properties
        WHERE LOWER(state) = LOWER(?)
          AND LOWER(type) = LOWER(?)
          AND median_price <= ?
          AND amenities IS NOT NULL
          AND TRIM(amenities) != ''
        ORDER BY median_price ASC
    """, (state, property_type, budget))

    rows = cursor.fetchall()
    conn.close()

    results = [dict(row) for row in rows]
    logging.info(f"FILTER | ✅ Found {len(results)} properties for state={state}, type={property_type}, budget={budget}")
    return results