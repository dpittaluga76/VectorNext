FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY evals/requirements.txt /tmp/evals-requirements.txt
RUN pip install --no-cache-dir -r /tmp/evals-requirements.txt
COPY evals ./evals
CMD ["python", "-m", "evals.validate"]
