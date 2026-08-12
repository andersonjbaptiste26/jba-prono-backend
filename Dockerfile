# Example Dockerfile (Debian-slim) - includes libpq runtime & build deps as a robust fallback
# - Installs libpq runtime (libpq5) so psycopg2 C-extension can load libpq.so.5
# - Installs libpq-dev + build-essential so pip can compile extensions if a wheel is not available

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install runtime and build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libpq5 \
       libpq-dev \
       build-essential \
       gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies early to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port and start the app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
