FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv pip install --system -e .

# Data directory for SQLite volume
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "bastuflotten.app:app", "--host", "0.0.0.0", "--port", "8000"]
