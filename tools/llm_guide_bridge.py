#!/usr/bin/env python3
"""
LLM Bridge for mod-llm-guide
Polls the database for pending questions and sends them to an LLM API.

Supports:
- Anthropic Claude (Haiku, Sonnet, Opus) - with tool calling
- OpenAI GPT (gpt-4o-mini, gpt-4o, etc.) - with tool calling
- Google Gemini (Gemini 3 Flash, 2.5 Flash, etc.) - with tool calling
- OpenRouter models - with OpenAI-compatible tool calling

Setup:
1. pip install -r requirements.txt
2. Configure mod_llm_guide.conf with your API key
3. Run: python llm_guide_bridge.py --config /path/to/mod_llm_guide.conf
"""

import argparse
import re
import time
import logging
import sys
from pathlib import Path

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from game_tools import GAME_TOOLS, GameToolExecutor


GOOGLE_OPENAI_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/openai/"
)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "anthropic/claude-haiku-4.5"

# Local inference servers (Ollama, LM Studio). Both expose an OpenAI-compatible
# surface, so they reuse call_openai() exactly as Google and OpenRouter do -
# no new transport is needed.
#
# The /v1 suffix matters: Ollama's native API lives at /api and does NOT
# implement the OpenAI tool-calling schema this module depends on, so pointing
# at /api would fail at the first question rather than at startup.
# validate_config() rejects a base URL without it.
OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_OLLAMA_MODEL = "qwen2.5:14b-instruct"
LMSTUDIO_BASE_URL = "http://localhost:1234/v1"
DEFAULT_LMSTUDIO_MODEL = "qwen2.5-14b-instruct"
# Neither server authenticates, but the openai client requires a non-empty
# api_key, so a placeholder is sent and ignored.
LOCAL_PLACEHOLDER_KEY = "local"
LOCAL_PROVIDERS = ("ollama", "lmstudio")


def resolve_model_alias(model_name: str) -> str:
    """Resolve friendly model aliases to provider model IDs."""
    normalized = (model_name or "").strip()
    aliases = {
        "google-2.5-flash": "gemini-2.5-flash",
        "google2.5-flash": "gemini-2.5-flash",
        "gemini-2.5-flash": "gemini-2.5-flash",
        "google-3.1-flash-lite": "gemini-3.1-flash-lite",
        "google3.1-flash-lite": "gemini-3.1-flash-lite",
        "gemini-3.1-flash-lite": "gemini-3.1-flash-lite",
        "google-3-flash": "gemini-3-flash-preview",
        "google3-flash": "gemini-3-flash-preview",
        "gemini-3-flash": "gemini-3-flash-preview",
        "gemini-3-flash-preview": "gemini-3-flash-preview",
        "openrouter-auto": "openrouter/auto",
    }
    return aliases.get(normalized.lower(), normalized)


def openrouter_headers(config: dict) -> dict:
    """Build optional OpenRouter app-attribution headers."""
    headers = {}
    referer = get_config_value(
        config, "LLMGuide.OpenRouter.HttpReferer", ""
    ).strip()
    title = get_config_value(
        config, "LLMGuide.OpenRouter.Title", ""
    ).strip()
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-OpenRouter-Title"] = title
    return headers


def convert_tools_to_openai_format(anthropic_tools: list) -> list:
    """Convert Anthropic tool format to OpenAI function calling format.

    Anthropic format:
        {"name": "...", "description": "...", "input_schema": {...}}

    OpenAI format:
        {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
    """
    openai_tools = []
    for tool in anthropic_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"]
            }
        })
    return openai_tools


# Pre-convert tools for OpenAI (done once at module load)
GAME_TOOLS_OPENAI = convert_tools_to_openai_format(GAME_TOOLS)


def extract_zone_from_context(char_context: str) -> str:
    """Extract the zone name from character context string.

    Context format: "Name is a level X Race Class in ZoneName. Faction..."
    Returns the zone name or None if not found.
    """
    if not char_context:
        return None
    # Match " in ZoneName." or " in ZoneName," or " in ZoneName "
    match = re.search(r' in ([^.]+?)(?:\.|,|\s+(?:Horde|Alliance))', char_context)
    if match:
        return match.group(1).strip()
    return None


def extract_player_defaults_from_context(
    char_context: str
) -> dict:
    """Extract structured player defaults from context text.

    Only parse fields that appear near the start of
    BuildCharacterContext(). The C++ side stores at most
    500 characters, so later sections are not safe to rely on.
    """
    defaults = {
        "level": None,
        "player_class": None,
        "faction": None,
    }
    if not char_context:
        return defaults

    level_match = re.search(
        r'level\s+(\d+)', char_context
    )
    if level_match:
        defaults["level"] = int(
            level_match.group(1)
        )

    class_match = re.search(
        r'\b(Death Knight|Warrior|Paladin|Hunter|'
        r'Rogue|Priest|Shaman|Mage|Warlock|Druid)\b'
        r'(?:\s+in\s+[^.]+|\.)',
        char_context,
        re.IGNORECASE,
    )
    if class_match:
        defaults["player_class"] = (
            class_match.group(1).lower()
        )

    faction_match = re.search(
        r'(?:^|[.]\s+)(Alliance|Horde|Unknown)\.',
        char_context,
        re.IGNORECASE,
    )
    if faction_match:
        defaults["faction"] = (
            faction_match.group(1).lower()
        )

    return defaults

