"""OSINT Toolkit — Flask app."""

import io
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, render_template, request, send_file, redirect, url_for, flash

from modules import vat, krs, knf, uokik, rekrutacje, whois_dns, powiazania
from pdf_generator import generate_pdf


def _is_nip(q: str) -> bool:
    d = re.sub(r"[\s\-]", "", q)
    return d.isdigit() and len(d) == 10 and not d.startswith("0")


def _shorten_for_search(name: str) -> str:
    """Usuwa formę prawną i zostawia max 3 pierwsze słowa do wyszukiwania."""
    import re as _re
    suffixes = _re.compile(
        r"\b(SPÓŁKA AKCYJNA|SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ|"
        r"SPÓŁKA JAWNA|SPÓŁKA KOMANDYTOWA|SPÓŁKA PARTNERSKA|SPÓŁKA CYWILNA|"
        r"S\.A\.|SP\. Z O\.O\.|SP\. J\.|SP\. K\.|S\.K\.A\.|"
        r"AKCYJNA|OGRANICZONĄ|ODPOWIEDZIALNOŚCIĄ)\b",
        _re.IGNORECASE,
    )
    short = suffixes.sub("", name).strip(" ,.-")
    words = short.split()
    return " ".join(words[:3]) if words else name

app = Flask(__name__)
app.secret_key = "osint-toolkit-dev"

MODULES = {
    "vat": {
        "name": "Wykaz Podatników VAT",
        "desc": "Status VAT, rachunki bankowe (MF/KAS)",
        "icon": "🏦",
        "fn": vat.run,
    },
    "krs": {
        "name": "KRS",
        "desc": "Krajowy Rejestr Sądowy — spółki (MS)",
        "icon": "🏛️",
        "fn": krs.run,
    },
    "knf": {
        "name": "KNF Ostrzeżenia",
        "desc": "Lista ostrzeżeń publicznych KNF",
        "icon": "⚠️",
        "fn": knf.run,
    },
    "uokik": {
        "name": "UOKiK",
        "desc": "Decyzje Urzędu Ochrony Konkurencji i Konsumentów",
        "icon": "⚖️",
        "fn": uokik.run,
    },
    "rekrutacje": {
        "name": "Rekrutacje",
        "desc": "Aktywne oferty pracy firmy (pracuj.pl, NoFluffJobs, JustJoin.it)",
        "icon": "💼",
        "fn": rekrutacje.run,
    },
    "whois_dns": {
        "name": "WHOIS / DNS",
        "desc": "Rejestracja domeny, rekordy MX/SPF/DMARC",
        "icon": "🌐",
        "fn": whois_dns.run,
    },
    "powiazania": {
        "name": "Powiązania właścicielskie",
        "desc": "Struktura zarządu, prokurenci, oddziały (KRS)",
        "icon": "🔗",
        "fn": powiazania.run,
    },
}


@app.route("/")
def index():
    return render_template("index.html", modules=MODULES)


@app.route("/generate", methods=["POST"])
def generate():
    query = re.sub(r"[\s\-]", "", request.form.get("query", "").strip())
    domain = request.form.get("domain", "").strip()
    selected = request.form.getlist("modules")

    if not query:
        flash("Wpisz NIP firmy.")
        return redirect(url_for("index"))

    if not _is_nip(query):
        flash("Podany ciąg nie wygląda jak NIP (10 cyfr, nie zaczyna się od 0).")
        return redirect(url_for("index"))

    if not selected:
        flash("Wybierz przynajmniej jeden moduł.")
        return redirect(url_for("index"))

    results = {}
    company_name: str | None = None
    nip_for_uokik: str = ""
    regon_for_uokik: str = ""

    NAME_MODULES = {"knf", "uokik", "rekrutacje"}

    # Pobierz nazwę firmy z VAT — potrzebna dla modułów name-based
    if any(m in selected for m in NAME_MODULES):
        try:
            vat_result = vat.run(query, "nip")
            if vat_result.get("status") == "ok":
                company_name = _shorten_for_search(vat_result["data"].get("nazwa", ""))
                nip_for_uokik = vat_result["data"].get("nip", "") or ""
                regon_for_uokik = vat_result["data"].get("regon", "") or ""
            if "vat" in selected:
                results["vat"] = vat_result
        except Exception as e:
            if "vat" in selected:
                results["vat"] = {"status": "error", "error": str(e), "data": {}}

    def _run_module(name: str):
        if name == "vat":
            return MODULES["vat"]["fn"](query, "nip")
        if name == "whois_dns":
            if not domain:
                return {"status": "skipped", "error": "Nie podano domeny — wpisz adres strony firmy.", "data": {}}
            return whois_dns.run(domain)
        if name == "powiazania":
            return powiazania.run(query, "nip")
        if name in NAME_MODULES:
            if not company_name:
                return {"status": "skipped", "error": "Brak nazwy firmy — moduł VAT nie zwrócił danych.", "data": {}}
            if name == "uokik":
                return uokik.run(company_name, "name", nip=nip_for_uokik, regon=regon_for_uokik)
            return MODULES[name]["fn"](company_name, "name")
        return MODULES[name]["fn"](query, "nip")

    remaining = [n for n in selected if n not in results]

    with ThreadPoolExecutor(max_workers=max(len(remaining), 1)) as executor:
        futures = {
            executor.submit(_run_module, name): name
            for name in remaining
            if name in MODULES
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result(timeout=60)
            except Exception as e:
                results[name] = {"status": "error", "error": str(e), "data": {}}

    pdf_bytes = generate_pdf(query, results, MODULES, selected)

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"raport_{query}.pdf",
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
