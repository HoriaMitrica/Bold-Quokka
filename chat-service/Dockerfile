FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
# sentence-transformers/torch wheels are large; allow slow PyPI downloads during build
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --default-timeout=600 --retries 10 -r requirements.txt

COPY . .

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${CHAT_SERVICE_PORT:-8006}"]
