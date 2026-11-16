# ADR-016: Metrics from the computer and from each container

- **Status:** Accepted for the first choice (the owner picked it). **Proposed** for the details (versions, which
  folders are mounted), which Claude chose. cAdvisor is **parked, not working**.
- **Date:** 2026-11-16

## The problem

The dashboard knew about the app but nothing about the computer under it. "Scans are slow" had no way to
become "because the disk is full or memory ran out".

## Decision (the owner's)

Use both Node Exporter (the computer) and cAdvisor (each container), with read-only access. The other options
were Node Exporter alone, and Docker's own metrics endpoint.

## What happened

- **Node Exporter v1.9.1 works.** CPU, memory, disk and more. Three panels were added: CPU in use, memory in
  use, disk space used.
- **cAdvisor does not work on this computer.** Docker 29.8 keeps containers in a newer way (the containerd
  image store). cAdvisor v0.52.1 and v0.53.0 both fail with "failed to identify the read-write layer ID", so they
  only report the whole machine and no individual container. Running it on raw cgroups also gave no
  per-container data.
- So cAdvisor is **parked**: it stays in `docker-compose.yml` behind a profile (`container-metrics`), is not
  started by default, and has no Prometheus job. The container was stopped, not deleted.

Ways to get per-container numbers later (none chosen, all cost something):

| Option | Cost |
|---|---|
| Switch Docker back to its classic image storage | Changes your Docker setup for every project; images get re-pulled |
| Wait for a cAdvisor release that supports it | Unknown time |
| Write a small exporter that reads the Docker API | Code to write and keep |

## Safe defaults (Claude's choice)

- No port is published. Only Prometheus reaches Node Exporter, over the Docker network.
- Node Exporter runs as `nobody` with all capabilities dropped, and sees the computer through a read-only mount
  of `/`. Tested: writing to it fails with "Read-only file system".
- It stays on the app network, not the computer's own network. That would publish a port on every address,
  which breaks the localhost-only rule. The cost: **network card numbers are the container's, not the
  computer's**, so don't read them as the machine's traffic.
- Mount points like `/dev`, `/proc`, `/sys` and Docker's own folders are left out of the disk numbers.

## What was tested

Node Exporter is scraped and all three panels' queries return data. Not tested: what happens when the disk gets
close to full, and a day of data.

## What this means

A read-only view of `/` lets Node Exporter see file names and sizes on the whole computer. It is there to read
disk and memory numbers, but it is wider access than the other containers have.
