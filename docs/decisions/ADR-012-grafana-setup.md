# ADR-012: How Grafana is set up

- **Status:** Accepted
- **Decided by:** the owner on the three choices below. Claude recommended each one and the owner chose it. The
  Grafana version (12.2.0) and the safety settings are Claude's choices, not joint ones.
- **Date:** 2026-11-12

## Decisions

| Question | Chosen | Other option |
|---|---|---|
| Does Grafana keep its own saved data? | **No.** The data source and dashboard come from files in the repo. Remove the container and you get the same Grafana back. UI changes are lost unless exported. | A small volume, so UI changes survive. But the admin password in `.env` is then only read the first time. |
| How is the dashboard made? | **A small generator script** (`platform/grafana/make_dashboard.py`) writes the dashboard JSON. The owner first built three panels by hand in the UI to learn how they work, then chose the script for all seven. | Export from the UI, Claude writes the JSON, or a bigger tool (Terraform, Grafana SDK) |
| Which panels? | **Core six plus outside calls:** requests per second, errors (5xx) per second, p95 latency, queue length, scans done vs failed, seconds per stage, calls to Groq and Google and their failures | Core six only, or a minimal four |

## Safety settings (Claude's choice)

- Listens on `127.0.0.1:3000` only.
- The admin password comes from `platform/.env` (ignored by Git). There is no default password.
- Sign-up, anonymous access and usage reporting are off.

## What this means

- Files: `platform/grafana/provisioning/` (data source and dashboard loader) and `platform/grafana/dashboards/`
  (exported dashboards).
- A dashboard you build by clicking is **not saved** until you export it into `platform/grafana/dashboards/`.
- Memory, measured 2026-11-12 right after the first start with no dashboard: Grafana used **98 MiB**. The whole
  stack was about 320 MiB, with about 2.5 GiB free on the machine. It will grow with dashboards and open browser
  tabs, so measure again after Step B is finished.

## What we learned (2026-11-12)

- A counter that first appears at value 1 makes `increase()` miss that first event. Fixed in the app: the scan,
  outside-call and stage counters are now created at 0 when the app starts, and a test checks the stage list
  against `pipeline.py`. This was checked in tests and on the running containers (the series exist at 0). It was not
  tested live with a scan and `increase()`.
- The owner decided to leave the three counter panels as running totals "since the worker started". They are easy
  to read and always show something.
- `newsscan_queue_depth` was exposed by both the API and the worker, but only the API fills it. The worker now
  drops it, so only the API reports it. The panel still filters on `job="newsscan-api"`, which is harmless.