# Setup logging
# Windows stdout defaults to cp1252, where one stray codepoint kills the log line.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except (AttributeError, ValueError):
    pass  # Python < 3.7, or a stream that cannot be reconfigured

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def parse_conf_file(filepath: str) -> dict:
    """
    Parse an AzerothCore .conf file.
    Returns a dictionary of key -> value pairs.
    """
    config = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse key = value
            match = re.match(r'^([A-Za-z0-9_.]+)\s*=\s*(.*)$', line)
            if match:
                key = match.group(1)
                value = match.group(2).strip()

                # Remove inline comments (but be careful with URLs)
                # Only remove comments that have a space before #
                if ' #' in value:
                    value = value.split(' #')[0].strip()

                config[key] = value

    return config


def get_config_value(config: dict, key: str, default: str = "") -> str:
    """Get a config value with a default."""
    return config.get(key, default)


def get_config_int(config: dict, key: str, default: int = 0) -> int:
    """Get a config value as int with a default."""
    try:
        return int(config.get(key, default))
    except (ValueError, TypeError):
        return default


def get_config_float(config: dict, key: str, default: float = 0.0) -> float:
    """Get a config value as float with a default."""
    try:
        return float(config.get(key, default))
    except (ValueError, TypeError):
        return default


def find_config_file() -> str:
    """Try to find the config file in common locations."""
    script_dir = Path(__file__).parent

    # Common locations to search
    search_paths = [
        script_dir.parent / "conf" / "mod_llm_guide.conf",
        script_dir.parent.parent.parent / "env" / "dist" / "etc" / "modules" / "mod_llm_guide.conf",
        Path("/etc/azerothcore/mod_llm_guide.conf"),
        Path("./mod_llm_guide.conf"),
    ]

    for path in search_paths:
        if path.exists():
            return str(path)

    return None


def load_config(config_path: str = None) -> dict:
    """Load and parse the configuration file."""
    if config_path is None:
        config_path = find_config_file()

    if config_path is None:
        logger.error("Could not find mod_llm_guide.conf")
        logger.error("Please specify with: python llm_guide_bridge.py --config /path/to/mod_llm_guide.conf")
        sys.exit(1)

    if not Path(config_path).exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    logger.info(f"Loading config from: {config_path}")
    return parse_conf_file(config_path)


