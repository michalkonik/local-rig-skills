# OpenClaw config cookbook (this rig)

Companion to `/update-openclaw-config` (procedure and short gotchas are in its SKILL.md; rig state, full traps and
per-area checks are in sections 4a-4c below). Paths checked against the
OpenClaw 2026.10.5 schema; anything not listed: `oc.py find <word>` / `oc.py schema <path>`
(`oc.py` = `~/Desktop/github_repos/local-rig-skills/skills/update-openclaw-config/scripts/oc.py`).
Docs root `D=~/.npm-global/lib/node_modules/openclaw/docs`. Every example is a patch file for
`openclaw config patch --file <file> --dry-run` (then without `--dry-run`); `...` means "copy the current value".

## 1. Most-used paths

| Area | Path | Notes |
|---|---|---|
| Orchestrator model | `agents.defaults.model.primary` (+ `.fallbacks`) | `"vllm/<llama-swap id>"`; per agent `agents.entries.<id>.model` |
| Sub-agent model/limits | `agents.defaults.subagents.{model,maxConcurrent,maxChildrenPerAgent,maxSpawnDepth,runTimeoutSeconds,delegationMode}` | maxSpawnDepth 1-5 (1 = children are leaves), maxChildrenPerAgent 1-20 |
| Model catalog | `models.providers.vllm.models[]` `{id,name,reasoning,input,cost,contextWindow,maxTokens}` | protected array: patch refuses to drop entries |
| Per-model settings | `agents.defaults.models["vllm/<id>"]` `{alias,params,streaming}` | map; `null` value deletes one |
| Allowed models | `agents.entries.miclaw.modelPolicy.allow` | exact refs or `vllm/*`; `[]`/absent = any model |
| Utility model | `agents.defaults.utilityModel` | titles, progress narration; `""` disables |
| Agent | `agents.entries.<id>.{name,description,workspace,identity{name,emoji,theme,avatar},model,skills,tools,subagents,heartbeat}` | id: `[a-z0-9_-]` |
| Agent run limits | `agents.defaults.{timeoutSeconds,maxConcurrent,bootstrapMaxChars,bootstrapTotalMaxChars,thinkingDefault}` | workspace files: 20000 chars each, 60000 total by default |
| Plugins | `plugins.entries.<id>.{enabled,config,hooks,llm,subagent}`, `plugins.{allow,deny,load.paths}` | `config` shape: `oc.py schema plugins.entries.<id>.config` |
| Skills | `skills.entries.<key>.{enabled,env,apiKey,config}`, `skills.load.extraDirs`, `agents.defaults.skills`, `agents.entries.<id>.skills` | allowlists: non-empty list = final set |
| MCP | `mcp.servers.<name>.{command,args,cwd,env,url,transport,enabled,toolFilter,requestTimeoutMs}` | tools appear as plugin `bundle-mcp` |
| Tools | `tools.{profile,allow,alsoAllow,deny}`, per agent `agents.entries.<id>.tools.*` | profiles minimal/coding/messaging/full |
| Exec | `tools.exec.{mode,host,timeoutSeconds,pathPrepend,safeBins}` | mode deny/allowlist/ask/auto/full; host approvals via `openclaw approvals` |
| Browser | `browser.{enabled,headless,executablePath,defaultProfile,profiles,ssrfPolicy,evaluateEnabled}` | |
| Telegram | `channels.telegram.{enabled,tokenFile,dmPolicy,allowFrom,groupPolicy,groups,streaming}` | dmPolicy + groupPolicy required |
| Routing | `bindings[]` `{agentId, match:{channel,accountId}}` | array, written whole |
| Heartbeat | `agents.defaults.heartbeat.{every,model,activeHours,target}` | Pedro: every 30m |
| Gateway | `gateway.{port,bind,auth,reload.mode}` | restart; keep loopback + token |

## 2. Recipes

