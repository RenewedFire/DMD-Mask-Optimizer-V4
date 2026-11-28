"""The non-blocking desktop authoring window."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (QApplication, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMainWindow, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from .inputs import InputValidationError, validate_inputs
from .job_controller import JobController, ProgressView
from .results import ResultView


class MainWindow(QMainWindow):
    """Collect bounded static-corpus input and dispatch it to a JobController."""

    def __init__(self, controller: JobController | None = None,
                 opener: Callable[[Path], object] | None = None) -> None:
        super().__init__()
        self.controller = controller or JobController()
        self._opener = opener or (lambda path: QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))))
        self._result_view: ResultView | None = None
        self.setWindowTitle("DMD Mask Optimizer")
        self.rom_path = QLineEdit()
        self.dump_paths = QLineEdit()
        self.output_path = QLineEdit()
        self.prior_run_path = QLineEdit()
        self.budget_seconds = QSpinBox()
        self.budget_seconds.setRange(1, 86_400)
        self.budget_seconds.setValue(1_800)
        self.start_button = QPushButton("Start")
        self.cancel_button = QPushButton("Cancel")
        self.resume_button = QPushButton("Resume")
        self.status = QLabel("Ready. Analysis uses the locked Twister corpus.")
        self.status.setWordWrap(True)
        self.result_status = QLabel("No completed result.")
        self.result_status.setWordWrap(True)
        self.open_project_button = QPushButton("Open editable project")
        self.open_report_button = QPushButton("Open report")
        self.open_folder_button = QPushButton("Open companion folder")
        for button in (self.open_project_button, self.open_report_button, self.open_folder_button):
            button.setEnabled(False)
        self._build_layout()
        self.start_button.clicked.connect(self._start)
        self.cancel_button.clicked.connect(self.controller.cancel)
        self.resume_button.clicked.connect(self._resume)
        self.controller.progress.connect(self._progress)
        self.controller.finished.connect(self._finished)
        self.controller.failed.connect(self._failed)
        self.open_project_button.clicked.connect(lambda: self._open_result("project_path"))
        self.open_report_button.clicked.connect(lambda: self._open_result("report_path"))
        self.open_folder_button.clicked.connect(lambda: self._open_result("companion_folder"))

    def _build_layout(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        form = QFormLayout()
        form.addRow("ROM", self._with_button(self.rom_path, "Load ROM", self._choose_rom))
        form.addRow("Optional dumps", self._with_button(self.dump_paths, "Add Dumps", self._choose_dumps))
        form.addRow("Output folder", self._with_button(self.output_path, "Choose", self._choose_output))
        form.addRow("Run limit (seconds)", self.budget_seconds)
        form.addRow("Prior run", self.prior_run_path)
        layout.addLayout(form)
        actions = QHBoxLayout()
        actions.addWidget(self.start_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.resume_button)
        layout.addLayout(actions)
        layout.addWidget(self.status)
        layout.addWidget(self.result_status)
        result_actions = QHBoxLayout()
        result_actions.addWidget(self.open_project_button)
        result_actions.addWidget(self.open_report_button)
        result_actions.addWidget(self.open_folder_button)
        layout.addLayout(result_actions)
        self.setCentralWidget(root)

    @staticmethod
    def _with_button(field: QLineEdit, label: str, callback) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(field)
        button = QPushButton(label)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return container

    def _choose_rom(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Twister ROM", filter="ZIP files (*.zip)")
        if path:
            self.rom_path.setText(path)

    def _choose_dumps(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select optional dumps", filter="Text dumps (*.txt)")
        if paths:
            self.dump_paths.setText(";".join(paths))

    def _choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output folder")
        if path:
            self.output_path.setText(path)

    def _request(self, prior_run: Path | None = None):
        dumps = tuple(Path(item) for item in self.dump_paths.text().split(";") if item.strip())
        return validate_inputs(Path(self.rom_path.text()), dumps, Path(self.output_path.text()),
                               float(self.budget_seconds.value()), prior_run)

    def _start(self) -> None:
        try:
            self.controller.start(self._request())
        except (InputValidationError, RuntimeError) as error:
            self.status.setText(str(error))
        else:
            self.status.setText("Job started using the locked static corpus.")

    def _resume(self) -> None:
        try:
            prior = Path(self.prior_run_path.text())
            self.controller.resume(prior, self._request(prior))
        except (InputValidationError, RuntimeError) as error:
            self.status.setText(str(error))
        else:
            self.status.setText("Resume requested; compatibility will be checked by the controller.")

    def _progress(self, progress: ProgressView) -> None:
        self.status.setText(f"{progress.stage}: {progress.elapsed_seconds:.1f}s elapsed, "
                            f"{progress.remaining_seconds:.1f}s remaining")

    def _finished(self, result) -> None:
        self.status.setText(f"{result.stop_reason}; checkpoint {result.checkpoint_digest or 'unavailable'}")
        manifest = result.diagnostics.get("manifest") if isinstance(result.diagnostics, dict) else None
        self._result_view = ResultView.from_run(result, manifest if isinstance(manifest, dict) else None)
        view = self._result_view
        self.result_status.setText(
            f"Stop: {view.stop_label}; recognition: {view.recognition_label}; "
            f"coverage: {view.coverage_label}; optimality: {view.optimality_label}; "
            f"export: {view.export_label}; pending: {view.pending_frames}; "
            f"elapsed: {view.elapsed_seconds:.1f}s; flush: {view.flush_seconds:.1f}s")
        self.open_project_button.setEnabled(view.editable_project_enabled)
        self.open_report_button.setEnabled(view.report_enabled)
        self.open_folder_button.setEnabled(view.folder_enabled)

    def _failed(self, message: str) -> None:
        self.status.setText(f"Job failed: {message}")

    def _open_result(self, name: str) -> None:
        path = getattr(self._result_view, name, None) if self._result_view else None
        if isinstance(path, Path) and path.exists():
            self._opener(path)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.controller.cancel()
        event.accept()


def launch_desktop(controller: JobController | None = None) -> int:
    """Launch the same window that the future packaged executable will use."""
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(controller)
    window.show()
    return app.exec()
