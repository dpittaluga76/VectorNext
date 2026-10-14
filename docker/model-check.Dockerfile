FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
WORKDIR /workspace
COPY experiments/t02/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY experiments ./experiments
COPY evals/dataset.json ./evals/dataset.json
COPY evals/fixtures ./evals/fixtures
CMD ["python", "-m", "experiments.t02.benchmark"]
