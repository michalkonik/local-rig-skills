#!/usr/bin/env python3
"""Build the monthly budget workbook.

One sheet per month. Ten category columns, each an amount plus a description.
Row 1 is the editable budget (default 9000) and what is left. Bank rows end
with [mbank] or [pko]. Other filled rows are manual and must be kept. Card
repayments sit below the total. Stdlib only.
"""
import argparse, json, re, zipfile
from xml.sax.saxutils import escape

CATS = [
    "Produkty spożywcze",
    "Jedzenie zamawiane i na mieście",
    "Transport",
    "Opłaty cykliczne",
    "wydatki w podróży",
    "Alkohol",
    "Dobry uczynek",
    "Rozwój osobisty i zdrowie",
    "Yana",
    "Reszta",
]
GROCERS = (
    ("żabka", "żabka"), ("zabka", "żabka"), ("biedronka", "biedronka"),
    ("lidl", "lidl"), ("carrefour", "carrefour"), ("auchan", "auchan"),
    ("kaufland", "kaufland"), ("netto", "netto"), ("stokrotka", "stokrotka"),
    ("lewiatan", "lewiatan"), ("polo market", "polo market"),
)
HEADER_COLORS = ["1F7A4D", "C46B2C", "1D4E89", "6B4C9A", "0E7C86", "8C3A4B", "A37B12", "2F6F6A", "A14D73", "5C6370"]
TINTS = ["E7F5EE", "FDE8D4", "E7F0FA", "F3E8F8", "E5F6F7", "F8E6EA", "FBF3D8", "E7F4F3", "F8E7F0", "F2F3F5"]
PAIRS = [(chr(ord("A") + i * 2), chr(ord("B") + i * 2)) for i in range(len(CATS))]
EMPTY = 8
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
BANNER = {
    "Budżet miesiąca", "Wydane", "Zostało do końca miesiąca", "SUM", "WSZYSTKO", "Przychody",
    "Edytuj żółte pole. Puste kratki są Twoje.",
}


def _blob(tx):
    return f"{tx.get('title') or ''} {tx.get('counterparty') or ''}".lower()


def _amount(tx):
    try:
        return float(tx.get("amount") or 0)
    except (TypeError, ValueError):
        return 0.0


def trip_on(date, trips):
    for trip in trips or []:
        if trip["start"] <= date <= trip["end"]:
            return trip["name"]
    return None


def classify(tx, trips=None):
    title = _blob(tx)
    cat = (tx.get("category") or "").lower()
    amount = _amount(tx)
    refund = cat == "refunds" and amount > 0
    if any(k in title for k in ("splata karty", "spłata karty", "spłata karty kredytowej")):
        return "transfer"
    if amount > 0 and not refund:
        return "income"
    if "yana" in title or "dla par" in title:
        return "Yana"
    if cat == "donations" or "zrzutka" in title:
        return "Dobry uczynek"
    subs = ("google", "youtube", "x corp", "chatgpt", "netflix", "opłata za rachunek", "oplata za rachunek")
    if cat in {"it_services", "entertainment", "bank_fees"} or any(k in title for k in subs):
        return "Opłaty cykliczne"
    health = ("apteka", "psycholog", "terapia", "medicover", "barber", "mikro", "leki")
    if cat in {"health", "personal_care"} or any(k in title for k in health):
        return "Rozwój osobisty i zdrowie"
    if "revolut" in title:
        return "Reszta"
    trip = trip_on(tx.get("date") or "", trips)
    online = any(k in title for k in ("empik", "allegro", "amazon", "olx"))
    if trip and not online:
        return "wydatki w podróży"
    if any(k in title for k in ("piwo", "alkohol", "wino", "whisky", "wódka", "wodka")):
        return "Alkohol"
    food_out = ("uber eats", "eats pending", "restauracj", "cafe", "cukrownia", "gospoda", "gastronom", "chef")
    if cat == "eating_out" or any(k in title for k in food_out):
        return "Jedzenie zamawiane i na mieście"
    if cat == "groceries" or any(k in title for k in ("biedronka", "żabka", "zabka", "lidl", "carrefour", "auchan", "piernik")):
        return "Produkty spożywcze"
    if cat == "travel" or any(k in title for k in ("easyjet", "ryanair", "wizz", "airbnb", "booking.com")):
        return "wydatki w podróży"
    ride = ("bolt", "uber", "intercity", "pkp", "circle k", "jet wash", "uber.com")
    if cat == "transport" or any(k in title for k in ride):
        return "Transport"
    return "Reszta"


