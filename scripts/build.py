#!/usr/bin/env python3
"""Download, normalize, and combine DNS blocking rules."""

from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
TIMEOUT = 30
MINIMUM_RULES = 50_000
USER_AGENT = "removeads-rule-builder/1.0 (+https://github.com/)"
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def normalize_domain(value: str) -> str | None:
    value = value.strip().rstrip(".").lstrip(".").lower()
    if not value or value == "localhost" or any(c in value for c in "/:*?[]@"):
        return None
    try:
        ipaddress.ip_address(value)
        return None
    except ValueError:
        pass
    try:
        value = value.encode("idna").decode("ascii").lower()
    except (UnicodeError, UnicodeDecodeError):
        return None
    return value if DOMAIN_RE.fullmatch(value) else None


def parse_line(raw: str) -> str | None:
    line = raw.strip().lstrip("\ufeff")
    if not line or line.startswith(("#", "!", ";", "//")):
        return None
    if "##" in line or "#@#" in line or line.startswith("/") and line.endswith("/"):
        return None

    upper = line.upper()
    for prefix in ("DOMAIN-SUFFIX,", "DOMAIN,"):
        if upper.startswith(prefix):
            return normalize_domain(line[len(prefix):].split(",", 1)[0])

    if line.startswith("||"):
        match = re.fullmatch(r"\|\|([^\^$]+)\^(?:\$.*)?", line)
        return normalize_domain(match.group(1)) if match else None

    fields = line.split()
    if len(fields) >= 2:
        try:
            ipaddress.ip_address(fields[0])
        except ValueError:
            return None
        return normalize_domain(fields[1])
    if len(fields) != 1:
        return None
    return normalize_domain(fields[0])


def read_local(path: Path) -> set[str]:
    domains: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        domain = parse_line(line)
        if domain:
            domains.add(domain)
    return domains


def download(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain,*/*;q=0.1"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read().decode("utf-8", errors="replace")


def is_allowed(domain: str, allowlist: set[str]) -> bool:
    return any(domain == allowed or domain.endswith("." + allowed) for allowed in allowlist)


def header(generated_at: str, successful: int, total: int, marker: str) -> str:
    return "\n".join((
        f"{marker} removeads DNS advertising rules",
        f"{marker} Generated at (UTC): {generated_at}",
        f"{marker} Successful sources: {successful}",
        f"{marker} Total rules: {total}",
        f"{marker} DO NOT EDIT MANUALLY",
        "",
    ))


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    sources = [line.strip() for line in (ROOT / "sources.txt").read_text(encoding="utf-8").splitlines()
               if line.strip() and not line.lstrip().startswith("#")]
    source_results: list[dict[str, object]] = []
    extracted_sets: list[set[str]] = []

    for url in sources:
        result: dict[str, object] = {"url": url, "status": "failed", "raw_lines": 0, "valid_domains": 0}
        try:
            text = download(url)
            lines = text.splitlines()
            domains = {domain for line in lines if (domain := parse_line(line))}
            result.update(status="success", raw_lines=len(lines), valid_domains=len(domains))
            extracted_sets.append(domains)
        except (OSError, urllib.error.URLError, UnicodeError) as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
            print(f"warning: failed to download {url}: {exc}", file=sys.stderr)
        source_results.append(result)

    successful = len(extracted_sets)
    if not successful:
        print("error: all sources failed; existing output was left untouched", file=sys.stderr)
        return 1

    merged_before = sum(len(domains) for domains in extracted_sets)
    merged = set().union(*extracted_sets)
    deduplicated = len(merged)
    allowlist = read_local(ROOT / "allowlist.txt")
    allowed_removed = sum(is_allowed(domain, allowlist) for domain in merged)
    merged = {domain for domain in merged if not is_allowed(domain, allowlist)}
    blocklist = read_local(ROOT / "blocklist.txt")
    block_added = len(blocklist - merged)
    merged.update(blocklist)
    ordered = sorted(merged)

    report = {
        "generated_at": generated_at,
        "source_results": source_results,
        "successful_sources": successful,
        "merged_before_deduplication": merged_before,
        "deduplicated_rules": deduplicated,
        "allowlist_removed": allowed_removed,
        "blocklist_added": block_added,
        "final_rules": len(ordered),
    }
    if len(ordered) < MINIMUM_RULES:
        print(f"error: final rule count {len(ordered):,} is below safety threshold {MINIMUM_RULES:,}; output was left untouched", file=sys.stderr)
        return 1

    domains_text = header(generated_at, successful, len(ordered), "#") + "\n".join(ordered) + "\n"
    adguard_text = header(generated_at, successful, len(ordered), "!") + "\n".join(f"||{domain}^" for domain in ordered) + "\n"
    atomic_write(OUTPUT / "domains.txt", domains_text)
    atomic_write(OUTPUT / "adguard-dns.txt", adguard_text)
    atomic_write(OUTPUT / "report.json", json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(f"sources: {successful}/{len(sources)} | before dedupe: {merged_before:,} | unique: {deduplicated:,} | allowlist removed: {allowed_removed:,} | blocklist added: {block_added:,} | final: {len(ordered):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
