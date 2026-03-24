#!/usr/bin/env python3
"""
LLM Bridge for mod-llm-guide
Polls the database for pending questions and sends them to an LLM API.

Supports:
- Anthropic Claude (Haiku, Sonnet, Opus) - with tool calling
- OpenAI GPT (gpt-4o-mini, gpt-4o, etc.) - with tool calling

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

# Setup logging
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
        self.provider = get_config_value(config, "LLMGuide.Provider", "anthropic")
        self.anthropic_key = get_config_value(config, "LLMGuide.Anthropic.ApiKey", "")
        self.anthropic_model = get_config_value(config, "LLMGuide.Anthropic.Model", "claude-haiku-4-5-20251001")
        self.openai_key = get_config_value(config, "LLMGuide.OpenAI.ApiKey", "")
        self.openai_model = get_config_value(config, "LLMGuide.OpenAI.Model", "gpt-4o-mini")
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

        # Add character_context column if it doesn't exist (migration)
        add_context_column = """
        ALTER TABLE `llm_guide_queue`
        ADD COLUMN IF NOT EXISTS `character_context` VARCHAR(500) DEFAULT NULL
        AFTER `character_name`
        """

        # Add question/response columns to memory table (migration)
        add_memory_question = """
        ALTER TABLE `llm_guide_memory`
        ADD COLUMN `question` TEXT NOT NULL AFTER `character_name`
        """
        add_memory_response = """
        ALTER TABLE `llm_guide_memory`
        ADD COLUMN `response` TEXT NOT NULL AFTER `question`
        """

        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            cursor.execute(create_queue_sql)
            cursor.execute(create_memory_sql)
            # Try to add columns (ignore error if already exists)
            try:
                cursor.execute(add_context_column)
            except Exception:
                pass  # Column already exists
            try:
                cursor.execute(add_memory_question)
            except Exception:
                pass  # Column already exists
            try:
                cursor.execute(add_memory_response)
            except Exception:
                pass  # Column already exists
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
                   position_x, position_y, map_id
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
            SELECT summary, question, response
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
        for summary, question, response in reversed(recent_rows):
            if question and response:
                recent.append({
                    'question': question,
                    'response': response,
                })

        # Extract topics from older memories using summary field
        older_topics = []
        for summary, question, response in older_rows:
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

    def store_memory(
        self, cursor, char_guid: int, char_name: str,
        summary: str, question: str = '', response: str = ''
    ):
        """Store a conversation memory with full Q&A for replay."""
        if not self.memory_enabled:
            return

        cursor.execute("""
            INSERT INTO llm_guide_memory
                (character_guid, character_name, question, response,
                 summary)
            VALUES (%s, %s, %s, %s, %s)
        """, (char_guid, char_name, question, response,
              summary[:500]))

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

        # Build messages with conversation history as real turns
        messages = []
        if memories_recent:
            for mem in memories_recent:
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

        for round_num in range(max_tool_rounds + 1):
            # Make API call with tools
            response = client.messages.create(
                model=self.anthropic_model,
                max_tokens=self.max_tokens,
                system=system_prompt or self.system_prompt,
                messages=messages,
                tools=GAME_TOOLS,
                temperature=self.temperature
            )

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
        memories_recent: list = None
    ) -> tuple:
        """Call OpenAI GPT API with full tool/function calling support.

        Args:
            question: The current user question
            system_prompt: System prompt string
            memories_recent: List of dicts with 'question'/'response'
                keys to replay as prior message turns

        Returns: (response_text, tokens_used, tools_were_used)
        """
        import openai
        import json

        client = openai.OpenAI(api_key=self.openai_key)

        # Build messages with conversation history as real turns
        messages = [
            {"role": "system",
             "content": system_prompt or self.system_prompt},
        ]
        if memories_recent:
            for mem in memories_recent:
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

        for round_num in range(max_tool_rounds + 1):
            # Make API call with tools
            response = client.chat.completions.create(
                model=self.openai_model,
                max_completion_tokens=self.max_tokens,
                messages=messages,
                tools=GAME_TOOLS_OPENAI,
                temperature=self.temperature
            )

            total_tokens += response.usage.total_tokens
            message = response.choices[0].message

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
        else:
            raise ValueError(
                f"Unknown LLM provider: {self.provider}"
            )

    def process_request(self, cursor, request):
        """Process a single request."""
        request_id, char_guid, char_name, char_context, question, pos_x, pos_y, map_id = request

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
                question=question, response=response
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
        else:
            logger.error(f"Unknown LLM provider: {self.provider}")
            return False

        return True

    def run(self):
        """Main loop."""
        logger.info("=" * 60)
        logger.info("LLM Bridge for mod-llm-guide starting...")
        logger.info(f"Provider: {self.provider}")
        logger.info(f"Model: {self.anthropic_model if self.provider == 'anthropic' else self.openai_model}")
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
