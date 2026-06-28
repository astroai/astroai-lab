from __future__ import annotations

import json
import os
from pathlib import Path

from canfar_lab.core.project import require_project
from canfar_lab.errors import LabError
from canfar_lab.utils.subprocess import run, run_capture, which


def _kernels_dir() -> Path:
    return Path.home() / ".local" / "share" / "jupyter" / "kernels"


def _python_for_project(project: Path) -> Path:
    kind = require_project(project)
    if kind.value == "pixi":
        return project / ".pixi" / "envs" / "default" / "bin" / "python"
    return project / ".venv" / "bin" / "python"


def register_kernel(project: Path, *, name: str | None = None) -> str:
    if which("jupyter") is None:
        raise LabError("jupyter not found.", hint="Use a notebook session image.")
    require_project(project)
    py = _python_for_project(project)
    if not py.is_file():
        raise LabError("Project environment not installed.", hint="pixi install  # or uv sync")

    os.environ.setdefault("JUPYTER_CONFIG_DIR", str(Path.home() / ".jupyter"))
    Path(os.environ["JUPYTER_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)

    kernel_name = name or project.name
    display = f"Python ({kernel_name})"
    run(
        [
            str(py),
            "-m",
            "ipykernel",
            "install",
            "--user",
            f"--name={kernel_name}",
            f"--display-name={display}",
        ]
    )
    return kernel_name


def list_kernels() -> list[dict[str, str]]:
    if which("jupyter") is None:
        return []
    try:
        out = run_capture(["jupyter", "kernelspec", "list", "--json"])
        data = json.loads(out)
        specs = data.get("kernelspecs", {})
        return [{"name": k, "path": v.get("resource_dir", "")} for k, v in specs.items()]
    except (LabError, json.JSONDecodeError):
        return []


def unregister_kernel(name: str) -> None:
    if which("jupyter") is None:
        raise LabError("jupyter not found.")
    run(["jupyter", "kernelspec", "remove", "-y", name])