**Switch Pedro's sub-agents to another model** (it must already be a llama-swap model in a group that runs next to
the orchestrator - otherwise first change the llama-swap group with /update-config-of-model):
```json5
// 20261101-subagents-qwen36.json5: sub-agents on qwen3.6-35b-a3b instead of the gemma pool (why: ...)
{
  models: { providers: { vllm: { models: [
    ...,   // all current entries from `openclaw config get models.providers.vllm.models --json`
    { id: "qwen3.6-35b-a3b", name: "Qwen3.6 35B (sub-agents)", reasoning: true, input: ["text"],
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }, contextWindow: 65536, maxTokens: 16384 },
  ] } } },
  agents: {
    defaults: { models: { "vllm/qwen3.6-35b-a3b": {} }, subagents: { model: "vllm/qwen3.6-35b-a3b" } },
    entries: { miclaw: { modelPolicy: { allow: ["vllm/qwen3.8-flash-next-uncensored", "vllm/gemma-4-26b-a4b-pool", "vllm/qwen3.6-35b-a3b"] } } },
  },
}
```
Test: `oc.py test miclaw "Spawn two sub-agents: one lists the files in your workspace, one says the date. Report both."`
- the JSON shows the orchestrator; sub-agent sessions appear in `openclaw health` as `agent:miclaw:subagent:<uuid>`.
Docs: `$D/concepts/models.md`, `$D/gateway/config-agents/models.md`, `$D/tools/subagents/*.md`,
`$D/gateway/config-tools/sessions-and-subagents.md`, `$D/providers/vllm.md`.

**Remove a model** from the catalog: write the array without it and add `--replace-path models.providers.vllm.models`;
also remove it from `agents.defaults.models` (`"vllm/<id>": null`), `modelPolicy.allow` and any `model` that uses it.

**Context window / output limit**: change `contextWindow` / `maxTokens` in the model's `models.providers.vllm.models[]`
entry (the whole array again). Never above what llama-swap serves per request (its `--ctx-size` per slot).

**Sub-agent limits**: `{ agents: { defaults: { subagents: { maxConcurrent: 8, maxChildrenPerAgent: 8 } } } }` - only
useful if the sub-agent model has that many parallel slots in llama-swap.

**New agent**: `timeout 60 openclaw agents add research --workspace ~/.openclaw/workspace-research --model vllm/<id> --non-interactive`
(`--role researcher|writer|reviewer|coordinator` seeds AGENTS.md/SOUL.md/IDENTITY.md). Then a patch for
`agents.entries.research.{identity,modelPolicy,skills,tools}`. Pedro may delegate to it only if
`agents.defaults.subagents.allowAgents` (or `agents.entries.miclaw.subagents.allowAgents`) lists it. Channel routing:
`openclaw agents bind --agent research --bind telegram:<accountId>`. Docs: `$D/cli/agents.md`, `$D/concepts/multi-agent.md`,
`$D/gateway/config-agents/entries-and-multi-agent.md`.

**Agent identity / personality / rules**: identity = `agents.entries.<id>.identity` (+ `IDENTITY.md`); persona and
tone = `SOUL.md`; operating rules, priorities, local tool notes = `AGENTS.md` (`## Tools` section); the user = `USER.md`.
Edit the files with a backup (`oc.py backup <what> ~/.openclaw/workspace/SOUL.md`), keep each under 20000 chars,
test in a new session (the test prints `TRUNCATED` when a file is cut). Docs: `$D/concepts/agent-workspace.md`,
`$D/concepts/soul.md`, `$D/gateway/config-agents/workspace-and-bootstrap.md`.

**Plugins**: `openclaw plugins list --enabled`, `openclaw plugins inspect <id> --runtime`; on/off:
`timeout 60 openclaw plugins enable <id>` / `disable <id>` (writes `plugins.entries.<id>.enabled`); settings:
```json5
{ plugins: { entries: { "<id>": { config: { /* keys from: oc.py schema plugins.entries.<id>.config */ } } } } }
```
After config changes the gateway replaces the plugin; if it reports a drain problem: `openclaw plugins reload <id> --wait`.
Install from ClawHub/npm/path: `openclaw plugins install <spec>` (ask the user first: third-party code).
Docs: `$D/tools/plugin.md`, `$D/cli/plugins.md`, `$D/cli/plugins/install.md`, `$D/plugins/<id>.md` if it exists.

**Skills**: bundled ones are switched in `skills.entries.<key>.enabled` (`openclaw skills list` shows status and
missing requirements, `openclaw skills check`). Per-agent visibility: `agents.entries.<id>.skills: [...]`. Env/API key
for one skill: `skills.entries.<key>.env` / `.apiKey` (SecretRef, not plaintext). Docs: `$D/tools/skills.md`,
`$D/tools/skills-config.md`, `$D/cli/skills.md`.

