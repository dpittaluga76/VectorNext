# Run the internally reviewed pilot

Use the [v1.8 execution amendment](internal-execution-v1.8.md). These commands
are separate from the older independently gated runners. They do not certify
independence, sealed custody, sample adequacy or a strategy promotion.

The successor package and all candidate captures remain in ignored `tmp/`.
The standard library runner executes on the Windows host; Rust diagnostic tools
execute offline in Linux/Docker. Setup uses installed images and model files.
Never point these tools at the normal application database or cache.

1. Build the current API and offline measurement examples. Run the measurement
   unit tests and applicable Rust checks. Save logs, including failed checks.
2. Build the successor with `internal_successor`; verify its frozen manifest.
3. Run `internal_runtime setup --output NEW_PRIVATE_DIRECTORY`, then
   `internal_runtime ingest --package PACKAGE --output PRIVATE_DIRECTORY`.
   This starts only the isolated API/processor. Wait for CPU readiness before
   ingestion. Keep original failures; use the same output to reconcile a stopped
   observer. It does not retry failed jobs.
4. Copy `measurement_evidence` and `measurement_candidate` into the run's `tools/`.
   In an offline Linux container run `internal_runtime inventory --output RUN
   --binary RUN/tools/measurement_evidence`.
5. Run `internal_evaluate prepare-oracles --root RUN --package PACKAGE` before
   reading any model output. Review aggregate availability and retain gaps.
6. Verify the normal app has no unfinished work. Record its current library,
   jobs and image/container identities. Stop only its generator, start the
   isolated generator from the private `compose.json`, and wait for readiness.
   Synthetic operational preflights are separate from measured cases.
7. Commit public source, gold revisions, policies and scorers. Run
   `internal_evaluate freeze --root RUN --package PACKAGE`. Commit a public
   aggregate receipt containing that private freeze's hash, image IDs and counts,
   without candidate identities or content. The runner verifies the source
   commit remains in history and all frozen bytes are unchanged.
8. Run `python -m evals.measurement.internal_execute_all --root RUN`.
   It executes controls, development strategies, original-table ablation,
   frozen development selection, exposed candidates and both models' oracle
   diagnostics. It records resource samples and restores the normal generator
   in `finally`. After an interrupted process, inspect/reconcile the backend
   and reactivate the same isolated containers before resuming. Direct uncertain
   calls are never repeated; durable API requests are polled by their original ID.
9. In an offline Linux container run `internal_oracle_results prepare --root RUN
   --binary RUN/tools/measurement_candidate`. Then run the `score` operations in
   `internal_results` and `internal_oracle_results`, and `internal_attribution`.
   All output files are create-only. Retain complete private raw captures and
   publish aggregate results and public-development changes separately.

The isolated operational answer records are cleared only after their exact
terminal captures and completion record have been fsynced. This prevents the
256 MiB operational quota from confounding a long sequential benchmark; archived
diagnostics remain intact. No normal-app records are cleared. CPU prefix token
counting/embedding calls retain aggregate counts and elapsed time; full request
and response capture is retained for reranking and generation operations. Older
preflight CPU captures remain preserved.

Changing source, inputs or runtime invalidates the freeze. A defect discovered
after measured work requires an explicit successor/amendment and preserves all
prior attempts; never edit a frozen scorer or retry failures into successes.
