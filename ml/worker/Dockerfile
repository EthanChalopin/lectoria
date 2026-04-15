FROM python:3.10-slim

WORKDIR /app

# Install dependencies.
COPY ml/worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full ML package so absolute imports such as ml.pipelines.* work.
COPY ml ./ml

CMD ["python", "-m", "ml.worker.worker"]
