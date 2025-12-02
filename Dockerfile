FROM python:3.11

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# install system deps for psycopg2, Pillow and GDAL
RUN apt-get update && \
    apt-get install -y \
    gcc \
    libpq-dev \
    python3-dev \
    musl-dev \
    libjpeg-dev \
    zlib1g-dev \
    gdal-bin \
    libgdal-dev \
    libgeos-dev && \
    rm -rf /var/lib/apt/lists/*

# Optional: expose GDAL include path for pip packages needing it
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# copy project
COPY . .

ENV PORT=8000

# copy entrypoint
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
