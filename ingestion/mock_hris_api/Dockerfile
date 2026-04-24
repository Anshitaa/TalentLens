FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.110.1 \
    uvicorn[standard]==0.29.0 \
    pydantic==2.7.0 \
    psycopg2-binary==2.9.9 \
    python-dotenv==1.0.1

COPY . .

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
