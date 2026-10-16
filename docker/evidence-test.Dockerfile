FROM rust:1.87.0-slim-bookworm@sha256:437507c3e719e4f968033b88d851ffa9f5aceeb2dcc2482cc6cb7647811a55eb AS build
WORKDIR /app
COPY Cargo.toml Cargo.lock LICENSE ./
RUN mkdir src && printf 'pub fn dependency_cache() {}\n' > src/lib.rs && cargo fetch --locked
COPY src/ src/
COPY examples/evidence_retrieval.rs examples/evidence_retrieval.rs
RUN cargo test --locked --offline --example evidence_retrieval && cargo build --release --locked --offline --example evidence_retrieval
FROM vectornext-app-processor:t18
COPY --from=build /app/target/release/examples/evidence_retrieval /usr/local/bin/evidence-retrieval
COPY model_worker/ model_worker/
COPY model_assets/ model_assets/
COPY experiments/t02/encoders.py experiments/t02/fetch_models.py experiments/t02/models.lock.json experiments/t02/models.26b.lock.json experiments/t02/
COPY evals/evidence/score.py evals/evidence/validate.py evals/evidence/test_evidence.py evals/evidence/
ENTRYPOINT ["evidence-retrieval"]
