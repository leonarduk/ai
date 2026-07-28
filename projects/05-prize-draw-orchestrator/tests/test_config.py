import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config, DEFAULT_CRITERIA


class TestConfigFromEnv:
    def test_defaults_to_ollama_and_dry_run(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        for key in [
            "LLM_PROVIDER",
            "DEEPSEEK_API_KEY",
            "ANTHROPIC_API_KEY",
            "DRY_RUN",
            "CONFIRM_PERSONAL_DATA",
            "CRITERIA_CONFIG_PATH",
            "MCP_SERVER_ARGS",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = Config.from_env()

        assert config.llm_provider == "ollama"
        assert config.dry_run is True
        assert config.confirm_personal_data is False
        assert config.criteria == DEFAULT_CRITERIA

    def test_dry_run_false_requires_explicit_opt_out(self, monkeypatch):
        monkeypatch.setenv("DRY_RUN", "false")
        assert Config.from_env().dry_run is False

    def test_confirm_personal_data_requires_explicit_opt_in(self, monkeypatch):
        monkeypatch.setenv("CONFIRM_PERSONAL_DATA", "true")
        assert Config.from_env().confirm_personal_data is True

    def test_criteria_loaded_from_json_file(self, monkeypatch, tmp_path):
        criteria_path = tmp_path / "criteria.json"
        criteria_path.write_text(json.dumps({"min_prize_value": 200}))
        monkeypatch.setenv("CRITERIA_CONFIG_PATH", str(criteria_path))

        config = Config.from_env()

        assert config.criteria["min_prize_value"] == 200
        # Unspecified keys still fall back to defaults.
        assert config.criteria["regions"] == DEFAULT_CRITERIA["regions"]

    def test_mcp_server_args_parsed_as_json_array(self, monkeypatch):
        monkeypatch.setenv("MCP_SERVER_ARGS", '["server.py", "--flag"]')
        config = Config.from_env()
        assert config.mcp_server_args == ["server.py", "--flag"]

    def test_mcp_server_args_parsed_as_space_separated(self, monkeypatch):
        monkeypatch.setenv("MCP_SERVER_ARGS", "server.py --flag")
        config = Config.from_env()
        assert config.mcp_server_args == ["server.py", "--flag"]
