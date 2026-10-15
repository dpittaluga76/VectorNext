# T27 operational amendment 02 — internal preflight transport

The second preflight loaded the model successfully but could not reach the requested host port: Docker did not publish the port from the generator's internal-only network. Its bounded readiness wait and restoration are retained as a harness failure, not an inference failure. No benchmark request ran.

Use `docker exec` to issue preflight HTTP requests on container loopback, preserving the internal-only inference network and exact raw response bytes. Remove the unused published generator port. Preflight request durations include exec transport overhead and are hardware/functionality checks, not the model-comparison latency measurement. The scored comparison still times the application HTTP endpoint. Model artifact, placement, context, batch sizes, runtime and scoring remain unchanged. Preserve this attempt and use a fresh preflight name.
