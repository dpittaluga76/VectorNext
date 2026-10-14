FROM rust:1.87.0-slim-bookworm@sha256:437507c3e719e4f968033b88d851ffa9f5aceeb2dcc2482cc6cb7647811a55eb
WORKDIR /app
RUN rustup component add rustfmt clippy
COPY Cargo.toml Cargo.lock LICENSE ./
RUN mkdir src && printf 'pub fn dependency_cache() {}\n' > src/lib.rs \
    && cargo fetch --locked
COPY src/ src/
COPY tests/ tests/
COPY evals/fixtures/ evals/fixtures/
COPY processor/fixtures/ processor/fixtures/
COPY examples/ examples/
RUN cargo test --locked --offline --all-targets --no-run
CMD ["cargo", "test", "--locked", "--offline", "--all-targets"]
