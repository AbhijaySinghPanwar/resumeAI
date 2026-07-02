FROM python:3.11-slim

# Force Python logs to stream immediately
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Cache requirements first
COPY requirements.txt .
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code and install project
COPY . .
RUN pip install .

WORKDIR /app/resumeai_app

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/api/health || exit 1

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
