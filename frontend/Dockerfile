FROM python:3.14.4-bookworm

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./

RUN uv sync

COPY . .

EXPOSE 8000

ENTRYPOINT ["uv", "run", "uvicorn"]

CMD ["--app-dir", "src", "--host", "0.0.0.0", "main:app"] 