def _purpose(title):
    text = (title or "").strip()
    upper = text.upper()
    for prefix in ("MICHAL KONIK ", "MICHAL I YANA - ", "MICHAL I YANA "):
        if upper.startswith(prefix):
            text = text[len(prefix):].strip(" -")
            upper = text.upper()
    if text.isupper():
        return text[:1].upper() + text[1:].lower()
    return text


def _person(tx):
    cp = tx.get("counterparty") or ""
    if "firehorse" in cp.lower():
        return "Firehorse — " + _purpose(tx.get("title") or "przelew")
    words = [w.strip(".") for w in cp.split() if w.strip(".")]
    words = [w for w in words if w.lower() not in {"psycholog", "terapia"}]
    if len(words) > 3:
        words = words[:3]
    name = " ".join(w.title() if w.isupper() else w for w in words) or "przelew"
    title = (tx.get("title") or "").strip()
    if not title or title.lower() in {"transfer", "przelew"}:
        return name
    return f"{name} — {_purpose(title)}"


def _merchant(title, counterparty):
    raw = (title or counterparty or "przelew").strip()
    low = f"{raw} {counterparty or ''}".lower()
    if "uber eats" in low or "eats pending" in low:
        return "Uber Eats"
    if "uber" in low or low.strip().startswith("ubr"):
        return "Uber"
    if "bolt" in low:
        return "Bolt"
    if "circle k" in low:
        return "Circle K Kraków" if "krakow" in low else "Circle K"
    if "jet wash" in low or "rekawka" in low:
        return "BP Rekawka, myjnia"
    if "intercity" in low:
        return "PKP Intercity"
    if "easyjet" in low:
        return "EasyJet"
    if "youtube" in low:
        return "YouTube Premium"
    if "google one" in low:
        return "Google One"
    if "cloud" in low and "google" in low:
        return "Google Cloud"
    if "x corp" in low:
        return "X Premium"
    if "opłata za rachunek" in low or "oplata za rachunek" in low:
        return "Opłata za rachunek"
    if "revolut" in low:
        return "Revolut, zasilenie"
    if "splata karty" in low or "spłata karty" in low:
        return "Spłata karty"
    if "blik" in low:
        return "Wypłata BLIK"
    if "bankomat" in low or "euronet" in low:
        return "Bankomat Euronet"
    if "media markt" in low:
        shop = re.search(r"p\d+", low)
        return "Media Markt " + shop.group(0).upper() if shop else "Media Markt"
    if "zettle" in low:
        name = re.sub(r"(?i)zettle[_\*\s]*", "", raw)
        name = re.sub(r"\s+", " ", name).strip(" *_")
        return ("Zettle " + (name.title() if name.isupper() else name)).strip()
    if "gastronomi" in low:
        return "Serwis gastronomiczny"
    if "piernik" in low:
        return "Sklep z piernikami"
    if "cukrownia" in low:
        return "Cukrownia Żnin" if "znin" in low else "Cukrownia"
    if "lisboa" in low:
        return "Cafe Lisboa"
    if "chef" in low:
        return "Le Chef Thai"
    if "harnas" in low or "harnaś" in low:
        return "Gospoda Harnaś"
    if "zorza" in low:
        return "Zorza Cafe"
    if "stage24" in low:
        return "Stage24"
    if "empik" in low:
        return "Empik"
    if "decathlon" in low:
        return "Decathlon Kraków"
    if "akisport" in low:
        return "Akisport"
    if "danfarm" in low:
        return "Apteka Danfarm"
    if "apteka" in low:
        return "Apteka"
    if "barber" in low or "kruk" in low:
        return "Kruk Barbershop"
    if "mikrobio" in low:
        return "Centrum badań mikrobiologicznych"
    if "vicenti" in low:
        return "Vicenti"
    if "trafika" in low:
        return "Trafika"
    if "couchsurfing" in low:
        return "Couchsurfing"
    if "distriben" in low:
        return "Distriben"
    if "bonheur" in low:
        return "Nie de Bonheur"
    if "clerydis" in low:
        return "SAS Clerydis"
    if "liya" in low:
        return "Liya"
    if "circulis" in low:
        return "Circulis Patrycja"
    if "medicover" in low:
        return "Medicover Sport"
    if "zrzutka" in low:
        return "zrzutka.pl"
    if "paczkarnia" in low:
        return "Dobra Paczkarnia"
    if "aruba" in low:
        return "Aruba"
    if "monika" in low:
        return "F.H.U. Monika Kuc"
    if "chleb" in low:
        return "Restauracja Chleb i Wi"
    text = re.sub(r"\bK\.\d+\b", "", raw, flags=re.I)
    text = re.sub(r"[*_]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if text.isupper():
        text = text.title()
    return text or "przelew"


def label_of(tx):
    blob = _blob(tx)
    for needle, name in GROCERS:
        if needle in blob:
            return name
    special = ("opłata za rachunek", "oplata za rachunek", "splata karty", "spłata karty", "revolut")
    if any(k in blob for k in special):
        return _merchant(tx.get("title") or "", tx.get("counterparty") or "")
    if not tx.get("counterpartyFromTitle") and tx.get("counterparty"):
        return _person(tx)
    return _merchant(tx.get("title") or "", tx.get("counterparty") or "")


def describe(tx, trip):
    name = label_of(tx)
    if trip and name not in {short for _needle, short in GROCERS}:
        name = f"{name} ({trip})"
    if (tx.get("category") or "") == "refunds" and _amount(tx) > 0:
        name += ", zwrot"
    pending = " pending" if tx.get("pending") else ""
    source = tx.get("source") or "mbank"
    return f"{tx.get('date')} {name}{pending} [{source}]"


def month_key(date_text):
    return date_text[:7]


def month_title(key):
    year, month = key.split("-")
    names = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
             "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    return f"{names[int(month) - 1]} {year}"


def group(txs, trips=None):
    out = {}
    for tx in txs:
        key = month_key(tx["date"])
        bucket = out.setdefault(key, {name: [] for name in CATS})
        bucket.setdefault("income", [])
        bucket.setdefault("transfer", [])
        kind = classify(tx, trips)
        trip = trip_on(tx.get("date") or "", trips) if kind == "wydatki w podróży" else None
        value = round(abs(_amount(tx)), 2)
        if (tx.get("category") or "") == "refunds" and _amount(tx) > 0 and kind not in {"income", "transfer"}:
            value = -value
        line = (value, describe(tx, trip))
        if kind == "income":
            bucket["income"].append(line)
        elif kind == "transfer":
            bucket["transfer"].append(line)
        else:
            bucket[kind].append(line)
    for bucket in out.values():
        for name in list(bucket):
            bucket[name].sort(key=lambda row: row[1])
    return out


class Styles:
    def __init__(self):
        self.fonts = [
            '<font><sz val="11"/><name val="Calibri"/><family val="2"/></font>',
            '<font><b/><sz val="11"/><name val="Calibri"/><family val="2"/></font>',
            '<font><b/><sz val="16"/><name val="Calibri"/><family val="2"/></font>',
            '<font><b/><sz val="14"/><name val="Calibri"/><family val="2"/></font>',
            '<font><i/><sz val="10"/><color rgb="FF6B7280"/><name val="Calibri"/><family val="2"/></font>',
            '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/><family val="2"/></font>',
        ]
        self.fills = [
            '<fill><patternFill patternType="none"/></fill>',
            '<fill><patternFill patternType="gray125"/></fill>',
        ]
        self.borders = [
            "<border/>",
            self._box("thin", "FFD0D5DD"),
            self._box("medium", "FFB8860B"),
            (
                '<border><left style="thin"><color rgb="FFD0D5DD"/></left>'
                '<right style="thin"><color rgb="FFD0D5DD"/></right>'
                '<top style="medium"><color rgb="FF98A2B3"/></top>'
                '<bottom style="thin"><color rgb="FFD0D5DD"/></bottom></border>'
            ),
        ]
        self.xfs = ['<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>']
        self.named = {}

    def _box(self, style, rgb):
        edges = "".join(
            f'<{edge} style="{style}"><color rgb="{rgb}"/></{edge}>' for edge in ("left", "right", "top", "bottom")
        )
        return f"<border>{edges}</border>"

    def fill(self, rgb):
        self.fills.append(
            f'<fill><patternFill patternType="solid"><fgColor rgb="FF{rgb}"/><bgColor indexed="64"/></patternFill></fill>'
        )
        return len(self.fills) - 1

    def xf(self, name, font=0, fill=0, border=0, num=False, horizontal=None, wrap=False):
        self.named[name] = len(self.xfs)
        align = ""
        if horizontal or wrap:
            bits = []
            if horizontal:
                bits.append(f' horizontal="{horizontal}"')
            bits.append(' vertical="center"')
            if wrap:
                bits.append(' wrapText="1"')
            align = "<alignment" + "".join(bits) + "/>"
        apply = ' applyAlignment="1"' if align else ""
        num_id = ' numFmtId="164" applyNumberFormat="1"' if num else ' numFmtId="0"'
        self.xfs.append(
            f'<xf{num_id} fontId="{font}" fillId="{fill}" borderId="{border}"'
            f' applyFont="1" applyFill="1" applyBorder="1"{apply}>{align}</xf>'
        )

    def xml(self):
        fonts = "".join(self.fonts)
        fills = "".join(self.fills)
        borders = "".join(self.borders)
        xfs = "".join(self.xfs)
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<styleSheet xmlns="{NS}">'
            '<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00 &quot;zł&quot;;[Red]-#,##0.00 &quot;zł&quot;"/></numFmts>'
            f'<fonts count="{len(self.fonts)}">{fonts}</fonts>'
            f'<fills count="{len(self.fills)}">{fills}</fills>'
            f'<borders count="{len(self.borders)}">{borders}</borders>'
            f'<cellXfs count="{len(self.xfs)}">{xfs}</cellXfs>'
            '<dxfs count="1"><dxf><font><b/><color rgb="FF9B1C1C"/></font>'
            '<fill><patternFill patternType="solid"><fgColor rgb="FFF4C7C3"/></patternFill></fill></dxf></dxfs>'
            "</styleSheet>"
        )


