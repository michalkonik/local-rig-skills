#!/usr/bin/env python3
"""Claims you are owed: EU261 flight compensation and consumer refund letters (EN + PL). The human sends them.

  claim.py eu261 --from WAW --to BCN --date 2026-08-14 --type delay --delay-h 3.5 --reason technical [--flight LO123]
           [--via FRA] [--eu-carrier yes|no] [--notice-days N] [--reroute-early-h H --reroute-late-h H]
  claim.py letter --kind withdrawal|nonconformity|price-guarantee --shop "Shop" --item "Item" --date 2026-10-01 [--amount 499]
  claim.py sent ID [--date D]       you sent it: starts the 30-day answer clock, logs it in the ledger
  claim.py outcome ID paid|refused [--amount 250 --currency EUR] [--hours 0.5]
  claim.py list | distance WAW BCN
Files go to ~/income/claims/<id>/ (claim.json, letter-en.md, letter-pl.md). Facts and sources: ../reference.md (skill folder)
"""
import argparse, csv, datetime, io, json, math, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "lib"))
import income, ledger  # noqa: E402

CLAIMS = income.INCOME / "claims"
# OurAirports (public domain), ~216 airports: IATA lat lon country. Unknown codes -> airports.csv cached on first use.
AIRPORTS_RAW = """
    BZG 53.0968 17.9777 PL | GDN 54.3776 18.4662 PL | KRK 50.0777 19.7848 PL | KTW 50.4760 19.0807 PL | LUZ 51.2402 22.7135 PL | LCJ 51.7219 19.3981 PL
    WMI 52.4511 20.6518 PL | POZ 52.4216 16.8234 PL | RDO 51.3894 21.2147 PL | RZE 50.1098 22.0242 PL | SZZ 53.5847 14.9022 PL | SZY 53.4819 20.9377 PL
    WAW 52.1657 20.9671 PL | WRO 51.1037 16.8821 PL | IEG 52.1385 15.7986 PL | LHR 51.4707 -0.4599 GB | LGW 51.1487 -0.1857 GB | STN 51.8850 0.2350 GB
    LTN 51.8747 -0.3683 GB | MAN 53.3494 -2.2795 GB | EDI 55.9501 -3.3723 GB | BHX 52.4539 -1.7480 GB | BRS 51.3823 -2.7165 GB | LPL 53.3349 -2.8496 GB
    NCL 55.0380 -1.6896 GB | GLA 55.8719 -4.4331 GB | BFS 54.6575 -6.2158 GB | DUB 53.4287 -6.2621 IE | SNN 52.7020 -8.9248 IE | ORK 51.8413 -8.4911 IE
    CDG 49.0090 2.5541 FR | ORY 48.7295 2.3590 FR | NCE 43.6584 7.2159 FR | LYS 45.7260 5.0901 FR | MRS 43.4381 5.2125 FR | BOD 44.8287 -0.7154 FR
    TLS 43.6291 1.3638 FR | NTE 47.1532 -1.6107 FR | BVA 49.4544 2.1128 FR | AMS 52.3086 4.7639 NL | EIN 51.4501 5.3745 NL | RTM 51.9569 4.4372 NL
    BRU 50.9014 4.4844 BE | CRL 50.4620 4.4596 BE | LUX 49.6268 6.2121 LU | FRA 50.0267 8.5584 DE | MUC 48.3538 11.7861 DE | BER 52.3617 13.5023 DE
    HAM 53.6304 9.9882 DE | DUS 51.2895 6.7668 DE | CGN 50.8659 7.1427 DE | STR 48.6899 9.2220 DE | HHN 49.9464 7.2617 DE | NUE 49.4987 11.0781 DE
    DTM 51.5183 7.6122 DE | HAJ 52.4611 9.6851 DE | LEJ 51.4207 12.2327 DE | BRE 53.0468 8.7893 DE | FMM 47.9881 10.2382 DE | VIE 48.1103 16.5697 AT
    SZG 47.7933 13.0043 AT | ZRH 47.4581 8.5481 CH | GVA 46.2381 6.1090 CH | BSL 47.6007 7.5211 FR | MAD 40.4934 -3.5722 ES | BCN 41.2971 2.0785 ES
    PMI 39.5517 2.7388 ES | AGP 36.6782 -4.5002 ES | ALC 38.2822 -0.5582 ES | VLC 39.4892 -0.4810 ES | IBZ 38.8729 1.3731 ES | SVQ 37.4180 -5.8931 ES
    BIO 43.3011 -2.9106 ES | TFS 28.0445 -16.5725 ES | TFN 28.4828 -16.3417 ES | LPA 27.9319 -15.3866 ES | ACE 28.9455 -13.6052 ES | FUE 28.4527 -13.8638 ES
    LIS 38.7813 -9.1359 PT | OPO 41.2481 -8.6814 PT | FAO 37.0159 -7.9709 PT | FNC 32.6978 -16.7746 PT | PDL 37.7412 -25.6979 PT | FCO 41.8045 12.2520 IT
    CIA 41.7988 12.5953 IT | MXP 45.6306 8.7281 IT | LIN 45.4451 9.2767 IT | BGY 45.6694 9.7089 IT | VCE 45.5053 12.3519 IT | BLQ 44.5354 11.2887 IT
    NAP 40.8860 14.2908 IT | PSA 43.6839 10.3927 IT | CTA 37.4668 15.0664 IT | PMO 38.1760 13.0910 IT | BRI 41.1389 16.7606 IT | CAG 39.2515 9.0543 IT
    TSF 45.6484 12.1944 IT | ATH 37.9364 23.9445 GR | SKG 40.5193 22.9700 GR | HER 35.3397 25.1803 GR | RHO 36.4054 28.0862 GR | CFU 39.6014 19.9122 GR
    KGS 36.7945 27.0911 GR | ZTH 37.7509 20.8843 GR | CHQ 35.5312 24.1507 GR | JTR 36.4000 25.4786 GR | JMK 37.4351 25.3481 GR | LCA 34.8751 33.6249 CY
    PFO 34.7180 32.4857 CY | MLA 35.8459 14.4915 MT | CPH 55.6179 12.6560 DK | BLL 55.7403 9.1570 DK | AAL 57.0948 9.8499 DK | OSL 60.1939 11.1004 NO
    BGO 60.2934 5.2181 NO | TRD 63.4578 10.9240 NO | SVG 58.8767 5.6378 NO | TRF 59.1867 10.2586 NO | ARN 59.6485 17.9288 SE | GOT 57.6628 12.2798 SE
    NYO 58.7897 16.9115 SE | MMX 55.5356 13.3763 SE | HEL 60.3184 24.9633 FI | TLL 59.4132 24.8326 EE | RIX 56.9208 23.9707 LV | VNO 54.6341 25.2858 LT
    KUN 54.9640 24.0858 LT | PRG 50.1009 14.2599 CZ | BRQ 49.1513 16.6940 CZ | BTS 48.1702 17.2127 SK | BUD 47.4302 19.2624 HU | OTP 44.5718 26.1033 RO
    CLJ 46.7860 23.6857 RO | TSR 45.8099 21.3379 RO | IAS 47.1796 27.6214 RO | SOF 42.6964 23.4177 BG | VAR 43.2321 27.8251 BG | BOJ 42.5699 27.5152 BG
    BEG 44.8184 20.3091 RS | ZAG 45.7429 16.0688 HR | SPU 43.5389 16.2980 HR | DBV 42.5622 18.2655 HR | ZAD 44.0970 15.3536 HR | PUY 44.8935 13.9222 HR
    LJU 46.2237 14.4576 SI | SKP 41.9581 21.6226 MK | TIA 41.4147 19.7206 AL | PRN 42.5728 21.0358 XK | TGD 42.3594 19.2519 ME | KEF 63.9850 -22.6056 IS
    AYT 36.8987 30.8005 TR | IST 41.2749 28.7321 TR | SAW 40.8986 29.3092 TR | ADB 38.2924 27.1570 TR | DLM 36.7131 28.7925 TR | BJV 37.2493 27.6640 TR
    ESB 40.1281 32.9951 TR | KBP 50.3450 30.8947 UA | LWO 49.8125 23.9561 UA | TBS 41.6692 44.9547 GE | KUT 42.1774 42.4854 GE | EVN 40.1489 44.3979 AM
    GYD 40.4728 50.0509 AZ | JFK 40.6394 -73.7793 US | EWR 40.6894 -74.1705 US | ORD 41.9786 -87.9048 US | LAX 33.9425 -118.4080 US | MIA 25.7960 -80.2898 US
    SFO 37.6198 -122.3748 US | BOS 42.3620 -71.0079 US | IAD 38.9445 -77.4558 US | ATL 33.6367 -84.4281 US | YYZ 43.6759 -79.6294 CA | YUL 45.4678 -73.7423 CA
    DXB 25.2498 55.3710 AE | AUH 24.4410 54.6492 AE | DOH 25.2731 51.6081 QA | TLV 32.0114 34.8867 IL | HRG 27.1768 33.7967 EG | SSH 27.9773 34.3947 EG
    RMF 25.5555 34.5924 EG | CAI 30.1115 31.3967 EG | RAK 31.6048 -8.0358 MA | AGA 30.3225 -9.4120 MA | TUN 36.8510 10.2272 TN | DJE 33.8737 10.7773 TN
    NBE 36.0758 10.4386 TN | CMN 33.3675 -7.5900 MA | BKK 13.6811 100.7470 TH | HKT 8.1133 98.3174 TH | DPS -8.7484 115.1671 ID | SIN 1.3502 103.9940 SG
    KUL 2.7456 101.7100 MY | HKG 22.3118 113.9149 HK | PEK 40.0773 116.5967 CN | PVG 31.1434 121.8050 CN | ICN 37.4691 126.4510 KR | NRT 35.7686 140.3887 JP
    HND 35.5497 139.7870 JP | DEL 28.5556 77.0952 IN | BOM 19.0887 72.8679 IN | MLE 4.1918 73.5291 MV | CMB 7.1808 79.8841 LK | CUN 21.0408 -86.8735 MX
    PUJ 18.5671 -68.3646 DO | HAV 22.9892 -82.4091 CU | GRU -23.4313 -46.4700 BR | EZE -34.8222 -58.5358 AR | MEX 19.4358 -99.0703 MX | JNB -26.1401 28.2468 ZA
    CPT -33.9740 18.6043 ZA | NBO -1.3189 36.9282 KE | ZNZ -6.2220 39.2249 TZ | MBA -4.0348 39.5942 KE | SYD -33.9461 151.1770 AU | MRU -20.4302 57.6836 MU
"""
AIRPORTS = {}
for _chunk in AIRPORTS_RAW.replace("\n", "|").split("|"):
    _p = _chunk.split()
    if len(_p) == 4:
        AIRPORTS[_p[0]] = (float(_p[1]), float(_p[2]), _p[3])
