import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from llm_guide_bridge import (
    LLMBridge,
    clean_final_response,
    openrouter_headers,
)


def response(content, finish_reason="stop", tool_calls=None, total_tokens=10):
    message = SimpleNamespace(
        content=content,
        tool_calls=tool_calls or [],
    )
    usage = SimpleNamespace(
        total_tokens=total_tokens,
        prompt_tokens=max(total_tokens - 2, 0),
        completion_tokens=min(total_tokens, 2),
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=message,
            finish_reason=finish_reason,
        )],
        usage=usage,
    )


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(
            completions=FakeCompletions(responses)
        )


class BridgeReliabilityTests(unittest.TestCase):
    def test_opencode_go_gets_required_session_headers(self):
        headers = openrouter_headers({
            "LLMGuide.OpenRouter.BaseUrl": (
                "https://opencode.ai/zen/go/v1"
            ),
        })
        self.assertEqual(
            headers["x-opencode-session"], "mod-llm-guide"
        )
        self.assertEqual(
            headers["User-Agent"], "mod-llm-guide/1.0"
        )

    def test_non_go_endpoint_has_no_session_headers(self):
        self.assertEqual(openrouter_headers({
            "LLMGuide.OpenRouter.BaseUrl": (
                "https://openrouter.ai/api/v1"
            ),
        }), {})

    def test_cleans_provider_thinking_wrappers(self):
        self.assertEqual(
            clean_final_response("</think>Final answer."),
            "Final answer.",
        )
        self.assertEqual(
            clean_final_response(
                "<think>private reasoning</think> Final answer."
            ),
            "Final answer.",
        )

    def make_bridge(self):
        return LLMBridge({
            "LLMGuide.Provider": "openrouter",
            "LLMGuide.OpenRouter.ApiKey": "test-key",
            "LLMGuide.OpenRouter.Model": "deepseek-v4-flash",
            "LLMGuide.OpenRouter.BaseUrl": (
                "https://opencode.ai/zen/go/v1"
            ),
            "LLMGuide.OpenAICompatible.DisableThinking": "1",
            "LLMGuide.OpenAICompatible.ReasoningControl": (
                "reasoning_none"
            ),
            "LLMGuide.MaxTokens": "300",
            "LLMGuide.TruncationRetryMaxTokens": "1600",
        })

    def call_with_fake(self, bridge, fake_client):
        fake_openai = SimpleNamespace(
            OpenAI=lambda **kwargs: fake_client
        )
        with patch.dict(sys.modules, {"openai": fake_openai}):
            return bridge.call_openrouter("test question")

    def test_retries_truncated_response_with_larger_budget(self):
        fake_client = FakeClient([
            response("Let me check.", "length", total_tokens=310),
            response("Complete answer.", total_tokens=20),
        ])
        result, tokens, tools_used = self.call_with_fake(
            self.make_bridge(), fake_client
        )

        self.assertEqual(result, "Complete answer.")
        self.assertEqual(tokens, 330)
        self.assertFalse(tools_used)
        self.assertEqual(
            [call["max_tokens"] for call in fake_client.chat.completions.calls],
            [300, 600],
        )
        for call in fake_client.chat.completions.calls:
            self.assertEqual(
                call["extra_body"],
                {"reasoning": {"effort": "none"}},
            )

    def test_final_round_forces_answer_without_more_tools(self):
        tool_call = SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(name="find_npc", arguments="{}"),
        )
        fake_client = FakeClient([
            response("", "tool_calls", [tool_call]),
            response("", "tool_calls", [tool_call]),
            response("", "tool_calls", [tool_call]),
            response("Final answer."),
        ])
        bridge = self.make_bridge()
        bridge.tool_executor = SimpleNamespace(
            execute_tool=lambda name, args: "tool result"
        )

        result, _, tools_used = self.call_with_fake(
            bridge, fake_client
        )

        self.assertEqual(result, "Final answer.")
        self.assertTrue(tools_used)
        calls = fake_client.chat.completions.calls
        self.assertNotIn("tool_choice", calls[0])
        self.assertEqual(calls[-1]["tool_choice"], "none")


if __name__ == "__main__":
    unittest.main()
