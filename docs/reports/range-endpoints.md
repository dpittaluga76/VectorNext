# README cleanup and exact range endpoint validation

Implemented before the single-call experiment, 2026-10-15. README narrative/display labels now describe features and benchmarks instead of task IDs. All original link destinations and table rows were preserved, including comparison measurements and limitations.

`src/answers/numeric.rs` recognizes full two-segment unsigned ranges in supplied source text. Exact endpoints support hyphen/en-dash ranges, horizontal-space-delimited `to`, literal decimal precision and English comma grouping. It never computes interior values or durations. Full-source guards reject signed/negative expressions, dates with three segments, identifiers, numeric chains and clipped digits/decimal/grouping fragments. JSON proof contracts and source/quote bytes remain unchanged.

Verification: Docker core build/full suite (163 top-level Rust checks), 32 answer integration tests, both table-driven range unit tests, formatting and Clippy passed. Logs are retained locally in `data/range-*-final.log` and `data/range-integration.log`. The initial run exposed a misplaced test module and an incorrect new assertion about old newline-separated standalone-number behavior; both were corrected before inference. This change adds no newline range recognition and does not redefine existing standalone acceptance across newlines.

The running production image and T29's retained API image intentionally still use the previous validator. Rebuild/activation is a separate operational step; the range implementation must not confound the single-call latency/quality comparison. Existing historical scores remain unchanged. Mechanical endpoint presence does not establish whether the question asks for the start or end.