OURAIRPORTS = "https://davidmegginson.github.io/ourairports-data/airports.csv"
# EU member states incl. outermost regions (GP MQ GF RE YT MF), plus EEA (IS LI NO) and CH, which apply 261/2004.
EU = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE GP MQ GF RE YT MF IS LI NO CH".split())
EXTRAORDINARY = {"weather": "bad weather", "atc": "air traffic control decision", "atc-strike": "air traffic control strike",
                 "airport-strike": "strike of airport staff (third party)", "bird-strike": "bird strike (C-315/15 Peskova)",
                 "security": "security risk", "political": "political instability", "medical": "passenger medical emergency"}
NOT_EXTRA = {"technical": "technical problem (C-549/07 Wallentin-Hermann: not extraordinary)",
             "crew": "crew shortage / scheduling", "own-strike": "airline's own staff strike (C-28/20: not extraordinary)",
             "overbooking": "overbooking", "operational": "airline operational reasons"}


def airport(code):
    code = code.upper()
    if code in AIRPORTS:
        return AIRPORTS[code]
    f = income.CACHE / "airports.csv"
    if not f.exists():
        print(f"{code} not in the built-in table; downloading OurAirports airports.csv once (~13 MB)...", file=sys.stderr)
        income.write(f, income.fetch(OURAIRPORTS, ttl=10 ** 9))
    for r in csv.DictReader(io.StringIO(f.read_text())):
        if r["iata_code"] == code:
            AIRPORTS[code] = (float(r["latitude_deg"]), float(r["longitude_deg"]), r["iso_country"])
            return AIRPORTS[code]
    raise SystemExit(f"ERROR unknown IATA code {code}. Check it on the boarding pass and retry.")


