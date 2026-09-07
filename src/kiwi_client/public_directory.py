"""Scrape and parse the explicitly authorized KiwiSDR public directory."""

from __future__ import annotations

import html
import re
import urllib.request
from typing import Any

PUBLIC_DIRECTORY_URL = "http://kiwisdr.com/public/"
_ENTRY_START_RE = re.compile(r"<div\s+class=['\"]cl-entry\b", re.IGNORECASE)
_COMMENT_RE = re.compile(r"<!--\s*([A-Za-z0-9_]+)=(.*?)\s*-->", re.DOTALL)
_HREF_RE = re.compile(r"<a\s+href=['\"](https?://[^'\"]+)['\"]", re.IGNORECASE)
_AUTH_RE = re.compile(r"setRequestHeader\(['\"]x-kiwi-auth['\"],['\"]([^'\"]+)['\"]\)")
_INTEGER_FIELDS = ("users", "users_max", "ext_api", "preempt", "tdoa_ch", "asl")


def _integer(metadata: dict[str, str], key: str) -> int | None:
    try:
        return int(metadata[key])
    except (KeyError, ValueError):
        return None


def _snr(metadata: dict[str, str]) -> tuple[int | None, int | None]:
    values = metadata.get("snr", "").split(",", 1)
    if len(values) != 2:
        return None, None
    try:
        return int(values[0]), int(values[1])
    except ValueError:
        return None, None


def _gps(metadata: dict[str, str]) -> tuple[float | None, float | None]:
    match = re.fullmatch(r"\(\s*([^,]+),\s*([^\)]+)\s*\)", metadata.get("gps", ""))
    if match is None:
        return None, None
    try:
        return float(match.group(1)), float(match.group(2))
    except ValueError:
        return None, None


def parse_public_directory(document: str) -> list[dict[str, Any]]:
    """Parse receiver entries and preserve every key/value metadata comment."""
    starts = [match.start() for match in _ENTRY_START_RE.finditer(document)]
    receivers: list[dict[str, Any]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(document)
        entry = document[start:end]
        href = _HREF_RE.search(entry)
        if href is None:
            continue
        metadata = {
            key: html.unescape(value.strip())
            for key, value in _COMMENT_RE.findall(entry)
        }
        snr_all, snr_hf = _snr(metadata)
        latitude, longitude = _gps(metadata)
        receiver: dict[str, Any] = {
            "url": html.unescape(href.group(1).strip()),
            "id": metadata.get("id"),
            "name": metadata.get("name", ""),
            "location": metadata.get("loc", ""),
            "grid": metadata.get("grid", ""),
            "latitude": latitude,
            "longitude": longitude,
            "snr_all_db": snr_all,
            "snr_hf_db": snr_hf,
            "antenna": metadata.get("antenna", ""),
            "hardware": metadata.get("sdr_hw", ""),
            "software_version": metadata.get("sw_version", ""),
            "bands": metadata.get("bands", ""),
            "mode": metadata.get("mode", ""),
            "status": metadata.get("status", ""),
            "updated": metadata.get("updated", ""),
            "metadata": metadata,
        }
        for key in _INTEGER_FIELDS:
            receiver[key] = _integer(metadata, key)
        receivers.append(receiver)
    return receivers


def fetch_public_directory(*, url: str = PUBLIC_DIRECTORY_URL, timeout: float = 20.0) -> str:
    """Perform the directory's click-through authorization and return its HTML."""
    opener = urllib.request.build_opener()
    with opener.open(url, timeout=timeout) as response:
        document = response.read().decode("utf-8", errors="replace")
    if _ENTRY_START_RE.search(document):
        return document
    match = _AUTH_RE.search(document)
    if match is None:
        raise RuntimeError("KiwiSDR directory did not provide click-through authorization")
    request = urllib.request.Request(url, headers={"x-kiwi-auth": match.group(1)})
    with opener.open(request, timeout=timeout) as response:
        response.read()
    with opener.open(url, timeout=timeout) as response:
        document = response.read().decode("utf-8", errors="replace")
    if not _ENTRY_START_RE.search(document):
        raise RuntimeError("KiwiSDR directory returned no receiver entries after click-through")
    return document
