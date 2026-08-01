"""Unit tests for option/argument value shell completions.

Covers the `autocompletion=` callables added for enumerable values:
`agent models free --preset` presets, `kernel` names, `agent install` tools,
`agent setup` bundles, `agent add` addons, and the `--kind` filters.
"""

from __future__ import annotations

from unittest.mock import patch

from typer.main import get_command

from astroai_lab.cli.main import app


def _click_command(path: str):
    cmd = get_command(app)
    for part in path.split():
        cmd = cmd.commands[part]
    return cmd


def _param(path: str, name: str):
    return next(p for p in _click_command(path).params if p.name == name)


def _completion_values(param, incomplete: str) -> set[str]:
    results = param.shell_complete(ctx=None, incomplete=incomplete)
    return {getattr(r, "value", str(r)) for r in results}


# --- preset completions (agent models free --preset) -----------------------


def test_preset_completer_offers_preset_names() -> None:
    from astroai_lab.cli.agent_cmd import _preset_completer

    offered = _preset_completer(None, "")
    assert "coding" in offered
    assert "long" in offered
    assert "reasoning" in offered


def test_preset_completer_filters_by_prefix() -> None:
    from astroai_lab.cli.agent_cmd import _preset_completer

    offered = _preset_completer(None, "co")
    assert offered == ["coding"]


def test_models_free_preset_option_wired() -> None:
    param = _param("agent models free", "preset")
    assert getattr(param, "_custom_shell_complete", None) is not None
    values = _completion_values(param, "")
    assert "coding" in values
    assert "long" in values


# --- kernel name completions ------------------------------------------------


def test_kernel_name_completer_offers_registered_kernels() -> None:
    from astroai_lab.cli.kernel import _kernel_name_completer

    with patch(
        "astroai_lab.cli.kernel.list_kernels",
        return_value=[{"name": "astroai", "path": "/x"}, {"name": "mylab", "path": "/y"}],
    ):
        offered = _kernel_name_completer(None, "")
    assert offered == ["astroai", "mylab"]


def test_kernel_name_completer_never_raises_without_jupyter() -> None:
    from astroai_lab.cli.kernel import _kernel_name_completer

    with patch("astroai_lab.cli.kernel.list_kernels", side_effect=RuntimeError("boom")):
        assert _kernel_name_completer(None, "") == []


def test_kernel_unregister_argument_wired() -> None:
    param = _param("kernel unregister", "name")
    assert getattr(param, "_custom_shell_complete", None) is not None
    with patch(
        "astroai_lab.cli.kernel.list_kernels",
        return_value=[{"name": "mylab", "path": "/y"}],
    ):
        values = _completion_values(param, "")
    assert "mylab" in values


def test_kernel_ensure_name_option_wired() -> None:
    param = _param("kernel ensure", "name")
    assert getattr(param, "_custom_shell_complete", None) is not None


# --- tool / bundle / addon completions --------------------------------------


def test_tool_completer_offers_installable_clis() -> None:
    from astroai_lab.cli.agent_cmd import _tool_completer

    with patch(
        "astroai_lab.cli.agent_cmd.agent_install.list_tools_status",
        return_value=[
            {"name": "kilo", "binary": "kilo", "installed": False, "description": ""},
            {"name": "goose", "binary": "goose", "installed": False, "description": ""},
        ],
    ):
        offered = _tool_completer(None, "")
    assert "kilo" in offered
    assert "goose" in offered


def test_tool_completer_filters_by_prefix() -> None:
    from astroai_lab.cli.agent_cmd import _tool_completer

    with patch(
        "astroai_lab.cli.agent_cmd.agent_install.list_tools_status",
        return_value=[
            {"name": "kilo", "binary": "kilo", "installed": False, "description": ""},
            {"name": "goose", "binary": "goose", "installed": False, "description": ""},
        ],
    ):
        offered = _tool_completer(None, "ki")
    assert offered == ["kilo"]


def test_agent_install_tool_argument_wired() -> None:
    param = _param("agent install", "tool")
    assert getattr(param, "_custom_shell_complete", None) is not None


def test_bundle_completer_offers_bundle_names() -> None:
    from astroai_lab.cli.agent_cmd import _bundle_completer

    with patch(
        "astroai_lab.cli.agent_cmd.agent_setup_mod.agent_list_bundles",
        return_value={"cursor": "Cursor config", "claude": "Claude config"},
    ):
        offered = _bundle_completer(None, "")
    assert "cursor" in offered
    assert "claude" in offered


def test_agent_setup_bundle_argument_wired() -> None:
    param = _param("agent setup", "bundle")
    assert getattr(param, "_custom_shell_complete", None) is not None


def test_addon_completer_offers_addon_ids() -> None:
    from astroai_lab.cli.agent_cmd import _addon_completer

    with patch(
        "astroai_lab.cli.agent_cmd.agent_addons.list_addons",
        return_value=[
            {
                "id": "ponytail",
                "kind": "rule",
                "default": False,
                "installed": False,
                "tags": ["lean"],
                "summary": "",
            }
        ],
    ):
        offered = _addon_completer(None, "")
    assert "ponytail" in offered


def test_agent_add_names_argument_wired() -> None:
    param = _param("agent add", "names")
    assert getattr(param, "_custom_shell_complete", None) is not None


# --- --kind filter completions ----------------------------------------------


def test_addon_kind_completer_offers_kinds() -> None:
    from astroai_lab.cli.agent_cmd import _addon_kind_completer

    assert set(_addon_kind_completer(None, "")) == {"skill", "bundle", "mcp", "tool", "rule"}


def test_catalog_kind_completer_offers_kinds() -> None:
    from astroai_lab.cli.agent_cmd import _catalog_kind_completer

    assert set(_catalog_kind_completer(None, "")) == {
        "agent",
        "skill",
        "rule",
        "mcp",
        "tool",
        "container",
    }


def test_addons_kind_option_wired() -> None:
    param = _param("agent addons", "kind")
    assert getattr(param, "_custom_shell_complete", None) is not None


def test_catalog_kind_option_wired() -> None:
    param = _param("agent catalog", "kind")
    assert getattr(param, "_custom_shell_complete", None) is not None