def distance(a, b):
    """Great-circle distance in km (art. 7(4): great circle route method), haversine, R = 6371 km."""
    (la1, lo1, _), (la2, lo2, _) = airport(a), airport(b)
    p1, p2, dp, dl = map(math.radians, (la1, la2, la2 - la1, lo2 - lo1))
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * 6371.0 * math.asin(math.sqrt(h)))


def eu261(x):
    """Return a dict with the verdict, amount, reasons and deadlines. Pure rules; no network unless a code is unknown."""
    dep, arr = airport(x.src), airport(x.dst)
    km = distance(x.src, x.dst)                       # first departure -> final destination (C-559/16 Bossen)
    intra = dep[2] in EU and arr[2] in EU
    notes, verdict = [], "ELIGIBLE"
    if dep[2] in EU:
        scope = f"departure from {dep[2]} (EU/EEA/CH): covered for any airline"
    elif arr[2] in EU and x.eu_carrier == "yes":
        scope = f"arrival in {arr[2]} on an EU/EEA/CH airline: covered (unless you got benefits under the departure country's law)"
    elif arr[2] in EU and x.eu_carrier == "unknown":
        scope, verdict = "arrival in the EU from outside: covered only if the operating airline is EU/EEA/CH - give --eu-carrier", "CHECK"
    else:
        return {"verdict": "NOT_ELIGIBLE", "km": km, "amount_eur": 0, "scope": "neither departure in the EU nor arrival on an EU airline",
                "notes": ["UK departures fall under UK261 (UK law), not EU261"] if dep[2] == "GB" else []}
    if km <= 1500:
        band, full, cap_h = "<= 1,500 km", 250, 2
    elif intra or km <= 3500:
        band, full, cap_h = ("intra-EU > 1,500 km" if intra else "1,500-3,500 km"), 400, 3
    else:
        band, full, cap_h = "> 3,500 km (not intra-EU)", 600, 4
    amount = full
    if x.type == "delay":
        if x.delay_h is None:
            raise SystemExit("ERROR --delay-h (arrival delay in hours, measured when the doors opened) is required for --type delay")
        if x.delay_h < 3:
            return {"verdict": "NOT_ELIGIBLE", "km": km, "band": band, "amount_eur": 0, "scope": scope,
                    "notes": [f"arrival delay {x.delay_h} h < 3 h (C-402/07 Sturgeon threshold)"]}
        if full == 600 and x.delay_h < 4:
            amount = 300
            notes.append("> 3,500 km and 3-4 h late: the airline may reduce by 50% (Sturgeon para 63, art. 7(2)(c))")
    elif x.type == "cancel":
        nd = x.notice_days
        if nd is None:
            raise SystemExit("ERROR --notice-days (days between being told and the departure) is required for --type cancel")
        early, late = x.reroute_early_h, x.reroute_late_h
        if nd >= 14:
            return {"verdict": "NOT_ELIGIBLE", "km": km, "band": band, "amount_eur": 0, "scope": scope,
                    "notes": ["told 14+ days before departure (art. 5(1)(c)(i)) - you can still claim a refund or rerouting"]}
        if early is not None and late is not None:
            if 7 <= nd < 14 and early <= 2 and late < 4 or nd < 7 and early <= 1 and late < 2:
                return {"verdict": "NOT_ELIGIBLE", "km": km, "band": band, "amount_eur": 0, "scope": scope,
                        "notes": [f"rerouting within the art. 5(1)(c)(ii)/(iii) limits (told {nd} days before)"]}
            if late <= cap_h:
                amount = full // 2
                notes.append(f"rerouted, arrived {late} h late (<= {cap_h} h for this band): 50% reduction allowed (art. 7(2))")
    elif x.type == "denied":
        if x.reroute_late_h is not None and x.reroute_late_h <= cap_h:
            amount = full // 2
            notes.append(f"rerouted, arrived {x.reroute_late_h} h late (<= {cap_h} h): 50% reduction allowed (art. 7(2))")
    r = x.reason
    if r in EXTRAORDINARY:
        verdict = "CHECK" if x.type != "denied" else verdict
        notes.append(f"reason '{EXTRAORDINARY[r]}' is usually an extraordinary circumstance (art. 5(3)); claim anyway only if "
                     "the airline cannot prove it, or the delay was not caused by it (ask for the reason in writing)")
    elif r in NOT_EXTRA:
        notes.append(f"reason: {NOT_EXTRA[r]} - compensation is due")
    else:
        notes.append("reason unknown: send the claim and ask the airline to state and prove any extraordinary circumstance")
    if x.via:
        notes.append(f"connection via {x.via.upper()}: one booking -> distance and delay count to the final destination "
                     "(C-11/11 Folkerts, C-559/16 Bossen)")
    flight = datetime.date.fromisoformat(x.date)
    limit = flight.replace(year=flight.year + 1) if not (flight.month == 2 and flight.day == 29) else flight + datetime.timedelta(days=365)
    return {"verdict": verdict, "km": km, "band": band, "intra_eu": intra, "full_eur": full, "amount_eur": amount,
            "scope": scope, "notes": notes, "limitation": str(limit), "send_by": str(limit - datetime.timedelta(days=60))}


