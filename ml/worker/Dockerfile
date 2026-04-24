FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/tmp/huggingface
ENV TRANSFORMERS_CACHE=/tmp/huggingface
ENV HUGGINGFACE_HUB_CACHE=/tmp/huggingface

# Install dependencies.
COPY ml/worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full ML package so absolute imports such as ml.pipelines.* work.
COPY ml ./ml

CMD ["python", "-m", "ml.worker.worker"]
