import sys
import logging
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

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "frontend" / "src" / "html"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

BACKEND_URL = "http://localhost:8000/search"
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
        summary_lines += f"{i+1}. {prop['township']} ({prop['area']}) — RM{prop['median_price']:,}, Score: {prop['score']}/100\n"

    prompt = f"""You are a Malaysian real estate advisor.
    A user is looking for a {property_type} in {state} with a budget of RM{budget:,.0f}.

    Here are the top recommended properties:
    {summary_lines}

    Write a short 2-3 sentence explanation of why {top['township']} is ranked first, 
    and briefly compare it to the other options. Be specific and helpful.
    Keep it conversational, no bullet points.
    """

    explanation = prompt_model(MODEL, prompt)

    if explanation.startswith("Error") or explanation.startswith("An error"):
        return f"{top['township']} is ranked first as it best matches your budget and location preferences among the available options."

    return explanation


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"backend_url": BACKEND_URL}
    )


@app.get("/result", response_class=HTMLResponse)
async def result(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="result.html",
        context={"request": request, "backend_url": BACKEND_URL}
    )


@app.post("/search")
async def search(body: SearchRequest):
    logging.info(f"SEARCH | budget={body.budget}, state={body.state}, type={body.property_type}")

    properties = filter_properties(
        budget=body.budget,
        state=body.state,
        property_type=body.property_type
    )

    if not properties:
        return JSONResponse(
            status_code=404,
            content={"error": "No properties found matching your criteria."}
        )

    ranked = rank_properties(properties, budget=body.budget, top_n=5)

    # rename tags to perks to match frontend
    for prop in ranked:
        prop["perks"] = prop.pop("tags", "") or ""

    ai_explanation = build_ai_explanation(ranked, body.budget, body.state, body.property_type)

    return {
        "recommendations": ranked,
        "ai_explanation": ai_explanation
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)