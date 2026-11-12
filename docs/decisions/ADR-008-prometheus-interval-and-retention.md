# ADR-008: How often to scrape, and how long to keep data

- **Status:** Accepted
- **Decided by:** the owner. Claude recommended it and the owner chose it.
- **Date:** 2026-11-12

## Options

| Option | Good | Bad |
|---|---|---|
| **Every 15s, keep 15 days, cap at 1 GB** (chosen) | 15s is Prometheus's default, so most guides match; 15 days is the default too; the cap stops the disk filling up | More history than a lab needs |
| Every 15s, keep 7 days | Less disk | Less history to compare |
| Every 5s, keep 2 days | Graphs react fast while we break things | 3x the data, noisier, unusual in real setups |
| Every 30s, keep 30 days | Half the data, a month of history | Rate windows must be at least 2 minutes; alerts react slower |

## Decision

`scrape_interval: 15s`, keep data for `15d`, and never more than `1GB`.

## Cost

About 300 series (separate metric streams) today.

Measured 2026-11-12, about one minute after the first start, with the app idle: Prometheus used **17.9 MiB**.
My earlier guess of 50 to 150 MiB was too high. This is a floor, because little data had built up. Measure again
after a day and after Steps B to D. Disk use was not measured. The whole stack used about 233 MiB.

## What this means

- In graphs and alerts, use a rate window of at least 1 minute (4 scrapes).
- If the 1 GB cap is reached, the oldest data is deleted first.
