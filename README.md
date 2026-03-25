<p align="center">
  <img src="images/banner.jpg" alt="The Azeroth Guide" width="100%">
</p>

# mod-llm-guide

An AI-powered in-game assistant for AzerothCore that actually queries your game database.

---

<p align="center">
  <a href="https://discord.gg/tvVcecuR"><img src="https://img.shields.io/badge/Discord-Join%20the%20Community-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Join Discord"></a>
</p>

> See my other module: **[mod-llm-chatter](https://github.com/Hokken/mod-llm-chatter)** — AI-powered ambient bot conversations for mod-playerbots

---

Ask a question, get an answer with clickable item/quest/spell links, backed by 29 specialized database tools that pull live data from your server.

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
    Scarlet Monastery chain — pick it up from [Raleigh the Devout]
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
Every answer comes from your actual game database — not from AI memory or training data. When the guide says [Riverpaw Leather Vest] drops from [Hogger] at 15%, that's the real drop rate on your server. No guesswork, no approximations, no outdated information.

### Closest Results First
Ask "where can I learn cooking?" and the guide shows the nearest trainer first, with the area they're in and map coordinates: *"Zarrin in Dolanaar (~15 m southeast at 57.1, 61.3)"*. Works with GPS addons. Supports yards or meters (configurable).

### Knows Your Character
The guide reads your character's live state: level, race, class, zone, gold, professions, gear, and quest log. Ask "what quests can I do here?" and it filters by your level, class, and faction. Ask "where should I train mining?" and it knows your current skill level.

### Clickable Links
Every item, quest, spell, and NPC name in responses becomes a proper in-game hyperlink. Hover for tooltips, click to inspect — just like links from real players.

### Understands Natural Language
Ask questions however you want. "Where can I buy cooking supplies?", "any blacksmith trainer near me?", "I need to find an inn" — the guide understands what you're looking for even with typos or casual phrasing.

### Multi-Provider Support
Works with Anthropic Claude or OpenAI GPT. Haiku and GPT-4o-mini are recommended for their speed and low cost.

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
- Python 3.8+
- An API key from [Anthropic](https://console.anthropic.com/) or [OpenAI](https://platform.openai.com/)

## Quick Start (Docker)

### 1. Configure the module

```bash
cp modules/mod-llm-guide/conf/mod_llm_guide.conf.dist \
   env/dist/etc/modules/mod_llm_guide.conf
```

Edit `env/dist/etc/modules/mod_llm_guide.conf`:
```ini
LLMGuide.Enable = 1
LLMGuide.Anthropic.ApiKey = sk-ant-your-key-here
LLMGuide.Database.Host = ac-database
```

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

Key settings in `mod_llm_guide.conf`:

| Setting | Default | Description |
|---------|---------|-------------|
| `LLMGuide.Enable` | 0 | Enable the module |
| `LLMGuide.Provider` | anthropic | `anthropic` or `openai` |
| `LLMGuide.Anthropic.ApiKey` | -- | Your Anthropic API key |
| `LLMGuide.OpenAI.ApiKey` | -- | Your OpenAI API key |
| `LLMGuide.Database.Host` | localhost | Use `ac-database` for Docker |
| `LLMGuide.CooldownSeconds` | 10 | Seconds between questions |
| `LLMGuide.MaxTokens` | 300 | Max response tokens |
| `LLMGuide.Temperature` | 0.7 | Creativity (0.0-1.0) |
| `LLMGuide.DistanceUnit` | yards | `yards` or `meters` |
| `LLMGuide.Memory.Enable` | 1 | Remember conversations |
| `LLMGuide.Memory.MaxPerCharacter` | 20 | Max stored memories |
| `LLMGuide.Memory.ContextCount` | 5 | Recent memories in context |

## Cost

| Provider | Model | Per 1000 questions |
|----------|-------|-------------------|
| Anthropic | Claude Haiku | ~$0.10-0.15 |
| OpenAI | GPT-4o-mini | ~$0.15-0.20 |

Tool-calling models are required. Haiku and GPT-4o-mini both support this and are the recommended choices.

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
