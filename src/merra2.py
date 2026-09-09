"""GES DISC JSON-WSP subset acquisition (no global-granule downloads)."""

from pathlib import Path
from tempfile import NamedTemporaryFile
import time
from urllib.parse import unquote, urlparse

import requests

GESDISC_SUBSET_URL = "https://disc.gsfc.nasa.gov/service/subset/jsonwsp"
HTTP_TIMEOUT = (10, 60)  # connection and read inactivity, seconds
JOB_TIMEOUT = 600
POLL_INTERVAL = 5


def _subset_rpc(method, args):
    request = {"methodname": method, "type": "jsonwsp/request",
               "version": "1.0", "args": args}
    delays = (5, 10, 20, 40, 60)
    for attempt in range(len(delays) + 1):
        try:
            with requests.post(GESDISC_SUBSET_URL, json=request,
                               timeout=HTTP_TIMEOUT) as response:
                response.raise_for_status()
                payload = response.json()
            break
        except (requests.RequestException, ValueError) as exc:
            status = exc.response.status_code if isinstance(exc, requests.HTTPError) and exc.response is not None else None
            transient = (status in (429, 500, 502, 503, 504)
                         or isinstance(exc, (requests.ConnectionError, requests.Timeout))
                         and not isinstance(exc, requests.exceptions.SSLError))
            if not transient or attempt == len(delays):
                raise RuntimeError(f"GES DISC {method}: {exc}") from exc
            delay = delays[attempt]
            reason = status if status is not None else type(exc).__name__
            print(f"GES DISC error temporal {reason}. Reintento {attempt + 1}/{len(delays)} en {delay} s...", flush=True)
            time.sleep(delay)
    if not isinstance(payload, dict) or payload.get("type") == "jsonwsp/fault":
        raise RuntimeError(f"GES DISC {method} fault: {payload}")
    if not isinstance(payload.get("result"), dict):
        raise RuntimeError(f"GES DISC {method}: missing result: {payload}")
    return payload["result"]


def merra_subset_request(dataset_id, variables, start, end, bbox):
    """Submit a new station subset and return its jobId and sessionId."""
    result = _subset_rpc("subset", {
        "role": "subset", "start": start, "end": end, "box": bbox,
        "crop": True, "mapping": "nearest",
        "data": [{"datasetId": dataset_id, "variable": v} for v in variables],
    })
    if not result.get("jobId") or not result.get("sessionId"):
        raise RuntimeError(f"GES DISC subset: missing job/session identifiers: {result}")
    return result["jobId"], result["sessionId"]


def merra_subset_result(job_id, session_id):
    """Return the single NetCDF link required by the daily acquisition path."""
    links = _subset_result_links(job_id, session_id)
    if len(links) != 1:
        raise RuntimeError(f"GES DISC job {job_id}: expected one NetCDF link, got {len(links)}")
    return links[0]


def _subset_result_links(job_id, session_id):
    """Wait at most JOB_TIMEOUT seconds, then return the NetCDF links.

    Each HTTP call also has bounded connection/read waits. An in-flight
    status request can finish after the polling deadline by its HTTP timeout.
    """
    args = {"jobId": job_id, "sessionId": session_id}
    deadline = time.monotonic() + JOB_TIMEOUT
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"GES DISC job {job_id}: exceeded {JOB_TIMEOUT}s")
        result = _subset_rpc("GetStatus", args)
        status = result.get("Status")
        if status == "Succeeded":
            break
        if status not in ("Accepted", "Running", "Pending", "Queued"):
            raise RuntimeError(f"GES DISC job {job_id}: {result}")
        time.sleep(max(0, min(POLL_INTERVAL, deadline - time.monotonic())))

    result = _subset_rpc("GetResult", args)
    items = result.get("items")
    if not isinstance(items, list):
        raise RuntimeError(f"GES DISC job {job_id}: missing result items")
    links = [item["link"] for item in items
             if isinstance(item, dict)
             and item.get("type") != "VIEW RELATED INFORMATION"
             and isinstance(item.get("link"), str)
             and urlparse(item["link"]).scheme == "https"
             and ".nc" in unquote(item["link"]).lower()]
    return links


def merra_download_subset(dataset_id, variables, start, end, bbox, output_file):
    """Request and download a subset; publish only a complete HTTP transfer.

    The caller validates NetCDF contents before treating the file as a cache.
    Failed transfers leave any pre-existing output untouched.
    """
    job_id, session_id = merra_subset_request(dataset_id, variables, start, end, bbox)
    link = merra_subset_result(job_id, session_id)
    return _download_link(link, output_file, dataset_id)


def _download_monthly_subsets(dataset_id, variables, start, end, bbox, directory):
    """Download all NetCDF results sequentially into a caller-owned staging dir."""
    job_id, session_id = merra_subset_request(dataset_id, variables, start, end, bbox)
    links = _subset_result_links(job_id, session_id)
    if not links:
        raise RuntimeError("GES DISC: missing monthly NetCDF links")
    return [_download_link(link, Path(directory) / f"{i:03d}.nc", dataset_id)
            for i, link in enumerate(links)]


def _download_link(link, output_file, dataset_id):
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    # A unique temporary name also avoids collisions between concurrent callers.
    temporary = None
    try:
        deadline = time.monotonic() + JOB_TIMEOUT
        with requests.get(link, stream=True, timeout=HTTP_TIMEOUT) as response:
            response.raise_for_status()
            with NamedTemporaryFile(dir=output_file.parent, suffix=".part", delete=False) as f:
                temporary = Path(f.name)
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"GES DISC {dataset_id}: download exceeded {JOB_TIMEOUT}s")
                    if chunk:
                        f.write(chunk)
        if temporary.stat().st_size == 0:
            raise RuntimeError(f"GES DISC {dataset_id}: empty download")
        temporary.replace(output_file)
    except requests.RequestException as exc:
        raise RuntimeError(f"GES DISC {dataset_id} download: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output_file
