FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.110" "uvicorn[standard]>=0.27" "sqlalchemy>=2.0" \
    "pydantic>=2.6" "pydantic-settings>=2.1" "pyjwt>=2.8" \
    "cryptography>=42.0" "numpy>=1.26" "asyncpg>=0.29"

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
