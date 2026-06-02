FROM python:3.14.4-bookworm

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./

RUN uv sync 

COPY src ./src
COPY data ./data


EXPOSE 8080

CMD ["uv", "run", "uvicorn", "--app-dir", "src", "--host", "0.0.0.0", "--port", "8080", "main:app"]