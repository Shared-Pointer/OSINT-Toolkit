"""PDF generator — buduje raport przy użyciu ReportLab."""

from __future__ import annotations
from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# ── Kolory ───────────────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#1a1a2e")
BLUE   = colors.HexColor("#4361ee")
GREEN  = colors.HexColor("#38a169")
RED    = colors.HexColor("#e53e3e")
ORANGE = colors.HexColor("#d97706")
GRAY   = colors.HexColor("#718096")
LGRAY  = colors.HexColor("#f7fafc")
WHITE  = colors.white


# ── Style ────────────────────────────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()
    S = {}
    S["title"] = ParagraphStyle("title", parent=base["Normal"],
        fontSize=22, textColor=WHITE, fontName="Helvetica-Bold", leading=28)
    S["subtitle"] = ParagraphStyle("subtitle", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#a0aec0"), leading=14)
    S["meta"] = ParagraphStyle("meta", parent=base["Normal"],
        fontSize=8, textColor=colors.HexColor("#a0aec0"), leading=12)
    S["section_title"] = ParagraphStyle("section_title", parent=base["Normal"],
        fontSize=11, textColor=WHITE, fontName="Helvetica-Bold", leading=16)
    S["body"] = ParagraphStyle("body", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#2d3748"), leading=14)
    S["label"] = ParagraphStyle("label", parent=base["Normal"],
        fontSize=9, textColor=GRAY, fontName="Helvetica-Bold", leading=14)
    S["value"] = ParagraphStyle("value", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#1a202c"), leading=14)
    S["small"] = ParagraphStyle("small", parent=base["Normal"],
        fontSize=8, textColor=GRAY, leading=12)
    S["alert_ok"] = ParagraphStyle("alert_ok", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#276749"), leading=14,
        backColor=colors.HexColor("#f0fff4"), borderPadding=8)
    S["alert_warn"] = ParagraphStyle("alert_warn", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#c05621"), leading=14)
    S["footer"] = ParagraphStyle("footer", parent=base["Normal"],
        fontSize=7.5, textColor=GRAY, alignment=TA_CENTER, leading=12)
    S["subject"] = ParagraphStyle("subject", parent=base["Normal"],
        fontSize=15, textColor=NAVY, fontName="Helvetica-Bold", leading=20)
    return S


# ── Helpers ──────────────────────────────────────────────────────────────────
def _header_row(text: str, status: str, icon: str, styles) -> Table:
    STATUS_COLORS = {
        "ok": colors.HexColor("#48bb78"),
        "not_found": GRAY,
        "error": RED,
        "no_token": ORANGE,
        "skipped": GRAY,
    }
    STATUS_LABELS = {
        "ok": "OK",
        "not_found": "BRAK",
        "error": "BŁĄD",
        "no_token": "BRAK TOKENU",
        "skipped": "POMINIĘTO",
    }

    badge_color = STATUS_COLORS.get(status, GRAY)
    badge_label = STATUS_LABELS.get(status, status.upper())

    title_cell = Paragraph(f"{icon}  {text}", styles["section_title"])
    badge = Table([[Paragraph(badge_label, ParagraphStyle("b", fontSize=8,
        textColor=WHITE, fontName="Helvetica-Bold", leading=12))]],
        colWidths=[2.2*cm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), badge_color),
        ("ROUNDEDCORNERS", (0,0), (-1,-1), [8,8,8,8]),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ]))

    header = Table([[title_cell, badge]], colWidths=[None, 2.8*cm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING", (0,0), (0,-1), 14),
        ("RIGHTPADDING", (-1,0), (-1,-1), 10),
        ("ROUNDEDCORNERS", (0,0), (-1,-1), [6,6,0,0]),
    ]))
    return header


def _data_table(rows: list[tuple[str, str]], styles) -> Table:
    """Tabela key-value z naprzemiennym tłem."""
    data = []
    for label, value in rows:
        if not value or value in ("—", "None", None):
            value = "—"
        data.append([
            Paragraph(label, styles["label"]),
            Paragraph(str(value), styles["value"]),
        ])

    t = Table(data, colWidths=[5*cm, None])
    ts = [
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING", (0,0), (0,-1), 12),
        ("LEFTPADDING", (1,0), (1,-1), 8),
        ("RIGHTPADDING", (1,0), (-1,-1), 12),
        ("LINEBELOW", (0,0), (-1,-2), 0.3, colors.HexColor("#e2e8f0")),
    ]
    # Naprzemienne tło — tylko dla istniejących wierszy
    for i in range(1, len(data), 2):
        ts.append(("BACKGROUND", (0, i), (-1, i), LGRAY))
    t.setStyle(TableStyle(ts))
    return t


