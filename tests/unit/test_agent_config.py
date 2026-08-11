"""Unit tests for `agent config <id>` (Phase 2, docs/agent-rethink-plan.md).

Covers format-aware show/get/set/unset across jsonc/json5 (textual edits
preserve comments), yaml, toml, and the read-only markdown case, plus the
CLI surface (`agent config hermes`, --key, key=value, --unset, --json).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from astroai_lab.agent import agent_config as ac
from astroai_lab.cli.main import app
from astroai_lab.errors import LabError

runner = CliRunner()

HERMES_YAML = """# hermes config
model: nousresearch/hermes-3-llama-3.1-405b
provider: openrouter
"""

KILO_JSONC = """{
  // kilo settings
  "model": "kilo-default", // the default model
  "provider": "openrouter",
}
"""

OPENCLAW_JSON5 = """{
  // openclaw gateway
  "model": "openai/gpt-4o",
  "gateway": {
    "enabled": true,
    "port": 8080,
  },
}
"""

CODEX_TOML = """# codex config
model = "gpt-5"
model_provider = "openrouter"

[chat]
auto_send = true
"""


def _home(tmp_path: Path, agent_id: str, rel: str, content: str) -> Path:
    """Materialize an agent config file under a temp home; return home."""
    home = tmp_path / "home"
    path = home / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return home


def _materialize(home: Path, rel: str, content: str) -> None:
    path = home / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Path / format resolution
# ---------------------------------------------------------------------------


def test_agent_config_path_resolves_tilde(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    path = ac.agent_config_path("hermes", home=home)
    assert path == home / ".hermes" / "config.yaml"


def test_agent_config_path_unknown_agent() -> None:
    with pytest.raises(LabError, match="Unknown agent"):
        ac.agent_config_path("not-an-agent")


def test_config_format_declared(tmp_path: Path) -> None:
    assert ac.config_format("hermes") == "yaml"
    assert ac.config_format("openclaw") == "json5"
    assert ac.config_format("kilo") == "jsonc"
    assert ac.config_format("codex") == "toml"
    assert ac.config_format("cline") == "markdown"


# ---------------------------------------------------------------------------
# Read + get
# ---------------------------------------------------------------------------


def test_read_yaml(tmp_path: Path) -> None:
    home = _home(tmp_path, "hermes", ".hermes/config.yaml", HERMES_YAML)
    path, data = ac.read_agent_config("hermes", home=home)
    assert data["model"] == "nousresearch/hermes-3-llama-3.1-405b"
    assert data["provider"] == "openrouter"


def test_read_missing_file(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    with pytest.raises(LabError, match="config not found"):
        ac.read_agent_config("hermes", home=home)


def test_read_jsonc_tolerates_comments(tmp_path: Path) -> None:
    home = _home(tmp_path, "kilo", ".config/kilo/kilo.jsonc", KILO_JSONC)
    _, data = ac.read_agent_config("kilo", home=home)
    assert data["model"] == "kilo-default"
    assert data["provider"] == "openrouter"


def test_read_broken_json_raises(tmp_path: Path) -> None:
    home = _home(tmp_path, "kilo", ".config/kilo/kilo.jsonc", '{\n  "model": [unclosed\n')
    with pytest.raises(LabError, match="Cannot parse"):
        ac.read_agent_config("kilo", home=home)


def test_read_markdown_readonly(tmp_path: Path) -> None:
    home = _home(tmp_path, "cline", ".config/canfar/lab/cline-notes.md", "# notes\n")
    with pytest.raises(LabError, match="read-only"):
        ac.read_agent_config("cline", home=home)


def test_get_config_value_dotted(tmp_path: Path) -> None:
    home = _home(tmp_path, "openclaw", ".openclaw/openclaw.json", OPENCLAW_JSON5)
    value, found = ac.get_config_value("openclaw", "gateway.port", home=home)
    assert found and value == 8080
    _, found = ac.get_config_value("openclaw", "gateway.missing", home=home)
    assert not found


def test_parse_value_literals() -> None:
    assert ac.parse_value("42") == 42
    assert ac.parse_value("true") is True
    assert ac.parse_value('"quoted"') == "quoted"
    assert ac.parse_value("plain-string") == "plain-string"


# ---------------------------------------------------------------------------
# JSONC / JSON5 textual edits (comments + trailing commas survive)
# ---------------------------------------------------------------------------


def test_set_jsonc_existing_key_preserves_comments(tmp_path: Path) -> None:
    home = _home(tmp_path, "kilo", ".config/kilo/kilo.jsonc", KILO_JSONC)
    actions = ac.edit_agent_config("kilo", home=home, set_items={"model": "kilo-new"})
    assert actions == [{"key": "model", "status": "set", "detail": "kilo-new"}]
    text = (home / ".config/kilo/kilo.jsonc").read_text(encoding="utf-8")
    assert "// kilo settings" in text  # comment preserved
    assert '"model": "kilo-new"' in text
    assert text.count('"model"') == 1  # replaced, not duplicated
    assert '"provider": "openrouter"' in text
    # still parses
    _, data = ac.read_agent_config("kilo", home=home)
    assert data["model"] == "kilo-new"
    assert data["provider"] == "openrouter"


def test_set_jsonc_insert_new_top_level(tmp_path: Path) -> None:
    home = _home(tmp_path, "kilo", ".config/kilo/kilo.jsonc", KILO_JSONC)
    ac.edit_agent_config("kilo", home=home, set_items={"temperature": 0.7})
    text = (home / ".config/kilo/kilo.jsonc").read_text(encoding="utf-8")
    assert '"temperature": 0.7' in text
    _, data = ac.read_agent_config("kilo", home=home)
    assert data["temperature"] == 0.7


def test_set_jsonc_insert_dotted_nested(tmp_path: Path) -> None:
    home = _home(tmp_path, "openclaw", ".openclaw/openclaw.json", OPENCLAW_JSON5)
    ac.edit_agent_config("openclaw", home=home, set_items={"gateway.timeout": 120})
    text = (home / ".openclaw/openclaw.json").read_text(encoding="utf-8")
    assert '"timeout": 120' in text
    _, data = ac.read_agent_config("openclaw", home=home)
    assert data["gateway"]["timeout"] == 120


def test_set_jsonc_insert_missing_root_creates_nested(tmp_path: Path) -> None:
    home = _home(tmp_path, "openclaw", ".openclaw/openclaw.json", "{}\n")
    ac.edit_agent_config("openclaw", home=home, set_items={"gateway.port": 9090})
    _, data = ac.read_agent_config("openclaw", home=home)
    assert data == {"gateway": {"port": 9090}}


def test_set_jsonc_dict_value(tmp_path: Path) -> None:
    home = _home(tmp_path, "openclaw", ".openclaw/openclaw.json", OPENCLAW_JSON5)
    ac.edit_agent_config(
        "openclaw",
        home=home,
        set_items={"server": {"command": "astroai-workload", "args": ["mcp", "serve"]}},
    )
    _, data = ac.read_agent_config("openclaw", home=home)
    assert data["server"]["args"] == ["mcp", "serve"]


def test_unset_jsonc_middle_entry(tmp_path: Path) -> None:
    home = _home(tmp_path, "kilo", ".config/kilo/kilo.jsonc", KILO_JSONC)
    ac.edit_agent_config("kilo", home=home, unsets=["provider"])
    text = (home / ".config/kilo/kilo.jsonc").read_text(encoding="utf-8")
    assert "provider" not in text
    _, data = ac.read_agent_config("kilo", home=home)
    assert "provider" not in data


def test_unset_jsonc_last_entry_no_dangling_comma(tmp_path: Path) -> None:
    home = _home(
        tmp_path,
        "kilo",
        ".config/kilo/kilo.jsonc",
        '{\n  "model": "kilo-default",\n  "provider": "openrouter"\n}\n',
    )
    ac.edit_agent_config("kilo", home=home, unsets=["provider"])
    text = (home / ".config/kilo/kilo.jsonc").read_text(encoding="utf-8")
    assert '"provider"' not in text
    assert "openrouter" not in text
    _, data = ac.read_agent_config("kilo", home=home)
    assert data == {"model": "kilo-default"}


def test_edit_dry_run_writes_nothing(tmp_path: Path) -> None:
    home = _home(tmp_path, "kilo", ".config/kilo/kilo.jsonc", KILO_JSONC)
    actions = ac.edit_agent_config("kilo", home=home, set_items={"model": "x"}, dry_run=True)
    assert actions[0]["status"] == "would_set"
    assert '"model": "kilo-default"' in (home / ".config/kilo/kilo.jsonc").read_text()


# ---------------------------------------------------------------------------
# YAML edits
# ---------------------------------------------------------------------------


def test_set_yaml(tmp_path: Path) -> None:
    home = _home(tmp_path, "hermes", ".hermes/config.yaml", HERMES_YAML)
    ac.edit_agent_config("hermes", home=home, set_items={"model": "new-model"})
    _, data = ac.read_agent_config("hermes", home=home)
    assert data["model"] == "new-model"
    assert data["provider"] == "openrouter"


def test_set_yaml_insert_dotted(tmp_path: Path) -> None:
    home = _home(tmp_path, "hermes", ".hermes/config.yaml", "model: x\n")
    ac.edit_agent_config("hermes", home=home, set_items={"gateway.port": 9000})
    _, data = ac.read_agent_config("hermes", home=home)
    assert data["gateway"]["port"] == 9000


def test_unset_yaml(tmp_path: Path) -> None:
    home = _home(tmp_path, "hermes", ".hermes/config.yaml", HERMES_YAML)
    ac.edit_agent_config("hermes", home=home, unsets=["provider"])
    _, data = ac.read_agent_config("hermes", home=home)
    assert "provider" not in data


# ---------------------------------------------------------------------------
# TOML edits (codex)
# ---------------------------------------------------------------------------


def test_set_toml_top_level(tmp_path: Path) -> None:
    home = _home(tmp_path, "codex", ".codex/config.toml", CODEX_TOML)
    ac.edit_agent_config("codex", home=home, set_items={"model": "gpt-6"})
    text = (home / ".codex/config.toml").read_text(encoding="utf-8")
    assert 'model = "gpt-6"' in text
    _, data = ac.read_agent_config("codex", home=home)
    assert data["model"] == "gpt-6"


def test_set_toml_table_key(tmp_path: Path) -> None:
    home = _home(tmp_path, "codex", ".codex/config.toml", CODEX_TOML)
    ac.edit_agent_config("codex", home=home, set_items={"chat.auto_send": False})
    _, data = ac.read_agent_config("codex", home=home)
    assert data["chat"]["auto_send"] is False


def test_set_toml_new_table(tmp_path: Path) -> None:
    home = _home(tmp_path, "codex", ".codex/config.toml", "# empty\n")
    ac.edit_agent_config("codex", home=home, set_items={"chat.auto_send": True})
    _, data = ac.read_agent_config("codex", home=home)
    assert data["chat"]["auto_send"] is True


def test_set_toml_complex_value_raises(tmp_path: Path) -> None:
    home = _home(tmp_path, "codex", ".codex/config.toml", CODEX_TOML)
    with pytest.raises(LabError, match="scalar"):
        ac.edit_agent_config("codex", home=home, set_items={"model": {"a": 1}})


def test_unset_toml(tmp_path: Path) -> None:
    home = _home(tmp_path, "codex", ".codex/config.toml", CODEX_TOML)
    ac.edit_agent_config("codex", home=home, unsets=["model"])
    text = (home / ".codex/config.toml").read_text(encoding="utf-8")
    assert 'model = "gpt-5"' not in text  # the model line is gone
    assert 'model_provider = "openrouter"' in text  # sibling key untouched
    _, data = ac.read_agent_config("codex", home=home)
    assert "model" not in data
    assert data["model_provider"] == "openrouter"


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_cli_config_show_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _materialize(tmp_path, ".hermes/config.yaml", HERMES_YAML)
    result = runner.invoke(app, ["--json", "agent", "config", "hermes"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["agent"] == "hermes"
    assert data["format"] == "yaml"
    assert data["data"]["model"] == "nousresearch/hermes-3-llama-3.1-405b"


def test_cli_config_key_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _materialize(tmp_path, ".hermes/config.yaml", HERMES_YAML)
    result = runner.invoke(app, ["--json", "agent", "config", "hermes", "--key", "model"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["value"] == "nousresearch/hermes-3-llama-3.1-405b"


def test_cli_config_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _materialize(tmp_path, ".hermes/config.yaml", HERMES_YAML)
    result = runner.invoke(app, ["--json", "agent", "config", "hermes", "model=new-model"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["actions"][0]["status"] == "set"
    assert "new-model" in (tmp_path / ".hermes/config.yaml").read_text()


def test_cli_config_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _materialize(tmp_path, ".hermes/config.yaml", HERMES_YAML)
    result = runner.invoke(app, ["--json", "agent", "config", "hermes", "--unset", "provider"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["actions"][0]["status"] == "unset"
    assert "provider" not in (tmp_path / ".hermes/config.yaml").read_text()


def test_cli_config_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = runner.invoke(app, ["--json", "agent", "config", "hermes"])
    assert result.exit_code == 1
    assert "config not found" in json.loads(result.stdout)["errors"][0]