def make_styles():
    styles = Styles()
    cream = styles.fill("F8F4EC")
    yellow = styles.fill("F6C945")
    green = styles.fill("E3F6D8")
    white = styles.fill("FFFFFF")
    gray = styles.fill("F3F4F6")
    styles.xf("banner", font=1, fill=cream, horizontal="left")
    styles.xf("budget", font=3, fill=yellow, border=2, num=True, horizontal="center")
    styles.xf("left", font=2, fill=green, border=1, num=True, horizontal="center")
    styles.xf("money", font=1, fill=cream, num=True, horizontal="center")
    styles.xf("hint", font=4, fill=cream, horizontal="left")
    styles.xf("section", font=1, fill=cream, horizontal="left")
    styles.xf("desc", font=0, fill=white, border=1, horizontal="left", wrap=True)
    styles.xf("sum", font=1, fill=gray, border=3, num=True)
    styles.xf("sumlabel", font=1, fill=gray, border=3, horizontal="left")
    styles.xf("total", font=2, fill=green, border=1, num=True)
    styles.xf("note", font=4, fill=white, wrap=True)
    for i, rgb in enumerate(HEADER_COLORS):
        styles.xf(f"h{i}", font=5, fill=styles.fill(rgb), border=1, horizontal="center", wrap=True)
    for i, rgb in enumerate(TINTS):
        styles.xf(f"a{i}", font=0, fill=styles.fill(rgb), border=1, num=True)
    return styles


