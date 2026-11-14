FROM python:3.12-slim

# Install system dependencies for BlueZ, DBus, and Pillow
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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pypixelcolor source and install it
COPY pypixelcolor/ /app/pypixelcolor/
RUN pip install --no-cache-dir -e /app/pypixelcolor/pypixelcolor-main

# Install FastAPI and Web dependencies
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pillow \
    pydantic \
    jinja2 \
    python-multipart \
    aiofiles \
    requests \
    bleak \
    crccheck \
    dbus-fast

# Copy application source
COPY src/ /app/src/
COPY data/ /app/data/

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "src.pixelweb.main:app", "--host", "0.0.0.0", "--port", "8000"]

