
import logging
import sqlite3
import importlib.util
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_dp = Path(__file__).resolve().parent / "dataProcess"
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "data.db"
filter_module = _load_module("filterProperty", _dp / "filterProperty.py")
rank_module = _load_module("rankProperty", _dp / "rankProperty.py")

filter_properties = filter_module.filter_properties
rank_properties = rank_module.rank_properties

# import prompt_model for AI explanation
_pm_path = Path(__file__).resolve().parent / "week_2" / "prompt_model.py"
_pm_spec = importlib.util.spec_from_file_location("prompt_model", _pm_path)
_pm_mod = importlib.util.module_from_spec(_pm_spec)
_pm_spec.loader.exec_module(_pm_mod)
prompt_model = _pm_mod.prompt_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "data" / "img")), name="static")

MODEL = "gemini-2.5-flash"

class SearchRequest(BaseModel):
    budget: float
    state: str
    property_type: str

class AskRequest(BaseModel):
    query: str


def build_ai_explanation(ranked: list[dict], budget: float, state: str, property_type: str) -> str:
    if not ranked:
        return "No matching properties were found for your criteria."

    top = ranked[0]
    summary_lines = ""
    for i, prop in enumerate(ranked):
        summary_lines += f"{i+1}. {prop['township']} ({prop['area']}) — RM{prop['median_price']:,}, Score: {prop['score']}/100, Amenities: {prop['amenities']}\n"

    prompt = f"""You are a Malaysian real estate advisor.
    A user is looking for a {property_type} in {state} with a budget of RM{budget:,.0f}.

    Here are the top recommended properties:
    {summary_lines}

    Write a short 2-3 sentence explanation of why {top['township']} is ranked first, 
    and briefly compare it to the other options. Be specific and helpful.
    Keep it conversational, no bullet points.
    """

    explanation = prompt_model(MODEL, prompt)
    logging.info(f"AI EXPLANATION | {explanation}")

    if explanation.startswith("Error") or explanation.startswith("An error"):
        return f"{top['township']} is ranked first as it best matches your budget and location preferences among the available options."

    return explanation


@app.get("/stats")
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM properties")
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT ROUND(AVG(median_price), 0) as avg_price FROM properties WHERE median_price IS NOT NULL")
    avg_price = cursor.fetchone()["avg_price"]

    cursor.execute("SELECT ROUND(AVG(median_psf), 0) as avg_psf FROM properties WHERE median_psf IS NOT NULL")
    avg_psf = cursor.fetchone()["avg_psf"]

    cursor.execute("SELECT COUNT(DISTINCT state) as total_states FROM properties")
    total_states = cursor.fetchone()["total_states"]

    conn.close()
    return {
        "total_properties": int(total),
        "avg_price": float(avg_price),
        "avg_psf": float(avg_psf),
        "total_states": int(total_states)
    }


@app.get("/properties")
def get_properties(
    state: str = None,
    property_type: str = None,
    min_price: float = None,
    max_price: float = None,
    limit: int = 50,
    offset: int = 0
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT township, area, state, type, tenure, 
               median_price, median_psf, transactions, 
               growth_potential, tags 
        FROM properties WHERE 1=1
    """
    params = []

    if state:
        query += " AND LOWER(state) = LOWER(?)"
        params.append(state)
    if property_type:
        query += " AND LOWER(type) = LOWER(?)"
        params.append(property_type)
    if min_price:
        query += " AND median_price >= ?"
        params.append(min_price)
    if max_price:
        query += " AND median_price <= ?"
        params.append(max_price)

    query += " ORDER BY transactions DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {"properties": rows, "count": len(rows)}


@app.post("/search")
async def search(body: SearchRequest):
    logging.info(f"SEARCH | budget={body.budget}, state={body.state}, type={body.property_type}")

    properties = filter_properties(
        budget=body.budget,
        state=body.state,
        property_type=body.property_type
    )

    if not properties:
        return {
        "recommendations": [],
        "ai_explanation": "No matching properties found. Try increasing your budget or changing the property type."
    }

    ranked = rank_properties(properties, budget=body.budget, top_n=5)

    # rename tags to perks to match frontend
    for prop in ranked:
        prop["perks"] = prop.pop("tags", "") or ""

    ai_explanation = build_ai_explanation(ranked, body.budget, body.state, body.property_type)

    return {
        "recommendations": ranked,
        "ai_explanation": ai_explanation
    }


@app.get("/chart-data")
def get_chart_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # properties by state
    cursor.execute("""
        SELECT state, COUNT(*) as count
        FROM properties
        WHERE state IS NOT NULL
        GROUP BY state
        ORDER BY count DESC
    """)
    by_state = [{"state": r["state"], "count": r["count"]} for r in cursor.fetchall()]

    # avg median price by property type
    cursor.execute("""
        SELECT type, ROUND(AVG(median_price), 0) as avg_price
        FROM properties
        WHERE type IN ('Flat', 'Apartment', 'Condominium', 'Terrace House', 'Cluster House', 'Semi D', 'Bungalow')
        AND median_price IS NOT NULL
        GROUP BY type
        ORDER BY avg_price DESC
    """)
    by_type = [{"type": r["type"], "avg_price": r["avg_price"]} for r in cursor.fetchall()]

    # growth potential distribution
    cursor.execute("""
        SELECT growth_potential, COUNT(*) as count
        FROM properties
        WHERE growth_potential IS NOT NULL
        GROUP BY growth_potential
    """)
    by_growth = [{"growth": r["growth_potential"], "count": r["count"]} for r in cursor.fetchall()]

    conn.close()

    return {
        "by_state": by_state,
        "by_type": by_type,
        "by_growth": by_growth,
    }

@app.post("/ask")
def ask(body: AskRequest):
    if not body.query.strip():
        return {"answer": "Please ask a question."}
    answer = prompt_model(MODEL, body.query)
    return {"answer": answer}