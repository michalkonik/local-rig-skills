# local-rig-skills

Four agent skills for work that local models do badly when you only prompt them: web research with citations, onion-site research through Tor, YouTube transcripts, and a summary of a transcript that replaces watching it.

A skill is a folder with a `SKILL.md` (when to use it, the steps, the reply shape) and a script that does the mechanical part. The model follows the file. It does not have to invent the procedure.

Nothing in this repo is an account, a secret, or one person's machine. The commands inside the skills use `~/Desktop/github_repos/local-rig-skills`. Clone it there, or change that path in the four `SKILL.md` files if you put the repo somewhere else.

## Skills

| Skill | Use it when |
|---|---|
| `/find-in-internet` | You want a sourced answer from the public web. Several queries, the best pages read, disagreements kept. |
| `/find-in-dark-web` | You want public `.onion` results through a local Tor proxy. Legitimate research only. Refuses illegal content. |
| `/transcript-youtube-video` | You want a full transcript as Markdown with `[mm:ss]` timestamps. Captions first, local Whisper if there are none. |
| `/summarize-transcript` | You have a transcript and want the talk instead of the wording: thesis, timestamped points, what to do, what to check, what to skip. |

Generated index: [INDEX.md](INDEX.md). House format for a new skill: [reference/skill-format.md](reference/skill-format.md).

## Install

```bash
git clone https://github.com/michalkonik/local-rig-skills.git ~/Desktop/github_repos/local-rig-skills
```

Python 3 is enough for the research and notes skills. `/find-in-dark-web` needs Tor listening on `127.0.0.1:9050` (`tor`, or `tor@default`). `/transcript-youtube-video` needs `ffmpeg` and creates its own `yt-dlp` venv on first use. Whisper is optional: an OpenAI-compatible server at `http://127.0.0.1:8001/v1` (Speaches does this). Captions work without it.

### OpenClaw

Add the skills directory to `skills.load.extraDirs` in `~/.openclaw/openclaw.json`:

```json
"extraDirs": [
  "/home/you/Desktop/github_repos/local-rig-skills/skills"
]
```

Restart is usually unnecessary. Check with `openclaw skills list`.

### Hermes

In `~/.hermes/config.yaml`, under `skills:`:

```yaml
external_dirs:
  - ~/Desktop/github_repos/local-rig-skills/skills
```

External directories are read-only. Hermes will not write back into this repo.

### Open WebUI and llama.cpp

If you already run this project's sync tools (Open WebUI on port 3000 and llama-swap):

```bash
python3 bin/sync_skills.py
```

That validates every `SKILL.md`, refreshes `INDEX.md`, and publishes one native skill plus a `/skill-name` prompt-menu entry. Without those tools, point the model at `skills/<name>/SKILL.md` yourself. A message that starts with `/find-in-internet` is the whole interface.

## Use one

Ask normally ("what changed in llama.cpp this month?") or start the message with the command:

```text
/transcript-youtube-video https://www.youtube.com/watch?v=...
/summarize-transcript ~/Documents/transcripts/that-video.md
```

The model is supposed to run the script in the skill, then answer in the shape at the bottom of the file. Check the "Before you finish" list if a reply has no URLs, no timestamps, or a pasted transcript that should have been a file.

## Add a skill

Copy the shape in [reference/skill-format.md](reference/skill-format.md). One folder, one `SKILL.md`, scripts beside it. Front matter is a single `name` and a single-line `description` that starts with "Use when". Keep the file under 10k characters. Then `python3 bin/sync_skills.py --check`.

## License

[MIT](LICENSE).
