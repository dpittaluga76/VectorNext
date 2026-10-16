FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false \
    HF_HOME=/tmp/huggingface HF_HUB_DISABLE_TELEMETRY=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr=5.5.0-1+b1 tesseract-ocr-eng=1:4.1.0-2 tesseract-ocr-osd=1:4.1.0-2 \
    libtesseract5=5.5.0-1+b1 poppler-utils=25.03.0-5+deb13u4 \
    libglib2.0-0t64=2.84.4-3~deb13u5 libgl1=1.7.0-1+b2 \
    && rm -rf /var/lib/apt/lists/*
COPY processor/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r /tmp/requirements.lock
COPY model_assets/requirements.txt /tmp/model-requirements.txt
RUN python -m venv /opt/model-env && /opt/model-env/bin/pip install --no-cache-dir -r /tmp/model-requirements.txt
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=/app
COPY processor/ processor/
COPY model_worker/ model_worker/
COPY model_assets/ model_assets/
COPY experiments/t31/models.bge.lock.json experiments/t31/
COPY experiments/t32/models.lock.json experiments/t32/
COPY deployment/ deployment/
CMD ["python", "-m", "deployment.processor_server"]
