# local-rig-skills

Umiejętności (skills) dla lokalnych modeli AI na moim rigu (mkoniu-B850-AI-TOP, 4x Radeon AI PRO R9700). Skill to
katalog z plikiem `SKILL.md` (kiedy go użyć + procedura krok po kroku) i opcjonalnymi skryptami. Korzysta z nich
każdy model serwowany przez llama-swap, w obu interfejsach czatu, a także agent OpenClaw Pedro. *English version: [README.md](README.md).*

**Rig i modele**

| Skill | Co robi |
|---|---|
| `/download-llm <model albo potrzeba>` | znajduje właściwe repozytorium i kwantyzację na Hugging Face, sprawdza miejsce na dysku, pobiera w tle, potem proponuje `/add-new-model-to-config` |
| `/add-new-model-to-config <model> [silnik/konfiguracja] [rola]` | dodaje model do llama-swap (llama.cpp ROCm/Vulkan, vLLM, radiance), testuje go i stroi pod szybkość bez utraty jakości |
| `/inspect-current-config-of-model <model>` | przegląda konfigurację modelu, szuka w internecie lepszych ustawień lub plików, proponuje zmiany i wprowadza zatwierdzone przez `/update-config-of-model` |
| `/update-config-of-model <model> <zmiany>` | wprowadza zmiany po jednej: kopia zapasowa, test, pomiar przed/po, wycofanie tego, co nie pomaga |
| `/update-monitoring <zmiana>` | zmienia alerty Netdata, kolektor GPU albo powiadomienia mailowe: plik przygotowany obok, jedno zatwierdzone polecenie sudo, gotowe cofnięcie |
| `/update-openclaw-config <zmiana>` | zmienia OpenClaw (Pedro): modele, sub-agenty, pluginy, skille, agentów, kanały, zatwierdzenia, narzędzia, MCP albo własną funkcję - znajduje dokładne miejsce w konfiguracji, robi kopię, sprawdza łatkę JSON5 na sucho, testuje prawdziwą turą agenta, zostawia polecenie cofnięcia |
| `/apply-change-on-local-machine <zmiana>` | każda inna zmiana na maszynie: plan, kontrola niebezpiecznych poleceń, kopia, wykonanie, weryfikacja, dziennik |
| `/load-rig-context` | daje świeżemu agentowi mapę riga (ścieżki, usługi, modele, narzędzia, zasady, który dokument czytać) i skrypt ze stanem na żywo; krótki, do częstego wczytywania |

**Research i czytanie**

| Skill | Co robi |
|---|---|
| `/find-in-internet <pytanie>` | research w sieci ze źródłami |
| `/find-in-dark-web <zapytanie>` | wyszukiwanie w sieci onion przez lokalne proxy Tor (tylko legalny research) |
| `/transcript-youtube-video <URL albo nazwa>` | pełna transkrypcja filmu z YouTube jako .md ze znacznikami czasu - najpierw napisy, bez nich lokalny Whisper (Speaches) |
| `/select-meaningful-information-from-text <tekst albo plik>` | najważniejsze punkty długiego tekstu lub transkrypcji: TL;DR, punkty według wagi z dowodami i czasem, wnioski do zastosowania, tezy do sprawdzenia, mapa co obejrzeć/pominąć |

**Treści: X i YouTube (przestrzeń `~/content/`)**

| Skill | Co robi |
|---|---|
| `/content-voice` | buduje profil Twojego stylu z Twoich własnych tekstów (zmierzone liczby + cytowane przykłady); szkice są z nim porównywane |
| `/content-ideas` | pomysły z prawdziwej aktywności riga + trendy w niszy (HF trending, r/LocalLLaMA, HN, wydania llama.cpp), z oceną i poleceniem, które je udowadnia |
| `/write-x-post <pomysł albo URL>` | jeden angielski szkic na X z pomysłu treści, Twoim stylem i z prawdziwymi liczbami; publikujesz ręcznie. To nie jest pętla dwóch kont |
| `/x-operate` | dwa konta X: poranny brief, audyt, z kim gadać, kogo obserwować albo odobserwować, szkice. Publikujesz ręcznie |
| `/x-voice` | przepisuje szkic tak, żeby brzmiał jak Ty: angielski na @local_agents, polski na @youroldpalhorse |
| `/make-youtube-video <pomysł>` | prawdziwe nagrania terminala -> slajdy, wykresy, kod z narracją (lokalny Kokoro), napisy, rozdziały, miniatury A/B, tytuły - wszystko na rigu |
| `/make-youtube-short <wynik>` | pionowy film 30-55 s z wtopionymi napisami, z jednego prawdziwego wyniku |
| `/publish-youtube-video <slug>` | wysyłka przez YouTube Data API jako prywatny/zaplanowany, z miniaturą, napisami i flagą treści syntetycznych |
| `/content-weekly-review` | eksporty statystyk X i YouTube -> co zadziałało, jeden eksperyment, plan na tydzień |

