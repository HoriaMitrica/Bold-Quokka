FROM python:3.11-slim

WORKDIR /app

# Copy the requirements for this service
COPY ./test-service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the service code
COPY ./test-service ./test-service

CMD ["uvicorn", "test-service.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