LETTER_EN = """[YOUR NAME]
[YOUR ADDRESS]
[YOUR E-MAIL]
{today}

To: {carrier} - customer relations / claims (use the airline's official claim form or address)

Subject: Claim for compensation under Regulation (EC) No 261/2004 - flight {flight} on {date}, booking [BOOKING REF]

I was a passenger on flight {flight} from {src} to {dst} on {date}{via}. {event}

Under Article 7(1) of Regulation (EC) No 261/2004 the compensation for this flight ({km} km, great-circle) is
EUR {amount}{basis}. {extra}

Please pay EUR {amount} to:
Account holder: [YOUR NAME]   IBAN: [IBAN]   BIC: [BIC]

Please answer within 30 days. If you refuse, state the exact extraordinary circumstance you rely on and the evidence
for it, and the reasonable measures you took. Without payment I will refer the case to the national enforcement body
({neb}) or court.

Attachments: boarding pass(es), booking confirmation.

[SIGNATURE]
"""
LETTER_PL = """[IMIĘ I NAZWISKO]
[ADRES]
[E-MAIL]
{today}

Do: {carrier} - dział reklamacji (formularz reklamacyjny przewoźnika lub adres z jego strony)

Temat: Reklamacja - odszkodowanie z rozporządzenia (WE) nr 261/2004, lot {flight} z dnia {date}, rezerwacja [NUMER REZERWACJI]

Byłem/byłam pasażerem lotu {flight} z {src} do {dst} w dniu {date}{via_pl}. {event_pl}

Na podstawie art. 7 ust. 1 rozporządzenia (WE) nr 261/2004 odszkodowanie dla tego lotu ({km} km, po ortodromie)
wynosi {amount} EUR{basis_pl}. {extra_pl}

Proszę o wypłatę {amount} EUR na rachunek:
Właściciel: [IMIĘ I NAZWISKO]   IBAN: [IBAN]   BIC: [BIC]

Proszę o odpowiedź w terminie 30 dni (art. 205c ust. 2 ustawy Prawo lotnicze). W razie odmowy proszę wskazać
konkretne nadzwyczajne okoliczności, dowody na nie oraz podjęte rozsądne środki. W braku wypłaty skieruję sprawę do
{neb_pl} lub do sądu.

Załączniki: karta(y) pokładowa(e), potwierdzenie rezerwacji.

[PODPIS]
"""
EVENTS = {"delay": ("The flight reached {dst} {h} hours late (arrival time = doors opened).",
                    "Lot dotarł do {dst} z opóźnieniem {h} godz. (liczonym do otwarcia drzwi samolotu).",
                    " (Articles 6 and 7, CJEU C-402/07 and C-432/07 Sturgeon)", " (art. 6 i 7, wyrok TSUE C-402/07 i C-432/07 Sturgeon)"),
          "cancel": ("The flight was cancelled; I was informed {n} days before the scheduled departure.",
                     "Lot został odwołany; poinformowano mnie {n} dni przed planowanym wylotem.",
                     " (Articles 5(1)(c) and 7)", " (art. 5 ust. 1 lit. c i art. 7)"),
          "denied": ("I was denied boarding against my will although I presented myself for check-in on time.",
                     "Odmówiono mi przyjęcia na pokład wbrew mojej woli, mimo stawienia się do odprawy na czas.",
                     " (Articles 4(3) and 7)", " (art. 4 ust. 3 i art. 7)")}


