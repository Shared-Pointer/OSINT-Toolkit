"""OSINT Toolkit — Flask app."""

import io
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, render_template, request, send_file, redirect, url_for, flash

from modules import ceidg, vat, krs, knf, uokik, rekrutacje
from pdf_generator import generate_pdf

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

    with ThreadPoolExecutor(max_workers=len(selected)) as executor:
        futures = {
            executor.submit(MODULES[name]["fn"], query, query_type): name
            for name in selected
            if name in MODULES
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result(timeout=45)
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
