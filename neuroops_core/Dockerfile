FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make CLI available as neuro-ops command
RUN pip install -e . 2>/dev/null || true

# Create data directory
RUN mkdir -p /data/neuro-ops/projects /data/neuro-ops/models

CMD ["python", "main.py"]