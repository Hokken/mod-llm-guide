#!/usr/bin/env python3
"""
End-to-end test runner for mod-llm-guide tools.
Tests each tool with sample questions and evaluates responses using Haiku.

Usage:
    python run_e2e_tests.py [--tool TOOL_NAME] [--verbose]

Options:
    --tool TOOL_NAME    Test only a specific tool
    --verbose           Show full responses and tool results
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime

# Add parent directory (tools/) to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from game_tools import GameToolExecutor, GAME_TOOLS
from spell_names import SPELL_NAMES, SPELL_DESCRIPTIONS

# ANSI colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def log_info(msg):
    print(f"{Colors.CYAN}[INFO]{Colors.END} {msg}")

def log_pass(msg):
    print(f"{Colors.GREEN}[PASS]{Colors.END} {msg}")

def log_fail(msg):
    print(f"{Colors.RED}[FAIL]{Colors.END} {msg}")

def log_warn(msg):
    print(f"{Colors.YELLOW}[WARN]{Colors.END} {msg}")

def log_test(tool_name, question_num):
    print(f"\n{Colors.BOLD}{Colors.BLUE}Testing: {tool_name} (Q{question_num}){Colors.END}")


class ToolTestRunner:
    def __init__(self, config_path=None,
                 verbose=False, host_mode=False):
        self.verbose = verbose
        self.host_mode = host_mode
        self.results = {}
        self.tool_calls = []
        self.current_tool_calls = []

        # Load configuration
        if config_path is None:
            if host_mode:
                # Running from Windows host
                script_dir = os.path.dirname(
                    os.path.abspath(__file__))
                config_path = os.path.join(
                    script_dir, '..', '..', '..',
                    '..', 'env', 'dist', 'etc',
                    'modules',
                    'mod_llm_guide.conf')
            else:
                config_path = "/config/mod_llm_guide.conf"

        self.config = self.load_config(config_path)

        # Override DB host for host-mode
        if host_mode:
            self.config['db_host'] = 'localhost'

        # Initialize Anthropic client
        import anthropic
        self.client = anthropic.Anthropic(api_key=self.config['api_key'])
        self.model = self.config.get('model', 'claude-haiku-4-5-20251001')

        # Initialize game tools
        db_config = {
            'host': self.config.get('db_host', 'ac-database'),
            'port': int(self.config.get('db_port', 3306)),
            'user': self.config.get('db_user', 'root'),
            'password': self.config.get('db_password', 'password'),
            'database': 'acore_world'
        }
        self.tool_executor = GameToolExecutor(db_config)

        # Load test questions
        test_file = os.path.join(os.path.dirname(__file__), 'test_questions.json')
        with open(test_file, 'r') as f:
            self.test_data = json.load(f)

        self.player_context = self.test_data['test_config']['player_context']

        # Set player position for distance sorting
        ctx = self.player_context
        if 'position_x' in ctx and 'position_y' in ctx:
            self.tool_executor.set_player_position(
                ctx['position_x'],
                ctx['position_y'],
                ctx.get('map_id', 0)
            )
        if 'zone' in ctx:
            self.tool_executor.set_player_zone(
                ctx['zone']
            )

    def load_config(self, config_path):
        """Load configuration from conf file."""
        config = {
            'api_key': os.environ.get('ANTHROPIC_API_KEY', ''),
            'model': 'claude-haiku-4-5-20251001',
            'db_host': 'ac-database',
            'db_port': 3306,
            'db_user': 'root',
            'db_password': 'password',
            'db_name': 'acore_world'
        }

        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"')

                        if key == 'LLMGuide.Anthropic.ApiKey':
                            config['api_key'] = value
                        elif key == 'LLMGuide.Model':
                            config['model'] = value
                        elif key == 'LLMGuide.Database.Host':
                            config['db_host'] = value
                        elif key == 'LLMGuide.Database.Port':
                            config['db_port'] = value
                        elif key == 'LLMGuide.Database.User':
                            config['db_user'] = value
                        elif key == 'LLMGuide.Database.Password':
                            config['db_password'] = value

        return config

    def build_system_prompt(self):
        """Build system prompt with player context."""
        ctx = self.player_context
        context_str = (
            f"{ctx['name']} is a level {ctx['level']} {ctx['race']} {ctx['class']} "
            f"in {ctx['zone']}. {ctx['faction']}. Gold: {ctx['gold']}. "
            f"Professions: {', '.join(ctx['professions'])}."
        )

        return f"""You are the Azeroth Guide for WoW WotLK (3.3.5). RESPONSE LENGTH: Match your answer length to question complexity. Simple questions get 1-2 sentence answers. Only elaborate for complex questions. Be direct. Use WoW terms. Level cap 80, Northrend endgame. CRITICAL: Plain text only, single paragraph, no line breaks, no markdown, no asterisks, no bullet points, no lists.

Current player info: {context_str}