def cell(ref, value=None, formula=None, style=0):
    attr = f' s="{style}"' if style else ""
    if formula:
        return f'<c r="{ref}"{attr}><f>{escape(formula)}</f></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"{attr}><v>{value}</v></c>'
    if value in (None, ""):
        return f'<c r="{ref}"{attr}/>' if style else ""
    return f'<c r="{ref}"{attr} t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def sheet_xml(bucket, note, styles, budget):
    named = styles.named
    height = max((len(bucket.get(name, [])) for name in CATS), default=0) + EMPTY
    header = 3
    first = 4
    last = header + height
    sum_row = last + 1
    total_row = sum_row + 1
    rows = []
    banner = [cell("A1", "Budżet miesiąca", style=named["banner"]),
              cell("B1", budget, style=named["budget"]),
              cell("C1", "Wydane", style=named["banner"]),
              cell("D1", formula=f"B{total_row}", style=named["money"]),
              cell("E1", "Zostało do końca miesiąca", style=named["banner"]),
              cell("F1", formula="B1-D1", style=named["left"]),
              cell("G1", "Edytuj żółte pole. Puste kratki są Twoje.", style=named["hint"])]
    for col in range(8, 21):
        letter = chr(ord("A") + col - 1)
        banner.append(cell(f"{letter}1", style=named["banner"]))
    rows.append(f'<row r="1" ht="32" customHeight="1">{"".join(banner)}</row>')
    rows.append('<row r="2" ht="8" customHeight="1"/>')
    heads = []
    for i, (name, (amount_col, _desc)) in enumerate(zip(CATS, PAIRS)):
        heads.append(cell(f"{amount_col}{header}", name, style=named[f"h{i}"]))
    rows.append(f'<row r="{header}" ht="36" customHeight="1">{"".join(heads)}</row>')
    for offset in range(height):
        row_n = first + offset
        bits = []
        for i, (name, (amount_col, desc_col)) in enumerate(zip(CATS, PAIRS)):
            lines = bucket.get(name, [])
            if offset < len(lines):
                amount, text = lines[offset]
                bits.append(cell(f"{amount_col}{row_n}", amount, style=named[f"a{i}"]))
                bits.append(cell(f"{desc_col}{row_n}", text, style=named["desc"]))
            else:
                bits.append(cell(f"{amount_col}{row_n}", style=named[f"a{i}"]))
                bits.append(cell(f"{desc_col}{row_n}", style=named["desc"]))
        rows.append(f'<row r="{row_n}">{"".join(bits)}</row>')
    sums = []
    for i, (amount_col, desc_col) in enumerate(PAIRS):
        sums.append(cell(f"{amount_col}{sum_row}", formula=f"SUM({amount_col}{first}:{amount_col}{last})", style=named["sum"]))
        sums.append(cell(f"{desc_col}{sum_row}", "SUM", style=named["sumlabel"]))
    rows.append(f'<row r="{sum_row}">{"".join(sums)}</row>')
    parts = ",".join(f"{amount_col}{sum_row}" for amount_col, _desc in PAIRS)
    rows.append(
        f'<row r="{total_row}" ht="24" customHeight="1">'
        f'{cell("A" + str(total_row), "WSZYSTKO", style=named["section"])}'
        f'{cell("B" + str(total_row), formula="SUM(" + parts + ")", style=named["total"])}'
        f'</row>'
    )
    cursor = total_row + 2
    rows.append(f'<row r="{cursor}">{cell("A" + str(cursor), "Przychody", style=named["section"])}</row>')
    start_income = cursor + 1
    for amount, text in bucket.get("income", []):
        cursor += 1
        rows.append(
            f'<row r="{cursor}">{cell("A" + str(cursor), amount, style=named["a9"])}{cell("B" + str(cursor), text, style=named["desc"])}</row>'
        )
    for _ in range(4):
        cursor += 1
        rows.append(
            f'<row r="{cursor}">{cell("A" + str(cursor), style=named["a9"])}{cell("B" + str(cursor), style=named["desc"])}</row>'
        )
    income_sum = cursor + 1
    rows.append(
        f'<row r="{income_sum}">{cell("A" + str(income_sum), formula=f"SUM(A{start_income}:A{income_sum - 1})", style=named["sum"])}'
        f'{cell("B" + str(income_sum), "SUM", style=named["sumlabel"])}</row>'
    )
    cursor = income_sum + 2
    rows.append(f'<row r="{cursor}">{cell("A" + str(cursor), "Spłata karty (poza sumą wydatków)", style=named["section"])}</row>')
    for amount, text in bucket.get("transfer", []):
        cursor += 1
        rows.append(
            f'<row r="{cursor}">{cell("A" + str(cursor), amount, style=named["a2"])}{cell("B" + str(cursor), text, style=named["desc"])}</row>'
        )
    if note:
        cursor += 2
        rows.append(f'<row r="{cursor}" ht="32" customHeight="1">{cell("A" + str(cursor), note, style=named["note"])}</row>')
    cols = "".join(
        f'<col min="{i}" max="{i}" width="{13 if i % 2 else 30}" customWidth="1"/>' for i in range(1, 21)
    )
    merges = "".join(
        f'<mergeCell ref="{amount_col}{header}:{desc_col}{header}"/>' for amount_col, desc_col in PAIRS
    )
    body = "".join(rows)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS}"><sheetPr><tabColor rgb="FF1F7A4D"/></sheetPr>'
        '<sheetViews><sheetView workbookViewId="0" zoomScale="110"><pane ySplit="3" topLeftCell="A4" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'<cols>{cols}</cols><sheetData>{body}</sheetData>'
        f'<mergeCells count="{len(PAIRS)}">{merges}</mergeCells>'
        '<conditionalFormatting sqref="F1"><cfRule type="cellIs" dxfId="0" priority="1" operator="lessThan"><formula>0</formula></cfRule></conditionalFormatting>'
        "</worksheet>"
    )


