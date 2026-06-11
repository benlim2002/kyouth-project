
import logging
import sqlite3
import importlib.util
import requests
import os
from pathlib import Path
from typing import Optional
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
    allow_origins=["http://localhost:8000", "https://propguide-kyouth.up.railway.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "data" / "img")), name="static")

MODEL = "gemini-3.1-flash-lite"

class SearchRequest(BaseModel):
    budget: float
    state: str
    property_type: str
    priority: Optional[str] = None

class AskRequest(BaseModel):
    query: str


def build_ai_explanation(ranked: list[dict], budget: float, state: str, property_type: str, priority: str) -> str:
    if not ranked:
        return "No matching properties were found for your criteria."

    top = ranked[0]
    summary_lines = ""
    for i, prop in enumerate(ranked):
        summary_lines += f"{i+1}. {prop['township']} ({prop['area']}) — RM{prop['median_price']:,}, Score: {prop['score']}/100, Amenities: {prop['amenities']}\n"

    prompt = f"""You are a Malaysian real estate advisor.
    A user is looking for a {property_type} in {state} with a budget of RM{budget:,.0f}, and has selected '{priority}' as their priority.

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
    logging.info(f"SEARCH | budget={body.budget}, state={body.state}, type={body.property_type}, priority={body.priority}")
    
    properties = filter_properties(
        budget=body.budget,
        state=body.state,
        property_type=body.property_type,
    )

    if not properties:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT township, area, state, type, tenure,
                   median_price, median_psf, transactions,
                   growth_potential, tags, amenities
            FROM properties
            WHERE LOWER(state) = LOWER(?) AND LOWER(type) = LOWER(?)
            AND median_price IS NOT NULL
            ORDER BY ABS(median_price - ?) ASC
            LIMIT 4
        """, (body.state, body.property_type, body.budget))
        closest = [dict(row) for row in cursor.fetchall()]
        conn.close()
        for prop in closest:
            prop["township"] = prop["township"].title()
            prop["amenities"] = prop["amenities"].title()
            prop["perks"] = prop.pop("tags", "") or ""

        closest_summary = "\n".join([
            f"{p['township']} ({p['area']}) — RM{p['median_price']:,}"
            for p in closest
        ])
        prompt = f"""You are a Malaysian real estate advisor.
        A user is looking for a {body.property_type} in {body.state} with a budget of RM{body.budget:,.0f}.
        No properties were found within their budget. Here are the closest options above budget:
        {closest_summary}
        
        Write 1-2 friendly sentences acknowledging they're over budget, but suggest these could still be worth considering. Be concise and encouraging.
        """
        ai_explanation = prompt_model(MODEL, prompt)

        return {
            "recommendations": [],
            "closest_matches": closest,
            "ai_explanation": ai_explanation  # replaces the hardcoded string
        }

    ranked = rank_properties(properties, budget=body.budget, priority=body.priority, top_n=15)

    # pad with over-budget properties if fewer than 5
    if len(ranked) < 5:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        existing_townships = [p["township"] for p in ranked]
        placeholders = ",".join("?" * len(existing_townships))

        cursor.execute(f"""
            SELECT township, area, state, type, tenure,
                   median_price, median_psf, transactions,
                   growth_potential, tags, amenities
            FROM properties
            WHERE LOWER(state) = LOWER(?)
            AND LOWER(type) = LOWER(?)
            AND median_price > ?
            AND township NOT IN ({placeholders})
            ORDER BY median_price ASC
            LIMIT ?
        """, (body.state, body.property_type, body.budget,
              *existing_townships, 5 - len(ranked)))

        extras = [dict(row) for row in cursor.fetchall()]
        conn.close()

        for prop in extras:
            prop["township"] = prop["township"].title()
            prop["amenities"] = prop["amenities"].title()
            prop["perks"] = prop.pop("tags", "") or ""
            prop["score"] = None  # marks as over-budget

        ranked.extend(extras)

    for prop in ranked:
        prop["township"] = prop["township"].title()
        prop["amenities"] = prop["amenities"].title()
        prop["perks"] = prop.pop("tags", "") or ""

    ai_explanation = build_ai_explanation(ranked, body.budget, body.state, body.property_type, body.priority)

    return {
        "recommendations": ranked,
        "closest_matches": [],
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


@app.get("/property-types")
def get_property_types(state: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT type FROM properties
        WHERE LOWER(state) = LOWER(?)
        AND type IS NOT NULL
    """, (state,))
    
    raw_types = [row["type"] for row in cursor.fetchall()]
    conn.close()

    # split combined types and deduplicate
    split_types = set()
    for t in raw_types:
        for part in t.split(","):
            split_types.add(part.strip())

    valid_types = {"Flat", "Apartment", "Condominium", "Terrace House", 
                   "Cluster House", "Semi D", "Bungalow", "Town House"}
    
    result = sorted(split_types & valid_types)
    return {"property_types": result}

@app.post("/search-all")
async def search_all(body: SearchRequest):
    properties = filter_properties(
        budget=body.budget,
        state=body.state,
        property_type=body.property_type
    )
    for prop in properties:
        prop["township"] = prop["township"].title()
        prop["amenities"] = prop["amenities"].title()
        prop["perks"] = prop.pop("tags", "") or ""
    return {"properties": properties}