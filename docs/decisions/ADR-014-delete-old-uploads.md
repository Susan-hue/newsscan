# ADR-014: Delete old uploaded files

- **Status:** Accepted for the two choices in the first table (the owner chose them). **Proposed** for the
  scheduler under "Claude's choice": Claude picked it alone, and it is not a joint decision.
- **Date:** 2026-11-13

## The problem

Every upload stays on disk forever, in the `newsscan_uploads` volume. On a laptop that fills up, and old scans of
other people's papers have no reason to stay.

## Decisions (the owner's)

| Question | Chosen | Other options |
|---|---|---|
| How long is a file kept? | **7 days** | 30 or 90 days |
| What happens to the database row? | **Kept.** Only the file goes. The text and report stay, and the row gets a `file_deleted_at` time | Delete the row too |

## Claude's choice (Proposed)

**Who runs the job: the worker, with Celery's built-in scheduler** (the `--beat` flag). It runs once an hour.

| Option | Good | Bad |
|---|---|---|
| **Worker with `--beat`** (chosen) | No new container. Same code, same volume | The schedule lives inside the worker. Two workers would both run it (harmless, because it can be repeated safely) |
| A separate scheduler container | Clear separation | One more thing to run and watch for a small job |
| A cron job on the laptop | Nothing in Docker | Lives outside the repo, needs the laptop on, easy to forget |

## Safe defaults (Claude's choice)

- **Off by default.** `NEWSSCAN_UPLOAD_RETENTION_DAYS=0` means never delete. Deleting is permanent, so the owner
  turns it on by setting 7, after a dry run.
- Only scans that are `done` or `failed` are touched. A scan still queued or running keeps its file.
- A file that is already gone is not an error. Running twice does no harm.
- Each row is saved right after its file is deleted. If one file fails, the others still go.
- Dry run: `python -m newsscan.cleanup --days 7 --dry-run` only counts.
- Metric: `newsscan_uploads_deleted_total`. It starts at 0.

## What was tested

Unit tests on throwaway files and a throwaway database: old files go, new ones stay, queued and running scans
stay, dry run changes nothing, 0 days means off, the row and its text survive, one failure doesn't stop the rest.
**Not tested:** the schedule firing inside the real worker, and a run on the real volume.

## What this means

After a file is deleted, the original image can't be looked at again, but the report can. Nothing in the app
serves the original file today, so nothing breaks. Backups of the volume would still hold older files.
