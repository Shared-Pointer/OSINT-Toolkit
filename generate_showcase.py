"""Generuje showcase PDF projektu OSINT Toolkit."""

from __future__ import annotations
import os
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, Image, KeepTogether, PageBreak,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Fonts ─────────────────────────────────────────────────────────────────────
_here = os.path.dirname(os.path.abspath(__file__))
_bundled = os.path.join(_here, "static", "fonts")

def _reg(candidates):
    return next((p for p in candidates if os.path.exists(p)), None)

_r = _reg([os.path.join(_bundled, "DejaVuSans.ttf"),
           "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
_b = _reg([os.path.join(_bundled, "DejaVuSans-Bold.ttf"),
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"])

if _r:
    pdfmetrics.registerFont(TTFont("F", _r))
    pdfmetrics.registerFont(TTFont("FB", _b or _r))
else:
    _r = "Helvetica"; _b = "Helvetica-Bold"
    pdfmetrics.registerFont = lambda *a: None
    F, FB = "Helvetica", "Helvetica-Bold"

F  = "F"  if _r and _r != "Helvetica" else "Helvetica"
FB = "FB" if _r and _r != "Helvetica" else "Helvetica-Bold"

# ── Colours ───────────────────────────────────────────────────────────────────
BLACK  = colors.HexColor("#1a1a1a")
DGRAY  = colors.HexColor("#333333")
MGRAY  = colors.HexColor("#666666")
LGRAY  = colors.HexColor("#f5f5f5")
BORDER = colors.HexColor("#dddddd")
NAVY   = colors.HexColor("#1a1a2e")
BLUE   = colors.HexColor("#2b5ce6")
GREEN  = colors.HexColor("#276749")
CODE_BG = colors.HexColor("#f8f8f8")
CODE_BD = colors.HexColor("#e0e0e0")
WHITE  = colors.white

W_PAGE = A4[0] - 4 * cm

# ── Styles ────────────────────────────────────────────────────────────────────
def styles():
    S = {}
    S["h1"] = ParagraphStyle("h1", fontName=FB, fontSize=22, leading=28,
                              textColor=BLACK, spaceAfter=6, alignment=TA_CENTER)
    S["h2"] = ParagraphStyle("h2", fontName=FB, fontSize=14, leading=19,
                              textColor=BLACK, spaceBefore=18, spaceAfter=6)
    S["h3"] = ParagraphStyle("h3", fontName=FB, fontSize=11, leading=15,
                              textColor=DGRAY, spaceBefore=12, spaceAfter=4)
    S["body"] = ParagraphStyle("body", fontName=F, fontSize=10, leading=15,
                                textColor=DGRAY, alignment=TA_JUSTIFY, spaceAfter=4)
    S["bullet"] = ParagraphStyle("bullet", fontName=F, fontSize=10, leading=15,
                                  textColor=DGRAY, leftIndent=16, spaceAfter=2,
                                  bulletIndent=4)
    S["code"] = ParagraphStyle("code", fontName="Courier", fontSize=8, leading=12,
                                textColor=colors.HexColor("#2d2d2d"),
                                backColor=CODE_BG, leftIndent=10, rightIndent=10,
                                spaceAfter=2, spaceBefore=2)
    S["caption"] = ParagraphStyle("caption", fontName=F, fontSize=8, leading=11,
                                   textColor=MGRAY, alignment=TA_CENTER,
                                   spaceBefore=4, spaceAfter=10)
    S["team"] = ParagraphStyle("team", fontName=F, fontSize=11, leading=18,
                                textColor=DGRAY, alignment=TA_CENTER)
    S["small"] = ParagraphStyle("small", fontName=F, fontSize=8.5, leading=13,
                                 textColor=MGRAY)
    S["badge_label"] = ParagraphStyle("bl", fontName=FB, fontSize=9, leading=13,
                                       textColor=NAVY)
    S["badge_val"] = ParagraphStyle("bv", fontName=F, fontSize=9, leading=13,
                                     textColor=DGRAY)
    S["footer"] = ParagraphStyle("footer", fontName=F, fontSize=7.5, leading=11,
                                  textColor=MGRAY, alignment=TA_CENTER)
    S["italic"] = ParagraphStyle("italic", fontName=F, fontSize=10, leading=15,
                                  textColor=MGRAY, alignment=TA_JUSTIFY)
    return S

# ── Helpers ───────────────────────────────────────────────────────────────────

def hr(color=BORDER, thickness=0.5, space=8):
    return [Spacer(1, space), HRFlowable(width="100%", thickness=thickness,
                                          color=color, spaceAfter=space)]

def section_header(title, S):
    return [
        Spacer(1, 4),
        Paragraph(title, S["h2"]),
        HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=8),
    ]

def subsection(title, S):
    return [Paragraph(title, S["h3"])]

def code_block(lines: list[str], S):
    out = []
    for line in lines:
        out.append(Paragraph(line.replace(" ", "&nbsp;").replace("<", "&lt;").replace(">", "&gt;"),
                             S["code"]))
    bg_table = Table([[Spacer(1, 0)]], colWidths=[W_PAGE])
    bg_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, CODE_BD),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    # Wrap code lines in a styled table
    data = [[Paragraph(l.replace(" ", "&nbsp;").replace("<", "&lt;").replace(">", "&gt;"),
                       S["code"])] for l in lines]
    t = Table(data, colWidths=[W_PAGE])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, CODE_BD),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return [t, Spacer(1, 6)]

def screenshot(path, caption, S, max_w=None, max_h=None):
    max_w = max_w or W_PAGE
    max_h = max_h or 10 * cm
    img = Image(path, width=max_w, height=max_h, kind="proportional")
    border = Table([[img]], colWidths=[W_PAGE])
    border.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [border, Paragraph(caption, S["caption"])]

def two_screenshots(p1, p2, cap1, cap2, S):
    hw = (W_PAGE - 0.5 * cm) / 2
    img1 = Image(p1, width=hw, height=8 * cm, kind="proportional")
    img2 = Image(p2, width=hw, height=8 * cm, kind="proportional")
    t = Table([[img1, img2]], colWidths=[hw, hw], hAlign="CENTER")
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (0, 0), 0.5, BORDER),
        ("BOX", (1, 0), (1, 0), 0.5, BORDER),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    cap = Table([[Paragraph(cap1, S["caption"]), Paragraph(cap2, S["caption"])]],
                colWidths=[hw, hw])
    return [t, cap]