def write_eu261(x, res):
    cid = f"{x.date}-{income.slug(x.flight or x.src + x.dst, 20)}"
    d = CLAIMS / cid
    ev = EVENTS[x.type]
    dep_c = airport(x.src)[2]
    neb = "Rzecznik Praw Pasażerów, Urząd Lotnictwa Cywilnego (Poland)" if dep_c == "PL" else f"the national enforcement body of {dep_c}"
    neb_pl = "Rzecznika Praw Pasażerów przy Urzędzie Lotnictwa Cywilnego" if dep_c == "PL" else f"krajowego organu wykonawczego ({dep_c})"
    half = res["amount_eur"] < res["full_eur"]
    v = dict(today=income.today(), carrier=x.carrier or "[AIRLINE]", flight=x.flight or "[FLIGHT NO]", date=x.date,
             src=x.src.upper(), dst=x.dst.upper(), km=res["km"], amount=res["amount_eur"], neb=neb, neb_pl=neb_pl,
             via=f" with a connection in {x.via.upper()} on one booking" if x.via else "",
             via_pl=f" z przesiadką w {x.via.upper()} w ramach jednej rezerwacji" if x.via else "",
             event=ev[0].format(dst=x.dst.upper(), h=x.delay_h, n=x.notice_days),
             event_pl=ev[1].format(dst=x.dst.upper(), h=x.delay_h, n=x.notice_days), basis=ev[2], basis_pl=ev[3],
             extra="The reduction under Article 7(2) has been applied." if half else
                   "No extraordinary circumstance has been communicated to me.",
             extra_pl="Uwzględniono obniżenie z art. 7 ust. 2." if half else "Nie poinformowano mnie o nadzwyczajnych okolicznościach.")
    income.write(d / "letter-en.md", LETTER_EN.format(**v))
    income.write(d / "letter-pl.md", LETTER_PL.format(**v))
    data = income.load_json(d / "claim.json", {})
    data.update({"id": cid, "kind": "eu261", "flight": x.flight, "date": x.date, "from": x.src.upper(), "to": x.dst.upper(),
                 "type": x.type, "reason": x.reason, **res, "status": data.get("status", "drafted"), "updated": str(income.today())})
    income.save_json(d / "claim.json", data)
    return d, data


