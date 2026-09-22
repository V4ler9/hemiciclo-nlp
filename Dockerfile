# Fase 5: imagen local para la API y el dashboard (uv + Python 3.12).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.20 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --extra app --frozen --no-dev

COPY src ./src
COPY app ./app

ENV PATH="/opt/venv/bin:$PATH"
EXPOSE 8000 8501

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
