from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QPixmap, QImage
import base64, httpx


STYLE = """
QWidget { background: #0d1117; color: #e6edf3; font-family: 'Segoe UI'; }
QLineEdit { background:#21262d; border:1px solid #30363d; border-radius:6px; padding:9px 12px; color:#e6edf3; font-size:13px; }
QLineEdit:focus { border-color:#2f81f7; }
QPushButton { background:#2f81f7; color:white; border:none; border-radius:6px; padding:9px 20px; font-weight:600; font-size:13px; }
QPushButton:hover { background:#388bfd; }
QPushButton:disabled { background:#21262d; color:#8b949e; }
QLabel { background:transparent; }
"""


class Setup2FAWorker(QThread):
    got_qr = pyqtSignal(str, str)
    error = pyqtSignal(str)

    def __init__(self, api):
        super().__init__()
        self.api = api

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
            data = self.api.setup_2fa()
            self.got_qr.emit(data["qr_code"], data["secret"])
        except httpx.HTTPStatusError as e:
            try:
                self.error.emit(e.response.json().get("detail", "Error"))
            except Exception:
                self.error.emit("Error loading 2FA")
        except Exception as e:
            self.error.emit(str(e))


class Setup2FAWindow(QWidget):
    setup_complete = pyqtSignal()

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.setFixedSize(460, 560)
        self.is_centered_view = True
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._load_qr()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(0)

        title = QLabel("Set Up Two-Factor Authentication")
        title.setWordWrap(True)
        title.setStyleSheet("font-size:17px;font-weight:700")
        layout.addWidget(title)
        layout.addSpacing(8)

        sub = QLabel("Scan the QR code with Google Authenticator or Authy. 2FA is mandatory for Master accounts.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#8b949e;font-size:12px")
        layout.addWidget(sub)
        layout.addSpacing(24)

        self.qr_label = QLabel("Loading QR code…")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedHeight(220)
        self.qr_label.setStyleSheet("background:#1c2128;border:1px solid #30363d;border-radius:8px")
        layout.addWidget(self.qr_label)
        layout.addSpacing(10)

        self.secret_label = QLabel("")
        self.secret_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.secret_label.setStyleSheet("color:#8b949e;font-size:11px")
        layout.addWidget(self.secret_label)
        layout.addSpacing(20)

        code_lbl = QLabel("Enter 6-digit code from your authenticator")
        code_lbl.setStyleSheet("color:#8b949e;font-size:12px")
        layout.addWidget(code_lbl)
        layout.addSpacing(6)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("123456")
        self.code_input.setMaxLength(6)
        self.code_input.returnPressed.connect(self._verify)
        layout.addWidget(self.code_input)
        layout.addSpacing(16)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:#f85149;font-size:12px")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.verify_btn = QPushButton("Verify & Enable 2FA")
        self.verify_btn.setFixedHeight(40)
        self.verify_btn.clicked.connect(self._verify)
        layout.addWidget(self.verify_btn)
        layout.addStretch()

    def _load_qr(self):
        self._worker = Setup2FAWorker(self.api)
        self._worker.got_qr.connect(self._show_qr)
        self._worker.error.connect(lambda e: self.qr_label.setText(f"Error: {e}"))
        self._worker.start()

    def _show_qr(self, qr_b64: str, secret: str):
        img_data = base64.b64decode(qr_b64)
        img = QImage.fromData(img_data)
        pix = QPixmap.fromImage(img).scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.qr_label.setPixmap(pix)
        self.secret_label.setText(f"Manual entry: {secret}")

    def _verify(self):
        code = self.code_input.text().strip()
        if len(code) != 6:
            self.error_label.setText("Enter a 6-digit code.")
            self.error_label.show()
            return
        self.verify_btn.setText("Verifying…")
        self.verify_btn.setEnabled(False)
        self.error_label.hide()
        try:
            self.api.verify_2fa(code)
            self.setup_complete.emit()
        except Exception as e:
            self.error_label.setText(str(e))
            self.error_label.show()
            self.verify_btn.setText("Verify & Enable 2FA")
            self.verify_btn.setEnabled(True)
