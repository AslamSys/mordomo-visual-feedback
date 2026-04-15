FROM python:3.12-slim

WORKDIR /app

# Build deps for rpi-ws281x (C extension) and numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    swig \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

CMD ["python", "-m", "src.main"]
