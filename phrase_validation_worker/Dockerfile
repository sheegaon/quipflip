FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

EXPOSE 9000

CMD ["uvicorn", "phrase_validation_worker.main:app", "--host", "0.0.0.0", "--port", "9000"]
