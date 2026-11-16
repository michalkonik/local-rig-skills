---
name: x-voice
description: Use when drafting or rewriting a post or reply so it sounds like Michał, English on @local_agents or Polish on @youroldpalhorse. Not for picking targets - use /x-operate. Input - the draft file.
---
# /x-voice
**Goal:** a draft Michał would actually send. **Output:** the DRAFT section of a proposal file.
The long version, with the reason for each rule, is `~/Desktop/komunikacja-x/GLOS.md`. Read it when a draft still sounds like a model after `xmgr.py check` is OK.

## Rules
1. First sentence is the fact or the snag. Delete a warm-up sentence.
2. One specific thing only he saw: a flag, a watt, a file, a card, a bug. If the sentence fits under someone else's post unchanged, it is not ready.
3. English is short and a bit rough. Polish is spoken, dry, and written fresh. Do not translate.
4. One em dash at most. No hashtags, no bullet list, no "thoughts?", no offer.
5. Vary the opening across the day's replies. The checker rejects a repeated opening.

## Shape
- Reply: 1 to 3 sentences. His detail, then stop. No "happy to help", no "great point".
- Post: one fact, the condition (cards, cap, date or commit), stop or one question a person with a GPU can answer today.
- Two `<!-- alt: -->` lines under the draft: other first sentences, not other posts.

## Examples
English reply, keep this density:

> 16 GB is enough until the KV cache shows up. On a 32 GB R9700 I can hold a 32B dense Q4 and still lose the long tool prompt before I lose the weights.

Polish post, keep this density:

> Wagi siadły, karta udaje że pracuje, a liczy jeden rdzeń CPU. Tokenów zero.

Reject and rewrite:

> Great point! Local AI is the future. What do you think?

## Before you finish
- [ ] the first sentence still carries the fact after you read it aloud
- [ ] `xmgr.py check` is the pass/fail, not your feeling about tone
