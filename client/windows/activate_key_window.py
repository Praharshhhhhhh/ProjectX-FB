from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton
from PyQt6.QtCore import pyqtSignal, QThread
import httpx

STYLE = """
QWidget { background:#0d1117; color:#e6edf3; font-family:'Segoe UI'; }
QLineEdit { background:#21262d; border:1px solid #30363d; border-radius:6px; padding:9px 12px; color:#e6edf3; font-size:13px; }
QLineEdit:focus { border-color:#2f81f7; }
QPushButton { background:#2f81f7; color:white; border:none; border-radius:6px; padding:9px 20px; font-weight:600; font-size:13px; }
QPushButton:hover { background:#388bfd; }
QPushButton:disabled { background:#21262d; color:#8b949e; }
QPushButton#ghost { background:rgba(255,255,255,0.05); border:1px solid #30363d; }
QPushButton#ghost:hover { background:rgba(255,255,255,0.1); }
QLabel { background:transparent; }
"""


class ActivateWorker(QThread):
    success = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, api, key_code, email, full_name, password):
        super().__init__()
        self.api, self.key_code, self.email = api, key_code, email
        self.full_name, self.password = full_name, password

    def start(self, *args, **kwargs):
        from widgets.common import _active_workers
        _active_workers.add(self)
        self.finished.connect(self._cleanup)
        super().start(*args, **kwargs)

    def _cleanup(self):
        from widgets.common import _active_workers
        _active_workers.discard(self)
        self.deleteLater()

    def run(self):
        try:
            data = self.api.activate_key(self.key_code, self.email, self.full_name, self.password)
            self.success.emit(data)
        except httpx.HTTPStatusError as e:
            try:
                self.error.emit(e.response.json().get("detail", "Activation failed"))
            except Exception:
                self.error.emit("Activation failed")
        except Exception as e:
            self.error.emit(str(e))


class ActivateKeyWindow(QWidget):
    activation_success = pyqtSignal(dict)
    goto_login = pyqtSignal()

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.setWindowTitle("ProjectX – Activate Master Account")
        self.setFixedSize(420, 560)
        self.is_centered_view = True
        self.setStyleSheet(STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(0)

        title = QLabel("Activate Master Account")
        title.setStyleSheet("font-size:18px;font-weight:700")
        layout.addWidget(title)
        layout.addSpacing(8)
        sub = QLabel("Enter the activation key provided by your system administrator.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#8b949e;font-size:12px")
        layout.addWidget(sub)
        layout.addSpacing(24)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:#f85149;font-size:12px")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        fields = [
            ("Activation Key", "PXKEY-XXXX-XXXX-XXXX", False),
            ("Full Name", "Your Name", False),
            ("Email", "you@company.com", False),
            ("Password", "Choose a strong password", True),
        ]
        self.inputs = []
        for label, placeholder, is_pass in fields:
            lbl = QLabel(label)
            lbl.setStyleSheet("color:#8b949e;font-size:12px;margin-bottom:4px")
            layout.addWidget(lbl)
            layout.addSpacing(4)
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            if is_pass:
                inp.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addWidget(inp)
            layout.addSpacing(12)
            self.inputs.append(inp)

        self.activate_btn = QPushButton("Activate Account")
        self.activate_btn.setFixedHeight(40)
        self.activate_btn.clicked.connect(self._do_activate)
        layout.addWidget(self.activate_btn)
        layout.addSpacing(10)

        back_btn = QPushButton("Back to Sign In")
        back_btn.setObjectName("ghost")
        back_btn.setFixedHeight(36)
        back_btn.clicked.connect(self.goto_login.emit)
        layout.addWidget(back_btn)
        layout.addStretch()

    def _do_activate(self):
        key, name, email, password = [i.text().strip() for i in self.inputs]
        if not all([key, name, email, password]):
            self._show_error("All fields are required.")
            return
        self.activate_btn.setText("Activating…")
        self.activate_btn.setEnabled(False)
        self.error_label.hide()

        self._worker = ActivateWorker(self.api, key, email, name, password)
        self._worker.success.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_success(self, data):
        self.activate_btn.setText("Activate Account")
        self.activate_btn.setEnabled(True)
        self.activation_success.emit(data)

    def _on_error(self, msg):
        self.activate_btn.setText("Activate Account")
        self.activate_btn.setEnabled(True)
        self._show_error(msg)

    def _show_error(self, msg):
        self.error_label.setText(msg)
        self.error_label.show()
