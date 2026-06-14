"""PDF generator — buduje raport przy użyciu ReportLab."""

from __future__ import annotations
from datetime import datetime
from html import escape as _xml_escape
from io import BytesIO
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ── Rejestracja fontów z polskimi znakami ────────────────────────────────────
def _register_fonts():
    # Ścieżka do fontów bundlowanych z projektem (static/fonts/)
    _here = os.path.dirname(os.path.abspath(__file__))
    bundled = os.path.join(_here, "static", "fonts")
    rl_fonts_dir = os.path.dirname(pdfmetrics.__file__).replace("pdfbase", "fonts")

    candidates_regular = [
        os.path.join(bundled, "DejaVuSans.ttf"),           # bundlowany w projekcie (zawsze)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", # Linux
        "/Library/Fonts/Arial Unicode.ttf",                # macOS fallback
        "C:/Windows/Fonts/arialuni.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        os.path.join(rl_fonts_dir, "Vera.ttf"),            # ostateczny fallback (brak PL)
    ]
    candidates_bold = [
        os.path.join(bundled, "DejaVuSans-Bold.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        os.path.join(rl_fonts_dir, "VeraBd.ttf"),
    ]

    reg = next((p for p in candidates_regular if os.path.exists(p)), None)
    bold = next((p for p in candidates_bold if os.path.exists(p)), None)

    if reg:
        pdfmetrics.registerFont(TTFont("UniFont", reg))
    if bold:
        pdfmetrics.registerFont(TTFont("UniFont-Bold", bold))
    elif reg:
        pdfmetrics.registerFont(TTFont("UniFont-Bold", reg))

    return bool(reg)


_UNICODE_FONTS = _register_fonts()
FONT_REGULAR = "UniFont" if _UNICODE_FONTS else FONT_REGULAR
FONT_BOLD    = "UniFont-Bold" if _UNICODE_FONTS else FONT_BOLD
FONT_ITALIC  = FONT_REGULAR  # Vera nie ma oddzielnego oblique


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
        fontSize=22, textColor=WHITE, fontName=FONT_BOLD, leading=28)
    S["subtitle"] = ParagraphStyle("subtitle", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#a0aec0"), fontName=FONT_REGULAR, leading=14)
    S["meta"] = ParagraphStyle("meta", parent=base["Normal"],
        fontSize=8, textColor=colors.HexColor("#a0aec0"), fontName=FONT_REGULAR, leading=12)
    S["section_title"] = ParagraphStyle("section_title", parent=base["Normal"],
        fontSize=11, textColor=WHITE, fontName=FONT_BOLD, leading=16)
    S["body"] = ParagraphStyle("body", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#2d3748"), fontName=FONT_REGULAR, leading=14)
    S["label"] = ParagraphStyle("label", parent=base["Normal"],
        fontSize=9, textColor=GRAY, fontName=FONT_BOLD, leading=14)
    S["value"] = ParagraphStyle("value", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#1a202c"), fontName=FONT_REGULAR, leading=14)
    S["small"] = ParagraphStyle("small", parent=base["Normal"],
        fontSize=8, textColor=GRAY, fontName=FONT_REGULAR, leading=12)
    S["alert_ok"] = ParagraphStyle("alert_ok", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#276749"), fontName=FONT_REGULAR, leading=14,
        backColor=colors.HexColor("#f0fff4"), borderPadding=8)
    S["alert_warn"] = ParagraphStyle("alert_warn", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#c05621"), fontName=FONT_REGULAR, leading=14)
    S["footer"] = ParagraphStyle("footer", parent=base["Normal"],
        fontSize=7.5, textColor=GRAY, fontName=FONT_REGULAR, alignment=TA_CENTER, leading=12)
    S["subject"] = ParagraphStyle("subject", parent=base["Normal"],
        fontSize=15, textColor=NAVY, fontName=FONT_BOLD, leading=20)
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
        textColor=WHITE, fontName=FONT_BOLD, leading=12))]],
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
    header = _header_row("Wykaz Podatników VAT (MF/KAS)", status, "[VAT]", styles)
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



