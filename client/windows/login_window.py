from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import httpx

# pyrefly: ignore [missing-import]
from config import APP_VERSION

DEMO_ACCOUNTS = [
    ("System Owner", "#fef3c7", "#92400e", "owner@projectx.io",    "Admin@123"),
    ("Master",       "#ede9fe", "#5b21b6", "master@techcorp.com",  "master123"),
    ("2nd Master",   "#dbeafe", "#1e40af", "second@techcorp.com",  "second123"),
    ("Admin",        "#dcfce7", "#166534", "admin@techcorp.com",   "admin123"),
    ("Trusted",      "#fce7f3", "#9d174d", "trusted@techcorp.com", "trusted123"),
]


class _DemoRow(QFrame):
    def __init__(self, label, bg, fg, email, pw, on_click):
        super().__init__()
        self._cb = on_click
        self._ss_n = "QFrame{background:white;border:1px solid #e2e8f0;border-radius:8px}"
        self._ss_h = "QFrame{background:#f8fafc;border:1px solid #cbd5e1;border-radius:8px}"
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(self._ss_n)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(10)

        badge = QLabel(label)
        badge.setFixedHeight(20)
        badge.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:10px;"
            f"padding:2px 10px;font-size:11px;font-weight:700"
        )
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        em = QLabel(email)
        em.setStyleSheet("color:#475569;font-size:13px;background:transparent")
        em.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        lay.addWidget(badge)
        lay.addWidget(em)
        lay.addStretch()

        self._email = email
        self._pw = pw

    # pyrefly: ignore [bad-override-param-name]
    def enterEvent(self, e):
        self.setStyleSheet(self._ss_h)

    # pyrefly: ignore [bad-override-param-name]
    def leaveEvent(self, e):
        self.setStyleSheet(self._ss_n)

    # pyrefly: ignore [bad-override-param-name]
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._cb(self._email, self._pw)


class _LoginWorker(QThread):
    success = pyqtSignal(dict, dict)
    error = pyqtSignal(str)

    def __init__(self, api, email, password):
        super().__init__()
        self.api = api
        self.email = email
        self.password = password

    def start(self, *args, **kwargs):
        from widgets.common import _active_workers
        _active_workers.add(self)
        super().start(*args, **kwargs)

    def run(self):
        try:
            token_data = self.api.login(self.email, self.password)
            me = self.api.get_me()
            try:
                from services.cache_service import cache_service
                cache_service.set_cache("_offline_auth", {
                    "email": self.email,
                    "password": self.password,
                    "token": token_data["access_token"],
                    "user": me
                })
            except Exception:
                pass
            self.success.emit(token_data, me)
        except httpx.ConnectError:
            try:
                from services.cache_service import cache_service
                data, _ = cache_service.get_cache("_offline_auth")
                if data and "token" in data and "user" in data:
                    if self.email == data.get("email") and self.password == data.get("password"):
                        self.api.token = data["token"]
                        self.api._password = self.password
                        self.api._user = data["user"]
                        self.success.emit({"access_token": data["token"], "requires_2fa": False}, data["user"])
                    else:
                        self.error.emit("Offline: Incorrect email or password.")
                else:
                    self.error.emit("Offline: No cache data available.")
            except Exception as ce:
                self.error.emit(f"Offline: Failed to load cache - {ce}")
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json().get("detail", "Login failed")
                if isinstance(detail, list):
                    detail = detail[0].get("msg", "Validation error")
                self.error.emit(str(detail))
            except Exception:
                self.error.emit("Login failed")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            from widgets.common import _active_workers
            _active_workers.discard(self)


