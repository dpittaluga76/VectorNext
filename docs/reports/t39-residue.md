# Removed-document residue audit

The isolated CPU audit confirms that **removal leaves original bytes on disk, including after compaction**, under `preserve-history-v1`. This preserves historical ingestion and stable retries. It is not data erasure. [Exact inventories and checks](t39-residue.json) · [Retention rules](../maintenance.md).

The fixture ingests one synthetic TXT document, replaces it with different bytes, removes it, adds one deliberately unreferenced blob, then inspects and compacts the offline store. It uses the real ingestion state machine with `TestEncoder`; no model, user document or existing library is involved.

| Observation | Before compaction | After compaction |
| --- | ---: | ---: |
| Searchable documents | 0 | 0 |
| Historical originals | 2 | 2 |
| Ingestion jobs | 2 | 2 |
| Retry receipts | 3 | 3 |
| Reserved revisions | 2 | 2 |
| Unreferenced control blobs | 1 | 0 |
| Journal bytes | 5,959 | 0 |
| Active store logical bytes | 12,680 | 8,131 |

Compaction reclaimed 4,549 logical bytes. The versioned JSON lists every relative file path, size and SHA-256 after ingest, replacement, removal and compaction. Receipt/revision state moves into the checkpoint; it is not discarded with journal payloads. Both original byte streams and saved jobs compare equal after reopening. Identical ingestion/publication/removal retries return their original records/receipts without resurrecting the removed document; conflicting identifiers and a new operation attempting to reuse an old revision fail.

Answer-job diagnostics, browser IndexedDB, caches and external backups are separate retention domains and were not created, inspected or erased by this fixture. Existing contracts retain captured evidence there independently. This audit makes no claim about physical disk-block recovery, deleted-file forensics, PDF artifact behavior or erasure from backups; PDF retention already has separate compaction tests.

Reproduce with the current source in the offline core image:

```powershell
docker compose run --rm core cargo test --locked --offline --test measurement_residue -- --nocapture
```

Set `VECTORNEXT_RESIDUE_REPORT` inside the container to an unused writable path to retain a JSON inventory; the output refuses overwrite. The test's database is a temporary Linux directory. The first test compile corrected a report-field type (`retained_ingestion_jobs.files`); the subsequent audit passed. No production code or retention rule changed.