def _section_krs(result: dict, styles) -> list:
    status = result.get("status", "error")
    header = _header_row("KRS — Krajowy Rejestr Sądowy", status, "[KRS]", styles)
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
    header = _header_row("KNF — Lista Ostrzeżeń Publicznych", status, "[KNF]", styles)
    d = result.get("data", {})

    if status == "ok" and d:
        if d.get("found"):
            matches = d.get("matches", [])
            alert = Paragraph(
                f"⚠ UWAGA: Podmiot figuruje na liście ostrzeżeń KNF ({len(matches)} wpis/y).",
                ParagraphStyle("warn", parent=styles["body"], textColor=colors.HexColor("#c05621"),
                               fontName=FONT_BOLD))
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
                                 textColor=GREEN, fontName=FONT_BOLD)),
                       Spacer(1,6)]
    else:
        msg = result.get("error") or "Nieznany błąd"
        content = [Spacer(1,6), Paragraph(f"Błąd: {msg}", ParagraphStyle("err", parent=styles["body"], textColor=RED)), Spacer(1,6)]

    return _section_box(header, content)


def _section_uokik(result: dict, styles) -> list:
    status = result.get("status", "error")
    header = _header_row("UOKiK — Decyzje Urzędu Ochrony Konkurencji", status, "[UOK]", styles)
    d = result.get("data", {})

    if status in ("ok", "not_found"):
        decisions = d.get("decisions", []) if d else []
        if decisions:
            alert = Paragraph(
                f"⚠ Znaleziono {len(decisions)} decyzji UOKiK dotyczących podmiotu.",
                ParagraphStyle("warn", parent=styles["body"], textColor=colors.HexColor("#c05621"),
                               fontName=FONT_BOLD))
            content = [Spacer(1,6), alert, Spacer(1,8)]
            for dec in decisions[:20]:
                title = (dec.get("title") or dec.get("url", ""))[:100]
                url = dec.get("url", "")
                link_style = ParagraphStyle("url", parent=styles["small"],
                    textColor=BLUE, fontName=FONT_REGULAR)
                content.append(Paragraph(f"• {_xml_escape(title)}", styles["body"]))
                if url:
                    safe_href = _xml_escape(url, quote=True)
                    display = _xml_escape((url[:90] + "…") if len(url) > 90 else url)
                    content.append(Paragraph(
                        f'<link href="{safe_href}">{display}</link>',
                        link_style,
                    ))
                content.append(Spacer(1, 3))
            content.append(Spacer(1, 4))
        else:
            content = [Spacer(1,6),
                       Paragraph("✓ Brak decyzji UOKiK dla podanego podmiotu.",
                                 ParagraphStyle("ok", parent=styles["body"],
                                 textColor=GREEN, fontName=FONT_BOLD)),
                       Spacer(1,6)]
    else:
        msg = result.get("error") or "Nieznany błąd"
        content = [Spacer(1,6), Paragraph(f"Błąd: {msg}", ParagraphStyle("err", parent=styles["body"], textColor=RED)), Spacer(1,6)]

    return _section_box(header, content)


def _section_rekrutacje(result: dict, styles) -> list:
    status = result.get("status", "error")
    header = _header_row("Rekrutacje — Aktywne Oferty Pracy", status, "[HR]", styles)
    d = result.get("data", {})

    if status == "ok" and d:
        offers = d.get("offers", [])
        total = d.get("total_count", len(offers))
        query_used = d.get("query_used", "")
        sources = d.get("sources", {})

        summary_text = f"Znaleziono {total} ofert pracy (zapytanie: \"{query_used}\")"

        # Statystyki per portal
        source_parts = []
        for src, stat in sources.items():
            cnt = stat.get("count", 0)
            err = stat.get("error")
            source_parts.append(f"{src}: {'błąd' if err else cnt}")
        source_summary = " · ".join(source_parts)

        flowables = [header, Spacer(1, 6)]
        flowables.append(Paragraph(summary_text, ParagraphStyle(
            "sum", parent=styles["body"], textColor=BLUE, fontName=FONT_BOLD)))
        if source_summary:
            flowables.append(Paragraph(source_summary, ParagraphStyle(
                "src", parent=styles["small"], textColor=GRAY)))
        flowables.append(Spacer(1, 10))

        # Subsekcje per portal
        SOURCE_ORDER = ["pracuj.pl", "nofluffjobs.com", "justjoin.it"]
        SOURCE_LABEL = {
            "pracuj.pl": "pracuj.pl",
            "nofluffjobs.com": "NoFluffJobs",
            "justjoin.it": "JustJoin.it",
        }

        col_widths = [5.5*cm, 3*cm, 3*cm, 3.5*cm, 1.3*cm]

        def _offers_table(offer_list):
            tdata = [[
                Paragraph("Stanowisko", styles["label"]),
                Paragraph("Firma", styles["label"]),
                Paragraph("Wynagrodzenie", styles["label"]),
                Paragraph("Lokalizacja", styles["label"]),
                Paragraph("Data", styles["label"]),
            ]]
            for offer in offer_list:
                loc = ", ".join(offer.get("locations", []))[:40]
                salary = offer.get("salary") or "—"
                date = offer.get("date", "")[:7]
                tdata.append([
                    Paragraph(offer.get("title", "")[:60], styles["value"]),
                    Paragraph(offer.get("company", "")[:30], styles["value"]),
                    Paragraph(salary[:28], styles["value"]),
                    Paragraph(loc, styles["value"]),
                    Paragraph(date, styles["value"]),
                ])
            t = Table(tdata, colWidths=col_widths, repeatRows=1)
            rc = len(tdata)
            cmds = [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, BLUE),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
            for i in range(2, rc, 2):
                cmds.append(("BACKGROUND", (0, i), (-1, i), LGRAY))
            t.setStyle(TableStyle(cmds))
            return t

        for src in SOURCE_ORDER:
            src_offers = [o for o in offers if o.get("source") == src]
            stat = sources.get(src, {})
            label = SOURCE_LABEL.get(src, src)

            flowables.append(Paragraph(
                label,
                ParagraphStyle("src_hdr", parent=styles["section_title"],
                               fontSize=9, textColor=NAVY, spaceAfter=4),
            ))

            if stat.get("error"):
                flowables.append(Paragraph(
                    f"Błąd: {stat['error']}",
                    ParagraphStyle("e", parent=styles["small"], textColor=RED),
                ))
            elif not src_offers:
                flowables.append(Paragraph(
                    "Brak ofert.",
                    ParagraphStyle("nb", parent=styles["small"], textColor=GRAY),
                ))
            else:
                flowables.append(_offers_table(src_offers))

            flowables.append(Spacer(1, 10))

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


