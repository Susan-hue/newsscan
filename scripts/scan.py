"""Upload a file to a running API, wait for the result, and print it.

Usage: python scripts/scan.py http://127.0.0.1:8000 path/to/scan.jpg
"""

import mimetypes
import sys
import time

import httpx

base, path = sys.argv[1], sys.argv[2]

with httpx.Client(base_url=base, timeout=30) as client:
    with open(path, "rb") as handle:
        response = client.post(
            "/v1/scans",
            files={
                "file": (
                    path.split("/")[-1],
                    handle,
                    mimetypes.guess_type(path)[0] or "application/octet-stream",
                )
            },
        )
    print("upload:", response.status_code, response.json())
    scan_id = response.json()["id"]

    started = time.time()
    while True:
        scan = client.get(f"/v1/scans/{scan_id}").json()
        if scan["status"] in ("done", "failed"):
            break
        if time.time() - started > 120:
            sys.exit("timed out waiting for the scan")
        time.sleep(0.5)

    print(f"status: {scan['status']} after {time.time() - started:.1f}s")
    if scan["status"] == "failed":
        sys.exit(f"error: {scan['error']}")
    document, report = scan["document"], scan["report"]
    print(
        f"pages={document['page_count']} chars={document['char_count']} "
        f"confidence={document['mean_confidence']} engine={document['ocr_engine']}"
    )
    print("band:", report["band"])
    print("--- recognised text ---")
    print(document["text"])
    print("--- signals ---")
    for signal in report["signals"]:
        print(f"{signal['name']:22} {signal['kind']:10} {signal['status']:8} {signal['value']}")
