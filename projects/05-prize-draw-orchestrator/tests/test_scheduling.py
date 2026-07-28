import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fakes import FakeLLMProvider, FakeMCPToolClient

from orchestrator import run_forever

CRITERIA = {"prize_types": ["cash"]}


class TestRunForever:
    def test_runs_the_configured_number_of_iterations_and_sleeps_between_them(self):
        client = FakeMCPToolClient(draws=[])
        llm = FakeLLMProvider()
        sleep_calls = []

        run_forever(
            client,
            llm,
            CRITERIA,
            interval_minutes=5,
            dry_run=True,
            confirm_personal_data=False,
            sleep_fn=sleep_calls.append,
            max_iterations=3,
        )

        assert len([c for c in client.calls if c[0] == "search_draws"]) == 3
        # Sleeps between iterations, not after the last one.
        assert sleep_calls == [300, 300]

    def test_a_bad_iteration_does_not_stop_the_loop(self):
        class ExplodingMCPClient:
            def __init__(self):
                self.attempts = 0

            def call_tool(self, name, arguments):
                self.attempts += 1
                if self.attempts == 1:
                    raise RuntimeError("network blip")
                return {"draws": []}

        client = ExplodingMCPClient()
        sleep_calls = []

        run_forever(
            client,
            FakeLLMProvider(),
            CRITERIA,
            interval_minutes=1,
            sleep_fn=sleep_calls.append,
            max_iterations=2,
        )

        assert client.attempts == 2
