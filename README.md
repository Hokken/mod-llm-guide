<p align="center">
  <img src="images/banner.jpg" alt="The Azeroth Guide" width="100%">
</p>

# mod-llm-guide

An AI-powered in-game assistant for AzerothCore that actually queries your game database.

---

<p align="center">
  <a href="https://discord.gg/tvVcecuR"><img src="https://img.shields.io/badge/Discord-Join%20the%20Community-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Join Discord"></a>
</p>

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

**It remembers what you talked about:**
```
You: .ag what drops from Edwin VanCleef?
Azeroth Guide: [Edwin VanCleef] in the Deadmines drops:
  [Blackened Defias Armor] (16%), [Cape of the Brotherhood] (14%),
  [Cruel Barb] (12%), and the quest item [Head of VanCleef]
  for [The Defias Brotherhood] chain.

You: .ag is any of that good for me?
Azeroth Guide: At level 22, [Blackened Defias Armor] would be a solid
  upgrade for your chest slot, it has 14 Agility which is great for
  a Rogue. [Cruel Barb] is also worth grabbing, 2.8 speed with
  a proc that fits your combat style.
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

### Zero Hallucination, Real Data, Not Guesswork
This isn't an AI that vaguely remembers WoW from training data. Every answer comes from **your actual game database**, the same tables your server uses. When the guide says [Riverpaw Leather Vest] drops from [Hogger] at 15%, that's the real drop rate from your `creature_loot_template`. When it says the closest mining trainer is 85 yards northeast, it calculated that from your character's live coordinates. No approximations, no "I think it's somewhere in Stormwind", real data, real answers.

### 29 Database Tools
The LLM has access to 29 specialized tools that query your game database in real time. It doesn't pick one and hope for the best, it chains multiple tools together to build complete answers. Ask "where can I learn dual wield?" and it identifies the spell, checks your class, finds the nearest trainer, and calculates the distance and direction from where you're standing.

### Distance and Direction, Your Personal Compass
Every NPC, trainer, and vendor result includes how far they are and which direction to go: *"~45 yards northeast"*, *"~320 yards south"*. The guide knows your exact position in the world and does the math so you don't have to open your map. It even handles unit preferences, yards or meters, your call.

### Knows Your Character Inside Out
The guide doesn't give generic answers. It reads your character's live state from the server: level, race, class, zone, gold, talent spec, professions (with skill levels), gear, guild, group status, and your full quest log. Ask "what quests can I do here?" and it filters by your level, class, and faction. Ask "where should I train mining?" and it knows your current skill level.

### Conversation Memory
The guide remembers what you asked. Mention [Hogger] in one question, then say "where is he?", it knows who you mean. Previous conversations are replayed as real multi-turn context so follow-ups, pronouns, and references just work. Older topics are summarized so the guide stays aware without burning through tokens.

### Clickable WoW Links
Every item, quest, spell, and NPC name in responses becomes a proper in-game hyperlink you can click, just like links from real players. Hover for tooltips, click to inspect. The guide formats them with correct quality colors and IDs straight from the database.

### Multi-Provider Support
Works with Anthropic Claude or OpenAI GPT, any model that supports tool calling. Haiku and GPT-4o-mini are the sweet spot: fast, cheap, and more than capable for database lookups. Local models (Ollama) are not currently supported, reliable function/tool calling across 29 tools requires models that can handle complex multi-step reasoning, and local models aren't quite there yet. Ollama support is on the roadmap for when local models catch up.

### Tool Categories

| Category | Tools | Examples |
|----------|-------|----------|
| NPCs & Services | 6 | Vendors, trainers, battlemasters, weapon skill trainers |
| Quests | 5 | Quest info, chains, class quests, quest givers |
| Spells | 2 | Spell details, spells by level |
| Items & Loot | 4 | Item stats, upgrades, boss/creature drops |
| Creatures | 4 | Find mobs, rare spawns, hunter pets |
| Gathering | 4 | Fishing, herbs, mining by zone, recipe sources |
| World | 3 | Dungeon info, flight paths, zone info |
| Reputation | 1 | Faction rep sources and rewards |

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

```
.ag <question>
```

Alternative syntax: `.llm ag <question>`

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

Tool-calling models are required for database lookups. Haiku and GPT-4o-mini both support this and are the recommended choices.

## Architecture

```
Worldserver (C++)           Python Bridge
 |                            |
 | Player asks .ag question   |
 |──── INSERT queue ────────▶ |
 |                            |── call LLM with tools
 |                            |── LLM calls database tools
 |                            |── format response + links
 | ◀──── UPDATE response ────|
 |
 | Deliver to player chat
```

## Files

```
mod-llm-guide/
├── README.md
├── LICENSE
├── .gitignore
├── include.sh
├── conf/
│   └── mod_llm_guide.conf.dist
├── data/sql/db-characters/base/
│   └── llm_guide_queue.sql
├── src/
│   ├── llm_guide_loader.cpp
│   ├── LLMGuideConfig.cpp
│   ├── LLMGuideConfig.h
│   └── LLMGuideScript.cpp
└── tools/
    ├── llm_guide_bridge.py
    ├── game_tools.py
    ├── spell_names.py
    ├── zone_coordinates.py
    └── requirements.txt
```

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