CONSUMER = {
    "withdrawal": ("Withdrawal from a distance contract (online purchase) - 14 days from receipt, no reason needed "
                   "(art. 27 ustawa o prawach konsumenta); refund within 14 days of the statement (art. 32).",
                   "Oświadczenie o odstąpieniu od umowy zawartej na odległość (art. 27 ustawy o prawach konsumenta). "
                   "Proszę o zwrot {amount} zł, w tym kosztów dostawy, w terminie 14 dni (art. 32).", 14),
    "nonconformity": ("Goods not in conformity with the contract - seller liable for 2 years from delivery (art. 43c); "
                      "demand repair or replacement (art. 43d); the seller must answer in 14 days or the complaint is accepted (art. 7a).",
                      "Reklamacja - towar niezgodny z umową (art. 43c ustawy o prawach konsumenta). Żądam naprawy albo wymiany "
                      "towaru (art. 43d). Proszę o odpowiedź w terminie 14 dni (art. 7a).", 730),
    "price-guarantee": ("Price guarantee / price-drop refund - only under the shop's own terms (regulamin); quote its clause.",
                        "Wniosek o zwrot różnicy w cenie zgodnie z gwarancją najniższej ceny z regulaminu sklepu "
                        "(punkt [NR PUNKTU REGULAMINU]). Różnica: {amount} zł.", None),
}