def _section_whois_dns(result: dict, styles) -> list:
    status = result.get("status", "error")
    header = _header_row("WHOIS / DNS — Analiza Domeny", status, "[DNS]", styles)
    d = result.get("data", {})

    if status == "ok" and d:
        w = d.get("whois", {})
        dns = d.get("dns", {})

        whois_rows = [
            ("Domena", d.get("domain")),
            ("Registrar", w.get("registrar")),
            ("Data rejestracji", w.get("creation_date")),
            ("Data wygaśnięcia", w.get("expiration_date")),
            ("Właściciel / Org", w.get("registrant")),
            ("Kraj rejestracji", w.get("country")),
        ]
        if w.get("is_new"):
            whois_rows.append(("⚠ UWAGA", "Domena zarejestrowana mniej niż 30 dni temu"))
        if w.get("expires_soon"):
            whois_rows.append(("⚠ UWAGA", "Domena wygasa w ciągu 30 dni"))

        dns_rows = [
            ("Adresy IP (A)", ", ".join(dns.get("a_records", [])) or "brak"),
            ("Serwery MX", "\n".join(dns.get("mx_records", [])) or "brak"),
            ("SPF", dns.get("spf") or "❌ BRAK — ryzyko phishingu"),
            ("DMARC", dns.get("dmarc") or "❌ BRAK — ryzyko phishingu"),
        ]

        content = [
            Spacer(1, 4),
            Paragraph("WHOIS", styles["section_title"]),
            _data_table(whois_rows, styles),
            Spacer(1, 8),
            Paragraph("DNS", styles["section_title"]),
            _data_table(dns_rows, styles),
            Spacer(1, 6),
        ]
    elif status == "skipped":
        content = [Spacer(1, 6), Paragraph(result.get("error", "Pominięto."), styles["body"]), Spacer(1, 6)]
    else:
        msg = result.get("error") or "Nieznany błąd"
        content = [Spacer(1, 6), Paragraph(f"Błąd: {msg}", ParagraphStyle("err", parent=styles["body"], textColor=RED)), Spacer(1, 6)]

    return _section_box(header, content)


