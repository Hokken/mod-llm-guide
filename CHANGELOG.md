# Changelog

### 2026-10-06 - LF Line Endings

* **Repository**: Add `.gitattributes` forcing LF line endings, so
  checkouts on Windows with `core.autocrlf` enabled no longer write CRLF
  files that break shell scripts in Linux builds. Committed files were
  already LF; no code, configuration or database changes.

### 2026-10-06 - Vendor Answers and Prompt Caching

* **Verified "not sold" answers**: When an exactly named item has no vendor
  entries anywhere, `find_vendor` now reports that no NPC sells it instead
  of an unresolved "No vendors" result. The answer-readiness guard no longer
  replaces the correct answer with "Which name or location do you mean?",
  and the model is pointed at `get_item_info` for the item's real sources.
* **Cache-friendly prompts**: The system prompt now places all
  request-independent rules first and player info, topics, lookup results,
  and readiness notes after them, so OpenAI-compatible providers can reuse
  the cached prefix across requests and tool rounds. Anthropic calls mark
  that prefix with an explicit cache breakpoint. Each call logs its cached
  prompt tokens (`Prompt cache: ...`) to confirm cache hits.

### 2026-09-14 - Model Compatibility and Provider Switching

* **Five provider backends**: The guide can use Anthropic, OpenAI, Google
  Gemini, OpenRouter, or a local Ollama server through documented, independent
  provider settings.
* **Model-aware requests**: OpenAI-compatible calls now select safe token,
  temperature, and reasoning parameters from the provider and model ID.
  Explicit unsupported-parameter responses receive bounded retries and
  process-local compatibility caching.
* **Reasoning-safe budgets**: `LLMGuide.OpenAI.MaxTokensMultiplier` protects
  visible answers from hidden reasoning-token use while preserving the normal
  budget for models running with supported `reasoning_effort = none`.
* **Ollama tool reliability**: Thinking can be disabled with
  `LLMGuide.Ollama.DisableThinking`. Because Ollama ignores `tool_choice`, an
  empty routing result falls through to deterministic and normal tool routing,
  and the final response round omits tool definitions entirely.
* **Server-owned Ollama context**: Removed the ineffective per-request context
  option. The README and configuration template now explain
  `OLLAMA_CONTEXT_LENGTH`, Modelfile `num_ctx`, and verification with
  `ollama ps`.
* **Configuration and documentation**: Provider examples, model-ID formats,
  configuration defaults, and runtime fallbacks are synchronized. Fine-tuned
  OpenAI IDs inherit their base-model profile.
