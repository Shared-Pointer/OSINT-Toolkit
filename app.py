"""OSINT Toolkit — Flask app."""

import io
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, render_template, request, send_file, redirect, url_for, flash

from modules import ceidg, vat, krs, knf, uokik, rekrutacje
from pdf_generator import generate_pdf


def _is_nip(q: str) -> bool:
    d = re.sub(r"[\s\-]", "", q)
    # NIP: 10 cyfr, NIE zaczyna się od 0 (pierwsze 3 cyfry = kod US, min 100)
    return d.isdigit() and len(d) == 10 and not d.startswith("0")


def _is_krs(q: str) -> bool:
    d = re.sub(r"[\s\-]", "", q)
    # KRS: do 10 cyfr, często z wiodącymi zerami (np. 0000399383)
    return d.isdigit() and 1 <= len(d) <= 10 and (d.startswith("0") or len(d) < 10)


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
        "needs_nip": True,
        "fn": vat.run,
    },
    "ceidg": {
        "name": "CEIDG",
        "desc": "Jednoosobowe działalności gospodarcze",
        "icon": "👤",
        "needs_nip": False,
        "fn": ceidg.run,
    },
    "krs": {
        "name": "KRS",
        "desc": "Krajowy Rejestr Sądowy — spółki (MS)",
        "icon": "🏛️",
        "needs_nip": True,
        "fn": krs.run,
    },
    "knf": {
        "name": "KNF Ostrzeżenia",
        "desc": "Lista ostrzeżeń publicznych KNF",
        "icon": "⚠️",
        "needs_nip": False,
        "fn": knf.run,
    },
    "uokik": {
        "name": "UOKiK",
        "desc": "Decyzje Urzędu Ochrony Konkurencji i Konsumentów",
        "icon": "⚖️",
        "needs_nip": False,
        "fn": uokik.run,
    },
    "rekrutacje": {
        "name": "Rekrutacje",
        "desc": "Aktywne oferty pracy firmy (pracuj.pl) — wymaga nazwy firmy",
        "icon": "💼",
        "needs_nip": False,
        "fn": rekrutacje.run,
    },
}


@app.route("/")
def index():
    return render_template("index.html", modules=MODULES)


@app.route("/generate", methods=["POST"])
def generate():
    query = request.form.get("query", "").strip()
    query_type = request.form.get("query_type", "auto")
    selected = request.form.getlist("modules")

    if not query:
        flash("Wpisz NIP, KRS lub nazwę firmy.")
        return redirect(url_for("index"))

    if not selected:
        flash("Wybierz przynajmniej jeden moduł.")
        return redirect(url_for("index"))

    results = {}

    NAME_MODULES = {"knf", "uokik", "rekrutacje"}

    # Explicit query_type ma priorytet nad auto-detekcją
    if query_type == "nip":
        detected_nip, detected_krs = True, False
    elif query_type == "krs":
        detected_nip, detected_krs = False, True
    else:  # auto
        detected_nip = _is_nip(query)
        detected_krs = not detected_nip and _is_krs(query)
    company_name: str | None = None
    nip_for_uokik: str = ""
    regon_for_uokik: str = ""

    # NIP → pobierz nazwę firmy z VAT (potrzebna dla name-based modułów)
    if detected_nip and any(m in selected for m in NAME_MODULES):
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

    # KRS → VAT nie obsługuje KRS, skip
    if detected_krs and "vat" in selected:
        results["vat"] = {
            "status": "skipped",
            "error": "Moduł VAT wymaga NIP — nie można wyszukać po numerze KRS.",
            "data": {},
        }

    def _run_module(name: str):
        # VAT już obsłużony powyżej
        if name == "vat":
            return MODULES["vat"]["fn"](query, query_type)

        if name in NAME_MODULES:
            if company_name:
                if name == "uokik":
                    return uokik.run(company_name, "name", nip=nip_for_uokik, regon=regon_for_uokik)
                return MODULES[name]["fn"](company_name, "name")
            # Brak nazwy (zapytanie to KRS lub nieznana forma) — pomiń
            if detected_krs or detected_nip:
                return {
                    "status": "skipped",
                    "error": "Brak nazwy firmy do wyszukania — podaj NIP lub nazwę firmy zamiast KRS.",
                    "data": {},
                }
        return MODULES[name]["fn"](query, query_type)

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

    pdf_bytes = generate_pdf(query, query_type, results, MODULES, selected)

    safe_name = query.replace(" ", "_").replace("/", "-")[:50]
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"raport_{safe_name}.pdf",
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
