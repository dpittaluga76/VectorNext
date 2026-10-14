FROM rust:1.87.0-slim-bookworm@sha256:437507c3e719e4f968033b88d851ffa9f5aceeb2dcc2482cc6cb7647811a55eb AS build
WORKDIR /app
COPY Cargo.toml Cargo.lock LICENSE ./
RUN mkdir src && printf 'pub fn dependency_cache() {}\n' > src/lib.rs && cargo fetch --locked
COPY src/ src/
RUN cargo build --release --locked --offline --bin vectornext
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=build /app/target/release/vectornext /usr/local/bin/vectornext
COPY deployment/ deployment/
COPY evals/fixtures/ evals/fixtures/
COPY tests/fixtures/answers/ tests/fixtures/answers/
ENTRYPOINT ["vectornext"]
CMD ["serve"]