def _section_box(header_table, content_flowables):
    """Zwraca header + content jako listę flowables (bez zewnętrznej tabeli — pozwala na podział stron)."""
    return [header_table] + content_flowables + [Spacer(1, 14)]


# ── Budowanie sekcji ─────────────────────────────────────────────────────────
def _section_vat(result: dict, styles) -> list:
    status = result.get("status", "error")
    header = _header_row("Wykaz Podatników VAT (MF/KAS)", status, "🏦", styles)
    d = result.get("data", {})

    if status == "ok" and d:
        vat_status = d.get("status_vat", "—")
        vat_color = GREEN if vat_status == "Czynny" else RED
        rows = [
            ("Nazwa", d.get("nazwa")),
            ("NIP", d.get("nip")),
            ("REGON", d.get("regon")),
            ("KRS", d.get("krs")),
            ("Status VAT", vat_status),
            ("Adres", d.get("adres")),
            ("Data rejestracji", d.get("data_rejestracji")),
        ]
        if d.get("data_wykreslenia"):
            rows.append(("Data wykreślenia", d["data_wykreslenia"]))
        if d.get("rachunki_bankowe"):
            rachunki = d["rachunki_bankowe"]
            shown = rachunki[:10]
            suffix = f" (+{len(rachunki)-10} więcej)" if len(rachunki) > 10 else ""
            rows.append(("Rachunki bankowe", "<br/>".join(shown) + suffix))
        if d.get("reprezentanci"):
            rows.append(("Reprezentanci", ", ".join(d["reprezentanci"])))
        if d.get("wspolnicy"):
            rows.append(("Wspólnicy", ", ".join(d["wspolnicy"])))
        content = [Spacer(1, 4), _data_table(rows, styles), Spacer(1, 4)]
    elif status == "not_found":
        content = [Spacer(1,6), Paragraph("Brak wpisu w Wykazie Podatników VAT.", styles["body"]), Spacer(1,6)]
    elif status == "skipped":
        content = [Spacer(1,6), Paragraph("Moduł wymaga NIP. Wpisz NIP jako zapytanie.", styles["body"]), Spacer(1,6)]
    else:
        msg = result.get("error") or "Nieznany błąd"
        content = [Spacer(1,6), Paragraph(f"Błąd: {msg}", ParagraphStyle("err", parent=styles["body"], textColor=RED)), Spacer(1,6)]

    return _section_box(header, content)


def _section_ceidg(result: dict, styles) -> list:
    status = result.get("status", "error")
    header = _header_row("CEIDG — Jednoosobowe Działalności Gospodarcze", status, "👤", styles)
    d = result.get("data", {})

    if status == "ok" and d:
        firms = d.get("firms", [d] if "nazwa" in d else [])
        content = [Spacer(1, 4)]
        for firm in firms[:5]:
            rows = [
                ("Nazwa", firm.get("nazwa")),
                ("NIP", firm.get("nip")),
                ("REGON", firm.get("regon")),
                ("Status", firm.get("status")),
                ("Adres", firm.get("adres")),
                ("Rozpoczęcie działalności", firm.get("data_rozpoczecia")),
            ]
            if firm.get("data_zawieszenia"):
                rows.append(("Data zawieszenia", firm["data_zawieszenia"]))
            if firm.get("data_wykreslenia"):
                rows.append(("Data wykreślenia", firm["data_wykreslenia"]))
            if firm.get("pkd_przewazajacy"):
                rows.append(("PKD (przeważające)", firm["pkd_przewazajacy"]))
            if firm.get("telefon"):
                rows.append(("Telefon", firm["telefon"]))
            if firm.get("email"):
                rows.append(("E-mail", firm["email"]))
            content.append(_data_table(rows, styles))
            content.append(Spacer(1, 6))
    elif status == "not_found":
        content = [Spacer(1,6), Paragraph("Brak wpisu w CEIDG.", styles["body"]), Spacer(1,6)]
    elif status == "no_token":
        content = [Spacer(1,6), Paragraph("Brak tokenu CEIDG. Ustaw zmienną środowiskową CEIDG_TOKEN.", styles["body"]), Spacer(1,6)]
    else:
        msg = result.get("error") or "Nieznany błąd"
        content = [Spacer(1,6), Paragraph(f"Błąd: {msg}", ParagraphStyle("err", parent=styles["body"], textColor=RED)), Spacer(1,6)]

    return _section_box(header, content)


