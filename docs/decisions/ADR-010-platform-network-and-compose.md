# ADR-010: How the monitoring stack reaches the app

- **Status:** Accepted
- **Decided by:** the owner. Claude recommended it and the owner chose it.
- **Date:** 2026-11-12

## Options

| Option | Good | Bad |
|---|---|---|
| **A separate compose file that joins the app's network** (chosen) | App and monitoring start, stop and rebuild separately; restarting monitoring never touches the app's database | Start the app first, or the network doesn't exist |
| Combine both with `-f a -f b` | One command | They start and stop together; one `down -v` would hit the app's data too |
| Put everything in the main compose file | Simplest | Monitoring stops being a separate part, and the app file grows |

## Decision

`platform/docker-compose.yml` is its own project. It joins the network `newsscan_default`, which the app's compose
file creates, so Prometheus can reach `api:8000` and `worker:9101` by name.

## What this means

- Start the app first, then the monitoring stack.
- The monitoring stack never deletes that network, and nothing is deleted without the owner's approval.
- The network name (`newsscan_default`) is fixed by `name: newsscan` in `app/docker-compose.yml`, so moving or renaming the folder doesn't change it. Don't remove that line.
