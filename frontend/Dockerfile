FROM python:3.14.4-bookworm

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./

RUN uv sync

COPY src ./src

EXPOSE 8000

CMD ["sh", "-c", "uv run uvicorn main:app --app-dir src --host 0.0.0.0 --port 8000"]