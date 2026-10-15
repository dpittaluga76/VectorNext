FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /app
RUN pip install --no-cache-dir numpy==2.5.4 'psycopg[binary]==3.2.10' typing_extensions==4.16.0
COPY experiments/t20/ experiments/t20/
ENTRYPOINT ["python", "-m", "experiments.t20.run"]
