#!/usr/bin/env python3
"""Build the budget workbook in the 2025_budget column layout.

One sheet per month. Each category is an amount column plus a description
column. Bank rows end with [mbank] or [pko]. Other filled rows are manual and
must be kept. Card repayments are listed under the totals and are not added
into spending. Stdlib only.
"""
import argparse, datetime, json, zipfile
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
PAIRS = [(chr(ord("A") + i * 2), chr(ord("B") + i * 2)) for i in range(len(CATS))]
EMPTY = 8
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def classify(tx):
    title = f"{tx.get('title') or ''} {tx.get('counterparty') or ''}".lower()
    cat = (tx.get("category") or "").lower()
    try:
        amount = float(tx.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if any(k in title for k in ("splata karty", "spłata karty", "spłata karty kredytowej")):
        return "transfer"
    if amount > 0:
        return "income"
    if "yana" in title or "dla par" in title:
        return "Yana"
    if any(k in title for k in ("piwo", "alkohol", "wino", "whisky", "wódka", "wodka")):
        return "Alkohol"
    food_out = ("uber eats", "eats pending", "restauracj", "cafe", "cukrownia", "gospoda", "gastronom", "chef")
    if cat == "eating_out" or any(k in title for k in food_out):
        return "Jedzenie zamawiane i na mieście"
    groceries = ("biedronka", "żabka", "zabka", "lidl", "carrefour", "auchan", "piernik")
    if cat == "groceries" or any(k in title for k in groceries):
        return "Produkty spożywcze"
    if cat == "travel" or any(k in title for k in ("easyjet", "ryanair", "wizz", "airbnb", "booking.com")):
        return "wydatki w podróży"
    ride = ("bolt", "uber", "intercity", "pkp", "circle k", "jet wash", "uber.com")
    if cat == "transport" or any(k in title for k in ride):
        return "Transport"
    subs = ("google", "youtube", "x corp", "chatgpt", "netflix", "opłata za rachunek", "oplata za rachunek")
    if cat in {"it_services", "entertainment", "bank_fees"} or any(k in title for k in subs):
        return "Opłaty cykliczne"
    if cat == "donations" or "zrzutka" in title:
        return "Dobry uczynek"
    health = ("apteka", "psycholog", "terapia", "medicover", "barber", "mikro", "leki")
    if cat in {"health", "personal_care"} or any(k in title for k in health):
        return "Rozwój osobisty i zdrowie"
    return "Reszta"


def month_key(date_text):
    return date_text[:7]


def month_title(key):
    year, month = key.split("-")
    names = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
             "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    return f"{names[int(month) - 1]} {year}"


def desc_of(tx):
    title = (tx.get("title") or tx.get("counterparty") or "przelew").strip()
    pending = " pending" if tx.get("pending") else ""
    source = tx.get("source") or "mbank"
    return f"{tx.get('date')} {title}{pending} [{source}]"


def group(txs):
    out = {}
    for tx in txs:
        key = month_key(tx["date"])
        bucket = out.setdefault(key, {name: [] for name in CATS})
        bucket.setdefault("income", [])
        bucket.setdefault("transfer", [])
        kind = classify(tx)
        amount = abs(float(tx["amount"]))
        line = (round(amount, 2), desc_of(tx))
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


def col_row(col, row):
    return f"{col}{row}"


def cell(ref, value=None, formula=None):
    if formula:
        return f'<c r="{ref}"><f>{escape(formula)}</f></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    if value in (None, ""):
        return ""
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def sheet_xml(bucket, note):
    height = max((len(bucket.get(name, [])) for name in CATS), default=0) + EMPTY
    rows = []
    header = "".join(cell(col_row(amount_col, 1), name) for name, (amount_col, _desc) in zip(CATS, PAIRS))
    rows.append(f'<row r="1">{header}</row>')
    for offset in range(height):
        row_n = 2 + offset
        bits = []
        for name, (amount_col, desc_col) in zip(CATS, PAIRS):
            lines = bucket.get(name, [])
            if offset < len(lines):
                amount, text = lines[offset]
                bits.append(cell(col_row(amount_col, row_n), amount))
                bits.append(cell(col_row(desc_col, row_n), text))
        rows.append(f'<row r="{row_n}">{"".join(bits)}</row>')
    sum_row = 2 + height
    bits = []
    for amount_col, desc_col in PAIRS:
        bits.append(cell(col_row(amount_col, sum_row), formula=f"SUM({amount_col}2:{amount_col}{sum_row - 1})"))
        bits.append(cell(col_row(desc_col, sum_row), "SUM"))
    rows.append(f'<row r="{sum_row}">{"".join(bits)}</row>')
    total_row = sum_row + 1
    parts = ",".join(f"{amount_col}{sum_row}" for amount_col, _desc in PAIRS)
    rows.append(
        f'<row r="{total_row}">{cell("I" + str(total_row), "WSZYSTKO")}{cell("K" + str(total_row), formula="SUM(" + parts + ")")}</row>'
    )
    cursor = total_row + 2
    rows.append(f'<row r="{cursor}">{cell("A" + str(cursor), "Przychody")}</row>')
    start_income = cursor + 1
    for amount, text in bucket.get("income", []):
        cursor += 1
        rows.append(f'<row r="{cursor}">{cell("A" + str(cursor), amount)}{cell("B" + str(cursor), text)}</row>')
    for _ in range(5):
        cursor += 1
    income_sum = cursor + 1
    rows.append(
        f'<row r="{income_sum}">{cell("A" + str(income_sum), formula=f"SUM(A{start_income}:A{income_sum - 1})")}{cell("B" + str(income_sum), "SUM")}</row>'
    )
    cursor = income_sum + 2
    rows.append(f'<row r="{cursor}">{cell("A" + str(cursor), "Spłata karty (poza sumą wydatków)")}</row>')
    for amount, text in bucket.get("transfer", []):
        cursor += 1
        rows.append(f'<row r="{cursor}">{cell("A" + str(cursor), amount)}{cell("B" + str(cursor), text)}</row>')
    if note:
        cursor += 2
        rows.append(f'<row r="{cursor}">{cell("A" + str(cursor), note)}</row>')
    cols = "".join(
        f'<col min="{i}" max="{i}" width="{14 if i % 2 else 42}" customWidth="1"/>' for i in range(1, 21)
    )
    body = "".join(rows)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS}"><cols>{cols}</cols><sheetData>{body}</sheetData></worksheet>'
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
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{overrides}</Types>"
    )


