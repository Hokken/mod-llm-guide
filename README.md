<p align="center">
  <img src="images/banner.jpg" alt="The Azeroth Guide" width="100%">
</p>

# mod-llm-guide

An AI-powered in-game assistant for AzerothCore that actually queries your game database.

---

<p align="center">
  <a href="https://discord.gg/9UBW7ZDZvY"><img src="https://img.shields.io/badge/Discord-Join%20the%20Community-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Join Discord"></a>
</p>

> See my other module: **[mod-llm-chatter](https://github.com/Hokken/mod-llm-chatter)**, AI-powered ambient bot conversations for mod-playerbots

---

Ask a question, get an answer with clickable item/quest/spell links, all backed by live data from your server.

## Latest Updates

See [CHANGELOG.md](CHANGELOG.md) for the full release history.

### September 2026 - Easier Model and Provider Switching

- Added model-aware request compatibility for Anthropic, OpenAI, Google
  Gemini, OpenRouter, and local Ollama models.
- Added reasoning-safe token budgets and bounded recovery when a provider
  rejects an unsupported request parameter.
- Expanded provider setup guidance so changing models normally requires only
  selecting the provider and exact model ID.

### May 2026 - Google Gemini and OpenRouter Support

- Added Google Gemini support through Google's OpenAI-compatible API,
  including Gemini 3.1 Flash-Lite defaults and Gemini reasoning/thinking
  config options.
- Added OpenRouter support through its OpenAI-compatible API, with
  optional attribution headers. Recommended OpenRouter models include
  `anthropic/claude-haiku-4.5`, `openai/gpt-4o-mini`, and
  `openai/gpt-4.1-mini`.
- Clarified that Azeroth Guide requires models with reliable
  tool/function calling, regardless of provider. Plain-chat models or
  models with weak function argument handling are not suitable for
  factual guide answers.

## What It Does

**It knows where things are, relative to you:**
```
You: .ag where's the closest leatherworking trainer?
Azeroth Guide: [Darianna] is ~120 yards southwest of you in the
  Craftsmen's Terrace. She can train you up to Artisan (300).
  Your Leatherworking is at 178, so you're good to go.
```

**It chains tools to build complete answers:**
```
You: .ag I just hit 40, what should I be doing?
Azeroth Guide: Congrats on 40! A few things to look into:
  • You can now learn [Plate Mail] from your class trainer
    [Ander Germaine] (~85 yards northeast)
  • The quest [In the Name of the Light] opens up the
    Scarlet Monastery chain, pick it up from [Raleigh the Devout]
    in Southshore
  • At your level, Stranglethorn Vale and Tanaris are solid
    zones. You've got 3 quests in STV already in your log
```

**It pulls real data from your server's database, not from memory:**
```
You: .ag where can I mine tin around here?
Azeroth Guide: Tin Ore nodes spawn throughout Darkshore, you'll need
  Mining 65+. Your Mining is at 72 so you're set. The densest
  spawns are along the cliffs between Auberdine and the Ruins
  of Mathystra. You might also pick up some [Shadowgem] and
  [Moss Agate] from the nodes.
```

Every item, quest, spell, and NPC name in responses becomes a clickable WoW link.

## Features

### Real Answers from Your Server
Factual questions require a tool lookup. Answers must use entity links returned
by tools, and empty answers or answers supported only by failed lookups are
rejected. The model still writes the explanation: these checks reduce errors
but do not prove every sentence correct. Loot weights, grouped/reference loot,
server rates and conditional drops must not be confused with an effective
player-specific drop probability.

### Closest Results First
Ask "where can I learn cooking?" and the guide shows the nearest trainer first, with the area they're in and map coordinates: *"Zarrin in Dolanaar (~15 m southeast at 57.1, 61.3)"*. Works with GPS addons. Supports yards or meters (configurable).

### Knows Your Character
The guide reads your character's live state: level, race, class, zone, gold, professions, gear, and quest log. Ask "what quests can I do here?" and it filters by your level, class, and faction. Ask "where should I train mining?" and it knows your current skill level.

### Clickable Links
Every item, quest, spell, and NPC name in responses becomes a proper in-game hyperlink. Hover for tooltips, click to inspect, just like links from real players.

### Understands Natural Language
Ask questions however you want. "Where can I buy cooking supplies?", "any blacksmith trainer near me?", "I need to find an inn", the guide understands what you're looking for even with typos or casual phrasing.

### Multi-Provider Support
Works with Anthropic Claude, OpenAI GPT, Google Gemini, OpenRouter, or
local Ollama models. OpenAI-compatible requests use automatic model
capability profiles and learn safe parameter corrections when a new
model explicitly rejects an option.
Haiku, GPT-5.6 Luna, GPT-4o-mini, GPT-4.1-mini, Gemini 3.1 Flash-Lite, and
OpenRouter-hosted Haiku 4.5 / GPT mini models are recommended for
their speed and low cost.

Model choice matters: Azeroth Guide depends on tool/function calling
for factual answers. Regardless of provider, use a model that reliably
supports tool calls and structured tool arguments. Models that only do
plain chat, ignore tools, or produce malformed function arguments will
give poor or incorrect guide answers.

### What You Can Ask It About

Azeroth Guide is not just a quest bot. It can help with most of the
questions players actually ask while leveling, gearing, traveling, and
planning what to do next.

- **NPCs and services**
  Find vendors, trainers, innkeepers, bankers, flight masters,
  battlemasters, and weapon skill trainers near you.

- **Quests**
  Check who starts a quest, what it rewards, what comes next in a chain,
  and which quests make sense for your level or class.

- **Spells and training**
  See when your class learns a spell, how much it costs to train, and
  what abilities you should already have by your current level.

- **Items and loot**
  Look up item stats, possible upgrades, boss drops, and creature loot
  tables.

- **Creatures and rare spawns**
  Find named mobs, hostile creatures in a zone, hunter pets, and rare
  spawns.

- **Gathering and professions**
  Ask where to fish, mine, pick herbs, or where a recipe comes from.

- **Zones, dungeons, and travel**
  Check zone level ranges, dungeon bosses, nearby zones, and flight
  paths.

- **Reputation**
  See how to gain rep, what rewards unlock, and whether a faction is
  worth working on.

## Requirements

- AzerothCore WotLK (3.3.5a)
- Python 3.10+
- An API key from [Anthropic](https://console.anthropic.com/),
  [OpenAI](https://platform.openai.com/),
  [Google AI Studio](https://aistudio.google.com/app/apikey), or
  [OpenRouter](https://openrouter.ai/keys); or a reachable local Ollama server

## Provider and Model Setup

Configuration uses unquoted `Key = value` lines. Copy exact API model IDs,
not provider display names. OpenRouter IDs use `vendor/model`; Ollama IDs use
the name and optional tag shown by `ollama list`. Leave an optional value
empty after `=`.

Unlike chatter's universal model key, the guide has one model key per
provider. This lets users keep several provider setups in the same file and
switch by changing only `LLMGuide.Provider` after the keys and model choices
have been entered once.

| Provider | Provider value | Model setting | Credential |
|----------|----------------|---------------|------------|
| Anthropic | `anthropic` | `LLMGuide.Anthropic.Model` | `LLMGuide.Anthropic.ApiKey` |
| OpenAI | `openai` | `LLMGuide.OpenAI.Model` | `LLMGuide.OpenAI.ApiKey` |
| Google | `google` | `LLMGuide.Google.Model` | `LLMGuide.Google.ApiKey` |
| OpenRouter | `openrouter` | `LLMGuide.OpenRouter.Model` | `LLMGuide.OpenRouter.ApiKey` |
| Ollama | `ollama` | `LLMGuide.Ollama.Model` | None |

Ready-to-copy examples (use only one provider value at a time):

```ini
# Anthropic
LLMGuide.Provider = anthropic
LLMGuide.Anthropic.Model = claude-haiku-4-5-20251001
LLMGuide.Anthropic.ApiKey = sk-ant-xxxxx

# OpenAI Luna
LLMGuide.Provider = openai
LLMGuide.OpenAI.Model = gpt-5.6-luna
LLMGuide.OpenAI.ApiKey = sk-xxxxx
LLMGuide.OpenAI.ReasoningEffort = none
LLMGuide.OpenAI.MaxTokensMultiplier = 4

# Google Gemini
LLMGuide.Provider = google
LLMGuide.Google.Model = gemini-3.1-flash-lite
LLMGuide.Google.ApiKey = AIza-xxxxx

# OpenRouter
LLMGuide.Provider = openrouter
LLMGuide.OpenRouter.Model = anthropic/claude-haiku-4.5
LLMGuide.OpenRouter.ApiKey = sk-or-v1-xxxxx

# Local Ollama from a Docker bridge
LLMGuide.Provider = ollama
LLMGuide.Ollama.Model = qwen3:8b
LLMGuide.Ollama.BaseUrl = http://host.docker.internal:11434
LLMGuide.Ollama.DisableThinking = 1
```

Restart `ac-llm-guide-bridge` after changing provider or model settings. The
bridge automatically selects compatible token, temperature, and reasoning
parameters, and remembers explicit unsupported-parameter corrections until
the process restarts. Users normally do not need to retune parameters merely
because they changed models.

For OpenAI Luna, `none` is the fast setting and allows the configured
temperature. Higher reasoning efforts can consume more of the output budget;
the bridge applies `OpenAI.MaxTokensMultiplier` whenever hidden reasoning may
be active and omits temperature when the selected model/effort does not
support it. See the [official Luna model page](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

For Ollama, first run `ollama pull <model>` on the Ollama host. A host-run
bridge normally uses `http://localhost:11434`; a Docker bridge normally uses
`http://host.docker.internal:11434`. Do not append `/v1`. The model must
reliably support OpenAI-style tool/function calling and structured arguments;
plain-chat models cannot provide grounded guide answers.

Ollama's OpenAI-compatible endpoint does not accept a per-request context
size. Because the guide sends a large tool catalog, set
`OLLAMA_CONTEXT_LENGTH` before starting Ollama, or create a custom model whose
Modelfile contains `PARAMETER num_ctx 8192`. Confirm the loaded value in the
`CONTEXT` column from `ollama ps`. Keep `Ollama.DisableThinking = 1` for
Qwen3-style models unless you deliberately want reasoning tokens.

Ollama accepts tool definitions through this endpoint but currently ignores
`tool_choice`. If its routing pass returns text instead of a tool call, the
guide skips that optional routing pass and lets the normal evidence/tool loop
handle the question. On the last tool round, the guide removes the tool
definitions entirely so the model must produce its final answer.

## Quick Start (Docker)

### 1. Configure the module

```bash
cp modules/mod-llm-guide/conf/mod_llm_guide.conf.dist \
   env/dist/etc/modules/mod_llm_guide.conf
```

Edit `env/dist/etc/modules/mod_llm_guide.conf`:
```ini
LLMGuide.Enable = 1
LLMGuide.Provider = anthropic
LLMGuide.Anthropic.Model = claude-haiku-4-5-20251001
LLMGuide.Anthropic.ApiKey = sk-ant-your-key-here
LLMGuide.Database.Host = ac-database
```

Use another recipe from [Provider and Model Setup](#provider-and-model-setup)
if you prefer OpenAI, Google, OpenRouter, or Ollama.

### 2. Add the bridge to docker-compose.override.yml

```yaml
services:
  ac-llm-guide-bridge:
    container_name: ac-llm-guide-bridge
    image: python:3.11-slim
    networks:
      - ac-network
    working_dir: /app
    environment:
      - PYTHONUNBUFFERED=1
    command: >
      bash -c "
        pip install --quiet -r /app/requirements.txt &&
        python llm_guide_bridge.py --config /config/mod_llm_guide.conf
      "
    volumes:
      - ./modules/mod-llm-guide/tools:/app:ro
      - ./env/dist/etc/modules:/config:ro
    restart: unless-stopped
    depends_on:
      ac-database:
        condition: service_healthy
    profiles: [dev]
```

### 3. Start

```bash
docker compose --profile dev up -d
```

### 4. Check logs

```bash
docker logs ac-llm-guide-bridge --since 5m
```

## Non-Docker Setup

### 1. Build the module

Place this repo under `modules/` in your AzerothCore source tree, then:

```bash
cd azerothcore/build
cmake .. -DCMAKE_INSTALL_PREFIX=/path/to/install
make -j$(nproc)
make install
```

### 2. Configure

```bash
cp conf/mod_llm_guide.conf.dist /path/to/etc/modules/mod_llm_guide.conf
```

Edit `mod_llm_guide.conf` and set your API key.

### 3. Start the bridge

```bash
cd tools/
pip install -r requirements.txt
python llm_guide_bridge.py --config /path/to/mod_llm_guide.conf
```

### 4. Start worldserver

Database tables are created automatically on first run.

## Usage

Use `.ag` for both normal questions and saved-history navigation.

```
.ag <question>
.ag history
.ag history 10
.ag history page 2
.ag history 10 page 2
.ag show 1
.ag show 11
.ag clear
.ag status
.ag cancel
```

### Commands

| Command | What it does |
|---------|--------------|
| `.ag <question>` | Ask Azeroth Guide a question |
| `.ag history` | Show page 1 of your saved history with 5 numbered entries by default |
| `.ag history <count>` | Show page 1 with up to `<count>` entries, capped at 10 |
| `.ag history page <number>` | Move to another history page while keeping the default page size of 5 |
| `.ag history <count> page <number>` | Move to a specific history page while also choosing how many entries to show per page, up to 10 |
| `.ag show <number>` | Open one saved interaction by its history number and show the full stored question and full stored answer |
| `.ag clear` | Clear this character's saved guide conversation history |
| `.ag status` | Show outstanding requests without making a provider call |
| `.ag cancel` | Cancel outstanding requests; late worker replies are discarded |

### History Navigation

Think of `.ag history` as your index and `.ag show` as your open
command.

- Run `.ag history` to see your most recent numbered entries.
- If you want older entries, run `.ag history page 2`, `.ag history page 3`, and so on.
- If you want more entries per page, use `.ag history 10` or `.ag history 10 page 2`.
- When you find the entry you want, run `.ag show <number>` with that exact number.

Example flow:

```text
.ag history
1. Q: what are my next spells
2. Q: where is the mining trainer
3. Q: what dungeon should I run

.ag show 2
```

That will open the full saved question and full saved answer for entry
`2`.

### Notes

- History is stored per character
- In `.ag history`, entry `1` is always your most recent interaction
- History numbering stays consistent across pages, so if page 2 shows
  `11.`, you can open it with `.ag show 11`
- `.ag clear` only clears guide conversation memory/history
- It does not cancel pending questions or change cooldowns

## Configuration

When upgrading, start the updated bridge before using the updated C++ module.
Bridge startup preserves existing data, widens character context storage and
adds the snapshot and request-recovery columns automatically. Its database
account needs ALTER permission. Full character snapshots and the status/cancel
commands require the updated C++ module to be built and installed.

Request timeouts, retry limits, worker count and gear comparison filters are
documented in `conf/mod_llm_guide.conf.dist`. Worldserver settings use
`.reload config`; bridge settings require a bridge restart. Gear comparisons
show base-stat tradeoffs and known requirements, not simulated performance;
gems, enchants, set bonuses, procs and source accessibility need further checks.

Equipment summaries label the actual worn slots (including separate rings,
trinkets and back) and provide verified item links. Profession summaries include
primary professions, Fishing, Cooking and First Aid; Riding is listed separately
as a travel skill, and racial skills are not listed as professions. These context
improvements require the updated C++ module.

The bridge links exact, unambiguous item names from the current request's tool
results, without inventing IDs. Comparison tools retain base-stat deltas,
required levels and acquisition source leads for the answer model. An optional
diagnostic appendix can repeat them in full. Unknown sources remain explicit. These checks
do not establish affordability, dungeon access, character DPS or pet scaling,
and candidates are not an exhaustive best-in-slot ranking.

Tool defaults are injected only into fields accepted by that tool's schema.
The bridge can restore canonical link formatting when the entity type, ID and
normalized name agree with current tool evidence. Unknown IDs, different names
and ambiguous matches remain rejected; rejected-link logs identify the entity
type and ID for diagnosis.

Shared question routing covers all registered guide tools. Narrow exact requests
can select a lookup directly; other factual questions use a classifier call on
the configured provider/model. Its complete plan is validated against existing
tool schemas before any lookup executes. Ambiguous or invalid plans ask for
clarification. Lookup results feed the answer stage, which can request further
tools. Routing shares the request deadline and can add latency and token cost.

Service routing uses canonical categories, not fuzzy title matching. Flight
masters are located by their database NPC flag, including Gryphon Masters.
Travel route data remains incomplete: routing does not prove a fastest route or
which flight nodes a character has unlocked. Model intent selection can still
be wrong; validation constrains calls but does not guarantee interpretation.

Answer-readiness checks run locally before each answer round, without a
separate model review call. They track failed, empty and unresolved lookups;
missing service-NPC distances; unavailable character snapshots; incomplete
upgrade comparisons; and the limits of travel data. The existing tool loop can
fill gaps within its normal deadline and round budget. Unresolved limitations
are retained in the final response. If no lookup produced usable information,
a deterministic limitation message replaces the model's answer without
exposing backend errors. Identical successful retries clear earlier failures;
different searches remain separate, and all checks reset with each request.

These checks recognize known result formats, not arbitrary natural-language
intent or every possible factual contradiction. They do not prove that the
selected tools fully answer the player's question. New tool output formats
should update the readiness rules and their regression tests.

All unresolved answer links are checked, including references previously
mentioned only as plain text. History itself is not evidence. NPCs, items
and quests are rechecked
by exact database ID and normalized name; spell identities use the current
spell-name catalog shared with spell tools. Only identities are refreshed:
historical locations, availability, stats and route claims are not revalidated
by this step. Gameplay answers still require current factual lookup evidence.
Missing IDs and mismatched names ask for clarification; a real identity does
not prove the answer's claims about it. Checks share the request deadline,
deduplicate repeated links,
and use a configurable budget without another LLM call.

Quest detail and chain tools accept `quest_id` for exact stage selection, or
`quest_name` for title lookup. Active quest IDs come from the server request,
are exposed by character context, and prioritize same-title stages before
result limits. Multiple active stages with the same title ask for clarification.
Chain output labels the selected active stage and reports partial-link limits;
it does not claim that the last returned stage establishes the final reward.

Conversation resolution is shared across subjects. With routing and memory
enabled, follow-ups get one additional bounded model call that rewrites the
question into a standalone request, preserving related goals, entity IDs and
constraints while discarding unrelated goals on topic switches. Ambiguous
references ask for clarification. Unsupported capabilities are explained
instead of silently substituting a different search. Interpretation remains
model-dependent; this does not implement new crafting or route-planning tools.

Compact intent and pending clarification state use the existing per-character
memory summary field. Entity references are reconstructed from answer links;
they are not evidence of current facts. Oversized intent falls back to legacy
Q&A history without storing truncated JSON. Memory pruning and memory-disabled
behavior remain unchanged. No additional tables or files store player state.

All provider adapters export portable copies of the same tool definitions;
local validation retains root alternative-argument requirements. Export tests
cover every catalog. Opt-in `test_provider_live.py` uses the configured provider
with synthetic conversations and no database writes; set
`GUIDE_TEST_PROVIDER_CONFIG` to a bridge config to run it. These tests make
paid API requests and are skipped by default.

Answers on every topic now target 60 words by default: a useful conclusion or
next action, essential locations/links and brief uncertainty, not exhaustive
lists. Explicit requests for detail can be longer. This is a soft generation
target, not truncation: existing link-safe chat chunking remains available.
Full comparison appendices are off by default. Readiness diagnostics remain in
model context, while player-facing limitations are short. These choices reduce
duplicate text and the frequency of multi-chunk replies.
Ordinary recommendations omit internal lists of unevaluated effects (enchants,
gems, procs and pet scaling), retaining useful tradeoffs and unknown sources.
Excluded effects are discussed only when requested or materially relevant.
Ordinary item recommendations use links, sources and qualitative reasons;
numeric stat parentheses are omitted because tooltips show the stats. A final
presentation pass removes known comparison boilerplate and stat parentheses
without modifying entity links, coordinates or equip requirements. Explicit
stat/comparison questions retain numeric detail. Old answers are cleaned for
provider history replay without modifying stored memories.

Key settings in `mod_llm_guide.conf`:

| Setting | Default | Description |
|---------|---------|-------------|
| `LLMGuide.Enable` | 0 | Enable the module |
| `LLMGuide.Provider` | anthropic | `anthropic`, `openai`, `google`, `openrouter`, or `ollama` |
| `LLMGuide.Anthropic.ApiKey` | -- | Your Anthropic API key |
| `LLMGuide.Anthropic.Model` | claude-haiku-4-5-20251001 | Exact Anthropic model ID |
| `LLMGuide.OpenAI.ApiKey` | -- | Your OpenAI API key |
| `LLMGuide.OpenAI.Model` | gpt-4o-mini | Exact OpenAI API model ID, such as `gpt-5.6-luna` |
| `LLMGuide.OpenAI.ReasoningEffort` | empty | Model default; use `none` for fast Luna requests |
| `LLMGuide.OpenAI.MaxTokensMultiplier` | 4 | Output multiplier used only when hidden OpenAI reasoning may be active |
| `LLMGuide.Google.ApiKey` | -- | Your Google Gemini API key |
| `LLMGuide.Google.Model` | gemini-3.1-flash-lite | Exact Gemini API model ID |
| `LLMGuide.Google.ReasoningEffort` | minimal | Used when `ThinkingBudget` is empty |
| `LLMGuide.Google.ThinkingBudget` | empty | Whole token budget; `0` disables thinking on Gemini 2.5 Flash |
| `LLMGuide.Google.MaxTokensMultiplier` | 1 | Output-budget multiplier |
| `LLMGuide.OpenRouter.ApiKey` | -- | Your OpenRouter API key |
| `LLMGuide.OpenRouter.Model` | anthropic/claude-haiku-4.5 | Exact `vendor/model` slug |
| `LLMGuide.OpenRouter.BaseUrl` | https://openrouter.ai/api/v1 | OpenAI-compatible endpoint |
| `LLMGuide.OpenRouter.HttpReferer` | empty | Optional complete attribution URL |
| `LLMGuide.OpenRouter.Title` | empty | Optional plain-text app title |
| `LLMGuide.Ollama.Model` | qwen3:8b | Local model; must support tool/function calling |
| `LLMGuide.Ollama.BaseUrl` | http://host.docker.internal:11434 | Local Ollama server URL |
| `LLMGuide.Ollama.DisableThinking` | 1 | Send `reasoning_effort = none` to compatible local models |
| `LLMGuide.Database.Host` | localhost | Use `ac-database` for Docker |
| `LLMGuide.Database.Name` | acore_characters | Characters database for requests and memories |
| `LLMGuide.Database.WorldName` | acore_world | World database for game-data lookups; restart the bridge after changing |
| `LLMGuide.CooldownSeconds` | 10 | Seconds between questions |
| `LLMGuide.MaxTokens` | 300 | Max response tokens |
| `LLMGuide.Temperature` | 0.7 | Creativity (0.0-1.0); omitted automatically when unsupported |
| `LLMGuide.DistanceUnit` | yards | `yards` or `meters` |
| `LLMGuide.Memory.Enable` | 1 | Remember conversations |
| `LLMGuide.Memory.MaxPerCharacter` | 20 | Max stored memories |
| `LLMGuide.Memory.ContextCount` | 5 | Recent memories in context |
| `LLMGuide.Routing.Enable` | 1 | Shared question triage; 0 restores direct tool calling |
| `LLMGuide.Conversation.Enable` | 1 | Resolve follow-ups before routing; shares request deadline and routing token budget |
| `LLMGuide.Answer.TargetWords` | 60 | Soft answer-length target for all topics |
| `LLMGuide.Answer.AppendComparisonDetails` | 0 | Opt into the full diagnostic comparison appendix |
| `LLMGuide.Routing.MaxCalls` | 3 | Maximum independent initial lookups |
| `LLMGuide.Routing.MaxTokens` | 600 | Classifier output token budget |
| `LLMGuide.Readiness.Enable` | 1 | Check lookup completeness and retain limitations; restart bridge after changes |
| `LLMGuide.Followup.MaxEntityChecks` | 8 | Maximum unresolved identities checked per answer; excess asks for clarification |

## Cost

Cost depends on the selected model, prompt/tool traffic, answer length, and
current provider prices. Check the live pricing page for
[Anthropic](https://www.anthropic.com/pricing),
[OpenAI](https://developers.openai.com/api/docs/pricing),
[Google Gemini](https://ai.google.dev/gemini-api/docs/pricing), or the chosen
[OpenRouter model](https://openrouter.ai/models). Local Ollama has no API
token charge but uses your own hardware and electricity.

Tool/function calling is required. The guide asks the model to call
database tools for quests, NPCs, items, spells, trainers, vendors, and
other factual lookups. Use a model that reliably supports function
calling on your chosen provider. Haiku, GPT-5.6 Luna, GPT-4o-mini, GPT-4.1-mini,
Gemini 3.1 Flash-Lite, and OpenRouter-hosted Claude Haiku 4.5 / GPT
mini models are the recommended choices.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "LLM Chat is currently disabled" | Set `LLMGuide.Enable = 1`, restart worldserver |
| No response to questions | Check bridge logs for errors |
| "Can't connect to MySQL" | Docker: use `ac-database`. Non-Docker: use `localhost` |
| "Please wait X seconds" | Rate limit, adjust `CooldownSeconds` |

**Check logs:**
- Docker: `docker logs ac-llm-guide-bridge --since 5m`
- Non-Docker: check terminal output or redirect to a log file

## License

GNU AGPL v3, same as AzerothCore.
