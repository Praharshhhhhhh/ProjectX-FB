from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
import httpx

STYLE = """
QWidget { background: #0d1117; color: #e6edf3; font-family: 'Segoe UI'; }
QLineEdit { background:#21262d; border:1px solid #30363d; border-radius:6px; padding:9px 12px; color:#e6edf3; font-size:14px; text-align: center; }
QLineEdit:focus { border-color:#2f81f7; }
QPushButton { background:#2f81f7; color:white; border:none; border-radius:6px; padding:9px 20px; font-weight:600; font-size:13px; }
QPushButton:hover { background:#388bfd; }
QPushButton:disabled { background:#21262d; color:#8b949e; }
QPushButton#ghost { background:transparent; border:1px solid #30363d; color:#8b949e; }
QPushButton#ghost:hover { background:rgba(255,255,255,0.05); color:#e6edf3; }
QLabel { background:transparent; }
"""


class VerifyOtpWorker(QThread):
    success = pyqtSignal(dict, dict)
    error = pyqtSignal(str)

    def __init__(self, api, email, code):
        super().__init__()
        self.api = api
        self.email = email
        self.code = code

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
            token_data = self.api.verify_otp(self.email, self.code)
            me = self.api.get_me()
            
            # Cache the successful login credentials offline
            try:
                from services.cache_service import cache_service
                cache_service.set_cache("_offline_auth", {
                    "email": self.email,
                    "password": self.api._password,
                    "token": token_data["access_token"],
                    "user": me
                })
            except Exception:
                pass
                
            self.success.emit(token_data, me)
        except httpx.HTTPStatusError as e:
            try:
                self.error.emit(e.response.json().get("detail", "Verification failed"))
            except Exception:
                self.error.emit("Verification failed")
        except Exception as e:
            self.error.emit(str(e))


class VerifyOtpWindow(QWidget):
    otp_verified = pyqtSignal(dict, dict)
    goto_login = pyqtSignal()

    def __init__(self, api, email):
        super().__init__()
        self.api = api
        self.email = email
        self.cooldown_sec = 60
        self.setFixedSize(420, 500)
        self.is_centered_view = True
        self.setStyleSheet(STYLE)
        self._build_ui()
        self._start_cooldown()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(0)

        title = QLabel("Verify Verification Code")
        title.setStyleSheet("font-size:18px;font-weight:700")
        layout.addWidget(title)
        layout.addSpacing(8)

        info = QLabel(f"We've sent a 6-digit one-time code to:\n{self.email}")
        info.setWordWrap(True)
        info.setStyleSheet("color:#8b949e;font-size:13px;line-height:1.4")
        layout.addWidget(info)
        layout.addSpacing(28)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:#f85149;font-size:12px")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        code_lbl = QLabel("Enter 6-digit code")
        code_lbl.setStyleSheet("color:#8b949e;font-size:12px;margin-bottom:4px")
        layout.addWidget(code_lbl)
        layout.addSpacing(6)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("000000")
        self.code_input.setMaxLength(6)
        self.code_input.setFixedHeight(45)
        self.code_input.setStyleSheet("font-size: 18px; font-weight: 700; letter-spacing: 4px;")
        self.code_input.returnPressed.connect(self._verify)
        layout.addWidget(self.code_input)
        layout.addSpacing(20)

        self.verify_btn = QPushButton("Verify Code")
        self.verify_btn.setFixedHeight(40)
        self.verify_btn.clicked.connect(self._verify)
        layout.addWidget(self.verify_btn)
        layout.addSpacing(12)

        self.resend_btn = QPushButton("Resend Code")
        self.resend_btn.setObjectName("ghost")
        self.resend_btn.setFixedHeight(36)
        self.resend_btn.clicked.connect(self._resend)
        layout.addWidget(self.resend_btn)
        layout.addSpacing(10)

        back_btn = QPushButton("Back to Login")
        back_btn.setObjectName("ghost")
        back_btn.setFixedHeight(36)
        back_btn.clicked.connect(self.goto_login.emit)
        layout.addWidget(back_btn)
        layout.addStretch()

    def _start_cooldown(self):
        self.resend_btn.setEnabled(False)
        self.cooldown_timer = QTimer(self)
        self.cooldown_timer.timeout.connect(self._update_cooldown)
        self.cooldown_timer.start(1000)
        self._update_cooldown_text()

    def _update_cooldown(self):
        self.cooldown_sec -= 1
        if self.cooldown_sec <= 0:
            self.cooldown_timer.stop()
            self.resend_btn.setEnabled(True)
            self.resend_btn.setText("Resend Code")
        else:
            self._update_cooldown_text()

    def _update_cooldown_text(self):
        self.resend_btn.setText(f"Resend Code ({self.cooldown_sec}s)")

    def _resend(self):
        self.resend_btn.setEnabled(False)
        self.error_label.hide()
        try:
            self.api.resend_otp(self.email)
            self.cooldown_sec = 60
            self._start_cooldown()
        except Exception as e:
            self.error_label.setText(f"Failed to resend code: {e}")
            self.error_label.show()
            self.resend_btn.setEnabled(True)

    def _verify(self):
        code = self.code_input.text().strip()
        if len(code) != 6 or not code.isdigit():
            self.error_label.setText("Enter a valid 6-digit numeric code.")
            self.error_label.show()
            return

        self.verify_btn.setText("Verifying…")
        self.verify_btn.setEnabled(False)
        self.error_label.hide()

        self._worker = VerifyOtpWorker(self.api, self.email, code)
        self._worker.success.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_success(self, token_data, me_data):
        self.verify_btn.setText("Verify Code")
        self.verify_btn.setEnabled(True)
        self.otp_verified.emit(token_data, me_data)

    def _on_error(self, msg):
        self.verify_btn.setText("Verify Code")
        self.verify_btn.setEnabled(True)
        self.error_label.setText(msg)
        self.error_label.show()