def write_xlsx(grouped, path, note):
    keys = sorted(grouped)
    files = {
        "[Content_Types].xml": content_types(len(keys)),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>"
        ),
    }
    sheet_tags = []
    rels = []
    for i, key in enumerate(keys, start=1):
        files[f"xl/worksheets/sheet{i}.xml"] = sheet_xml(grouped[key], note)
        sheet_tags.append(f'<sheet name="{escape(month_title(key))}" sheetId="{i}" r:id="rId{i}"/>')
        rels.append(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
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


def manual_rows(path):
    import xml.etree.ElementTree as ET
    found = []
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.startswith("xl/worksheets/sheet")]
        for name in sorted(names):
            root = ET.fromstring(zf.read(name))
            for node in root.iter("{%s}t" % NS):
                text = node.text or ""
                if text and not text.endswith("]") and text not in {"SUM", "WSZYSTKO", "Przychody"} \
                        and "[mbank]" not in text and "[pko]" not in text and not text.startswith("Spłata") \
                        and not text.startswith("PKO"):
                    if text not in CATS:
                        found.append(text)
    return found


def cmd_manual(args):
    rows = manual_rows(args.xlsx)
    print(f"OK manual {len(rows)}")
    for row in rows:
        print("- " + row)


def cmd_build(args):
    txs = json.loads(open(args.txs, encoding="utf-8").read())
    if not isinstance(txs, list) or not txs:
        raise SystemExit("ERROR txs file is empty")
    grouped = group(txs)
    note = args.note or ""
    write_xlsx(grouped, args.out, note)
    counts = {key: sum(len(v) for name, v in bucket.items() if name in CATS) for key, bucket in grouped.items()}
    print(f"OK build {args.out} months {len(grouped)} " + " ".join(f"{month_title(k)}:{counts[k]}" for k in sorted(counts)))


def selftest():
    assert classify({"title": "ZABKA", "amount": "-4", "category": "groceries"}) == "Produkty spożywcze"
    assert classify({"title": "UBER * EATS", "amount": "-10", "category": "eating_out"}) == "Jedzenie zamawiane i na mieście"
    assert classify({"title": "SPLATA KARTY", "amount": "-12000", "category": "transport"}) == "transfer"
    assert classify({"title": "MICHAL I YANA - TERAPIA", "amount": "-350", "category": "people"}) == "Yana"
    assert classify({"title": "Przelew środków", "amount": "7000", "category": "income"}) == "income"
    assert classify({"title": "zrzutka.pl", "amount": "-50", "category": "donations"}) == "Dobry uczynek"
    sample = [
        {"date": "2026-10-02", "amount": "-4.00", "title": "ZABKA", "category": "groceries", "source": "mbank"},
        {"date": "2026-11-07", "amount": "-10", "title": "SPLATA KARTY", "category": "transport", "source": "mbank"},
    ]
    grouped = group(sample)
    assert "2026-10" in grouped and "2026-11" in grouped
    assert grouped["2026-11"]["transfer"][0][0] == 10
    import os, tempfile
    path = os.path.join(tempfile.mkdtemp(), "b.xlsx")
    write_xlsx(grouped, path, "note")
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("xl/worksheets/sheet1.xml").decode()
    assert "Produkty spożywcze" in xml and "SUM(A2:" in xml and "[mbank]" in xml
    print("OK selftest")


def build():
    p = argparse.ArgumentParser(prog="budget.py", description="Build the monthly budget workbook.")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--txs", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--note", default="")
    b.set_defaults(fn=cmd_build)
    m = sub.add_parser("manual")
    m.add_argument("--xlsx", required=True)
    m.set_defaults(fn=cmd_manual)
    s = sub.add_parser("selftest")
    s.set_defaults(fn=lambda args: selftest())
    return p


def main(argv=None):
    args = build().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