**Zarobek (szukanie i selekcja; ostateczny krok należy do Ciebie)**

| Skill | Co robi |
|---|---|
| `/claim-money-owed` | odszkodowania lotnicze EU261 i inne roszczenia: kwota, termin, gotowe pismo (EN/PL), które wysyłasz |
| `/track-bank-promotions` | promocje bankowe: nowe/zakończone, lista warunków z datami |
| `/find-freelance-gigs` | publiczne zlecenia ocenione pod Twój profil, szkice ofert, które wysyłasz ręcznie |
| `/scan-bailiff-auctions` | e-licytacje komornicze (licytacje.komornik.pl): rabat wobec oszacowania, wadium i terminy, krótka lista do Twojej decyzji |
| `/income-ledger` | wspólny dziennik przychodów (SQLite): próby, godziny, koszty, przychód, kill-check |
| `/income-weekly-review` | tygodniowa strona z dziennika: liczby na strumień, werdykty zostaw/porzuć według kryteriów z kursu, nadchodzące terminy, Twoje decyzje |
| `/deal-hunter <status, deals, show, explain, books, start, stop>` | pytanie i sterowanie agentem Deal Hunter (okazje na sprzęt, progi, rozbicie zysku netto, koszty); tylko znajduje okazje, nigdy nie kupuje ani nie pisze do sprzedawców |

**Notatki (OneNote przez Microsoft Graph)**

| Skill | Co robi |
|---|---|
| `/onenote-list` | drzewo notatnik → grupa sekcji → sekcja, albo strony jednej sekcji |
| `/onenote-read` | szuka stron i wypisuje treść jednej |
| `/onenote-write` | nowa strona albo dopisek; wysyła tylko z `--apply` |

Skrypt to `bin/onenote.py`. Czyta pole `access_token` z pozycji Bitwarden `onenote` (`bw-secret onenote#access_token`). Token musi mieć zakres Graph `Notes.ReadWrite`.

**OneDrive (ten sam token Graph, zakres `Files.ReadWrite`)**

| Skill | Co robi |
|---|---|
| `/drive-list` | lista jednego folderu albo szukanie na dysku |
| `/drive-read` | treść małego pliku tekstowego, albo sam rozmiar gdy to nie tekst |
| `/drive-write` | wysyłka, nowy folder albo usunięcie jednej rzeczy; wysyła tylko z `--apply` |

Skrypt: `bin/drive.py`. To samo pole Bitwarden. Token skopiowany przed zgodą nie otworzy dysku.

**Google Drive (konto `michal.konik.praca@gmail.com`, zakres OAuth `drive`)**

| Skill | Co robi |
|---|---|
| `/gdrive-list` | lista jednego folderu Mojego dysku albo szukanie po nazwie |
| `/gdrive-read` | podgląd Dokumentu lub małego pliku tekstowego, albo pobranie (Arkusze jako xlsx, Dokumenty jako docx) |
| `/gdrive-write` | wysyłka, podmiana Dokumentu/Arkusza, zapis komórek, nowy folder albo kosz; wysyła tylko z `--apply` |

Skrypt: `bin/gdrive.py`. Token: `~/Documents/keep/gmail-tokens.json`. To nie jest skrypt OneDrive. Zapis komórek wymaga włączonego Sheets API w projekcie OAuth.

**PKO (Enable Banking, tylko odczyt)**

| Skill | Co robi |
|---|---|
| `/pko-balance` | salda i limit karty kredytowej dla podłączonych rachunków PKO |
| `/pko-transactions` | historia transakcji dla podanego zakresu dat |
| `/pko-card-timeline` | ile dni do odsetek karty, tylko gdy bank przysłał termin spłaty |

Skrypt: `bin/pko.py`. Sekrety: pozycja Bitwarden `enablebanking-pko` (`bw-secret`, nigdy w gicie). mBank zostaje przy `/read-mbank-balance`. Podłączenie konta w panelu tylko aktywuje aplikację; salda wymagają jednej sesji zgody przez API.

