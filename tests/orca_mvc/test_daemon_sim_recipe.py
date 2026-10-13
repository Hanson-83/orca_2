"""离线锁定 PURE_SIM 配方字符串。不导入 orca，也不连接 daemon。"""

from __future__ import annotations

from pathlib import Path

from examples.mvc_daemon_sim.specs import (
    PLATE_READOUT_SPEC,
    PLATE_READOUT_WORKFLOW,
    SEAL_AND_SHAKE_SPEC,
    SEAL_AND_SHAKE_WORKFLOW,
    TOPOLOGY_SPEC,
)

_README = Path(__file__).resolve().parents[2] / "src" / "orca_mvc" / "README.md"


def test_recipe_names_match_control_plane_protocols() -> None:
    assert TOPOLOGY_SPEC == "examples.mvc_daemon_sim:build_topology"
    assert PLATE_READOUT_WORKFLOW == "plate_readout"
    assert SEAL_AND_SHAKE_WORKFLOW == "seal_and_shake"
    assert PLATE_READOUT_SPEC.endswith(":build_workflow")
    assert SEAL_AND_SHAKE_SPEC.endswith(":build_workflow")
    assert PLATE_READOUT_SPEC != SEAL_AND_SHAKE_SPEC


def test_package_import_does_not_load_topology() -> None:
    import sys

    import examples.mvc_daemon_sim as pkg

    assert "build_topology" not in vars(pkg)
    assert "examples.mvc_daemon_sim.topology" not in sys.modules


def test_readme_has_copy_paste_mount_and_load() -> None:
    text = _README.read_text(encoding="utf-8")
    for snippet in (
        TOPOLOGY_SPEC,
        PLATE_READOUT_SPEC,
        SEAL_AND_SHAKE_SPEC,
        "ORCA_MVC_RUNTIME=daemon",
        "python -m examples.mvc_daemon_sim.smoke",
    ):
        assert snippet in text
    assert "<module:build_topology>" not in text
    assert "examples.mvc_daemon_sim:build_topology --sim" in text