**MCP server**: `timeout 60 openclaw mcp add <name> --command <cmd> --arg <arg> --cwd <dir>` (stdio) or
`--url <url> --transport streamable-http --include 'search,read_*'`; then `openclaw mcp doctor <name> --probe`. As a patch:
```json5
{ mcp: { servers: { fetch: { command: "uvx", args: ["mcp-server-fetch"], enabled: true, requestTimeoutMs: 20000 } } } }
```
With a restricted tools profile add `tools.alsoAllow: ["bundle-mcp"]`. Docs: `$D/tools/mcp.md`, `$D/cli/mcp/registry.md`,
`$D/gateway/config-extensions.md`.

**Telegram**: token from @BotFather into `~/.secrets/telegram-bot-token` (mode 600, regular file, the user pastes
it - never in chat), then:
```json5
{
  channels: { telegram: { enabled: true, tokenFile: "/home/mkoniu/.secrets/telegram-bot-token",
                          dmPolicy: "pairing", groupPolicy: "disabled" } },
  bindings: [ { agentId: "miclaw", match: { channel: "telegram", accountId: "default" } } ],
}
```
`pairing` = unknown senders get a code: `openclaw pairing list telegram`, `openclaw pairing approve telegram <CODE>`; `allowlist` + `allowFrom: [<user id>]` =
only listed users. Check `openclaw channels status --probe`. Docs: `$D/channels/telegram/setup.md`,
`$D/channels/telegram/access-control.md`, `$D/channels/pairing.md`, `$D/gateway/config-channels.md`.

**Exec approvals / what Pedro may run**: inspect `openclaw approvals get`, `openclaw exec-policy show --agent miclaw`.
Policy: `tools.exec.mode` (or per agent `agents.entries.<id>.tools.exec.mode`); do not mix with legacy
`security`/`ask` in the same object (patch refuses). Allowlist: `openclaw approvals allowlist add --agent miclaw "/usr/bin/uptime"`
(back up with `approvals get --json` first). Docs: `$D/tools/exec-approvals.md`, `$D/cli/approvals.md`, `$D/tools/exec.md`.

**Tool profile / allow / deny**: `{ tools: { profile: "coding", alsoAllow: ["web_search", "web_fetch"], deny: ["browser"] } }`;
per agent under `agents.entries.<id>.tools`. `write` and `apply_patch` are separate ids: to block file writes deny
`["write", "edit", "apply_patch"]` (`group:fs` would remove `read` too). Docs: `$D/gateway/config-tools/tool-policy.md`, `$D/gateway/config-tools/built-in-tools.md`.

**Browser**: `{ browser: { enabled: true, headless: true } }`; profiles and CDP in `browser.profiles`. Docs:
`$D/tools/browser.md`, `$D/tools/browser-linux-troubleshooting.md`, `$D/gateway/config-browser-ui-desktop.md`.

**Gateway**: port/bind/auth changes need a restart and break every client that has the old address/token (Control UI,
CLI, phone). Keep `bind: "loopback"` unless the user explicitly wants LAN access (then token auth stays on).
Docs: `$D/gateway/config-gateway.md`, `$D/gateway/configuration/hot-reload.md`, `$D/gateway/security/`.

## 3. Custom capabilities (OpenClaw does not ship it)
Pick the lightest option that works, in this order:
1. **Workspace skill** - instructions (+ optional scripts) the agent follows with its normal tools. Folder
   `~/.openclaw/workspace/skills/<name>/SKILL.md`, front matter `name` (= folder, lowercase-hyphen) and one-line
   `description` (< 160 chars; it decides when the agent picks the skill), scripts in the same folder referenced as
   `{baseDir}/scripts/x.py`. Picked up live (watcher): `openclaw skills info <name>`, then
   `oc.py test miclaw "<a request the skill should handle>"` - the skill must be in the printed skills list (in chat:
   `/new`, then `/skill <name>` forces it). Optional gating (`requires.bins`, `requires.env`): `$D/tools/skills.md#gating`.
   Docs: `$D/tools/creating-skills.md`, `$D/tools/skills.md`.
2. **Exec script / CLI** - a script the agent runs with `exec` (needs `tools.exec` policy to allow it). Keep it in the
   workspace (e.g. `~/.openclaw/workspace/bin/`), describe usage in a skill or in AGENTS.md `## Tools`. Docs: `$D/tools/exec.md`.
3. **MCP server** - when a ready-made MCP server exists or other clients (opencode, Open WebUI) should use the same tool.
   Wire it in with `openclaw mcp add` (section 2). Docs: `$D/tools/mcp.md`.