def _section_krs(result: dict, styles) -> list:
    status = result.get("status", "error")
    header = _header_row("KRS — Krajowy Rejestr Sądowy", status, "🏛", styles)
    d = result.get("data", {})

    if status == "ok" and d:
        rows = [
            ("Nazwa", d.get("nazwa")),
            ("KRS", d.get("krs")),
            ("NIP", d.get("nip")),
            ("REGON", d.get("regon")),
            ("Forma prawna", d.get("forma_prawna")),
            ("Adres", d.get("adres")),
            ("Kapitał zakładowy", d.get("kapital_zakladowy")),
        ]
        if d.get("zarzad"):
            rows.append(("Zarząd", "\n".join(d["zarzad"])))
        content = [Spacer(1, 4), _data_table(rows, styles), Spacer(1, 4)]
    elif status == "not_found":
        content = [Spacer(1,6), Paragraph("Brak wpisu w KRS.", styles["body"]), Spacer(1,6)]
    elif status == "skipped":
        content = [Spacer(1,6), Paragraph(result.get("error", "KRS wymaga NIP lub numeru KRS."), styles["body"]), Spacer(1,6)]
    else:
        msg = result.get("error") or "Nieznany błąd"
        content = [Spacer(1,6), Paragraph(f"Błąd: {msg}", ParagraphStyle("err", parent=styles["body"], textColor=RED)), Spacer(1,6)]

    return _section_box(header, content)


def _section_knf(result: dict, styles) -> list:
    status = result.get("status", "error")
    header = _header_row("KNF — Lista Ostrzeżeń Publicznych", status, "⚠", styles)
    d = result.get("data", {})

    if status == "ok" and d:
        if d.get("found"):
            matches = d.get("matches", [])
            alert = Paragraph(
                f"⚠ UWAGA: Podmiot figuruje na liście ostrzeżeń KNF ({len(matches)} wpis/y).",
                ParagraphStyle("warn", parent=styles["body"], textColor=colors.HexColor("#c05621"),
                               fontName="Helvetica-Bold"))
            content = [Spacer(1,6), alert, Spacer(1,8)]
            for w in matches:
                rows = [
                    ("Firma", w.get("company")),
                    ("KRS", w.get("krs") or "—"),
                    ("Prokurent", w.get("prosecutor") or "—"),
                    ("Data wpisu", w.get("date")),
                    ("Opis", w.get("description") or "—"),
                ]
                content.append(_data_table(rows, styles))
                content.append(Spacer(1, 6))
        else:
            total = d.get("total_in_list", 0)
            ok_text = f"Podmiot nie figuruje na liście ostrzeżeń KNF. Sprawdzono {total} wpisów."
            content = [Spacer(1,6),
                       Paragraph(f"✓ {ok_text}", ParagraphStyle("ok", parent=styles["body"],
                                 textColor=GREEN, fontName="Helvetica-Bold")),
                       Spacer(1,6)]
    else:
        msg = result.get("error") or "Nieznany błąd"
        content = [Spacer(1,6), Paragraph(f"Błąd: {msg}", ParagraphStyle("err", parent=styles["body"], textColor=RED)), Spacer(1,6)]

    return _section_box(header, content)


