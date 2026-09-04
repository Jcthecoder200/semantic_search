FROM python:3.11-slim

WORKDIR /app

# Install deps first so Docker caches this layer (only re-runs if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the actual code
COPY search_api ./search_api

# Where the index file will live inside the container.
# We'll mount a volume here so the index survives container restarts.
ENV INDEX_PATH=/data/index.pkl

EXPOSE 9120

CMD ["python", "-m", "search_api.main"]