def write_consumer(x):
    cid = f"{x.date}-{income.slug(x.shop, 20)}-{x.kind}"
    info, pl, days = CONSUMER[x.kind]
    dl = str(datetime.date.fromisoformat(x.date) + datetime.timedelta(days=days)) if days else "see the shop's terms"
    pl_body = pl.format(amount=x.amount or "[KWOTA]")
    text = (f"[IMIĘ I NAZWISKO], [ADRES], [E-MAIL]\n{income.today()}\n\nDo: {x.shop}\n\nDotyczy: {x.item}, zakup/dostawa z dnia "
            f"{x.date}, zamówienie [NUMER ZAMÓWIENIA]\n\n{pl_body}\n\n[OPIS: co się stało, kiedy wada się ujawniła]\n\n"
            f"Numer rachunku do zwrotu: [IBAN]\n\n[PODPIS]\n\n---\nEN summary: {info}\n")
    d = CLAIMS / cid
    income.write(d / "letter-pl.md", text)
    data = {"id": cid, "kind": x.kind, "shop": x.shop, "item": x.item, "date": x.date, "amount_pln": x.amount,
            "limitation": dl, "status": "drafted", "updated": str(income.today())}
    income.save_json(d / "claim.json", data)
    return d, data


def load(cid):
    f = CLAIMS / cid / "claim.json"
    if not f.exists():
        raise SystemExit(f"ERROR claim '{cid}' not found. See: claim.py list")
    return f, json.loads(f.read_text())


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0 if a else 2)
    p = argparse.ArgumentParser(prog="claim.py", description=__doc__.split("\n\n")[0])
    sp = p.add_subparsers(dest="cmd", required=True)
    e = sp.add_parser("eu261")
    e.add_argument("--from", dest="src", required=True); e.add_argument("--to", dest="dst", required=True)
    e.add_argument("--date", required=True); e.add_argument("--type", required=True, choices=("delay", "cancel", "denied"))
    e.add_argument("--delay-h", type=float); e.add_argument("--notice-days", type=int)
    e.add_argument("--reroute-early-h", type=float); e.add_argument("--reroute-late-h", type=float)
    e.add_argument("--reason", default="unknown", choices=sorted(EXTRAORDINARY) + sorted(NOT_EXTRA) + ["unknown"])
    e.add_argument("--flight", default=""); e.add_argument("--carrier", default=""); e.add_argument("--via", default="")
    e.add_argument("--eu-carrier", default="unknown", choices=("yes", "no", "unknown"))
    lt = sp.add_parser("letter")
    lt.add_argument("--kind", required=True, choices=sorted(CONSUMER)); lt.add_argument("--shop", required=True)
    lt.add_argument("--item", required=True); lt.add_argument("--date", required=True); lt.add_argument("--amount", type=float)
    s = sp.add_parser("sent"); s.add_argument("id"); s.add_argument("--date"); s.add_argument("--hours", type=float, default=0.3)
    o = sp.add_parser("outcome"); o.add_argument("id"); o.add_argument("status", choices=("paid", "refused", "escalated"))
    o.add_argument("--amount", type=float, default=0.0); o.add_argument("--currency", default="EUR"); o.add_argument("--hours", type=float)
    sp.add_parser("list")
    di = sp.add_parser("distance"); di.add_argument("a"); di.add_argument("b")
    x = p.parse_args()
    t = income.today()

    if x.cmd == "distance":
        print(f"OK {x.a.upper()}-{x.b.upper()} {distance(x.a, x.b)} km (great circle)")
    elif x.cmd == "eu261":
        res = eu261(x)
        print(f"{x.src.upper()}-{x.dst.upper()} {res['km']} km, {res.get('band', '')}; {res['scope']}")
        for n in res["notes"]:
            print(f"- {n}")
        if res["verdict"] == "NOT_ELIGIBLE":
            print("OK NOT ELIGIBLE - no letter written"); return
        days_left = (datetime.date.fromisoformat(res["limitation"]) - t).days
        print(f"Limitation (PL, art. 205c ust. 7 Prawo lotnicze): {res['limitation']} ({days_left} days left); send by {res['send_by']}")
        if days_left < 0:
            print("WARN past the Polish 1-year limit - no letter written; only worth pursuing if another country's law applies")
            return
        d, data = write_eu261(x, res)
        print(f"Letters: {d}/letter-en.md, {d}/letter-pl.md  (fill the [PLACEHOLDERS], then send it yourself)")
        print(f"{'WARN CHECK' if res['verdict'] == 'CHECK' else 'OK ELIGIBLE'} EUR {res['amount_eur']} claim drafted: {data['id']}")
    elif x.cmd == "letter":
        d, data = write_consumer(x)
        print(f"Deadline: {data['limitation']}. Letter: {d}/letter-pl.md (fill the [PLACEHOLDERS], then send it yourself)")
        print(f"OK {x.kind} letter drafted: {data['id']}")
    elif x.cmd == "sent":
        f, data = load(x.id)
        day = x.date or str(t)
        data.update(status="sent", sent=day, answer_due=str(datetime.date.fromisoformat(day) + datetime.timedelta(days=30)))
        if data["kind"] == "eu261":
            data["escalate_from"] = data["answer_due"]
            data["escalate_until"] = data["limitation"]
        if not data.get("ledger_id"):
            data["ledger_id"] = ledger.add_attempt("claims", f"{data['id']} ({data['kind']})", day, x.hours, status="sent",
                                                   note=f"claimed {data.get('amount_eur', data.get('amount_pln'))}")
        income.save_json(f, data)
        print(f"Airline/shop must answer by {data['answer_due']}. Ledger attempt {data['ledger_id']}.")
        if data["kind"] == "eu261":
            print(f"No answer or refusal -> RPP/NEB complaint from {data['escalate_from']} until {data['escalate_until']} (art. 205a ust. 8, 15)")
        print(f"OK {data['id']} marked sent")
    elif x.cmd == "outcome":
        f, data = load(x.id)
        data["status"] = x.status
        if data.get("ledger_id"):
            ledger.update(data["ledger_id"], status=x.status, revenue=x.amount or None, currency=x.currency, hours=x.hours)
        income.save_json(f, data)
        print(f"OK {data['id']} -> {x.status}" + (f", {x.amount} {x.currency} logged in the ledger" if x.amount else ""))
    elif x.cmd == "list":
        rows = [json.loads(f.read_text()) for f in sorted(CLAIMS.glob("*/claim.json"))]
        for r in rows:
            due = r.get("answer_due") if r["status"] == "sent" else r.get("limitation")
            print(f"{r['id']:<40} {r['status']:<9} {r['kind']:<15} next date {due}")
        print(f"OK {len(rows)} claim(s) in {CLAIMS}")


if __name__ == "__main__":
    main()
