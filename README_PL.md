# local-rig-skills

Cztery skille dla lokalnych modeli: research w sieci ze źródłami, szukanie publicznych stron `.onion` przez Tor, transkrypcje YouTube i wyciąganie tego, co ważne, z długiego tekstu.

Skill to folder z `SKILL.md` (kiedy użyć, kroki, kształt odpowiedzi) i skryptem, który robi mechaniczną robotę. Model ma iść za plikiem, a nie wymyślać procedury.

W tym repozytorium nie ma kont, sekretów ani konfiguracji jednej maszyny. Domyślna ścieżka to `~/Desktop/github_repos/local-rig-skills`.

## Skille

| Skill | Kiedy |
|---|---|
| `/find-in-internet` | Odpowiedź ze źródłami z publicznej sieci. Kilka zapytań, przeczytane strony, rozbieżności zostają. |
| `/find-in-dark-web` | Publiczne wyniki `.onion` przez lokalne proxy Tor. Tylko legalny research. |
| `/transcript-youtube-video` | Pełna transkrypcja w Markdown ze znacznikami `[mm:ss]`. Najpierw napisy, Whisper gdy ich nie ma. |
| `/select-meaningful-information-from-text` | Sedno długiego tekstu: TL;DR, punkty, co zrobić, co sprawdzić, co pominąć. |

Indeks: [INDEX.md](INDEX.md). Format nowego skilla: [reference/skill-format.md](reference/skill-format.md).

## Instalacja

```bash
git clone https://github.com/michalkonik/local-rig-skills.git ~/Desktop/github_repos/local-rig-skills
```

Wystarczy Python 3. `/find-in-dark-web` potrzebuje Tora na `127.0.0.1:9050`. `/transcript-youtube-video` potrzebuje `ffmpeg` i samo zakłada venv z `yt-dlp`. Whisper jest opcjonalny (serwer zgodny z OpenAI na `http://127.0.0.1:8001/v1`).

OpenClaw: dopisz katalog `skills` do `skills.load.extraDirs`. Hermes: `skills.external_dirs`. Open WebUI i llama.cpp, jeśli masz lokalne narzędzia sync:

```bash
python3 bin/sync_skills.py
```

Bez nich wskaż modelowi `skills/<nazwa>/SKILL.md`. Wiadomość zaczynająca się od `/find-in-internet` wystarcza.

## Licencja

[MIT](LICENSE).