class LLMBridge:
    def __init__(self, config: dict):
        self.config = config

        # Database settings
        self.db_config = {
            "host": get_config_value(config, "LLMGuide.Database.Host", "localhost"),
            "port": get_config_int(config, "LLMGuide.Database.Port", 3306),
            "user": get_config_value(config, "LLMGuide.Database.User", "acore"),
            "password": get_config_value(config, "LLMGuide.Database.Password", "acore"),
            "database": get_config_value(config, "LLMGuide.Database.Name", "acore_characters")
        }
        # Note: Table creation moved to run() after database connection is verified

        # LLM settings
        self.provider = get_config_value(
            config, "LLMGuide.Provider", "anthropic"
        ).lower()
        self.anthropic_key = get_config_value(config, "LLMGuide.Anthropic.ApiKey", "")
        self.anthropic_model = get_config_value(config, "LLMGuide.Anthropic.Model", "claude-haiku-4-5-20251001")
        self.openai_key = get_config_value(config, "LLMGuide.OpenAI.ApiKey", "")
        self.openai_model = get_config_value(config, "LLMGuide.OpenAI.Model", "gpt-4o-mini")
        self.google_key = get_config_value(config, "LLMGuide.Google.ApiKey", "")
        self.google_model = resolve_model_alias(get_config_value(
            config, "LLMGuide.Google.Model", "gemini-3.1-flash-lite"
        ))
        self.google_base_url = get_config_value(
            config, "LLMGuide.Google.BaseUrl", GOOGLE_OPENAI_BASE_URL
        )
        self.google_reasoning_effort = get_config_value(
            config, "LLMGuide.Google.ReasoningEffort", "minimal"
        ).strip().lower()
        self.google_thinking_budget = get_config_value(
            config, "LLMGuide.Google.ThinkingBudget", ""
        ).strip()
        self.google_max_tokens_multiplier = get_config_float(
            config, "LLMGuide.Google.MaxTokensMultiplier", 1
        )
        self.openrouter_key = get_config_value(
            config, "LLMGuide.OpenRouter.ApiKey", ""
        )
        self.openrouter_model = resolve_model_alias(
            get_config_value(
                config, "LLMGuide.OpenRouter.Model",
                DEFAULT_OPENROUTER_MODEL,
            )
        )
        self.openrouter_base_url = get_config_value(
            config, "LLMGuide.OpenRouter.BaseUrl",
            OPENROUTER_BASE_URL,
        )
        self.openrouter_headers = openrouter_headers(config)
        self.ollama_base_url = get_config_value(
            config, "LLMGuide.Ollama.BaseUrl", OLLAMA_BASE_URL,
        )
        self.ollama_model = get_config_value(
            config, "LLMGuide.Ollama.Model", DEFAULT_OLLAMA_MODEL,
        )
        self.lmstudio_base_url = get_config_value(
            config, "LLMGuide.LMStudio.BaseUrl", LMSTUDIO_BASE_URL,
        )
        self.lmstudio_model = get_config_value(
            config, "LLMGuide.LMStudio.Model", DEFAULT_LMSTUDIO_MODEL,
        )
        self.max_tokens = get_config_int(config, "LLMGuide.MaxTokens", 500)
        self.temperature = get_config_float(config, "LLMGuide.Temperature", 0.7)
        self.system_prompt = get_config_value(config, "LLMGuide.SystemPrompt",
            "You are a helpful WoW guide. Be concise.")

        # Replace escaped newlines
        self.system_prompt = self.system_prompt.replace("\\n", "\n")

        # Polling settings
        self.poll_interval = get_config_int(config, "LLMGuide.Bridge.PollIntervalSeconds", 2)

        # Memory settings
        self.memory_enabled = get_config_int(config, "LLMGuide.Memory.Enable", 1) == 1
        self.memory_max_per_character = get_config_int(config, "LLMGuide.Memory.MaxPerCharacter", 20)
        self.memory_context_count = get_config_int(config, "LLMGuide.Memory.ContextCount", 5)
        self.memory_summarize_threshold = get_config_int(config, "LLMGuide.Memory.SummarizeThreshold", 10)

        # Distance unit setting
        self.distance_unit = get_config_value(
            config, "LLMGuide.DistanceUnit", "yards"
        ).lower()

        # Game data tool executor for Claude tool use
        self.tool_executor = GameToolExecutor(self.db_config)
        self.tool_executor.distance_unit = self.distance_unit

    def get_db_connection(self):
        """Create a database connection."""
        import mysql.connector
        return mysql.connector.connect(**self.db_config)

    def wait_for_database(self, max_retries: int = 30, initial_delay: float = 2.0) -> bool:
        """Wait for database to become available with exponential backoff.

        Args:
            max_retries: Maximum number of connection attempts
            initial_delay: Initial delay between retries (doubles each retry, max 30s)

        Returns:
            True if connected successfully, False if all retries exhausted
        """
        import mysql.connector

        delay = initial_delay
        for attempt in range(1, max_retries + 1):
            try:
                conn = mysql.connector.connect(**self.db_config)
                conn.close()
                logger.info(f"Database connection established (attempt {attempt})")
                return True
            except mysql.connector.Error as e:
                if attempt == max_retries:
                    logger.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                    return False
                logger.info(f"Waiting for database... (attempt {attempt}/{max_retries}, retry in {delay:.1f}s)")
                time.sleep(delay)
                delay = min(delay * 1.5, 30.0)  # Exponential backoff, max 30s

        return False

    def _ensure_table_exists(self):
        """Create the database tables if they don't exist."""
        import mysql.connector

        def add_column_if_missing(
            cursor,
            table_name: str,
            column_name: str,
            column_definition: str,
            after_column: str | None = None,
        ):
            cursor.execute(
                f"SHOW COLUMNS FROM `{table_name}` LIKE %s",
                (column_name,),
            )
            if cursor.fetchone():
                return

            alter_sql = (
                f"ALTER TABLE `{table_name}` "
                f"ADD COLUMN `{column_name}` "
                f"{column_definition}"
            )
            if after_column:
                alter_sql += f" AFTER `{after_column}`"
            cursor.execute(alter_sql)

        create_queue_sql = """
        CREATE TABLE IF NOT EXISTS `llm_guide_queue` (
            `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
            `character_guid` INT UNSIGNED NOT NULL,
            `character_name` VARCHAR(12) NOT NULL,
            `character_context` VARCHAR(500) DEFAULT NULL,
            `question` TEXT NOT NULL,
            `response` TEXT DEFAULT NULL,
            `status` ENUM('pending', 'processing', 'complete', 'delivered', 'cancelled', 'error') NOT NULL DEFAULT 'pending',
            `error_message` VARCHAR(255) DEFAULT NULL,
            `tokens_used` INT UNSIGNED DEFAULT 0,
            `position_x` FLOAT DEFAULT NULL,
            `position_y` FLOAT DEFAULT NULL,
            `map_id` INT UNSIGNED DEFAULT NULL,
            `active_quest_ids` VARCHAR(255) DEFAULT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `processed_at` TIMESTAMP NULL DEFAULT NULL,
            PRIMARY KEY (`id`),
            KEY `idx_status` (`status`),
            KEY `idx_character_pending` (`character_guid`, `status`),
            KEY `idx_created` (`created_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='LLM Chat request queue for mod-llm-guide'
        """

        create_memory_sql = """
        CREATE TABLE IF NOT EXISTS `llm_guide_memory` (
            `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
            `character_guid` INT UNSIGNED NOT NULL,
            `character_name` VARCHAR(12) NOT NULL,
            `summary` VARCHAR(500) NOT NULL,
            `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `idx_character` (`character_guid`),
            KEY `idx_created` (`created_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='LLM Chat conversation memory'
        """

        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            cursor.execute(create_queue_sql)
            cursor.execute(create_memory_sql)
            add_column_if_missing(
                cursor,
                "llm_guide_queue",
                "character_context",
                "VARCHAR(500) DEFAULT NULL",
                after_column="character_name",
            )
            add_column_if_missing(
                cursor,
                "llm_guide_queue",
                "position_x",
                "FLOAT DEFAULT NULL",
                after_column="tokens_used",
            )
            add_column_if_missing(
                cursor,
                "llm_guide_queue",
                "position_y",
                "FLOAT DEFAULT NULL",
                after_column="position_x",
            )
            add_column_if_missing(
                cursor,
                "llm_guide_queue",
                "map_id",
                "INT UNSIGNED DEFAULT NULL",
                after_column="position_y",
            )
            add_column_if_missing(
                cursor,
                "llm_guide_queue",
                "active_quest_ids",
                "VARCHAR(255) DEFAULT NULL",
                after_column="map_id",
            )
            add_column_if_missing(
                cursor,
                "llm_guide_memory",
                "question",
                "TEXT NOT NULL",
                after_column="character_name",
            )
            add_column_if_missing(
                cursor,
                "llm_guide_memory",
                "response",
                "TEXT NOT NULL",
                after_column="question",
            )
            add_column_if_missing(
                cursor,
                "llm_guide_memory",
                "tools_used",
                "TINYINT(1) NOT NULL DEFAULT 0",
                after_column="response",
            )
            conn.commit()
            cursor.close()
            conn.close()
            logger.info("Database tables ready (llm_guide_queue, llm_guide_memory)")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            sys.exit(1)

    def fetch_pending_requests(self, cursor):
        """Fetch pending requests from the queue."""
        cursor.execute("""
            SELECT id, character_guid, character_name, character_context, question,
                   position_x, position_y, map_id, active_quest_ids
            FROM llm_guide_queue
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 5
        """)
        return cursor.fetchall()

    def fetch_memories(self, cursor, character_guid: int) -> dict:
        """Fetch recent conversation memories for a character.

        Returns a dict with:
        - 'recent': list of dicts with 'question', 'response' keys
          for replaying as real message turns (up to memory_context_count)
        - 'older_topics': list of topics from older memories (condensed)
        """
        if not self.memory_enabled:
            return {'recent': [], 'older_topics': []}

        # Fetch more memories than we display to check for older ones
        fetch_count = (
            self.memory_context_count + self.memory_summarize_threshold
        )
        cursor.execute("""
            SELECT summary, question, response, tools_used
            FROM llm_guide_memory
            WHERE character_guid = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (character_guid, fetch_count))

        rows = cursor.fetchall()

        # Split into recent (for message replay) and older (topics)
        recent_rows = rows[:self.memory_context_count]
        older_rows = rows[self.memory_context_count:]

        # Build recent list as dicts; skip entries with empty Q&A
        # (legacy rows before this migration won't have Q&A text)
        recent = []
        for summary, question, response, tools_used in reversed(recent_rows):
            if question and response:
                recent.append({
                    'question': question,
                    'response': response,
                    'tools_used': bool(tools_used),
                })

        # Extract topics from older memories using summary field
        older_topics = []
        for summary, question, response, tools_used in older_rows:
            topic = self._extract_topic(summary)
            if topic and topic not in older_topics:
                older_topics.append(topic)

        return {
            'recent': recent,
            'older_topics': older_topics
        }

    def _extract_topic(self, memory: str) -> str:
        """Extract the topic/subject from a memory string."""
        # Memory format is "Q: <question> | A: <response>"
        # For older entries, may be "Asked: <question>"

        question = None

        if memory.startswith("Q: "):
            # New format - extract question part before " | A:"
            parts = memory.split(" | A:")
            question = parts[0][3:]  # Remove "Q: " prefix
        elif memory.startswith("Asked: "):
            # Legacy format
            question = memory[7:]  # Remove "Asked: " prefix

        if question:
            q_lower = question.lower()

            # Remove common question words
            for prefix in ["what ", "where ", "how ", "when ", "why ", "can i ", "should i ",
                          "do i ", "is ", "are ", "which ", "who "]:
                if q_lower.startswith(prefix):
                    question = question[len(prefix):]
                    break

            # Truncate to first few words as the topic
            words = question.split()
            if len(words) > 4:
                return " ".join(words[:4])
            return question.rstrip("?").strip()

        return memory[:30] if len(memory) > 30 else memory

    # Conversational openers that need no database lookup.
    SMALL_TALK = (
        'hello', 'hi', 'hey', 'greetings', 'thanks', 'thank you', 'ta',
        'cheers', 'bye', 'goodbye', 'cya', 'lol', 'ok', 'okay', 'yes', 'no',
        'who are you', 'what are you', 'how are you', 'what can you do',
        'help', 'sorry', 'nvm', 'nevermind', 'never mind',
    )

    def question_needs_lookup(self, question: str) -> bool:
        """True if this question must be grounded in a database lookup.

        Biased towards True: a needless lookup is harmless, an invented fact is not.
        """
        q = (question or '').strip().lower().rstrip('?!.,')
        if not q:
            return False
        if q in self.SMALL_TALK:
            return False
        # Catches "hi there", "thanks!" and similar.
        if len(q.split()) <= 3:
            for phrase in self.SMALL_TALK:
                if q.startswith(phrase):
                    return False
        return True

    def partition_memories(self, memories_recent: list) -> tuple:
        """Split history into database-verified turns and unverified ones.

        Returns: (verified_turns, unverified_pairs)
        """
        verified, unverified = [], []
        for mem in memories_recent or []:
            # Legacy rows have no tools_used value - treat those as unverified.
            if mem.get('tools_used'):
                verified.append(mem)
            else:
                unverified.append(mem)
        return verified, unverified

    def annotate_system_prompt(
        self, system_prompt: str, unverified: list
    ) -> str:
        """Note what was asked before, without restating unverified answers.

        Including the answers leaked invented coordinates into later ones, even
        when labelled unverified, so only the questions are kept.
        """
        if not unverified:
            return system_prompt
        asked = "; ".join(m['question'] for m in unverified)
        return (
            f"{system_prompt}\n\n"
            "Earlier in this conversation the player asked about: "
            f"{asked}. Those answers were not database-verified, so look up "
            "anything you need again rather than relying on what was said."
        )

    def store_memory(
        self, cursor, char_guid: int, char_name: str,
        summary: str, question: str = '', response: str = '',
        tools_used: bool = False
    ):
        """Store a conversation memory with full Q&A for replay."""
        if not self.memory_enabled:
            return

        cursor.execute("""
            INSERT INTO llm_guide_memory
                (character_guid, character_name, question, response,
                 summary, tools_used)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (char_guid, char_name, question, response,
              summary[:500], 1 if tools_used else 0))

        # Prune old memories if over limit
        self.prune_memories(cursor, char_guid)

    def prune_memories(self, cursor, character_guid: int):
        """Keep only the most recent memories for a character."""
        cursor.execute("""
            SELECT COUNT(*) FROM llm_guide_memory WHERE character_guid = %s
        """, (character_guid,))

        count = cursor.fetchone()[0]

        if count > self.memory_max_per_character:
            # Delete oldest entries
            delete_count = count - self.memory_max_per_character
            cursor.execute("""
                DELETE FROM llm_guide_memory
                WHERE character_guid = %s
                ORDER BY created_at ASC
                LIMIT %s
            """, (character_guid, delete_count))

    def generate_summary(self, question: str, response: str) -> str:
        """Generate a summary of the Q&A exchange including both question and answer.

        This is critical for maintaining conversation context - the AI needs to
        remember what it said, not just what was asked. For example, if the AI
        mentioned 'Mythrin'dir sells arrows', we need to remember that name so
        follow-up questions like 'where is she?' make sense.
        """
        # Truncate question if needed
        q_truncated = question if len(question) <= 80 else question[:77] + "..."

        # Truncate response if needed - aim for ~150 chars to capture key info
        r_truncated = response if len(response) <= 150 else response[:147] + "..."

        # Format: "Q: <question> | A: <response>"
        # This preserves both sides of the conversation for context
        summary = f"Q: {q_truncated} | A: {r_truncated}"

        # Final safety truncation to stay within 500 char limit
        if len(summary) > 495:
            summary = summary[:492] + "..."

        return summary

    def mark_processing(self, cursor, request_id):
        """Mark a request as being processed."""
        cursor.execute("""
            UPDATE llm_guide_queue
            SET status = 'processing'
            WHERE id = %s
        """, (request_id,))

    def save_response(self, cursor, request_id, response, tokens_used=0):
        """Save the LLM response."""
        cursor.execute("""
            UPDATE llm_guide_queue
            SET status = 'complete',
                response = %s,
                tokens_used = %s,
                processed_at = NOW()
            WHERE id = %s
        """, (response, tokens_used, request_id))

    def save_error(self, cursor, request_id, error_message):
        """Save an error for a request."""
        cursor.execute("""
            UPDATE llm_guide_queue
            SET status = 'error',
                error_message = %s,
                processed_at = NOW()
            WHERE id = %s
        """, (str(error_message)[:255], request_id))

    def build_system_prompt(self, char_context: str, memories: dict) -> str:
        """Build the system prompt with character context and memories.

        Recent conversation history is no longer included here — it is
        replayed as real user/assistant message turns for proper
        multi-turn context (pronoun resolution, follow-ups, etc.).
        Only older topic summaries are included in the system prompt.

        Args:
            char_context: Player info string
            memories: Dict with 'recent' and 'older_topics' lists
        """
        parts = [self.system_prompt]

        if char_context:
            parts.append(f"\n\nCurrent player info: {char_context}")

        older_topics = memories.get('older_topics', [])

        if older_topics:
            topics_str = ", ".join(older_topics[:10])
            parts.append(
                f"\n\nPreviously discussed topics: {topics_str}"
            )

        return "".join(parts)

    def call_anthropic(
        self, question: str, system_prompt: str = None,
        memories_recent: list = None
    ) -> tuple:
        """Call Anthropic Claude API with tool use support.

        Args:
            question: The current user question
            system_prompt: System prompt string
            memories_recent: List of dicts with 'question'/'response'
                keys to replay as prior message turns

        Returns: (response_text, tokens_used, tools_were_used)
        """
        import anthropic

        client = anthropic.Anthropic(api_key=self.anthropic_key)

        # Replay only verified answers as turns; the rest go in the system prompt.
        verified, unverified = self.partition_memories(memories_recent)
        system_prompt = self.annotate_system_prompt(
            system_prompt or self.system_prompt, unverified
        )

        # Build messages with conversation history as real turns
        messages = []
        for mem in verified:
            messages.append({
                "role": "user",
                "content": mem['question']
            })
            messages.append({
                "role": "assistant",
                "content": mem['response']
            })
        messages.append({"role": "user", "content": question})
        total_tokens = 0
        max_tool_rounds = 3  # Limit tool use iterations
        tools_were_used = False  # Track if any tools were called

        force_first_tool = self.question_needs_lookup(question)
        for round_num in range(max_tool_rounds + 1):
            # Make API call with tools. See call_openai for why round 0 is forced.
            create_kwargs = {
                "model": self.anthropic_model,
                "max_tokens": self.max_tokens,
                "system": system_prompt or self.system_prompt,
                "messages": messages,
                "tools": GAME_TOOLS,
                "temperature": self.temperature,
            }
            if force_first_tool and round_num == 0:
                create_kwargs["tool_choice"] = {"type": "any"}
            response = client.messages.create(**create_kwargs)

            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            # Check if we need to handle tool use
            if response.stop_reason == "tool_use":
                tools_were_used = True  # Mark that tools were used
                # Extract tool use blocks
                tool_results = []
                assistant_content = response.content

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_use_id = block.id

                        logger.info(f"Tool call: {tool_name}({tool_input})")

                        # Execute the tool
                        result = self.tool_executor.execute_tool(tool_name, tool_input)
                        logger.info(f"Tool result: {result[:200]}..." if len(result) > 200 else f"Tool result: {result}")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result
                        })

                # Add assistant's response and tool results to messages
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})

            else:
                # No more tool calls - extract final text response
                text = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        text += block.text

                return text, total_tokens, tools_were_used

        # If we hit max rounds, return whatever we have
        logger.warning(f"Hit max tool rounds ({max_tool_rounds}), returning partial response")
        return "I'm having trouble looking that up. Please try rephrasing your question.", total_tokens, tools_were_used

    def call_openai(
        self, question: str, system_prompt: str = None,
        memories_recent: list = None,
        api_key: str = None,
        model: str = None,
        base_url: str = None,
        default_headers: dict = None,
        compatible_provider: str = "openai",
    ) -> tuple:
        """Call an OpenAI-compatible API with tool/function support.

        Args:
            question: The current user question
            system_prompt: System prompt string
            memories_recent: List of dicts with 'question'/'response'
                keys to replay as prior message turns

        Returns: (response_text, tokens_used, tools_were_used)
        """
        import openai
        import json

        client_kwargs = {
            "api_key": api_key or self.openai_key,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        if default_headers:
            client_kwargs["default_headers"] = default_headers
        client = openai.OpenAI(**client_kwargs)
        model = model or self.openai_model

        # Replay only verified answers as turns; the rest go in the system prompt.
        verified, unverified = self.partition_memories(memories_recent)
        messages = [
            {"role": "system",
             "content": self.annotate_system_prompt(
                 system_prompt or self.system_prompt, unverified
             )},
        ]
        for mem in verified:
            messages.append({
                "role": "user",
                "content": mem['question']
            })
            messages.append({
                "role": "assistant",
                "content": mem['response']
            })
        messages.append({"role": "user", "content": question})
        total_tokens = 0
        max_tool_rounds = 3  # Limit tool use iterations
        tools_were_used = False
        google_thinking_config = None
        if compatible_provider == "google" and self.google_thinking_budget:
            try:
                google_thinking_config = {
                    "thinking_budget": int(
                        self.google_thinking_budget
                    )
                }
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid LLMGuide.Google.ThinkingBudget=%r",
                    self.google_thinking_budget,
                )

        force_first_tool = self.question_needs_lookup(question)
        for round_num in range(max_tool_rounds + 1):
            # Make API call with tools
            request_kwargs = {
                "model": model,
                "messages": messages,
                "tools": GAME_TOOLS_OPENAI,
                "temperature": self.temperature,
            }
            # Require a tool on round 0 so lookups cannot bypass the database.
            # Later rounds stay unforced so the model can write the answer.
            if force_first_tool and round_num == 0:
                request_kwargs["tool_choice"] = "required"
            if compatible_provider in ("google", "openrouter"):
                multiplier = max(
                    1.0,
                    min(
                        self.google_max_tokens_multiplier
                        if compatible_provider == "google"
                        else 1.0,
                        8.0,
                    ),
                )
                request_kwargs["max_tokens"] = int(
                    self.max_tokens * multiplier
                )
                if compatible_provider == "google" and google_thinking_config:
                    request_kwargs["extra_body"] = {
                        "extra_body": {
                            "google": {
                                "thinking_config": (
                                    google_thinking_config
                                ),
                            },
                        },
                    }
                elif (
                    compatible_provider == "google"
                    and
                    self.google_reasoning_effort
                    and self.google_reasoning_effort
                    not in ("0", "none", "off", "disabled")
                ):
                    request_kwargs["reasoning_effort"] = (
                        self.google_reasoning_effort
                    )
            else:
                request_kwargs["max_completion_tokens"] = self.max_tokens
            try:
                response = client.chat.completions.create(
                    **request_kwargs
                )
            except openai.BadRequestError:
                # Not every OpenAI-compatible server implements tool_choice.
                if request_kwargs.pop("tool_choice", None) is None:
                    raise
                logger.warning(
                    "Provider %r rejected tool_choice=required; falling back "
                    "to unforced tool use (answers may be less reliable)",
                    compatible_provider,
                )
                force_first_tool = False
                response = client.chat.completions.create(
                    **request_kwargs
                )

            usage = getattr(response, "usage", None)
            total_tokens += int(
                getattr(usage, "total_tokens", 0) or 0
            )
            message = response.choices[0].message

            # Replayed prose answers teach the model to answer in prose, tools ignored.
            # Holds even when those answers were correct and tool-derived.
            # Measured on qwen2.5:32b: 0/5 lookups called a tool with history, 4/5 without.
            # Ollama accepts tool_choice=required and ignores it, so drop the history.
            if (
                force_first_tool
                and round_num == 0
                and not message.tool_calls
                and len(messages) > 2
            ):
                logger.info(
                    "No tool call on a lookup question; retrying without "
                    "replayed history"
                )
                messages = [messages[0], {"role": "user", "content": question}]
                request_kwargs["messages"] = messages
                response = client.chat.completions.create(**request_kwargs)
                usage = getattr(response, "usage", None)
                total_tokens += int(getattr(usage, "total_tokens", 0) or 0)
                message = response.choices[0].message
                if message.tool_calls:
                    logger.info("Retry without history produced a tool call")
                else:
                    logger.warning(
                        "Still no tool call after dropping history; the answer "
                        "to %r is not database-verified", question[:60]
                    )

            # Check if we need to handle tool calls
            if message.tool_calls:
                tools_were_used = True

                # Add assistant message with tool calls to history
                messages.append(message)

                # Process each tool call
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        tool_input = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_input = {}

                    logger.info(f"Tool call: {tool_name}({tool_input})")

                    # Execute the tool
                    result = self.tool_executor.execute_tool(tool_name, tool_input)
                    log_result = f"{result[:200]}..." if len(result) > 200 else result
                    logger.info(f"Tool result: {log_result}")

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
            else:
                # No more tool calls - return final text response
                text = message.content or ""
                return text, total_tokens, tools_were_used

        # If we hit max rounds, return whatever we have
        logger.warning(f"Hit max tool rounds ({max_tool_rounds}), returning partial response")
        return "I'm having trouble looking that up. Please try rephrasing your question.", total_tokens, tools_were_used

    def call_google(
        self, question: str, system_prompt: str = None,
        memories_recent: list = None,
    ) -> tuple:
        """Call Gemini through Google's OpenAI-compatible endpoint."""
        return self.call_openai(
            question,
            system_prompt,
            memories_recent,
            api_key=self.google_key,
            model=self.google_model,
            base_url=self.google_base_url,
            compatible_provider="google",
        )

    def call_openrouter(
        self, question: str, system_prompt: str = None,
        memories_recent: list = None,
    ) -> tuple:
        """Call OpenRouter through its OpenAI-compatible endpoint."""
        return self.call_openai(
            question,
            system_prompt,
            memories_recent,
            api_key=self.openrouter_key,
            model=self.openrouter_model,
            base_url=self.openrouter_base_url,
            default_headers=self.openrouter_headers,
            compatible_provider="openrouter",
        )

    def call_local(
        self, question: str, system_prompt: str = None,
        memories_recent: list = None,
    ) -> tuple:
        """Call a local inference server through its OpenAI-compatible endpoint.

        Serves both Ollama and LM Studio; they differ only in default port and
        model-naming convention, so one implementation covers both.

        compatible_provider is passed as the provider name rather than "openai"
        so none of the Google thinking-budget or OpenRouter reasoning branches
        in call_openai apply - a local server implements the plain OpenAI
        surface.
        """
        if self.provider == "lmstudio":
            base_url, model = self.lmstudio_base_url, self.lmstudio_model
        else:
            base_url, model = self.ollama_base_url, self.ollama_model

        return self.call_openai(
            question,
            system_prompt,
            memories_recent,
            api_key=LOCAL_PLACEHOLDER_KEY,
            model=model,
            base_url=base_url,
            compatible_provider=self.provider,
        )

    def call_llm(
        self, question: str, system_prompt: str = None,
        memories_recent: list = None
    ) -> tuple:
        """Call the configured LLM provider."""
        if self.provider == "anthropic":
            return self.call_anthropic(
                question, system_prompt, memories_recent
            )
        elif self.provider == "openai":
            return self.call_openai(
                question, system_prompt, memories_recent
            )
        elif self.provider == "google":
            return self.call_google(
                question, system_prompt, memories_recent
            )
        elif self.provider == "openrouter":
            return self.call_openrouter(
                question, system_prompt, memories_recent
            )
        elif self.provider in LOCAL_PROVIDERS:
            return self.call_local(
                question, system_prompt, memories_recent
            )
        else:
            raise ValueError(
                f"Unknown LLM provider: {self.provider}"
            )

    def process_request(self, cursor, request):
        """Process a single request."""
        (request_id, char_guid, char_name, char_context, question,
         pos_x, pos_y, map_id, active_quest_ids) = request

        logger.info(f"Processing request {request_id} from {char_name}: {question[:50]}...")
        self.mark_processing(cursor, request_id)

        try:
            # Extract player's zone from context and set for tool auto-injection
            player_zone = extract_zone_from_context(char_context)
            if player_zone:
                self.tool_executor.set_player_zone(player_zone)
                logger.info(f"Player zone for tool injection: {player_zone}")
            else:
                self.tool_executor.set_player_zone(None)

            player_defaults = extract_player_defaults_from_context(
                char_context
            )
            self.tool_executor.set_player_defaults(
                level=player_defaults.get('level'),
                player_class=player_defaults.get(
                    'player_class'
                ),
                faction=player_defaults.get('faction'),
            )
            logger.info(
                "Player defaults for tool injection: "
                f"{player_defaults}"
            )

            parsed_active_quest_ids = []
            if active_quest_ids:
                for part in str(active_quest_ids).split(','):
                    part = part.strip()
                    if part.isdigit():
                        parsed_active_quest_ids.append(
                            int(part)
                        )
            self.tool_executor.set_active_quest_ids(
                parsed_active_quest_ids
            )

            # Set player position for distance calculations in tool results
            if pos_x is not None and pos_y is not None and map_id is not None:
                self.tool_executor.set_player_position(pos_x, pos_y, map_id)
                logger.info(f"Player position: ({pos_x:.1f}, {pos_y:.1f}) on map {map_id}")
            else:
                self.tool_executor.set_player_position(None, None, None)

            # Fetch conversation memories for this character
            memories = self.fetch_memories(cursor, char_guid)

            # Build enriched system prompt with context and memory
            system_prompt = self.build_system_prompt(char_context, memories)

            # Add tool use instructions to system prompt
            unit_label = (
                "meters (m) and kilometers (km)"
                if self.distance_unit == "meters"
                else "yards"
            )
            system_prompt += (
                "\n\nYou have access to tools that "
                "query the ACTUAL game database. "
                "ALWAYS use them for ANY factual "
                "game question — quests, items, "
                "NPCs, vendors, trainers, spells, "
                "dungeons, or gear. NEVER answer "
                "from memory when a tool can verify "
                "the facts. Your training data may "
                "be wrong or from a different game "
                "version. The database is the source "
                "of truth for this 3.3.5a server.\n"
                "When reporting distances, ALWAYS "
                f"use {unit_label}. Never mix units."
            )

            # Log the full system prompt being sent
            logger.info(f"=== SYSTEM PROMPT ===\n{system_prompt}\n=== END PROMPT ===")

            # Log what's being sent to AI
            logger.info(f"Context: {char_context}" if char_context else "Context: (none)")
            recent = memories.get('recent', [])
            older_topics = memories.get('older_topics', [])
            if recent:
                logger.info(f"Recent memories ({len(recent)}): {recent}")
            if older_topics:
                logger.info(f"Older topics ({len(older_topics)}): {older_topics}")

            # Call LLM with enriched prompt + conversation history
            recent = memories.get('recent', [])
            response, tokens, tools_used = self.call_llm(
                question, system_prompt, memories_recent=recent
            )
            self.save_response(cursor, request_id, response, tokens)

            # Store memory with full Q&A for future message replay
            summary = self.generate_summary(question, response)
            logger.info(f"Storing memory: {summary[:100]}...")
            self.store_memory(
                cursor, char_guid, char_name, summary,
                question=question, response=response,
                tools_used=tools_used
            )

            logger.info(f"Request {request_id} completed ({tokens} tokens)")
        except Exception as e:
            logger.error(f"Request {request_id} failed: {e}")
            self.save_error(cursor, request_id, str(e))

    def validate_config(self) -> bool:
        """Validate the configuration."""
        if self.provider == "anthropic":
            if not self.anthropic_key:
                logger.error("Anthropic API key not configured (LLMGuide.Anthropic.ApiKey)")
                return False
        elif self.provider == "openai":
            if not self.openai_key:
                logger.error("OpenAI API key not configured (LLMGuide.OpenAI.ApiKey)")
                return False
        elif self.provider == "google":
            if not self.google_key:
                logger.error("Google API key not configured (LLMGuide.Google.ApiKey)")
                return False
        elif self.provider == "openrouter":
            if not self.openrouter_key:
                logger.error("OpenRouter API key not configured (LLMGuide.OpenRouter.ApiKey)")
                return False
        elif self.provider in LOCAL_PROVIDERS:
            # No API key to validate - local servers don't authenticate. Check
            # the two things that actually go wrong instead: a missing model,
            # and a base URL pointing at a non-OpenAI-compatible endpoint
            # (Ollama's native /api cannot do tool calling, so it would fail at
            # the first question instead of here).
            label = "LMStudio" if self.provider == "lmstudio" else "Ollama"
            model = (self.lmstudio_model if self.provider == "lmstudio"
                     else self.ollama_model)
            base_url = (self.lmstudio_base_url if self.provider == "lmstudio"
                        else self.ollama_base_url)
            if not model:
                logger.error(
                    "%s model not configured (LLMGuide.%s.Model)", label, label
                )
                return False
            if not base_url.rstrip("/").endswith("/v1"):
                logger.error(
                    "LLMGuide.%s.BaseUrl must end in /v1 (the OpenAI-compatible "
                    "endpoint); got '%s'. A native API path does not support "
                    "tool calling, which this module requires.", label, base_url
                )
                return False
        else:
            logger.error(f"Unknown LLM provider: {self.provider}")
            return False

        return True

    def active_model(self) -> str:
        """Return the configured model for the active provider."""
        if self.provider == "anthropic":
            return self.anthropic_model
        if self.provider == "openai":
            return self.openai_model
        if self.provider == "google":
            return self.google_model
        if self.provider == "openrouter":
            return self.openrouter_model
        if self.provider == "ollama":
            return self.ollama_model
        if self.provider == "lmstudio":
            return self.lmstudio_model
        return "(unknown)"

    def run(self):
        """Main loop."""
        logger.info("=" * 60)
        logger.info("LLM Bridge for mod-llm-guide starting...")
        logger.info(f"Provider: {self.provider}")
        logger.info(f"Model: {self.active_model()}")
        logger.info(f"Tools: {len(GAME_TOOLS)} game data tools available")
        logger.info(f"Distance unit: {self.distance_unit}")
        logger.info(f"Poll interval: {self.poll_interval}s")
        logger.info(f"Database: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
        if self.memory_enabled:
            logger.info(f"Memory: enabled (max {self.memory_max_per_character}/char, {self.memory_context_count} recent, {self.memory_summarize_threshold} summarized)")
        else:
            logger.info("Memory: disabled")
        logger.info("=" * 60)

        if not self.validate_config():
            sys.exit(1)

        # Wait for database to be ready (handles Docker startup order)
        if not self.wait_for_database():
            logger.error("Could not connect to database. Exiting.")
            sys.exit(1)

        # Now ensure tables exist
        self._ensure_table_exists()

        while True:
            try:
                conn = self.get_db_connection()
                cursor = conn.cursor()

                requests = self.fetch_pending_requests(cursor)

                for request in requests:
                    self.process_request(cursor, request)
                    conn.commit()

                cursor.close()
                conn.close()

            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")

            time.sleep(self.poll_interval)


def main():
    parser = argparse.ArgumentParser(description='LLM Bridge for mod-llm-guide')
    parser.add_argument('--config', '-c', type=str, help='Path to mod_llm_guide.conf')
    args = parser.parse_args()

    config = load_config(args.config)
    bridge = LLMBridge(config)
    bridge.run()


if __name__ == "__main__":
    main()
