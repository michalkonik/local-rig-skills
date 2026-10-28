# Bailiff auction rules and sources (checked 29 Oct 2026)

Course: `ai-income-asymmetries/01-OPPORTUNITIES.md` §6. Kill criterion: after 2 months and 3 purchases, net
margin < 10% or capital stuck in unsold items -> stop.

| Rule | Where | Verified in |
|---|---|---|
| Movables, 1st term: opening price 3/4 of the appraisal; 2nd term: 1/2 | art. 867 § 2 KPC | course (ISAP, t.j. Dz.U. 2026) |
| Movables deposit (rękojmia): 1/10 of the appraisal; none if appraisal < 5,000 PLN | art. 867¹ § 1 KPC | course |
| E-auction: deposit on the bailiff's account at least 2 working days before the start; bidder gives PESEL, ID number, marital status | art. 879⁵ KPC | course |
| Real estate, 1st auction: opening price 3/4 of the appraisal | art. 965 KPC | secondary sources (e-prawnik.pl, lexlege.pl), not ISAP |
| Real estate, 2nd auction: opening price 2/3 of the appraisal | art. 983 § 1 KPC | secondary sources, not ISAP |
| Real estate deposit: 1/10 of the appraisal | art. 962 § 1 KPC | course |
| Unregistered activity limit 2026: 10,813.50 PLN revenue per quarter, then CEIDG within 7 days | money.pl, 19 Aug 2026 | course (03 §1.1) |

Note: the course states 3/4 and 1/2 for movables only. The 2/3 second-term rule applies to real estate.

## Portal
- https://licytacje.komornik.pl/ (Krajowa Rada Komornicza). robots.txt allows the public pages and disallows
  logged-in areas (`/bailiff/`, `/user/`, `/moj-profil/`).
- The search page `/wyszukiwarka-licytacji?mainCategory=MOVABLE&subCategory=CARS&province=...&limit=100&offset=0`
  is server-rendered; the script reads its `__NUXT_DATA__` block (fields: `estimate` = appraisal,
  `openingValue` = opening price, `marginDueDate`, `startAuctionAt`, `endAuctionAt`, `eauction`, `joinable`).
- Item pages load their details in the browser only.
- Sources: [KPC (ISAP)](https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=WDU19640430296) ·
  [e-prawnik.pl, licytacja](https://e-prawnik.pl/kodeksy/kodeks-postepowania-cywilnego/egzekucja-z-nieruchomosci-egzekucja-swiadczen-pienieznych/licytacja.html)
