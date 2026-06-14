"""Risk scoring - aggregate module results into a 0-100 score."""

from __future__ import annotations


WEIGHTS = {
    "knf_hit":           -40,   # firma na liście ostrzeżeń KNF
    "uokik_decision":    -10,   # każda decyzja UOKiK (max -30)
    "vat_zwolniony":      -5,   # status VAT "Zwolniony"
    "vat_niezarejestr":  -25,   # brak rejestracji VAT
    "branch_knf_hit":    -15,   # oddział na liście KNF
    "domain_new":        -15,   # domena < 30 dni
    "domain_no_spf":      -5,   # brak SPF
    "domain_no_dmarc":    -5,   # brak DMARC
    "no_krs":             -5,   # brak wpisu w KRS (może być JDG)
}

LEVEL_THRESHOLDS = [
    (70, "niski",    "#276749"),  # zielony
    (40, "średni",   "#b7791f"),  # żółty
    (0,  "wysoki",   "#c53030"),  # czerwony
]


def calculate(results: dict) -> dict:
    """Calculate risk score from module results. Returns score, level, color, reasons."""
    score = 100
    reasons: list[str] = []

    # VAT
    vat = results.get("vat", {})
    if vat.get("status") == "ok":
        status_vat = (vat.get("data", {}).get("status_vat") or "").lower()
        if "zwolniony" in status_vat:
            score += WEIGHTS["vat_zwolniony"]
            reasons.append("Status VAT: Zwolniony")
        elif "niezarejestrowany" in status_vat or "niezarejestrowan" in status_vat:
            score += WEIGHTS["vat_niezarejestr"]
            reasons.append("Podmiot niezarejestrowany jako podatnik VAT")

    # KNF
    knf = results.get("knf", {})
    if knf.get("status") == "ok":
        knf_data = knf.get("data", {})
        matches = knf_data.get("matches", [])
        if matches or knf_data.get("found"):
            score += WEIGHTS["knf_hit"]
            reasons.append(f"Podmiot figuruje na liście ostrzeżeń KNF ({len(matches)} wpis/ów)")

    # UOKiK
    uokik = results.get("uokik", {})
    if uokik.get("status") == "ok":
        decisions = uokik.get("data", {}).get("decisions", [])
        if decisions:
            penalty = max(WEIGHTS["uokik_decision"] * len(decisions), -30)
            score += penalty
            reasons.append(f"Znaleziono {len(decisions)} decyzji UOKiK dotyczących podmiotu")

    # KRS
    krs = results.get("krs", {})
    if krs.get("status") in ("not_found", "skipped", "error"):
        score += WEIGHTS["no_krs"]
        reasons.append("Brak wpisu w KRS (podmiot nie jest spółką)")

    # Powiązania - branch KNF check
    pow_data = results.get("powiazania", {}).get("data", {})
    branch_checks = pow_data.get("branch_checks", {})
    branch_hits = [n for n, c in branch_checks.items() if c.get("hit")]
    if branch_hits:
        score += WEIGHTS["branch_knf_hit"]
        reasons.append(f"Oddział figuruje na liście ostrzeżeń KNF: {branch_hits[0][:50]}")

    # WHOIS / DNS
    dns_data = results.get("whois_dns", {}).get("data", {})
    if dns_data:
        whois_info = dns_data.get("whois", {})
        dns_info = dns_data.get("dns", {})

        if whois_info.get("is_new"):
            score += WEIGHTS["domain_new"]
            reasons.append("Domena zarejestrowana mniej niż 30 dni temu")

        if not dns_info.get("has_spf"):
            score += WEIGHTS["domain_no_spf"]
            reasons.append("Brak rekordu SPF — zwiększone ryzyko phishingu")

        if not dns_info.get("has_dmarc"):
            score += WEIGHTS["domain_no_dmarc"]
            reasons.append("Brak rekordu DMARC — zwiększone ryzyko phishingu")

    score = max(0, min(100, score))

    level_label, level_color = "niski", "#276749"
    for threshold, label, color in LEVEL_THRESHOLDS:
        if score >= threshold:
            level_label, level_color = label, color
            break

    return {
        "score": score,
        "level": level_label,
        "color": level_color,
        "reasons": reasons,
    }
