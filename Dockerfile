FROM python:3.11-slim

# Force Python logs to stream immediately
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Cache requirements first
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code and install project
COPY . .
RUN pip install -e .

WORKDIR /app/resumeai_app

EXPOSE 8080

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
