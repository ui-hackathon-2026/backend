FROM python:3.14-slim

# libgomp1 is required at runtime by lightgbm/shap (OpenMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Migrations run once per deploy via fly.toml's [deploy] release_command,
# not on every machine boot — keeps cold-start from scale-to-zero fast.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
