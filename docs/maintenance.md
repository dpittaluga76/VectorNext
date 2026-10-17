# Offline compaction and garbage collection

VectorNext can reclaim obsolete journal payloads and unreferenced blobs without changing current documents, source mappings, vectors or retry results. Maintenance is explicit, offline and CPU-only. It does not change retrieval or model behavior.

## Before maintenance

- Build the API/admin image from the current checkout. Compose selects the current application images; building does not restart the running app.
- Stop the API before inspection or compaction. Both commands require its exclusive writer lock. Pause other tools that open this database, and keep it stopped throughout maintenance.
- Keep a verified backup on another destination. Database export includes ingestion history but excludes the sibling answer-job store; preserve that separately if needed. See [backup and restore](development.md#run-the-integrated-local-application).
- Use a Linux Docker volume with room for a separate compacted copy. Maintenance requires same-filesystem hard links and atomic directory exchange; it fails rather than using sequential renames. A database mounted directly as a filesystem root cannot be exchanged; the normal `/storage/db` subdirectory is supported.

For the default database, from PowerShell at the repository root:

```powershell
docker compose -f compose.app.yaml build vectornext
docker compose -f compose.app.yaml stop vectornext
docker compose -f compose.app.yaml run --rm admin storage-plan /storage/db
```

`storage-plan` opens only an existing store, validates it without journal repair, and prints JSON. It creates no database/checkpoint and changes no store contents. A live API, unknown store entries, symlinks, non-files, corrupt blobs/checkpoints or invalid saved jobs stop the operation.

Inspect the report and take a verified backup before applying. Use a new backup/restore destination each time:

```powershell
docker compose -f compose.app.yaml run --rm admin export /storage/db /backups/before-compaction
docker compose -f compose.app.yaml run --rm admin restore /backups/before-compaction /storage/compaction-backup-check
docker compose -f compose.app.yaml run --rm admin compact /storage/db --apply
docker compose -f compose.app.yaml run --rm admin storage-plan /storage/db
docker compose -f compose.app.yaml up -d --no-build --pull never vectornext
```

Each command must succeed before proceeding; do not paste past an error. The export's existing 8 GiB limit is unchanged. If it prevents creating a backup, first make and verify a complete stopped-volume copy using your backup tooling. Do not delete the old journal to work around that limit. The restored verification copy and external backups are deliberately excluded from GC; remove or archive them separately only after verifying they are no longer needed.

If `VECTORNEXT_DATA` uses another path, substitute that path in every command. The launcher does not automatically compact or clear history. Model weights, caches and the processor/generator services are not involved.

## Retention policy: `preserve-history-v1`

| Data | Rule |
| --- | --- |
| Current documents and embedding spaces | Preserve complete state, generation, exact values, source locations, vectors and model identities. |
| Operation receipts | Preserve every operation ID, request digest and original generation indefinitely. Identical retries still return the original receipt; changed reuse fails. |
| Used revision IDs | Preserve all reservations indefinitely, including deleted/replaced revisions. No resurrection by reusing an old revision ID. |
| Ingestion jobs | Copy every saved job byte-for-byte, including completed, failed and unfinished work. Preserve its policies, attempts, diagnostics, draft and receipt. |
| Originals and artifacts | Retain blobs referenced by current documents or any ingestion job, including available PDF preparation artifacts. Conservatively pin matching hash strings in stored data/processing metadata. |
| Unreferenced blobs | Omit from the replacement store only after validating their names/content and the complete retention set. There is no age cutoff. |
| Journal and temporary writes | Replace the recovered committed state with a verified checkpoint and empty journal. Omit recognized uncommitted tails and pending files; reject complete corruption. |
| Answer jobs and browser history | Leave untouched. Answer jobs retain their own quota and explicit clear operation; browser history stays in IndexedDB. |
| Models, caches and backups | Leave untouched, including abandoned maintenance workspaces from previous interruptions. |

Completed ingestion jobs can pin originals for documents removed from the searchable collection. That is intentional: historical job inspection and retries still work. Compaction does not add an API for reopening deleted/replaced revisions. Captured answer/browser evidence retains its existing behavior, including stale revision checks; current evidence is never substituted into historical answers.

**This is not a fixed disk-size guarantee.** Full ingestion history, operation receipts and reserved revisions grow with accepted work. Reclamation removes superseded journal payloads and genuinely unreferenced files. Expiring ingestion history or retry identities would require a separate explicit contract; this release introduces neither.

## Reading the report

- `document_blobs` and `history_only_blobs`: retained blob counts/bytes, split by current document versus other retained references. Shared files are counted once.
- `retained_ingestion_jobs`, `retained_receipts`, `retained_revision_ids`: history preserved without expiry.
- `unreferenced_blobs`, `journal_bytes`, `uncommitted_tail_bytes`, `old_checkpoint_bytes`, `disposable_pending_bytes`: existing file categories. The whole journal is replaced; its current logical state and receipts remain in the new checkpoint.
- `store_bytes_before`, `replacement_bytes`, `estimated_reclaimed_bytes`, `estimated_growth_bytes`: exact logical file-length accounting. Tiny stores can grow because their first checkpoint has overhead.
- `temporary_bytes_required`: replacement file bytes plus a 64 MiB reserve for filesystem overhead. `available_bytes` and `enough_space` report current filesystem availability; later space consumption can still cause a safe failure.
- `actual_reclaimed_bytes`: logical bytes removed from the active store after successful publication and cleanup. It is not a measurement of physical device blocks, Docker virtual-disk shrinkage or space in external backups.
- `leftover_workspaces`: sibling directories matching this database's maintenance prefix, reported without following or deleting them. Their bytes are not included in the active-store savings.

## Publication, interruption and recovery

1. Lock and validate the existing database without modifying its journal, even if it has an uncommitted tail.
2. Create a unique sibling `.vnx-compact-…` directory. Copy retained files with size/SHA-256 checks, write/fsync a version-2 checkpoint of the same state and an empty journal, and reopen the candidate through normal recovery validation.
3. Link the original locked `writer.lock` inode into the candidate and sync its directories. The original lock remains held throughout.
4. Exchange the database and candidate directories using one Linux `renameat2(RENAME_EXCHANGE)`, then sync the parent. The visible path is always a complete old or complete new store, with the same lock inode.
5. Verify the displaced file set again, unlink only its known files, remove its directories and sync the parent. No recursive wildcard deletion is used.

If a command fails, its error identifies whether exchange occurred and the workspace location. A killed process may leave a partial candidate, a complete retired store or partially reclaimed retired files; a failure after final cleanup can leave no workspace. The active database remains reopenable with the original logical state and retry history. On a sync failure, retain both directories if present and validate recovery before deciding which copy to keep. These guarantees assume the Linux filesystem honors its atomicity/fsync contracts; tests do not certify physical power-loss behavior.

Do not automatically resume a failed maintenance attempt or treat every hidden directory as disposable. `storage-plan` reports matching leftovers. Keep the API stopped, validate the active store, preserve a verified backup, and inspect the specifically reported workspace before explicitly removing it with your filesystem tools. Unknown/corrupt contents require investigation; no automated leftover-deletion command is provided in this release.

The marker remains `VNXSTORE1`, and compacted checkpoints use the already-supported version 2. Current and pre-compaction version-2 readers can reopen the result. Older binaries that predate version-2 checkpoints still require an untouched compatible backup. See [storage contracts](storage.md) and [architecture](architecture.md).
