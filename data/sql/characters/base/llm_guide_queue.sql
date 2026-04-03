-- --------------------------------------------------------
-- LLM Guide Queue Table
-- Stores pending questions and responses for the LLM bridge
-- --------------------------------------------------------

DROP TABLE IF EXISTS `llm_guide_queue`;

CREATE TABLE `llm_guide_queue` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `character_guid` INT UNSIGNED NOT NULL,
  `character_name` VARCHAR(12) NOT NULL,
  `character_context` VARCHAR(500) DEFAULT NULL COMMENT 'Player context: level, class, race, zone, etc.',
  `question` TEXT NOT NULL,
  `response` TEXT DEFAULT NULL,
  `status` ENUM('pending', 'processing', 'complete', 'delivered', 'cancelled', 'error') NOT NULL DEFAULT 'pending',
  `error_message` VARCHAR(255) DEFAULT NULL,
  `tokens_used` INT UNSIGNED DEFAULT 0,
  `position_x` FLOAT DEFAULT NULL COMMENT 'Player X coordinate when question was asked',
  `position_y` FLOAT DEFAULT NULL COMMENT 'Player Y coordinate when question was asked',
  `map_id` INT UNSIGNED DEFAULT NULL COMMENT 'Map ID when question was asked',
  `active_quest_ids` VARCHAR(255) DEFAULT NULL COMMENT 'Comma-separated active quest IDs for availability filtering',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `processed_at` TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_status` (`status`),
  KEY `idx_character_pending` (`character_guid`, `status`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='LLM Guide request queue for mod-llm-guide';

-- --------------------------------------------------------
-- LLM Guide Memory Table
-- Stores conversation summaries per character for context
-- Note: Memory is cleared on each login for a fresh session start
-- --------------------------------------------------------

DROP TABLE IF EXISTS `llm_guide_memory`;

CREATE TABLE `llm_guide_memory` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `character_guid` INT UNSIGNED NOT NULL,
  `character_name` VARCHAR(12) NOT NULL,
  `summary` VARCHAR(500) NOT NULL COMMENT 'Brief summary of a Q&A exchange',
  `question` TEXT NOT NULL COMMENT 'Full question text for multi-turn context',
  `response` TEXT NOT NULL COMMENT 'Full response text for multi-turn context',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_character` (`character_guid`),
  KEY `idx_created` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='LLM Guide conversation memory for mod-llm-guide';