class LoginWindow(QWidget):
    login_success = pyqtSignal(dict, dict)
    goto_activate = pyqtSignal()

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.setStyleSheet("QWidget { font-family: 'Segoe UI'; }")
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left dark branding panel ─────────────────────────────────────
        left = QFrame()
        left.setFixedWidth(370)
        left.setStyleSheet("QFrame { background: #0d1b2a; }")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(40, 44, 40, 36)
        ll.setSpacing(0)

        # Logo row
        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        x_box = QLabel("✕")
        x_box.setFixedSize(36, 36)
        x_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        x_box.setStyleSheet(
            "background:#2563eb;color:white;border-radius:8px;"
            "font-weight:700;font-size:16px"
        )
        logo_lbl = QLabel("ProjectX")
        logo_lbl.setStyleSheet("color:white;font-size:18px;font-weight:700")
        logo_row.addWidget(x_box)
        logo_row.addWidget(logo_lbl)
        logo_row.addStretch()
        ll.addLayout(logo_row)
        ll.addSpacing(52)

        # Headline
        title = QLabel("Secure OT Network\nAccess Platform")
        title.setStyleSheet(
            "color:white;font-size:26px;font-weight:800;background:transparent"
        )
        title.setWordWrap(True)
        ll.addWidget(title)
        ll.addSpacing(16)

        desc = QLabel(
            "Role-based remote access for industrial devices.\n"
            "Powered by ZeroTier with enterprise-grade security."
        )
        desc.setStyleSheet("color:#94a3b8;font-size:13px;background:transparent")
        desc.setWordWrap(True)
        ll.addWidget(desc)
        ll.addSpacing(36)

        # Feature badges
        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        for text in ["5 Roles", "2FA Enforced", "256-bit AES"]:
            b = QLabel(text)
            b.setFixedHeight(28)
            b.setStyleSheet(
                "background:rgba(255,255,255,0.08);color:#cbd5e1;"
                "border:1px solid rgba(255,255,255,0.15);"
                "border-radius:14px;padding:0px 14px;font-size:12px;font-weight:500"
            )
            badges_row.addWidget(b)
        badges_row.addStretch()
        ll.addLayout(badges_row)
        ll.addStretch()

        ver = QLabel(f"ProjectX Platform · v{APP_VERSION}")
        ver.setStyleSheet("color:#475569;font-size:12px;background:transparent")
        ll.addWidget(ver)
        root.addWidget(left)

        # ── Right login panel ────────────────────────────────────────────
        right = QWidget()
        right.setStyleSheet("background:#f1f5f9")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(48, 40, 48, 40)
        rl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # White card
        card = QFrame()
        card.setObjectName("lcard")
        card.setStyleSheet(
            "QFrame#lcard{background:white;border:1px solid #e2e8f0;border-radius:16px}"
        )
        card.setFixedWidth(440)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(40, 36, 40, 36)
        cl.setSpacing(0)

        welcome = QLabel("Welcome back")
        welcome.setStyleSheet(
            "font-size:22px;font-weight:700;color:#0f172a;background:transparent"
        )
        cl.addWidget(welcome)
        cl.addSpacing(5)

        sub = QLabel("Sign in to your account to continue")
        sub.setStyleSheet("font-size:13px;color:#64748b;background:transparent")
        cl.addWidget(sub)
        cl.addSpacing(24)

        # Error bar (hidden until needed)
        self._err = QLabel("")
        self._err.setWordWrap(True)
        self._err.setVisible(False)
        self._err.setStyleSheet(
            "background:#fee2e2;color:#b91c1c;border:1px solid #fecaca;"
            "border-radius:8px;padding:10px 12px;font-size:13px"
        )
        cl.addWidget(self._err)

        # Email field
        em_lbl = QLabel("EMAIL ADDRESS")
        em_lbl.setStyleSheet(
            "font-size:11px;font-weight:700;color:#64748b;"
            "letter-spacing:0.5px;background:transparent"
        )
        cl.addWidget(em_lbl)
        cl.addSpacing(6)
        self._email = QLineEdit()
        self._email.setPlaceholderText("you@company.com")
        self._email.setFixedHeight(44)
        self._email.setStyleSheet(_input_ss())
        cl.addWidget(self._email)
        cl.addSpacing(16)

        # Password field
        pw_lbl = QLabel("PASSWORD")
        pw_lbl.setStyleSheet(
            "font-size:11px;font-weight:700;color:#64748b;"
            "letter-spacing:0.5px;background:transparent"
        )
        cl.addWidget(pw_lbl)
        cl.addSpacing(6)
        self._pw = QLineEdit()
        self._pw.setPlaceholderText("••••••••")
        self._pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw.setFixedHeight(44)
        self._pw.setStyleSheet(_input_ss())
        self._pw.returnPressed.connect(self._do_login)
        cl.addWidget(self._pw)
        cl.addSpacing(22)

        # Sign In button
        self._btn = QPushButton("Sign In")
        self._btn.setFixedHeight(46)
        self._btn.setStyleSheet("""
            QPushButton {
                background:#2563eb;color:white;border:none;
                border-radius:8px;font-size:15px;font-weight:600;
            }
            QPushButton:hover    { background:#1d4ed8; }
            QPushButton:disabled { background:#93c5fd; }
        """)
        self._btn.clicked.connect(self._do_login)
        cl.addWidget(self._btn)
        cl.addSpacing(22)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color:#e2e8f0")
        cl.addWidget(div)
        cl.addSpacing(18)

        # Demo accounts
        demo_hdr = QLabel("DEMO ACCOUNTS — CLICK TO AUTO-FILL")
        demo_hdr.setStyleSheet(
            "font-size:11px;font-weight:600;color:#94a3b8;"
            "letter-spacing:0.5px;background:transparent"
        )
        cl.addWidget(demo_hdr)
        cl.addSpacing(10)

        for label, bg, fg, email, pw in DEMO_ACCOUNTS:
            row = _DemoRow(label, bg, fg, email, pw, self._autofill)
            cl.addWidget(row)
            cl.addSpacing(6)

        cl.addSpacing(8)
        hint = QLabel("All passwords follow the pattern: role + 123")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("font-size:12px;color:#94a3b8;background:transparent")
        cl.addWidget(hint)

        cl.addSpacing(16)
        act_btn = QPushButton("Activate Master Account with Key →")
        act_btn.setStyleSheet("""
            QPushButton {
                background:transparent;border:none;
                color:#2563eb;font-size:13px;
            }
            QPushButton:hover { color:#1d4ed8; }
        """)
        act_btn.clicked.connect(self.goto_activate.emit)
        cl.addWidget(act_btn)

        rl.addStretch()
        rl.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        rl.addStretch()
        root.addWidget(right, 1)

    # ── slots ──────────────────────────────────────────────────────────────
    def _autofill(self, email: str, pw: str):
        self._email.setText(email)
        self._pw.setText(pw)
        self._email.setFocus()

    def _do_login(self):
        email = self._email.text().strip()
        pw    = self._pw.text()
        if not email or not pw:
            self._show_err("Please enter email and password.")
            return
        self._btn.setText("Signing in…")
        self._btn.setEnabled(False)
        self._err.setVisible(False)
        self._worker = _LoginWorker(self.api, email, pw)
        self._worker.success.connect(self._on_success)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_success(self, token_data: dict, me: dict):
        self._btn.setText("Sign In")
        self._btn.setEnabled(True)
        self.login_success.emit(token_data, me)

    def _on_error(self, msg: str):
        self._btn.setText("Sign In")
        self._btn.setEnabled(True)
        self._show_err(msg)

    def _show_err(self, msg: str):
        self._err.setText(msg)
        self._err.setVisible(True)


def _input_ss() -> str:
    return """
        QLineEdit {
            background:#f8fafc;border:1.5px solid #e2e8f0;
            border-radius:8px;padding:10px 14px;
            color:#0f172a;font-size:14px;
        }
        QLineEdit:focus { border-color:#2563eb; }
    """
