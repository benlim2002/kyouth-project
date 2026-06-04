import sqlite3
import json
import logging
import time
import importlib.util
from pathlib import Path
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)


_prompt_model_path = Path(__file__).resolve().parent.parent / "week_2" / "prompt_model.py"
_spec = importlib.util.spec_from_file_location("prompt_model", _prompt_model_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
prompt_model = _module.prompt_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

BASE_DIR = Path(__file__).resolve().parents[2]  # kyouth-project/
DB_PATH = BASE_DIR / "data" / "data.db"

MODEL = "gemini-3.1-flash-lite"
BATCH_SIZE = 5  # rows per API call


def fetch_unenriched(conn, limit=None):
    cursor = conn.cursor()
    query = """
        SELECT id, township, area, state, tenure, type, median_price, median_psf, transactions
        FROM properties
        WHERE amenities IS NULL OR tags IS NULL OR summary IS NULL OR growth_potential IS NULL
    """
    if limit:
        query += f" LIMIT {limit}"
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def build_batch_prompt(rows: list) -> str:
    rows_text = ""
    for i, row in enumerate(rows):
        rows_text += f"""
    Row {i + 1}:
    Township: {row['township']}, Area: {row['area']}, State: {row['state']}
    Tenure: {row['tenure']}, Type: {row['type']}
    Median Price: RM{row['median_price']}, Median PSF: RM{row['median_psf']}
    Transactions: {row['transactions']}
    """

    return f"""You are a Malaysian real estate analyst with access to Google Search.
    Search for EACH township individually and return accurate, specific information.

    IMPORTANT:
    - Each row MUST have DIFFERENT amenities based on its actual location
    - Do NOT copy the same amenities across rows


    {rows_text}

    Return a JSON array with exactly {len(rows)} objects in the same order. Each object must have these keys:
    - "amenities": string — specific amenities for THAT township only (schools, malls, hospitals, MRT/LRT)
    - "growth_potential": string — exactly one of: "LOW", "MED", "HIGH"
    - "tags": string — comma-separated traits specific to THAT township
    - "summary": string — 2 sentence overview specific to THAT township

    Return only the JSON array, no markdown, no explanation.
    """


def update_row(conn, row_id, amenities, growth_potential, tags, summary):
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE properties
        SET amenities = ?, growth_potential = ?, tags = ?, summary = ?
        WHERE id = ?
    """, (amenities, growth_potential, tags, summary, row_id))
    conn.commit()


def parse_response(response_text: str):
    try:
        clean = response_text.strip()
        logging.debug(f"ENRICH | Raw response: {clean[:200]}")  # add this
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()
        import re
        clean = re.sub(r",\s*([\]}])", r"\1", clean)
        return json.loads(clean)
    except Exception as e:
        logging.error(f"ENRICH | ❌ Failed to parse response: {e}")
        logging.info(f"ENRICH | Raw response was: {response_text[:300]}")  # and this
        return None


def enrich(dry_run=False):
    if not DB_PATH.exists():
        logging.error(f"ENRICH | ❌ Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    rows = fetch_unenriched(conn)

    if not rows:
        logging.info("ENRICH | ✅ All rows already enriched, nothing to do")
        conn.close()
        return
    
    logging.info(f"ENRICH | 🔍 Found {len(rows)} unenriched rows")
    logging.info(f"ENRICH | 📦 Batch size: {BATCH_SIZE} → ~{-(-len(rows) // BATCH_SIZE)} API calls")

    updated = 0
    failed = 0

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start: batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1

        logging.info(f"ENRICH | 📤 Sending batch {batch_num} ({len(batch)} rows)")

        prompt = build_batch_prompt(batch)

        if dry_run:
            logging.info("ENRICH | 🧪 Dry run — skipping API call")
            logging.info("ENRICH | Prompt preview:\n{prompt[:300]}...")
            continue

        MAX_RETRIES = 3
        response_text = None

        for attempt in range(MAX_RETRIES):
            logging.info(f"ENRICH | 🔄 Attempt {attempt + 1} for batch {batch_num}")
            response_text = prompt_model(MODEL, prompt)
            if not response_text.startswith("An error occurred"):
                break
            logging.warning(f"ENRICH | ⏳ Retry {attempt + 1}/{MAX_RETRIES} for batch {batch_num}")
            time.sleep(10 * (attempt + 1))

        if response_text.startswith("Error") or response_text.startswith("An error"):
            logging.error(f"ENRICH | ❌ All retries failed for batch {batch_num}, skipping")
            failed += len(batch)
            continue

        parsed = parse_response(response_text)

        if not parsed or len(parsed) != len(batch):
            logging.error(f"ENRICH | ❌ Unexpected response length on batch {batch_num}, skipping")
            failed += len(batch)
            continue

        # reject if model copy-pasted same amenities across rows
        amenities_list = [r.get("amenities") for r in parsed]
        if len(set(amenities_list)) == 1 and len(parsed) > 1:
            logging.warning(f"ENRICH | 🔁 Detected duplicate amenities in batch {batch_num}, retrying...")
            time.sleep(5)
            continue

        for row, result in zip(batch, parsed):
            try:
                update_row(
                    conn,
                    row_id=row["id"],
                    amenities=result.get("amenities"),
                    growth_potential=result.get("growth_potential"),
                    tags=result.get("tags"),
                    summary=result.get("summary"),
                )
                logging.info(f"ENRICH | ✅ Updated: {row['township']}, {row['area']}")
                updated += 1
            except Exception as e:
                logging.error(f"ENRICH | ❌ Failed to update row {row['id']}: {e}")
                failed += 1

        if batch_start + BATCH_SIZE < len(rows):
            time.sleep(5)

    conn.close()
    logging.info(f"ENRICH | 🏁 Done — Updated: {updated} | Failed: {failed}")


if __name__ == "__main__":
    enrich(dry_run=False)