4. **Plugin** - typed tools running inside the gateway, own config schema, hooks, channels or providers. Scaffold in a
   git repo, not in `~/.openclaw`:
   `cd ~/Desktop/github_repos && timeout 60 openclaw plugins init <id> --type tool`, `cd <id> && npm install &&
   npm run plugin:build && npm run plugin:validate && npm test`, then `timeout 120 openclaw plugins install -l ./`
   (link for development), `openclaw plugins inspect <id> --runtime`; after edits `npm run plugin:build` +
   `openclaw plugins reload <id> --wait`. Docs: `$D/plugins/building-plugins.md`, `$D/plugins/tool-plugins.md`,
   `$D/plugins/manifest.md`, `$D/plugins/hooks.md`, `$D/plugins/sdk-overview.md`, `$D/cli/plugins/authoring.md`.
Scheduled work: `openclaw cron` (`$D/automation/cron-jobs.md`); reacting to events: hooks (`$D/automation/hooks.md`);
standing instructions: `$D/automation/standing-orders.md`; periodic check-ins: heartbeat (`$D/gateway/heartbeat.md`).

## 4a. Rig state (28 Oct 2026; moved here from SKILL.md - check with `oc.py state`)
- **OpenClaw 2026.10.5**, global npm install `~/.npm-global/lib/node_modules/openclaw`, CLI `~/.npm-global/bin/openclaw`
  (put `~/.npm-global/bin` on PATH if `openclaw` is not found). Gateway: systemd user service `openclaw-gateway`,
  127.0.0.1:18789 (loopback, token auth), reload mode hybrid: most edits apply live, the CLI says when a restart is needed.
- **Config** `~/.openclaw/openclaw.json` (plain JSON, 0600) holds the gateway token and the provider key. OpenClaw's
  own `openclaw.json.bak`, `.bak.1-4` and `.last-good` rotate on every write - not your backup.
- **Agent** `miclaw` = "Pedro", the only agent. Workspace `~/.openclaw/workspace` (AGENTS.md, SOUL.md, IDENTITY.md,
  USER.md; no workspace skills yet), agent dir `~/.openclaw/agents/miclaw/agent` (sessions in SQLite).
- **Models**: provider `vllm` = llama-swap `http://127.0.0.1:8080/v1` (api openai-completions; the name is
  historical). Orchestrator `vllm/qwen3.8-flash-next-uncensored` (`agents.defaults.model.primary`, ctx 131072,
  maxTokens 32768); sub-agents `vllm/gemma-4-26b-a4b-pool` (`agents.defaults.subagents.model`, ctx 65536, maxTokens
  16384, maxConcurrent 4, maxChildrenPerAgent 4, maxSpawnDepth 1 - the pool serves 4 parallel slots).
  `agents.entries.miclaw.modelPolicy.allow` lists exactly these two.
- **llama-swap**: config `~/.config/llama-swap/config.yaml` (watched, saving reloads it). Group `pedro` keeps both
  Pedro models loaded, group `duo` = qwen3.8-flash-next + qwen3.6-35b-a3b; any model outside the active group unloads
  that group. RAM 60 GB is the limit: radiance models (qwen3.8-flash-next*) pin ~30 GB RAM - never two at once.
- **Enabled now**: plugins vllm, telegram, gmail, browser-automation, browser-use, duckduckgo, llama-cpp,
  expedia-openclaw, aws-knowledge (+ stock plugins on by default). `gmail` fails at start (no `username`) - known,
  not your change. 28 bundled skills disabled in `skills.entries`; no `channels.*` configured yet (Telegram plugin on,
  no bot); no MCP servers; `tools.profile: "full"`; exec approvals: security full, ask off (SQLite, not openclaw.json).
- Pedro's bundled helper skills (`openclaw skills info add-model-provider|configure-channel|diagnose-gateway|skill-creator`)
  are good extras. Offline docs: ~1300 pages.
- Rig docs: `~/Desktop/github_repos/llm-private-education/en/03-MODELS-AND-SERVING.md` (OpenClaw section),
  `en/08-CONFIG-MAP.md` (+ PL versions).

