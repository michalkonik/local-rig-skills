---
name: onenote-list
description: Use when the user wants the OneNote tree or a list of notebooks, section groups, sections, or pages ("show my notebooks", "what's in this section"). Not for page text - use /onenote-read. Not for saving - use /onenote-write. Input - optional notebook or section name.
---
# /onenote-list
**Goal:** show the notebook → group → section tree, or the pages in one section.
**Output:** lines `OK ...` then `- name | id`.
`N="python3 $HOME/Desktop/github_repos/local-rig-skills/bin/onenote.py"`

## Rules
1. Do not run `bw-secret` yourself. The script reads item `onenote` field `access_token`.
2. Copy ids from the script output. Do not invent them.
3. Default view is the tree. List pages only after a section name or id is known.

## Steps
1. Whole structure: `$N tree`. One notebook: `$N tree "NAME"`.
2. Sections of one notebook, including groups: `$N sections "NAME"`.
3. Pages in one section: `$N pages "SECTION"`. Add `--top 50` only if the first list is cut off.
4. If the script prints `ERROR`, stop and report that line. Do not retry with a different token.

## Reply
```
Notebooks: <count>
- <notebook> / <group or section>
Pages in <section>: <title> | <id>
```

## Gotchas
- A 401 that mentions Notes.ReadWrite means the saved token can sign in but cannot read OneNote. Stop.
- Section groups are parent topics. Pages live in sections, not directly in a group.

## Before you finish
- [ ] every id in the reply came from the script
- [ ] an ERROR line was quoted, not paraphrased into a success
