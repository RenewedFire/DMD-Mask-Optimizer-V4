"""Generated-fixture tests for the desktop workflow; no live pinball apps."""

from pathlib import Path
import json
import subprocess
import sys

import pytest
from PySide6.QtCore import QObject, Qt, Signal

from dmd_optimizer.ui.inputs import InputValidationError, validate_inputs
from dmd_optimizer.ui.main import MainWindow
from dmd_optimizer.ui.preview import render_frame
from dmd_optimizer.ui.results import ResultView
from dmd_optimizer.controller.model import RunResult


class FakeController(QObject):
    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.started = []
        self.cancelled = False

    @property
    def is_running(self) -> bool:
        return bool(self.started) and not self.cancelled

    def start(self, request):
        self.started.append(request)
        return "job-fixture"

    def cancel(self) -> None:
        self.cancelled = True

    def resume(self, prior_run, request):
        self.started.append(request)
        return "job-resume"


def fixture_inputs(tmp_path: Path):
    rom = tmp_path / "ROM files" / "twst_405.zip"
    dump_a = tmp_path / "captures" / "game one.txt"
    dump_b = tmp_path / "captures" / "game two.txt"
    output = tmp_path / "published output"
    for path in (rom, dump_a, dump_b):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    return rom, (dump_a, dump_b), output


def test_validate_inputs_accepts_supported_rom_multiple_optional_dumps_and_default_budget(tmp_path):
    """Changing path validation or the 1,800-second default would reject valid author input."""
    rom, dumps, output = fixture_inputs(tmp_path)

    request = validate_inputs(rom, dumps, output, 1800, None)

    assert request.rom_path == rom
    assert request.dump_paths == dumps
    assert request.output_dir == output
    assert request.budget_seconds == 1800


def test_validate_inputs_rejects_missing_or_unsupported_rom(tmp_path):
    """Removing the profile gate would silently call an unsupported ROM supported."""
    _, dumps, output = fixture_inputs(tmp_path)
    unsupported = tmp_path / "other.zip"
    unsupported.write_bytes(b"fixture")

    with pytest.raises(InputValidationError, match="missing"):
        validate_inputs(tmp_path / "twst_405.zip", (), output, 1800, None)
    with pytest.raises(InputValidationError, match="unsupported"):
        validate_inputs(unsupported, dumps, output, 1800, None)


def test_window_wires_start_cancel_and_resume_without_manual_grouping(qtbot, tmp_path):
    """Removing form wiring would strand authors at an unresponsive manual workflow."""
    rom, dumps, output = fixture_inputs(tmp_path)
    controller = FakeController()
    window = MainWindow(controller)
    qtbot.addWidget(window)
    window.rom_path.setText(str(rom))
    window.dump_paths.setText(";".join(map(str, dumps)))
    window.output_path.setText(str(output))

    qtbot.mouseClick(window.start_button, Qt.LeftButton)
    qtbot.mouseClick(window.cancel_button, Qt.LeftButton)
    prior = tmp_path / "prior run"
    prior.mkdir()
    window.prior_run_path.setText(str(prior))
    qtbot.mouseClick(window.resume_button, Qt.LeftButton)

    assert len(controller.started) == 2
    assert controller.started[0].budget_seconds == 1800
    assert controller.cancelled is True
    assert not hasattr(window, "grouping_prompt")


def test_result_view_only_enables_existing_verified_editable_project(tmp_path):
    """Guessing an output path would incorrectly offer a nonexistent editable project."""
    result = RunResult("run", "deadline", "observed", "provisional", "unknown", "diagnostic-only",
                       "v1", None, 4, "digest", 1800, 2, {})
    report = tmp_path / "report.json"
    report.write_text("{}")

    view = ResultView.from_run(result, {"report_path": str(report), "project_path": str(tmp_path / "missing")})

    assert view.editable_project_enabled is False
    assert view.report_enabled is True
    assert view.stop_label == "deadline"
    assert view.pending_frames == 4


def test_preview_uses_four_shades_and_integer_scale():
    """Changing nearest-neighbor scaling would blur the author’s native DMD pixels."""
    image = render_frame(bytes([0, 1, 2, 3]), 2, 2, 3)

    assert (image.width(), image.height()) == (6, 6)
    assert image.pixelColor(0, 0).red() == 0
    assert image.pixelColor(5, 5).red() == 255


def test_window_shows_result_labels_and_only_opens_verified_paths(qtbot, tmp_path):
    """Guessing result paths or enabling diagnostic projects would mislead authors."""
    report, folder = tmp_path / "report.json", tmp_path / "companion"
    report.write_text("{}")
    folder.mkdir()
    opened = []
    controller = FakeController()
    window = MainWindow(controller, opener=opened.append)
    qtbot.addWidget(window)
    result = RunResult("run", "deadline", "observed", "partial", "unknown", "diagnostic-only",
                       "v1", None, 7, "digest", 1800, 3,
                       {"manifest": {"report_path": str(report), "companion_folder": str(folder)}})

    controller.finished.emit(result)
    qtbot.mouseClick(window.open_report_button, Qt.LeftButton)
    qtbot.mouseClick(window.open_folder_button, Qt.LeftButton)

    assert "Stop: deadline" in window.result_status.text()
    assert "flush: 3.0s" in window.result_status.text()
    assert window.open_project_button.isEnabled() is False
    assert opened == [report, folder]


def test_window_coalesces_rapid_progress_and_cancels_on_close(qtbot):
    """A progress flood or window close must not freeze the event loop or abandon cancellation."""
    controller = FakeController()
    window = MainWindow(controller)
    qtbot.addWidget(window)
    for index in range(100):
        controller.progress.emit(type("P", (), {"stage": "solve", "elapsed_seconds": index,
                                                  "remaining_seconds": 100 - index})())

    window.close()

    assert "99.0s elapsed" in window.status.text()
    assert controller.cancelled is True


def test_launcher_check_reports_readiness_without_opening_external_apps():
    """Replacing the thin check with an editor launch would violate static-corpus qualification."""
    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run([sys.executable, "scripts/launch_desktop.py", "--check"], cwd=root,
                               text=True, capture_output=True, check=False)

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["external_apps_required"] is False
    assert "pyside6_available" in report