def _section_uokik(result: dict, styles) -> list:
    status = result.get("status", "error")
    header = _header_row("UOKiK — Decyzje Urzędu Ochrony Konkurencji", status, "⚖", styles)
    d = result.get("data", {})

    if status in ("ok", "not_found"):
        decisions = d.get("decisions", []) if d else []
        if decisions:
            alert = Paragraph(
                f"⚠ Znaleziono {len(decisions)} decyzji UOKiK dotyczących podmiotu.",
                ParagraphStyle("warn", parent=styles["body"], textColor=colors.HexColor("#c05621"),
                               fontName="Helvetica-Bold"))
            content = [Spacer(1,6), alert, Spacer(1,8)]
            for dec in decisions[:20]:
                title = (dec.get("title") or dec.get("url", ""))[:120]
                url = dec.get("url", "")
                content.append(Paragraph(f"• {title}", styles["body"]))
                content.append(Paragraph(url, ParagraphStyle("url", parent=styles["small"],
                    textColor=BLUE)))
                content.append(Spacer(1, 3))
            content.append(Spacer(1, 4))
        else:
            content = [Spacer(1,6),
                       Paragraph("✓ Brak decyzji UOKiK dla podanego podmiotu.",
                                 ParagraphStyle("ok", parent=styles["body"],
                                 textColor=GREEN, fontName="Helvetica-Bold")),
                       Spacer(1,6)]
    else:
        msg = result.get("error") or "Nieznany błąd"
        content = [Spacer(1,6), Paragraph(f"Błąd: {msg}", ParagraphStyle("err", parent=styles["body"], textColor=RED)), Spacer(1,6)]

    return _section_box(header, content)


def _section_rekrutacje(result: dict, styles) -> list:
    status = result.get("status", "error")
    header = _header_row("Rekrutacje — Aktywne Oferty Pracy (pracuj.pl)", status, "💼", styles)
    d = result.get("data", {})

    if status == "ok" and d:
        offers = d.get("offers", [])
        total = d.get("total_count", len(offers))
        days_back = d.get("days_back", 30)
        query_used = d.get("query_used", "")

        summary_text = f"Znaleziono {total} ofert pracy za ostatnie {days_back} dni"
        if total > len(offers):
            summary_text += f" — pokazano pierwszych {len(offers)}"
        summary_text += f" (zapytanie: \"{query_used}\")"

        content = [
            Spacer(1, 6),
            Paragraph(summary_text, ParagraphStyle("sum", parent=styles["body"],
                textColor=BLUE, fontName="Helvetica-Bold")),
            Spacer(1, 10),
        ]

        if total > len(offers):
            content.append(Paragraph(
                f"ℹ Pracuj.pl udostępnia maks. 50 wyników bez logowania. "
                f"Pozostałe {total - len(offers)} ofert dostępne na stronie.",
                ParagraphStyle("note", parent=styles["small"], textColor=GRAY,
                    fontName="Helvetica-Oblique"),
            ))
            content.append(Spacer(1, 8))

        # Tabela ofert
        table_data = [[
            Paragraph("Stanowisko", styles["label"]),
            Paragraph("Firma", styles["label"]),
            Paragraph("Wynagrodzenie", styles["label"]),
            Paragraph("Lokalizacja", styles["label"]),
            Paragraph("Data", styles["label"]),
        ]]

        for offer in offers:
            locations_str = ", ".join(offer.get("locations", []))[:40]
            salary = offer.get("salary") or "—"
            date = offer.get("date", "")[:7]  # YYYY-MM
            table_data.append([
                Paragraph(offer.get("title", "")[:60], styles["value"]),
                Paragraph(offer.get("company", "")[:35], styles["value"]),
                Paragraph(salary[:30], styles["value"]),
                Paragraph(locations_str, styles["value"]),
                Paragraph(date, styles["value"]),
            ])

        col_widths = [5.5*cm, 3.5*cm, 3*cm, 3*cm, 1.8*cm]
        offers_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        row_count = len(table_data)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, BLUE),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        for i in range(2, row_count, 2):
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), LGRAY))
        offers_table.setStyle(TableStyle(style_cmds))
        # Tabela może być wielostronicowa — zwracamy ją poza section_box
        flowables = [header]
        flowables += [Spacer(1, 6),
                      Paragraph(summary_text, ParagraphStyle("sum", parent=styles["body"],
                          textColor=BLUE, fontName="Helvetica-Bold")),
                      Spacer(1, 6)]
        if total > len(offers):
            flowables.append(Paragraph(
                f"ℹ Pracuj.pl udostępnia maks. 50 wyników bez logowania. "
                f"Pozostałe {total - len(offers)} ofert dostępne na stronie.",
                ParagraphStyle("note", parent=styles["small"], textColor=GRAY,
                    fontName="Helvetica-Oblique")))
            flowables.append(Spacer(1, 6))
        flowables.append(offers_table)
        flowables.append(Spacer(1, 14))
        return flowables

    elif status == "not_found":
        content = [Spacer(1, 6),
                   Paragraph("Brak aktywnych ofert pracy dla podanej nazwy firmy.", styles["body"]),
                   Spacer(1, 6)]
    elif status == "skipped":
        content = [Spacer(1, 6),
                   Paragraph(result.get("error", "Moduł wymaga nazwy firmy."), styles["body"]),
                   Spacer(1, 6)]
    else:
        msg = result.get("error") or "Nieznany błąd"
        content = [Spacer(1, 6),
                   Paragraph(f"Błąd: {msg}",
                              ParagraphStyle("err", parent=styles["body"], textColor=RED)),
                   Spacer(1, 6)]

    return _section_box(header, content)


