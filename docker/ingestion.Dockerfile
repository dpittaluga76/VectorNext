FROM rust:1.87.0-slim-bookworm@sha256:437507c3e719e4f968033b88d851ffa9f5aceeb2dcc2482cc6cb7647811a55eb AS core
WORKDIR /app
COPY Cargo.toml Cargo.lock LICENSE ./
RUN mkdir src && printf 'pub fn dependency_cache() {}\n' > src/lib.rs && cargo fetch --locked
COPY src/ src/
COPY examples/ examples/
RUN cargo build --release --locked --offline --example model_ingest --example ask

FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
WORKDIR /workspace
COPY experiments/t02/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY --from=core /app/target/release/examples/model_ingest /usr/local/bin/model_ingest
COPY --from=core /app/target/release/examples/ask /usr/local/bin/ask
COPY experiments/t02/encoders.py experiments/t02/fetch_models.py experiments/t02/models.lock.json experiments/t02/models.26b.lock.json experiments/t02/
COPY model_worker/ model_worker/
COPY evals/fixtures/ evals/fixtures/
COPY tests/fixtures/pdf/ tests/fixtures/pdf/
COPY tests/fixtures/answers/ tests/fixtures/answers/
ENTRYPOINT ["model_ingest"]
