
import logging
import sqlite3
import importlib.util
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# import filterProperty and rankProperty from dataProcess
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

# TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "frontend" / "src" / "html"
# templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

BACKEND_URL = "http://localhost:8000"
MODEL = "gemini-2.5-flash"

class SearchRequest(BaseModel):
    budget: float
    state: str
    property_type: str


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
        prop["amenities"] = prop.pop("amenities", "") or ""

    ai_explanation = build_ai_explanation(ranked, body.budget, body.state, body.property_type)

    return {
        "recommendations": ranked,
        "ai_explanation": ai_explanation
    }


# @app.get("/", response_class=HTMLResponse)
# async def home(request: Request):
#     return templates.TemplateResponse(
#         request=request,
#         name="home.html",
#         context={"backend_url": BACKEND_URL}
#     )


# @app.get("/result", response_class=HTMLResponse)
# async def result(request: Request):
#     return templates.TemplateResponse(
#         request=request,
#         name="result.html",
#         context={"request": request, "backend_url": BACKEND_URL}
#     )




# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)