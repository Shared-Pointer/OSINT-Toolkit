"""WHOIS/DNS module — rejestracja domeny i rekordy DNS."""

from __future__ import annotations
import re
import socket
from datetime import datetime, timezone
from typing import Optional

import dns.resolver
import whois


def _normalize_domain(raw: str) -> str:
    raw = raw.strip().lower()
    raw = re.sub(r"https?://", "", raw)
    raw = re.sub(r"/.*", "", raw)
    return raw


def _days_since(dt) -> Optional[int]:
    if dt is None:
        return None
    if isinstance(dt, list):
        dt = dt[0]
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    return None


def _days_until(dt) -> Optional[int]:
    if dt is None:
        return None
    if isinstance(dt, list):
        dt = dt[0]
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt - datetime.now(timezone.utc)).days
    return None


def _get_whois(domain: str) -> dict:
    try:
        w = whois.whois(domain)
        return {
            "registrar": w.registrar,
            "creation_date": str(w.creation_date[0] if isinstance(w.creation_date, list) else w.creation_date),
            "expiration_date": str(w.expiration_date[0] if isinstance(w.expiration_date, list) else w.expiration_date),
            "country": w.country,
            "registrant": w.registrant_name or w.org,
            "days_old": _days_since(w.creation_date),
            "days_until_expiry": _days_until(w.expiration_date),
            "is_new": (_days_since(w.creation_date) or 999) < 30,
            "expires_soon": 0 <= (_days_until(w.expiration_date) or 999) < 30,
        }
    except Exception as e:
        return {"error": str(e)}


def _get_dns(domain: str) -> dict:
    result = {}

    # A record
    try:
        answers = dns.resolver.resolve(domain, "A")
        result["a_records"] = [str(r) for r in answers]
    except Exception:
        result["a_records"] = []

    # MX
    try:
        answers = dns.resolver.resolve(domain, "MX")
        result["mx_records"] = sorted(
            [f"{r.preference} {r.exchange}" for r in answers],
            key=lambda x: int(x.split()[0]),
        )
    except Exception:
        result["mx_records"] = []

    # SPF (TXT records)
    spf = None
    try:
        answers = dns.resolver.resolve(domain, "TXT")
        for r in answers:
            txt = r.to_text().strip('"')
            if txt.startswith("v=spf1"):
                spf = txt
                break
    except Exception:
        pass
    result["spf"] = spf

    # DMARC
    dmarc = None
    try:
        answers = dns.resolver.resolve(f"_dmarc.{domain}", "TXT")
        for r in answers:
            txt = r.to_text().strip('"')
            if "v=DMARC1" in txt:
                dmarc = txt
                break
    except Exception:
        pass
    result["dmarc"] = dmarc

    # Flagi bezpieczeństwa
    result["has_spf"] = spf is not None
    result["has_dmarc"] = dmarc is not None
    result["phishing_risk"] = not spf or not dmarc

    return result


# ── Module interface ──────────────────────────────────────────────────────────

def run(domain: str, query_type: str = "domain") -> dict:
    domain = _normalize_domain(domain)
    if not domain or "." not in domain:
        return {"status": "skipped", "error": "Nieprawidłowa domena.", "data": {}}

    try:
        whois_data = _get_whois(domain)
        dns_data = _get_dns(domain)

        return {
            "status": "ok",
            "data": {
                "domain": domain,
                "whois": whois_data,
                "dns": dns_data,
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "data": {}}
