FROM python:3.12-slim

# Install system dependencies for BlueZ, DBus, Pillow, and Timezone data
RUN apt-get update && apt-get install -y --no-install-recommends \
    bluez \
    libbluetooth-dev \
    libdbus-1-dev \
    git \
    pkg-config \
    gcc \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install dependencies directly from PyPI
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application source and bundled fonts
COPY src/ /app/src/
COPY data/ /app/data/
COPY data/fonts/ /app/bundled_fonts/
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8080

ENV PYTHONUNBUFFERED=1 \
    TZ=UTC \
    LOG_LEVEL=INFO \
    PORT=8080 \
    HOST=0.0.0.0

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh", "-c", "uvicorn src.pixelweb.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8080} --log-level ${LOG_LEVEL:-info}"]