def _section_powiazania(result: dict, styles) -> list:
    status = result.get("status", "error")
    header = _header_row("Powiązania właścicielskie — Struktura KRS", status, "[POW]", styles)
    d = result.get("data", {})

    if status == "ok" and d:
        board = d.get("board", {})
        content = [Spacer(1, 4)]

        # Nota o anonimizacji
        content.append(Paragraph(
            d.get("note", ""),
            ParagraphStyle("note_rodo", parent=styles["small"], textColor=GRAY,
                           fontName=FONT_ITALIC),
        ))
        content.append(Spacer(1, 8))

        # Dane rejestrowe
        reg_rows = [
            ("Numer KRS", d.get("krs")),
            ("Forma prawna", d.get("forma_prawna")),
            ("Kapitał zakładowy", d.get("kapital_zakladowy")),
        ]
        content.append(_data_table(reg_rows, styles))
        content.append(Spacer(1, 8))

        # Struktura zarządu
        content.append(Paragraph("Organy zarządzające", styles["section_title"]))
        content.append(Spacer(1, 4))

        organ_rows = []
        organ_rows.append(("Organ reprezentacji", board.get("organ_reprezentacji", "—")))
        for pos in board.get("sklad", []):
            organ_rows.append((pos["funkcja"], f"{pos['liczba']} osob{'y' if pos['liczba'] > 1 else 'a'}"))
        if board.get("prokurenci_liczba", 0) > 0:
            organ_rows.append(("Prokurenci", str(board["prokurenci_liczba"])))
        for org in board.get("organy_nadzoru", []):
            organ_rows.append((org["nazwa"], f"{org['liczba_czlonkow']} członków"))

        content.append(_data_table(organ_rows, styles))

        # Sposob reprezentacji
        if board.get("sposob_reprezentacji"):
            content.append(Spacer(1, 6))
            content.append(Paragraph(
                f"Sposób reprezentacji: {board['sposob_reprezentacji'][:250]}",
                ParagraphStyle("repr", parent=styles["small"], textColor=GRAY),
            ))

        # Oddziały
        oddzialy = d.get("oddzialy", [])
        if oddzialy:
            content.append(Spacer(1, 10))
            content.append(Paragraph(f"Oddziały / jednostki terenowe ({len(oddzialy)})", styles["section_title"]))
            content.append(Spacer(1, 4))

            branch_checks = d.get("branch_checks", {})
            branch_rows = []
            for name in oddzialy:
                checks = branch_checks.get(name, {})
                knf_hit = "⚠ KNF" if checks.get("knf", {}).get("hit") else ""
                uokik_hit = f"UOKiK ({checks['uokik']['count']})" if checks.get("uokik", {}).get("hit") else ""
                flags = " ".join(filter(None, [knf_hit, uokik_hit])) or "brak powiązań"
                branch_rows.append((name[:70], flags))

            content.append(_data_table(branch_rows, styles))

        content.append(Spacer(1, 6))
        return _section_box(header, content)

    elif status == "skipped":
        content = [Spacer(1, 6),
                   Paragraph(result.get("error", "Pominięto."), styles["body"]),
                   Spacer(1, 6)]
    elif status == "not_found":
        content = [Spacer(1, 6),
                   Paragraph("Brak wpisu w KRS.", styles["body"]),
                   Spacer(1, 6)]
    else:
        msg = result.get("error") or "Nieznany błąd"
        content = [Spacer(1, 6),
                   Paragraph(f"Błąd: {msg}", ParagraphStyle("err", parent=styles["body"], textColor=RED)),
                   Spacer(1, 6)]

    return _section_box(header, content)


SECTION_BUILDERS = {
    "vat": _section_vat,
    "krs": _section_krs,
    "knf": _section_knf,
    "uokik": _section_uokik,
    "rekrutacje": _section_rekrutacje,
    "whois_dns": _section_whois_dns,
    "powiazania": _section_powiazania,
}


# ── Główna funkcja ────────────────────────────────────────────────────────────
def generate_pdf(
    query: str,
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
        canvas.setFont(FONT_BOLD, 9)
        canvas.drawString(2*cm, A4[1] - 0.9*cm, "OSINT Toolkit")
        canvas.setFont(FONT_REGULAR, 8)
        canvas.setFillColor(colors.HexColor("#a0aec0"))
        canvas.drawRightString(A4[0] - 2*cm, A4[1] - 0.9*cm, query)
        # Footer line
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.setLineWidth(0.5)
        canvas.line(2*cm, 1.8*cm, A4[0] - 2*cm, 1.8*cm)
        canvas.setFont(FONT_REGULAR, 7.5)
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
        [Paragraph("OSINT Toolkit", styles["title"])],
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
        [Paragraph("NIP", styles["label"]),
         Paragraph("Źródła", styles["label"]),
         Paragraph("Data", styles["label"])],
        [Paragraph(query, ParagraphStyle("q", parent=styles["value"], fontSize=11, fontName=FONT_BOLD)),
         Paragraph(str(len(selected)), styles["value"]),
         Paragraph(generated_at, styles["value"])],
    ]
    meta_t = Table(meta_data, colWidths=[W*0.55, W*0.15, W*0.30])
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