**Arkusz budżetu**

| Skill | Co robi |
|---|---|
| `/manage-budget-file` | uzupełnia arkusz Google `Budżet 2026` z mBank i PKO, jedna karta na miesiąc, dziesięć kategorii z datą, kwotą i opisem; żółte B1 to edytowalny budżet miesiąca; karta Log mówi, dokąd sięga odczyt banku |

Skrypt: `bin/budget.py`. Id arkusza jest w `~/.local/state/rig-skills/budget.json`, nie w gicie.
Pełna, generowana lista: [INDEX.md](INDEX.md).

## Jak modele dostają skille
- **Open WebUI** (`https://192.168.0.39:3443` albo `http://192.168.0.39:3000`): każdy skill jest zarejestrowany jako
  natywny Skill Open WebUI. Modele z natywnym wywoływaniem narzędzi widzą listę i wczytują skill narzędziem
  `view_skill`, gdy pasuje. Żeby wybrać skill samemu, wpisz `/` w polu czatu: każdy skill jest w menu z podpowiadaniem
  (`/dow` -> `/download-llm`); wybierz go i dopisz swoje polecenie. `$` też pokazuje listę skilli.
- **Czat llama.cpp** (llama-swap, `http://192.168.0.39:8080`): katalog jest częścią promptu systemowego każdego
  modelu (pisze go `~/.config/llama-swap/tools/sync_prompts.py`); wiadomość zaczynająca się od `/nazwa-skilla`
  sprawia, że model czyta ten `SKILL.md` narzędziem do plików i wykonuje procedurę.
- **OpenClaw (Pedro)** wczytuje katalog `skills/` bezpośrednio (`skills.load.extraDirs`, od 29 paź 2026).
- **Skrypty** uruchamiają się na rigu przez narzędzia powłoki modeli. Działania jako root zawsze idą przez stronę
  zatwierdzania sudo (każde polecenie zatwierdzasz swoim hasłem; modele go nie widzą).

## Układ
```
skills/<nazwa>/SKILL.md       instrukcja (nagłówek: name, description); <nazwa>/scripts/ skrypty tylko tego skilla
bin/                          wspólne narzędzia: ls_entry.py (bezpieczne zmiany w llama-swap), model_facts.py (fakty
                              o GGUF/safetensors + plan kart), smoke.py (test ładowania/odpowiedzi/narzędzi/obrazu),
                              bench.py (szybkość przed/po), model_report.py (przegląd modelu na jednej stronie),
                              bg (zadania w tle), sync_skills.py (publikacja)
lib/                          rig.py (ścieżki, llama-swap, zasoby, kopie, dziennik), hf.py (API Hugging Face),
                              content.py (przestrzeń treści, długość na X, wykrywanie śladów AI), ledger.py (dziennik przychodów), income.py (grzeczne pobieranie stron, kursy NBP)
reference/skill-format.md     standard skilli dla lokalnych modeli (przeczytaj przed pisaniem nowego)
reference/rig-map.md          pełne tabele riga za /load-rig-context
reference/serving-playbook.md zasady wyniesione z pomiarów na tym rigu: silniki, flagi, limity, mierzenie
reference/openclaw-config.md  ścieżki konfiguracji OpenClaw, przepisy, własne funkcje, mapa dokumentacji (/update-openclaw-config)
```
Stan zapisywany przez skrypty (poza gitem): `~/.local/state/rig-skills/` - `journal.log` (każda zmiana z
poleceniem cofnięcia), `backups/`, `bench/`, `downloads/`, `jobs/`, `monitoring/`.

## Dodanie lub zmiana skilla
1. Utwórz `skills/<nazwa>/SKILL.md` z szablonu w `reference/skill-format.md`: praca w skrypcie, treść poniżej
   6 tys. znaków (twardy limit 10 tys.), opis poniżej 300 znaków zaczynający się od "Use when...". Przetestuj go raz
   przez Pedra albo Open WebUI prawdziwym poleceniem.
2. `python3 bin/sync_skills.py` - sprawdza, odtwarza INDEX.md, aktualizuje Open WebUI i wszystkie prompty systemowe.
3. Commit i push.

Dokumentacja całej konfiguracji (prywatna): `~/Desktop/github_repos/llm-private-education` (rozdział 05 = skille).