SECTION_BUILDERS = {
    "vat": _section_vat,
    "ceidg": _section_ceidg,
    "krs": _section_krs,
    "knf": _section_knf,
    "uokik": _section_uokik,
    "rekrutacje": _section_rekrutacje,
}


# ── Główna funkcja ────────────────────────────────────────────────────────────
def generate_pdf(
    query: str,
    query_type: str,
    results: dict,
    modules_meta: dict,
    selected: list[str],
) -> bytes:
    buf = BytesIO()
    styles = _build_styles()

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2.5*cm,
        title=f"Raport OSINT — {query}",
        author="OSINT Toolkit",
    )

    W = A4[0] - 4*cm  # szerokość treści

    def on_page(canvas, doc):
        canvas.saveState()
        # Header bar
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 1.4*cm, A4[0], 1.4*cm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(2*cm, A4[1] - 0.9*cm, "OSINT Toolkit")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#a0aec0"))
        canvas.drawRightString(A4[0] - 2*cm, A4[1] - 0.9*cm, query)
        # Footer line
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.setLineWidth(0.5)
        canvas.line(2*cm, 1.8*cm, A4[0] - 2*cm, 1.8*cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GRAY)
        canvas.drawString(2*cm, 1.1*cm, "OSINT Toolkit · Dane z publicznych rejestrów · Nie stanowi porady prawnej")
        canvas.drawRightString(A4[0] - 2*cm, 1.1*cm, f"Strona {doc.page}")
        canvas.restoreState()

    frame = Frame(2*cm, 2.5*cm, W, A4[1] - 4.5*cm, id="main")
    template = PageTemplate(id="main", frames=[frame], onPage=on_page)
    doc.addPageTemplates([template])

    story = []

    # ── Cover block ──────────────────────────────────────────────────────
    cover = Table([
        [Paragraph("🔍 OSINT Toolkit", styles["title"])],
        [Paragraph("Raport Wywiadowczy — Publiczne Rejestry Gospodarcze", styles["subtitle"])],
    ], colWidths=[W])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("TOPPADDING", (0,0), (-1,-1), 14),
        ("BOTTOMPADDING", (0,0), (-1,-1), 14),
        ("LEFTPADDING", (0,0), (-1,-1), 20),
        ("RIGHTPADDING", (0,0), (-1,-1), 20),
        ("ROUNDEDCORNERS", (0,0), (-1,-1), [8,8,8,8]),
    ]))
    story.append(cover)
    story.append(Spacer(1, 12))

    # ── Meta row ─────────────────────────────────────────────────────────
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    meta_data = [
        [Paragraph("Podmiot", styles["label"]),
         Paragraph("Typ zapytania", styles["label"]),
         Paragraph("Źródła", styles["label"]),
         Paragraph("Data", styles["label"])],
        [Paragraph(query, ParagraphStyle("q", parent=styles["value"], fontSize=11, fontName="Helvetica-Bold")),
         Paragraph(query_type, styles["value"]),
         Paragraph(str(len(selected)), styles["value"]),
         Paragraph(generated_at, styles["value"])],
    ]
    meta_t = Table(meta_data, colWidths=[W*0.45, W*0.15, W*0.15, W*0.25])
    meta_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), LGRAY),
        ("BACKGROUND", (0,1), (-1,1), WHITE),
        ("BOX", (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("LINEBELOW", (0,0), (-1,0), 0.5, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("ROUNDEDCORNERS", (0,0), (-1,-1), [4,4,4,4]),
    ]))
    story.append(meta_t)
    story.append(Spacer(1, 20))

    # ── Sekcje modułów ────────────────────────────────────────────────────
    for mod_key in selected:
        if mod_key not in results:
            continue
        builder = SECTION_BUILDERS.get(mod_key)
        if builder:
            flowables = builder(results[mod_key], styles)
            story.extend(flowables)

    doc.build(story)
    return buf.getvalue()