## 4b. Traps (full list; the SKILL.md gotchas are the short form)
- **Model ids are not checked**: `agents.defaults.model.primary: "vllm/does-not-exist"` passes dry-run, apply and
  validate (local endpoints accept any name) and fails only at the first turn. Check every id against
  `curl -s localhost:8080/v1/models`. A model used anywhere needs a `models.providers.vllm.models[]` entry (that
  is where its contextWindow, maxTokens and image input come from) and, for Pedro, a `modelPolicy.allow` entry.
- **Silent array replace**: only `models.providers*`, `agents.defaults.models`, `agents.entries`, `plugins.entries`
  and `auth.profiles` are protected. `modelPolicy.allow: ["vllm/gemma-4-26b-a4b-pool"]` dry-runs fine and drops the
  orchestrator from Pedro's allowlist; `{ plugins: { entries: { gmail: null } } }` silently deletes the entry.
- **Per-agent values replace defaults**: `agents.entries.<id>.skills` (non-empty = the final set, `[]` = none),
  `.modelPolicy.allow`, `.model`, `.tools.*`. Per-agent `subagents` has only allowAgents, delegationMode, model,
  requireAgentId, thinking - limits (maxConcurrent...) exist only in `agents.defaults.subagents`.
- **Sessions keep old state**: existing sessions keep a model picked with `/model` (`/model default` clears it)
  and their skills snapshot. Always test in a new session (`/new` in chat, new `--session-key` on the CLI).
- **llama-swap must match**: sub-agent and orchestrator models must sit in the same llama-swap group or every
  spawn swaps models (minutes, kills the other). More concurrent sub-agents than the pool's `--parallel` slots
  only queue. `contextWindow`/`maxTokens` must not exceed what the llama-swap entry serves per request.
- **OpenClaw rewrites the file**: every write reserializes openclaw.json as plain JSON (comments lost - keep them
  in the patch files). Hand edits are validated by the watcher; an invalid one is skipped and the old runtime stays
  (looks like "nothing happened") - only hand-copy a backup back, otherwise use `config patch`.
- **CLI writers**: `plugins install/enable/disable/uninstall`, `skills install`, `mcp add/set`, `agents add/bind`,
  `channels add` write openclaw.json too - back up before and `oc.py diff` after. Exec approvals are in SQLite
  (`~/.openclaw/state/openclaw.sqlite`): config backups do not cover them.
- **Wizards and repairs**: no `openclaw configure`, `onboard`, `setup`, `doctor --fix`, `reset` unless that is the
  request - they rewrite large parts of the config. `config set <path> <value>` without `--strict-json` skips the
  schema check in dry-run; prefer patch files.
- **Restarts** end every running Pedro turn and sub-agent; check `openclaw health` first.
- Deleting files: `gio trash PATH`, never `rm -rf`. Never print tokens (`~/.secrets/`, openclaw.json, `.env`).

## 4c. Verification commands per area
`openclaw models list --provider vllm`; `openclaw plugins inspect <id> --runtime`; `openclaw skills list` /
`skills info <name>`; `openclaw mcp doctor <name> --probe`; `openclaw channels status --probe`;
`openclaw exec-policy show --agent miclaw`; `openclaw health`.
Raw test turn (what `oc.py test` wraps):
`timeout 960 openclaw agent --agent miclaw --session-key agent:miclaw:<new-key> --json --timeout 900 --message "..."`.

## 4. Where to read (docs map)
| Need | Page |
|---|---|
| config commands, patch semantics, dry-run, write safety | `$D/cli/config.md` |
| what hot-applies vs needs restart | `$D/gateway/configuration/hot-reload.md` |
| full key index | `$D/gateway/configuration-reference.md` |
| model selection, policy, "Model is not allowed" | `$D/concepts/models.md`, `$D/gateway/config-agents/models.md` |
| local OpenAI-compatible provider | `$D/providers/vllm.md`, `$D/gateway/local-models.md` |
| sub-agents | `$D/tools/subagents/` (tool-policy, nesting, operations), `$D/gateway/config-tools/sessions-and-subagents.md` |
| agents, routing, workspaces | `$D/cli/agents.md`, `$D/concepts/multi-agent.md`, `$D/concepts/agent-workspace.md` |
| secrets (SecretRef, files, env) | `$D/gateway/secrets.md`, `$D/tools/secrets.md` |
| sandboxing and elevated exec | `$D/gateway/sandboxing.md`, `$D/gateway/sandbox-vs-tool-policy-vs-elevated.md` |
| when something breaks | `$D/gateway/troubleshooting.md`, `openclaw logs`, `journalctl --user -u openclaw-gateway -n 100` |