def content_types(n_sheets):
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, n_sheets + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{overrides}</Types>"
    )


def write_xlsx(grouped, path, note, budget=9000, budgets=None):
    styles = make_styles()
    keys = sorted(grouped)
    files = {
        "[Content_Types].xml": content_types(len(keys)),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
        "xl/styles.xml": styles.xml(),
    }
    sheet_tags = []
    rels = []
    for i, key in enumerate(keys, start=1):
        month_budget = float((budgets or {}).get(key, budget))
        files[f"xl/worksheets/sheet{i}.xml"] = sheet_xml(grouped[key], note, styles, month_budget)
        sheet_tags.append(f'<sheet name="{escape(month_title(key))}" sheetId="{i}" r:id="rId{i}"/>')
        rels.append(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        )
    rels.append(
        f'<Relationship Id="rId{len(keys) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    )
    files["xl/workbook.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{"".join(sheet_tags)}</sheets></workbook>'
    )
    files["xl/_rels/workbook.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels) + "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)


def _sheet_names(zf):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(zf.read("xl/workbook.xml"))
    names = []
    for node in root.iter("{%s}sheet" % NS):
        names.append(node.attrib.get("name") or "")
    return names


def manual_rows(path):
    import xml.etree.ElementTree as ET
    found = []
    with zipfile.ZipFile(path) as zf:
        names = sorted(n for n in zf.namelist() if n.startswith("xl/worksheets/sheet"))
        for name in names:
            root = ET.fromstring(zf.read(name))
            for node in root.iter("{%s}t" % NS):
                text = node.text or ""
                if not text or text in BANNER or text in CATS:
                    continue
                if text.endswith("]") or "[mbank]" in text or "[pko]" in text:
                    continue
                if text.startswith(("Spłata", "PKO", "Edytuj")):
                    continue
                found.append(text)
    return found


def cmd_manual(args):
    rows = manual_rows(args.xlsx)
    print(f"OK manual {len(rows)}")
    for row in rows:
        print("- " + row)


def cmd_budgets(args):
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(args.xlsx) as zf:
        names = _sheet_names(zf)
        sheets = sorted(n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        print(f"OK budgets {len(sheets)}")
        for name, sheet in zip(names, sheets):
            root = ET.fromstring(zf.read(sheet))
            value = ""
            for node in root.iter("{%s}c" % NS):
                if node.attrib.get("r") == "B1":
                    value = "".join(v.text or "" for v in node.iter("{%s}v" % NS))
            print(f"{name}\t{value}")


def _load_trips(path):
    if not path:
        return []
    data = json.loads(open(path, encoding="utf-8").read())
    if not isinstance(data, list):
        raise SystemExit("ERROR trips file must be a list")
    for trip in data:
        if not {"start", "end", "name"} <= set(trip):
            raise SystemExit("ERROR each trip needs start, end, name")
    return data


def cmd_build(args):
    txs = json.loads(open(args.txs, encoding="utf-8").read())
    if not isinstance(txs, list) or not txs:
        raise SystemExit("ERROR txs file is empty")
    trips = _load_trips(args.trips)
    budgets = json.loads(open(args.budgets, encoding="utf-8").read()) if args.budgets else None
    grouped = group(txs, trips)
    write_xlsx(grouped, args.out, args.note or "", budget=args.budget, budgets=budgets)
    counts = {key: sum(len(v) for name, v in bucket.items() if name in CATS) for key, bucket in grouped.items()}
    print(f"OK build {args.out} months {len(grouped)} " + " ".join(f"{month_title(k)}:{counts[k]}" for k in sorted(counts)))


def selftest():
    assert classify({"title": "ZABKA Z5582", "amount": "-4", "category": "groceries"}) == "Produkty spożywcze"
    assert label_of({"title": "ZABKA Z5582 K.2", "counterparty": "Żabka", "counterpartyFromTitle": True}) == "żabka"
    assert label_of({"title": "JMP S.A. BIEDRONKA 580", "counterparty": "Biedronka", "counterpartyFromTitle": True}) == "biedronka"
    assert label_of({"title": "CAFE LISBOA 01", "counterparty": "Cafe Lisboa", "counterpartyFromTitle": True}) == "Cafe Lisboa"
    assert label_of({"title": "Zettle_*JAN KOWAL", "counterparty": "Zettle", "counterpartyFromTitle": True}) == "Zettle Jan Kowal"
    assert classify({"title": "UBER * EATS", "amount": "-10", "category": "eating_out"}) == "Jedzenie zamawiane i na mieście"
    assert classify({"title": "SPLATA KARTY", "amount": "-12000", "category": "transport"}) == "transfer"
    assert classify({"title": "MICHAL I YANA - TERAPIA", "amount": "-350", "category": "people"}) == "Yana"
    assert classify({"title": "Przelew środków", "amount": "7000", "category": "income"}) == "income"
    assert classify({"title": "zrzutka.pl", "amount": "-50", "category": "donations"}) == "Dobry uczynek"
    assert classify({"title": "DECATHLON KRAKOW", "amount": "20", "category": "refunds"}) == "Reszta"
    trips = [{"start": "2026-10-04", "end": "2026-10-07", "name": "Paris"}]
    assert classify({"date": "2026-10-05", "title": "CAFE TEST", "amount": "-10", "category": "other"}, trips) == "wydatki w podróży"
    assert classify({"date": "2026-10-05", "title": "GOOGLE *YouTubePremium", "amount": "-10", "category": "entertainment"}, trips) == "Opłaty cykliczne"
    assert classify({"date": "2026-10-04", "title": "REVOLUT**0102*", "amount": "-10", "category": "other"}, trips) == "Reszta"
    assert classify({"date": "2026-10-05", "title": "ZABKA", "amount": "-4", "category": "groceries"}, trips) == "wydatki w podróży"
    assert describe({"date": "2026-10-05", "title": "ZABKA Z1", "amount": "-4", "category": "groceries", "source": "mbank"}, "Paris").endswith("żabka [mbank]")
    sample = [
        {"date": "2026-10-02", "amount": "-4.00", "title": "ZABKA", "category": "groceries", "source": "mbank", "counterpartyFromTitle": True},
        {"date": "2026-10-05", "amount": "-83.60", "title": "CAFE TEST", "category": "other", "source": "mbank", "counterpartyFromTitle": True},
        {"date": "2026-11-07", "amount": "-10", "title": "SPLATA KARTY", "category": "transport", "source": "mbank"},
    ]
    grouped = group(sample, trips)
    assert grouped["2026-10"]["wydatki w podróży"][0][0] == 83.60
    assert "Cafe Test (Paris)" in grouped["2026-10"]["wydatki w podróży"][0][1]
    assert grouped["2026-11"]["transfer"][0][0] == 10
    import os, tempfile
    path = os.path.join(tempfile.mkdtemp(), "b.xlsx")
    write_xlsx(grouped, path, "PKO note", budget=9000)
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("xl/worksheets/sheet1.xml").decode()
        styles = zf.read("xl/styles.xml").decode()
    assert "Produkty spożywcze" in xml and "SUM(A4:" in xml and "[mbank]" in xml
    assert "Budżet miesiąca" in xml and "<f>B1-D1</f>" in xml and "9000" in xml
    assert "F6C945" in styles and "mergeCell" in xml
    assert "Budżet miesiąca" not in manual_rows(path)
    print("OK selftest")


def build():
    parser = argparse.ArgumentParser(prog="budget.py", description="Build the monthly budget workbook.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    cmd = sub.add_parser("build")
    cmd.add_argument("--txs", required=True)
    cmd.add_argument("--out", required=True)
    cmd.add_argument("--note", default="")
    cmd.add_argument("--trips", default="")
    cmd.add_argument("--budget", type=float, default=9000)
    cmd.add_argument("--budgets", default="")
    cmd.set_defaults(fn=cmd_build)
    manual = sub.add_parser("manual")
    manual.add_argument("--xlsx", required=True)
    manual.set_defaults(fn=cmd_manual)
    budgets = sub.add_parser("budgets")
    budgets.add_argument("--xlsx", required=True)
    budgets.set_defaults(fn=cmd_budgets)
    sub.add_parser("selftest").set_defaults(fn=lambda args: selftest())
    return parser


def main(argv=None):
    args = build().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