def info_box(text, S, bg=LGRAY):
    t = Table([[Paragraph(text, S["body"])]], colWidths=[W_PAGE])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    return [t, Spacer(1, 8)]

# ── Page callbacks ────────────────────────────────────────────────────────────

def make_on_page(title_text):
    def on_page(canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setFillColor(NAVY)
            canvas.rect(0, A4[1] - 1.2 * cm, A4[0], 1.2 * cm, fill=1, stroke=0)
            canvas.setFillColor(WHITE)
            canvas.setFont(FB, 8)
            canvas.drawString(2 * cm, A4[1] - 0.78 * cm, "Projekt z Cyberbezpieczeństwa")
            canvas.setFont(F, 7.5)
            canvas.setFillColor(colors.HexColor("#a0aec0"))
            canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 0.78 * cm, "OSINT Toolkit")
        # footer
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.4)
        canvas.line(2 * cm, 1.8 * cm, A4[0] - 2 * cm, 1.8 * cm)
        canvas.setFont(F, 7.5)
        canvas.setFillColor(MGRAY)
        canvas.drawString(2 * cm, 1.1 * cm, "Politechnika / Uczelnia, Projekt z Cyberbezpieczenstwa 2025/2026")
        canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Strona {doc.page}")
        canvas.restoreState()
    return on_page

# ── Build document ────────────────────────────────────────────────────────────

IMGS = "/Users/kajetan/OSINT-Toolkit/showcase_imgs"

