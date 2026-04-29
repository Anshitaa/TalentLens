FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Use slim production requirements (no PySpark / sentence-transformers / SHAP)
COPY api/requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy entire project (api imports ml/, llm/ as sibling packages)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