You have access to tools to look up game data. Use them when players ask about vendors, trainers, NPCs, spells, or other factual game information. The tools query the actual game database for accurate information."""

    def call_llm_with_tools(self, question):
        """Call the LLM with tools and capture tool usage."""
        self.current_tool_calls = []

        messages = [{"role": "user", "content": question}]
        system_prompt = self.build_system_prompt()
        max_rounds = 3
        total_tokens = 0

        for round_num in range(max_rounds + 1):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=800,
                system=system_prompt,
                messages=messages,
                tools=GAME_TOOLS,
                temperature=0.3
            )

            total_tokens += response.usage.input_tokens + response.usage.output_tokens

            if response.stop_reason == "tool_use":
                tool_results = []
                assistant_content = response.content

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_use_id = block.id

                        # Execute the tool
                        result = self.tool_executor.execute_tool(tool_name, tool_input)

                        # Record tool call
                        self.current_tool_calls.append({
                            'tool': tool_name,
                            'input': tool_input,
                            'result': result[:500] if len(result) > 500 else result
                        })

                        if self.verbose:
                            log_info(f"  Tool: {tool_name}({json.dumps(tool_input)})")
                            log_info(f"  Result: {result[:200]}...")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result
                        })

                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})
            else:
                # Extract final text
                text = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        text += block.text

                return text, total_tokens, self.current_tool_calls

        return "Error: Max tool rounds exceeded", total_tokens, self.current_tool_calls

    def evaluate_response(self, tool_name, question, response, expected_behavior, tool_calls):
        """Evaluate response for practical issues (not subjective quality)."""
        import re

        tools_used = [tc['tool'] for tc in tool_calls]
        issues = []

        # 1. Check if ANY tool was called (critical - should use tools not general knowledge)
        if not tools_used:
            issues.append("NO TOOL CALLED - LLM used general knowledge instead of querying database")

        # 2. Check if expected tool was used
        tool_used = tool_name in tools_used or any(
            tool_name.replace('_', '') in t.replace('_', '') for t in tools_used
        )
        if tools_used and not tool_used:
            # Tool was called but not the expected one - may be ok if related
            related = False
            for t in tools_used:
                # Check if tools are related (e.g., find_vendor and find_npc)
                if any(word in t for word in tool_name.split('_')) or any(word in tool_name for word in t.split('_')):
                    related = True
                    break
            if not related:
                issues.append(f"Wrong tool called: expected {tool_name}, got {', '.join(tools_used)}")

        # 2. Check for uncleaned placeholders (major issue)
        placeholder_patterns = [
            r'\$[sdomtax]\d',  # $s1, $d, $o1, $t1, $a1, $m1, $x1
            r'\$\{[^}]+\}',    # ${formula}
            r'\$[A-Z]{2,}',    # $RAP, $AP, $SP
            r'\$/\d+;',        # $/10;
            r'\$\?[a-z]\d+',   # $?s12345
            r'\$[gl][^;]+;',   # $ghis:her; $litem:items;
        ]
        for pattern in placeholder_patterns:
            if re.search(pattern, response):
                issues.append(f"Uncleaned placeholder: {pattern}")
                break

        # 3. Check for broken link markers
        # Valid: [[npc:123:Name]], [[item:123:Name]], [[spell:123:Name]], [[quest:123:Name]]
        broken_links = re.findall(r'\[\[[^\]]*\]\]', response)
        for link in broken_links:
            if not re.match(r'\[\[(npc|item|spell|quest):\d+:[^\]]+\]\]', link):
                issues.append(f"Malformed link: {link[:30]}")
                break

        # 4. Check for error responses
        error_indicators = [
            "error", "failed", "couldn't find", "not found in database",
            "unknown", "invalid", "no results"
        ]
        response_lower = response.lower()
        if any(err in response_lower for err in error_indicators) and len(response) < 100:
            issues.append("Response appears to be an error")

        # 5. Check for empty/useless response
        if len(response.strip()) < 20:
            issues.append("Response too short")

        # 6. Check tool results for errors
        for tc in tool_calls:
            if 'error' in tc.get('result', '').lower()[:100]:
                issues.append(f"Tool returned error: {tc['tool']}")

        # Build result
        result = {
            'tool_used': tool_used,
            'no_placeholders': not any('placeholder' in i.lower() for i in issues),
            'valid_links': not any('link' in i.lower() for i in issues),
            'no_errors': not any('error' in i.lower() for i in issues),
            'passed': len(issues) == 0,
            'reason': '; '.join(issues) if issues else 'All checks passed'
        }

        return result

    def test_tool(self, tool_name, tool_config):
        """Test a single tool with its questions."""
        results = []

        for i, question in enumerate(tool_config['questions'], 1):
            log_test(tool_name, i)
            print(f"  Question: {question}")

            start_time = time.time()
            response, tokens, tool_calls = self.call_llm_with_tools(question)
            elapsed = time.time() - start_time

            # Evaluate
            evaluation = self.evaluate_response(
                tool_name, question, response,
                tool_config['expected_behavior'], tool_calls
            )

            # Log result
            tools_used = [tc['tool'] for tc in tool_calls]

            if evaluation['passed']:
                log_pass(f"Response OK ({elapsed:.1f}s, {tokens} tokens)")
                if self.verbose:
                    print(f"  Response: {response[:200]}...")
            else:
                log_fail(f"Response failed: {evaluation['reason']}")
                print(f"  Response: {response[:200]}...")

            print(f"  Tools called: {', '.join(tools_used) if tools_used else 'None'}")
            print(f"  Checks: tool={evaluation['tool_used']}, placeholders={evaluation['no_placeholders']}, links={evaluation['valid_links']}, no_errors={evaluation['no_errors']}")

            results.append({
                'question': question,
                'response': response,
                'tokens': tokens,
                'time': elapsed,
                'tools_called': tool_calls,
                'evaluation': evaluation
            })

        return results

    def run_all_tests(self, filter_tool=None):
        """Run tests for all tools or a specific tool."""
        log_info(f"Starting end-to-end tests using {self.model}")
        log_info(f"Player context: {self.player_context['name']}, Level {self.player_context['level']} {self.player_context['class']}")
        print("=" * 60)

        start_time = time.time()

        tools_to_test = self.test_data['tools']
        if filter_tool:
            if filter_tool in tools_to_test:
                tools_to_test = {filter_tool: tools_to_test[filter_tool]}
            else:
                log_fail(f"Tool '{filter_tool}' not found in test questions")
                return

        for tool_name, tool_config in tools_to_test.items():
            self.results[tool_name] = self.test_tool(tool_name, tool_config)

        total_time = time.time() - start_time

        # Generate report
        self.generate_report(total_time)

    def generate_report(self, total_time):
        """Generate markdown test report."""
        print("\n" + "=" * 60)
        log_info("Generating test report...")

        # Calculate statistics
        total_tests = 0
        passed_tests = 0
        failed_tools = []

        for tool_name, results in self.results.items():
            for r in results:
                total_tests += 1
                if r['evaluation']['passed']:
                    passed_tests += 1
                else:
                    if tool_name not in [t[0] for t in failed_tools]:
                        failed_tools.append((tool_name, r['evaluation']['reason']))

        # Print summary
        print(f"\n{Colors.BOLD}=== TEST SUMMARY ==={Colors.END}")
        print(f"Total tests: {total_tests}")
        print(f"Passed: {Colors.GREEN}{passed_tests}{Colors.END}")
        print(f"Failed: {Colors.RED}{total_tests - passed_tests}{Colors.END}")
        print(f"Time: {total_time:.1f}s")

        if failed_tools:
            print(f"\n{Colors.RED}Failed tools:{Colors.END}")
            for tool, reason in failed_tools:
                print(f"  - {tool}: {reason}")

        # Generate markdown report
        if hasattr(self, 'host_mode') and self.host_mode:
            report_path = os.path.join(
                os.path.dirname(
                    os.path.abspath(__file__)),
                'tool-test-report.md')
        else:
            report_path = '/tmp/tool-test-report.md'

        with open(report_path, 'w') as f:
            f.write(f"# Tool Test Report\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Model:** {self.model}\n")
            f.write(f"**Total Time:** {total_time:.1f}s\n\n")

            f.write(f"## Summary\n\n")
            f.write(f"| Metric | Value |\n")
            f.write(f"|--------|-------|\n")
            f.write(f"| Total Tests | {total_tests} |\n")
            f.write(f"| Passed | {passed_tests} |\n")
            f.write(f"| Failed | {total_tests - passed_tests} |\n")
            f.write(f"| Pass Rate | {passed_tests/total_tests*100:.1f}% |\n\n")

            f.write(f"## Results by Tool\n\n")

            for tool_name, results in self.results.items():
                tool_passed = all(r['evaluation']['passed'] for r in results)
                status = "✅" if tool_passed else "❌"

                f.write(f"### {status} {tool_name}\n\n")

                for i, r in enumerate(results, 1):
                    eval_status = "✅" if r['evaluation']['passed'] else "❌"
                    f.write(f"**Q{i}:** {r['question']}\n\n")
                    f.write(f"- Status: {eval_status}\n")
                    f.write(f"- Tools called: {', '.join([tc['tool'] for tc in r['tools_called']]) or 'None'}\n")
                    f.write(f"- Tokens: {r['tokens']}, Time: {r['time']:.1f}s\n")

                    if not r['evaluation']['passed']:
                        f.write(f"- **Issue:** {r['evaluation']['reason']}\n")
                        f.write(f"- Response: {r['response'][:200]}...\n")

                    f.write("\n")

            # Issues to fix section
            if failed_tools:
                f.write(f"## Issues to Fix\n\n")
                for tool, reason in failed_tools:
                    f.write(f"- [ ] **{tool}**: {reason}\n")

        log_info(f"Report saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Run end-to-end tool tests')
    parser.add_argument(
        '--tool', help='Test only a specific tool')
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Show detailed output')
    parser.add_argument(
        '--host', action='store_true',
        help='Run from Windows host (uses localhost '
        'for DB, reads config from env/dist/)')
    args = parser.parse_args()

    runner = ToolTestRunner(
        verbose=args.verbose,
        host_mode=args.host)
    runner.run_all_tests(filter_tool=args.tool)


if __name__ == '__main__':
    main()