def build():
    S = styles()
    buf = BytesIO()

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=1.6 * cm, bottomMargin=2.5 * cm,
        title="OSINT Toolkit Showcase",
        author="Kajetan Mieloch, Kacper Wiszniewski, Paweł Szydłowski, Michał Nowakowski, Oskar Chrostowski",
    )
    W = A4[0] - 4 * cm

    frame_p1 = Frame(2 * cm, 2.5 * cm, W, A4[1] - 5 * cm, id="cover")
    frame_rest = Frame(2 * cm, 2.5 * cm, W, A4[1] - 4.2 * cm, id="main")

    def on_page_cover(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDER); canvas.setLineWidth(0.4)
        canvas.line(2 * cm, 1.8 * cm, A4[0] - 2 * cm, 1.8 * cm)
        canvas.setFont(F, 7.5); canvas.setFillColor(MGRAY)
        canvas.drawString(2 * cm, 1.1 * cm, "Politechnika / Uczelnia, Projekt z Cyberbezpieczenstwa 2025/2026")
        canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Strona {doc.page}")
        canvas.restoreState()

    tmpl_cover = PageTemplate(id="cover", frames=[frame_p1], onPage=on_page_cover)
    tmpl_main  = PageTemplate(id="main",  frames=[frame_rest], onPage=make_on_page("OSINT Toolkit"))
    doc.addPageTemplates([tmpl_cover, tmpl_main])

    story = []

    # ══════════════════════════════════════════════════════════════════════════
    # STRONA 1 — TYTUŁOWA
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 1.5 * cm))

    # Tytuł dokumentu
    story.append(Paragraph("Projekt z Cyberbezpieczeństwa", S["h1"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="60%", thickness=1.5, color=NAVY,
                             hAlign="CENTER", spaceAfter=20))
    story.append(Spacer(1, 0.4 * cm))

    # Skład zespołu
    team_data = [
        [Paragraph("<b>Skład zespołu</b>", ParagraphStyle("th", fontName=FB, fontSize=11,
                    leading=16, alignment=TA_CENTER, textColor=BLACK))],
        [Paragraph("inż. Kajetan Mieloch", S["team"])],
        [Paragraph("inż. Kacper Wiszniewski", S["team"])],
        [Paragraph("inż. Paweł Szydłowski", S["team"])],
        [Paragraph("inż. Michał Nowakowski", S["team"])],
        [Paragraph("inż. Oskar Chrostowski", S["team"])],
    ]
    team_t = Table(team_data, colWidths=[W])
    team_t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(team_t)
    story.append(Spacer(1, 0.6 * cm))

    # Temat
    topic_t = Table([
        [Paragraph("<b>Temat pracy</b>", ParagraphStyle("th2", fontName=FB, fontSize=11,
                    leading=16, textColor=BLACK))],
        [Paragraph(
            "OSINT Toolkit: Zintegrowany system automatycznego zbierania, korelacji "
            "i wizualizacji informacji wywiadowczych o organizacji z wykorzystaniem technik "
            "open-source intelligence, web scrapingu i analizy publicznych rejestrów gospodarczych",
            S["body"]
        )],
        [Spacer(1, 4)],
        [Paragraph(
            "<i>Tematyka nr 5: Środowisko zagrożeń cyberbezpieczeństwa. Identyfikacja zagrożeń. "
            "Przykłady incydentów i określanie sposobów ich zapobiegania, minimalizacji wystąpień.</i>",
            S["italic"]
        )],
    ], colWidths=[W])
    topic_t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(topic_t)
    story.append(Spacer(1, 0.6 * cm))

    # Cel pracy
    cel_t = Table([
        [Paragraph("<b>Cel pracy</b>", ParagraphStyle("th3", fontName=FB, fontSize=11,
                    leading=16, textColor=BLACK))],
        [Paragraph(
            "Celem projektu jest zaprojektowanie i zbudowanie modularnego toolkitu OSINT, który "
            "na podstawie jednego inputu (NIP, numer KRS lub nazwa firmy) automatycznie odpytuje "
            "sześć publicznych rejestrów: Wykaz Podatników VAT (MF/KAS), CEIDG, KRS, listę "
            "ostrzeżeń KNF, decyzje UOKiK oraz aktywne ogłoszenia o pracę (pracuj.pl). "
            "Wyniki są korelowane i eksportowane w formie raportu PDF gotowego do analizy.",
            S["body"]
        )],
    ], colWidths=[W])
    cel_t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(cel_t)
    story.append(Spacer(1, 0.6 * cm))

    # Status projektu
    status_t = Table([
        [Paragraph("<b>Status projektu</b>", ParagraphStyle("ts", fontName=FB, fontSize=11,
                    leading=16, textColor=BLACK))],
        [Paragraph(
            "Projekt zrealizowany w gałęzi deweloperskiej i scalony do <b>main</b> poprzez Pull Request "
            "po weryfikacji wszystkich modułów na danych rzeczywistych. "
            "Aplikacja działa jako serwer Flask dostępny lokalnie pod <b>http://localhost:5001</b>.",
            S["body"]
        )],
    ], colWidths=[W])
    status_t.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(status_t)

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STRONA 2 — ARCHITEKTURA I METODOLOGIA
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_header("1. Architektura i metodologia", S))

    story.append(Paragraph(
        "System zbudowany jest w architekturze modularnej. Każdy moduł jest niezależnym "
        "komponentem odpytywanym rownolegle, a aplikacja Flask uruchamia go w osobnym watku "
        "(ThreadPoolExecutor), co minimalizuje czas oczekiwania na wynik.",
        S["body"]
    ))
    story.append(Spacer(1, 8))

    # Tabela modułów
    mod_header = [
        Paragraph("Moduł", ParagraphStyle("mh", fontName=FB, fontSize=9, leading=13, textColor=WHITE)),
        Paragraph("Źródło", ParagraphStyle("mh", fontName=FB, fontSize=9, leading=13, textColor=WHITE)),
        Paragraph("Metoda dostępu", ParagraphStyle("mh", fontName=FB, fontSize=9, leading=13, textColor=WHITE)),
        Paragraph("Wymagany input", ParagraphStyle("mh", fontName=FB, fontSize=9, leading=13, textColor=WHITE)),
    ]
    mod_rows = [
        ["VAT / MF/KAS", "api.mf.gov.pl", "REST API (JSON)", "NIP"],
        ["CEIDG", "dane.biznes.gov.pl", "REST API (JSON)", "NIP / nazwa"],
        ["KRS", "api-krs.ms.gov.pl", "REST API (JSON)", "NIP / KRS"],
        ["KNF Ostrzeżenia", "knf.gov.pl", "Web scraping (Playwright)", "nazwa / NIP"],
        ["UOKiK Decyzje", "decyzje.uokik.gov.pl", "Web scraping (Playwright)", "nazwa"],
        ["Rekrutacje", "pracuj.pl", "Scraping __NEXT_DATA__ JSON", "nazwa firmy"],
    ]
    sv = ParagraphStyle("mv", fontName=F, fontSize=9, leading=13, textColor=DGRAY)
    table_data = [mod_header] + [[Paragraph(c, sv) for c in row] for row in mod_rows]
    mod_t = Table(table_data, colWidths=[3.2 * cm, 3.8 * cm, 4.2 * cm, 3 * cm])
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), FB),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, BLUE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for i in range(2, len(table_data), 2):
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), LGRAY))
    mod_t.setStyle(TableStyle(style_cmds))
    story.append(mod_t)
    story.append(Spacer(1, 12))

    story.extend(subsection("Przepływ danych", S))
    story.append(Paragraph(
        "Użytkownik podaje NIP, numer KRS lub nazwę firmy. System automatycznie wykrywa typ "
        "zapytania (lub pozwala wybrać ręcznie). Moduły wymagające nazwy firmy (KNF, UOKiK, "
        "Rekrutacje) najpierw pobierają pełną nazwę z rejestru VAT. Wszystkie moduły są "
        "wykonywane współbieżnie. Po zebraniu wyników generowany jest raport PDF.",
        S["body"]
    ))
    story.append(Spacer(1, 8))

    # Pipeline diagram jako tabela
    pipeline = ["NIP / KRS / Nazwa", "→", "Auto-detekcja typu", "→",
                "ThreadPoolExecutor (6 wątków)", "→", "Raport PDF"]
    pipe_cells = [[Paragraph(step,
                    ParagraphStyle("ps", fontName=FB if i % 2 == 0 else F,
                                   fontSize=8.5, leading=13,
                                   textColor=WHITE if i % 2 == 0 else MGRAY,
                                   alignment=TA_CENTER))
                   for i, step in enumerate(pipeline)]]
    widths = [3.2 * cm, 0.5 * cm, 2.8 * cm, 0.5 * cm, 4.2 * cm, 0.5 * cm, 2.5 * cm]
    pipe_t = Table(pipe_cells, colWidths=widths)
    pipe_style = [
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in [0, 2, 4, 6]:
        pipe_style.append(("BACKGROUND", (i, 0), (i, 0), NAVY))
        pipe_style.append(("ROUNDEDCORNERS", (i, 0), (i, 0), [4, 4, 4, 4]))
    pipe_t.setStyle(TableStyle(pipe_style))
    story.append(pipe_t)
    story.append(Spacer(1, 16))

    # ── 2. Implementacja — snippet kodu ───────────────────────────────────────
    story.extend(section_header("2. Implementacja: kluczowe fragmenty kodu", S))

    story.extend(subsection("2.1 Rownolegle wykonywanie modulow (app.py)", S))
    story.append(Paragraph(
        "Kazdy wybrany modul uruchamiany jest w osobnym watku. Dzieki temu czas odpowiedzi "
        "to czas najwolniejszego modulu, a nie suma wszystkich.",
        S["body"]
    ))
    story.append(Spacer(1, 6))
    story.extend(code_block([
        "# Run all selected modules in parallel threads",
        "with ThreadPoolExecutor(max_workers=len(remaining)) as executor:",
        "    futures = {",
        "        executor.submit(_run_module, name): name",
        "        for name in remaining if name in MODULES",
        "    }",
        "    for future in as_completed(futures):",
        "        name = futures[future]",
        "        try:",
        "            results[name] = future.result(timeout=60)",
        "        except Exception as e:",
        "            results[name] = {\"status\": \"error\", \"error\": str(e)}",
    ], S))

    story.extend(subsection("2.2 Web scraping pracuj.pl: ekstrakcja z __NEXT_DATA__ (rekrutacje.py)", S))
    story.append(Paragraph(
        "Modul rekrutacji uruchamia przegladarke Chromium (bezglowa) przez Playwright, "
        "akceptuje cookies i wyciaga dane ofert z wbudowanego w strone bloku JSON "
        "<b>__NEXT_DATA__</b>, bez parsowania HTML.",
        S["body"]
    ))
    story.append(Spacer(1, 6))
    story.extend(code_block([
        "# Ekstrakcja danych ofert ze struktury Next.js",
        "m = re.search(r'id=\"__NEXT_DATA__\"[^>]*>(.*?)</script>',",
        "              html, re.DOTALL)",
        "data = json.loads(m.group(1))",
        "queries = data[\"props\"][\"pageProps\"][\"dehydratedState\"][\"queries\"]",
        "",
        "for q in queries:",
        "    if \"jobOffers\" in str(q.get(\"queryKey\", \"\")):",
        "        grouped_offers = q[\"state\"][\"data\"].get(\"groupedOffers\", [])",
        "        total_count    = q[\"state\"][\"data\"].get(\"offersTotalCount\", 0)",
        "        break",
    ], S))

    story.extend(subsection("2.3 Scraping listy ostrzezen KNF (knf.py)", S))
    story.append(Paragraph(
        "Lista ostrzezen KNF pobierana jest jednorazowo i cache'owana na 6 godzin "
        "w pamieci procesu. Playwright renderuje strone do stanu <i>networkidle</i>, "
        "a nastepnie iteruje po wierszach tabeli.",
        S["body"]
    ))
    story.append(Spacer(1, 6))
    story.extend(code_block([
        "CACHE_TTL = 3600 * 6  # 6h in-memory cache",
        "",
        "def _get_all_warnings() -> list[dict]:",
        "    if _cache[\"data\"] and (time.time() - _cache[\"ts\"]) < CACHE_TTL:",
        "        return _cache[\"data\"]  # cache hit, skip network",
        "",
        "    page.goto(\"https://www.knf.gov.pl/dla_konsumenta/ostrzezenia_publiczne\")",
        "    page.wait_for_load_state(\"networkidle\", timeout=60000)",
        "",
        "    for row in page.query_selector_all(\"tr.warning-row\"):",
        "        tds = row.query_selector_all(\"td\")",
        "        if len(tds) == 6:",
        "            data.append({\"company\": tds[1].inner_text(), ...})",
    ], S))

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STRONA 3 — GIT WORKFLOW
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_header("3. Workflow Git: galerie i Pull Request", S))

    story.append(Paragraph(
        "Projekt prowadzony był z zachowaniem standardowego git-flow: nowe funkcjonalności "
        "powstawały na dedykowanych gałęziach tematycznych, a integracja z <b>main</b> "
        "odbywała się wyłącznie przez Pull Request po weryfikacji działania wszystkich modułów.",
        S["body"]
    ))
    story.append(Spacer(1, 10))

    # Branch diagram jako tabela
    branches = [
        ("main", "Galaz produkcyjna, stabilna wersja toolkitu"),
        ("feature/flask-app", "Szkielet aplikacji Flask, routing, UI (templates + static)"),
        ("feature/vat-krs-modules", "Moduly REST API: VAT (MF/KAS) i KRS (MS)"),
        ("feature/ceidg-module", "Modul CEIDG, jednoosobowe dzialalnosci gospodarcze"),
        ("feature/knf-uokik-scraping", "Scraping KNF i UOKiK przy uzyciu Playwright"),
        ("feature/rekrutacje-pracujpl", "Scraping ofert pracy pracuj.pl (__NEXT_DATA__)"),
        ("feature/pdf-generator", "Generator raportow PDF (ReportLab) z polskimi fontami"),
        ("feature/parallel-execution", "Refaktor: rownolegle wykonanie modulow (ThreadPoolExecutor)"),
    ]
    bh = ParagraphStyle("bh", fontName=FB, fontSize=9, leading=13, textColor=WHITE)
    bv = ParagraphStyle("bv", fontName=F, fontSize=9, leading=13, textColor=DGRAY)
    bname = ParagraphStyle("bn", fontName="Courier", fontSize=8.5, leading=13,
                            textColor=colors.HexColor("#2b5ce6"))
    b_data = [[Paragraph("Gałąź", bh), Paragraph("Zakres zmian", bh)]]
    for name, desc in branches:
        bg_col = NAVY if name == "main" else None
        text_col = WHITE if name == "main" else colors.HexColor("#2b5ce6")
        b_data.append([
            Paragraph(name, ParagraphStyle("bn2",
                                            fontName=FB if name == "main" else "Courier",
                                            fontSize=8.5, leading=13, textColor=text_col)),
            Paragraph(desc, bv),
        ])
    b_t = Table(b_data, colWidths=[4.5 * cm, None])
    b_style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#e8f0fe")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, BLUE),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for i in range(3, len(b_data), 2):
        b_style.append(("BACKGROUND", (0, i), (-1, i), LGRAY))
    b_t.setStyle(TableStyle(b_style))
    story.append(b_t)
    story.append(Spacer(1, 12))

    story.extend(info_box(
        "<b>Pull Request do main:</b> Po zakończeniu implementacji wszystkich gałęzi "
        "przeprowadzono ręczne testy end-to-end na kilku podmiotach (m.in. WSB Merito, "
        "spółki z KRS, osoby fizyczne). PR zatwierdzony i scalony do <b>main</b>. "
        "Gałąź main reprezentuje aktualną, działającą wersję toolkitu.",
        S
    ))

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STRONA 4–5 — DEMO: WSB MERITO
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_header("4. Demo: Uniwersytet WSB Merito (NIP: 8942450411)", S))

    story.append(Paragraph(
        "Jako przykład testowy wybrano <b>Uniwersytet WSB Merito we Wrocławiu</b>. "
        "Proces: wpisanie NIP w interfejsie, wybór trybu <i>NIP</i> z rozwijanej listy, "
        "zaznaczenie wszystkich zrodel, klikniecie 'Generuj raport PDF'.",
        S["body"]
    ))
    story.append(Spacer(1, 8))

    story.extend(two_screenshots(
        f"{IMGS}/16.png", f"{IMGS}/15.png",
        "Rys. 1. Interfejs z NIP 8942450411 (WSB Merito), trwa generowanie raportu",
        "Rys. 2. Interfejs z NIP 8731247021 (Marek Padlo), trwa generowanie raportu",
        S
    ))
    story.append(Spacer(1, 6))

    story.extend(screenshot(
        f"{IMGS}/10.png",
        "Rys. 3. Wygenerowany raport WSB Merito, sekcja VAT (MF/KAS): dane rejestrowe, "
        "status VAT Czynny, 94 rachunki bankowe. Sekcja KRS: brak wpisu.",
        S, max_h=11 * cm
    ))

    story.append(PageBreak())

    story.extend(screenshot(
        f"{IMGS}/12.png",
        "Rys. 4. Raport WSB Merito c.d.: KNF brak wpisu (660 sprawdzonych), "
        "UOKiK 10 decyzji (zbieznosc nazw), Rekrutacje preview.",
        S, max_h=11 * cm
    ))
    story.append(Spacer(1, 6))

    story.extend(screenshot(
        f"{IMGS}/11.png",
        "Rys. 5. Sekcja Rekrutacje: 3 aktywne ogloszenia WSB Merito z pracuj.pl (ostatnie 30 dni).",
        S, max_h=7 * cm
    ))
    story.append(Spacer(1, 10))

    story.extend(info_box(
        "<b>Uwaga dot. wyników UOKiK:</b> Dla WSB Merito system zwrócił 10 decyzji UOKiK. "
        "Po weryfikacji linkow okazalo sie, ze sa to zbieznosci nazw, a decyzje dotycza innych podmiotow. "
        "Jest to znane ograniczenie obecnej implementacji, brak filtrowania po NIP w wyszukiwarce UOKiK. "
        "Podejscie to zapewnia wysoka kompletosc wynikow (recall) kosztem precyzji, "
        "nigdy nie pomijamy istotnych trafien, choc moga pojawic sie wyniki nadmiarowe. "
        "Poprawa precyzji filtrowania zaplanowana jest jako jeden z kolejnych krokow.",
        S
    ))

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STRONA 6 — DEMO: KNF ALERT
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_header("5. Demo: podmiot z wpisem w KNF (NIP: 8731247021)", S))

    story.append(Paragraph(
        "Drugi przyklad testowy to podmiot <b>Marek Padlo</b> (NIP 8731247021), "
        "ktory figuruje na liscie ostrzezen publicznych KNF. "
        "System poprawnie wykryl i zaraportawal 1 wpis: Handel, Posrednictwo, Uslugi Marek Padlo, "
        "sprawa prowadzona przez Prokurature Okregowa w Warszawie na podstawie "
        "art. 178 w zw. z art. 69 ust. 2 pkt 1 ustawy o obrocie instrumentami finansowymi.",
        S["body"]
    ))
    story.append(Spacer(1, 8))

    story.extend(screenshot(
        f"{IMGS}/13.png",
        "Rys. 6. Raport Marek Padlo, sekcja VAT: status Zwolniony, adres Bogumilowice. Sekcja KRS: brak wpisu.",
        S, max_h=9 * cm
    ))
    story.append(Spacer(1, 6))

    story.extend(screenshot(
        f"{IMGS}/14.png",
        "Rys. 7. Sekcja KNF: alert, podmiot figuruje na liscie ostrzezen (1 wpis). "
        "Szczegoly: firma Handel Posrednictwo Uslugi Marek Padlo, NIP oraz KRS, Prokuratura Okregowa w Warszawie.",
        S, max_h=9 * cm
    ))

    story.append(Spacer(1, 12))

    story.extend(info_box(
        "<b>Wynik:</b> System sprawdza 660+ wpisów listy ostrzeżeń KNF i metodą "
        "fuzzy-match (normalizacja nazwy: usunięcie myślników, spacji, lowercase) "
        "identyfikuje potencjalne trafienia. Dla czystych podmiotów raport wyświetla "
        "zielone potwierdzenie braku wpisu.",
        S
    ))

    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # STRONA 7 — PLANY ROZWOJU
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_header("6. Plany rozwoju", S))

    story.append(Paragraph(
        "Aktualna wersja toolkitu stanowi działający fundament. Poniżej lista "
        "zaplanowanych rozszerzeń w kolejnych iteracjach:",
        S["body"]
    ))
    story.append(Spacer(1, 8))

    roadmap = [
        ("Rozszerzenie modułu Rekrutacje",
         "Aktualnie system scrape'uje wyłącznie pracuj.pl. "
         "W kolejnej wersji planowane jest dodanie 3 kolejnych popularnych portali: "
         "LinkedIn Jobs, NoFluffJobs oraz JustJoin.it, co pozwoli uzyskac pelniejszy "
         "obraz aktywnosci rekrutacyjnej badanego podmiotu."),
        ("Rekurencyjne sprawdzanie powiązań właścicielskich",
         "Planowane jest dodanie modułu, który na podstawie danych z KRS i CEIDG "
         "wyciągnie listę właścicieli / wspólników / zarządu badanej spółki, "
         "a następnie automatycznie sprawdzi każdą z tych osób na listach KNF i UOKiK. "
         "Cel: wykrycie sieci powiązanych podmiotów podejrzanych o działalność niezgodną z prawem."),
        ("Poprawa precyzji wyszukiwania UOKiK",
         "Filtrowanie wyników UOKiK po NIP lub REGON zamiast samej nazwy, "
         "co wyeliminuje fałszywe trafienia wynikające ze zbieżności nazw."),
        ("Moduł WHOIS / DNS",
         "Sprawdzanie domeny powiązanej z firmą: rejestracja domeny, "
         "rekordy MX/SPF/DMARC, przydatne przy analizie phishingu."),
        ("Scoring ryzyka",
         "Automatyczny wskaźnik ryzyka (0–100) obliczany na podstawie "
         "kombinacji wyników: wpis KNF, decyzje UOKiK, status VAT, "
         "aktywność rekrutacyjna vs obroty."),
    ]

    for i, (title, desc) in enumerate(roadmap, 1):
        story.append(KeepTogether([
            Paragraph(f"{i}. {title}", S["h3"]),
            Paragraph(desc, S["body"]),
            Spacer(1, 6),
        ]))

    story.append(Spacer(1, 10))

    # ══════════════════════════════════════════════════════════════════════════
    # ROADBLOCKS
    # ══════════════════════════════════════════════════════════════════════════
    story.extend(section_header("7. Znane blokady i ograniczenia (Roadblocks)", S))

    story.append(Paragraph(
        "W trakcie realizacji projektu zidentyfikowano trzy istotne ograniczenia, "
        "które wpływają na kompletność lub jakość generowanych raportów:",
        S["body"]
    ))
    story.append(Spacer(1, 10))

    RED_BOX = colors.HexColor("#fff5f5")
    RED_BD  = colors.HexColor("#fc8181")
    ORANGE_BOX = colors.HexColor("#fffbeb")
    ORANGE_BD  = colors.HexColor("#f6ad55")
    YELLOW_BOX = colors.HexColor("#fffff0")
    YELLOW_BD  = colors.HexColor("#ecc94b")

    def roadblock_box(number, title, body_text, S, bg, border_col):
        title_p = Paragraph(
            f"<b>#{number} &nbsp; {title}</b>",
            ParagraphStyle("rbt", fontName=FB, fontSize=10, leading=15, textColor=BLACK)
        )
        body_p = Paragraph(body_text, S["body"])
        inner = Table(
            [[title_p], [Spacer(1, 4)], [body_p]],
            colWidths=[W_PAGE - 0.6 * cm]
        )
        inner.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ]))
        outer = Table([[inner]], colWidths=[W_PAGE])
        outer.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("BOX", (0, 0), (-1, -1), 1, border_col),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        return [outer, Spacer(1, 10)]

    story.extend(roadblock_box(
        1,
        "CEIDG: brak dostepu, token wymaga podpisu kwalifikowanego",
        "Modul CEIDG (Centralna Ewidencja i Informacja o Dzialalnosci Gospodarczej) jest "
        "zaimplementowany i gotowy do uzycia, jednak wymaga tokenu API, ktory uzyskac mozna "
        "wylacznie przez formalny wniosek do CEIDG z podpisem kwalifikowanym lub profilem "
        "zaufanym ePUAP. Jest to powazna procedura rzadowa, token nie jest wydawany "
        "automatycznie i wymaga recznej weryfikacji tozsamosci wnioskodawcy. "
        "W konsekwencji modul CEIDG jest dostepny w interfejsie (opcja do zaznaczenia), "
        "ale bez skonfigurowanego tokenu zwraca komunikat 'Brak tokenu CEIDG'. "
        "Ograniczenie to dotyczy danych o jednoosobowych dzialalnosci gospodarczych, "
        "spolki dostepne sa przez KRS, a osoby fizyczne przez VAT MF/KAS.",
        S, RED_BOX, RED_BD
    ))

    story.extend(roadblock_box(
        2,
        "UOKiK: nadmiarowe wyniki z powodu zbieznosci nazw, brak filtrowania po NIP",
        "Wyszukiwarka decyzji UOKiK (decyzje.uokik.gov.pl) nie udostepnia filtrowania "
        "po NIP ani REGON, jedynym dostepnym kryterium jest fraza tekstowa nazwy podmiotu. "
        "W efekcie zapytanie o firme o popularnej nazwie (np. zawierajacej slowa 'WSB', 'Merito', "
        "'Handel', 'Uslugi') moze zwrocic decyzje dotyczace zupelnie innych podmiotow. "
        "Obecna implementacja celowo preferuje wysokie pokrycie (recall) nad precyzja, "
        "lepiej wyswietlic kilka nadmiarowych trafien niz przeoczyc istotny wynik. "
        "Planowane rozwiazanie: post-filtering po NIP/REGON na podstawie tresci dokumentu PDF "
        "decyzji lub rozszerzenie scrappingu o dodatkowy kontekst ze strony wynikow.",
        S, ORANGE_BOX, ORANGE_BD
    ))

    story.extend(roadblock_box(
        3,
        "Zaleznosc od NIP: KRS jako samodzielne zrodlo daje slabsze raporty",
        "Najlepsze i najbogatsze raporty generowane sa przy podaniu NIP jako wejscia. "
        "NIP pozwala odpytac VAT MF/KAS, skad system pobiera pelna nazwe firmy potrzebna "
        "dla modulow KNF, UOKiK i Rekrutacje, a takze identyfikuje rachunki bankowe "
        "i status podatkowy. Przy zapytaniu po numerze KRS modul VAT jest pomijany, "
        "bo VAT API nie obsluguje KRS, a moduly oparte na nazwie firmy sa blokowane "
        "z powodu braku nazwy. Przy zapytaniu po nazwie firmy wyniki sa mniej precyzyjne "
        "ze wzgledu na mozliwe zbieznosci. Rekomendacja: zawsze uzywac NIP jako "
        "podstawowego identyfikatora, numer KRS jest uzywany pomocniczo gdy NIP jest nieznany.",
        S, YELLOW_BOX, YELLOW_BD
    ))

    story.append(Spacer(1, 10))

    story.extend(section_header("8. Podsumowanie", S))

    story.append(Paragraph(
        "OSINT Toolkit dostarcza w jednym miejscu dane z szesciu publicznych rejestrow "
        "i generuje czytelny raport PDF. Zadanie, ktore recznie zajmowaloby kilkanascie minut, "
        "wykonywane jest automatycznie w czasie ponizej 30 sekund. "
        "System jest modularny i gotowy na rozszerzenia. "
        "Kod scalony do gałęzi main, aplikacja uruchomiona i zweryfikowana na danych rzeczywistych.",
        S["body"]
    ))

    # Build
    doc.build(story)
    return buf.getvalue()


if __name__ == "__main__":
    out = "/Users/kajetan/Downloads/osint_toolkit_showcase.pdf"
    pdf_bytes = build()
    with open(out, "wb") as f:
        f.write(pdf_bytes)
    print(f"Wygenerowano: {out} ({len(pdf_bytes) // 1024} KB)")
