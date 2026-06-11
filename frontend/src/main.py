from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "src" / "html"))

backend_url = os.getenv("BACKEND_URL", "")

@app.get("/")
def landing_page(request: Request):
	
	print(f"Backend URL from environment variable: {backend_url}")
	return templates.TemplateResponse(request=request,
								   name="home.html",
								   context={"backend_url": backend_url})

@app.get("/result.html")
def result_page(request: Request):
	return templates.TemplateResponse(request=request,
								   name="result.html",
								   context={"backend_url": backend_url})