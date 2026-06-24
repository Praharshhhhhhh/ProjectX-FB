from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget
from PyQt6.QtCore import pyqtSignal
import httpx

STYLE = """
QWidget { background:#0d1117; color:#e6edf3; font-family:'Segoe UI'; }
QLineEdit { background:#21262d; border:1px solid #30363d; border-radius:6px; padding:9px 12px; color:#e6edf3; font-size:13px; }
QLineEdit:focus { border-color:#2f81f7; }
QPushButton { background:#2f81f7; color:white; border:none; border-radius:6px; padding:9px 20px; font-weight:600; font-size:13px; }
QPushButton:hover { background:#388bfd; }
QPushButton:disabled { background:#21262d; color:#8b949e; }
QLabel { background:transparent; }
QTabWidget::pane { border: 1px solid #30363d; border-radius: 6px; background: #0d1117; }
QTabBar::tab { background: #21262d; color: #8b949e; padding: 8px 16px; border: 1px solid #30363d; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background: #0d1117; color: #e6edf3; font-weight: bold; }
"""

class ClaimNetworkWindow(QWidget):
    claim_success = pyqtSignal()

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.setFixedSize(480, 650)
        self.is_centered_view = True
        self.setStyleSheet(STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Claim Network Server")
        title.setStyleSheet("font-size:20px;font-weight:700")
        layout.addWidget(title)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:#f85149;font-size:13px;font-weight:bold;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_zt_tab(), "ZeroTier")
        layout.addWidget(self.tabs)

    def _build_zt_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        
        sub = QLabel("Enter the 16-character ZeroTier Network ID included with your device package.")
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#8b949e;font-size:13px")
        layout.addWidget(sub)
        layout.addSpacing(16)

        net_lbl = QLabel("ZeroTier Network ID")
        net_lbl.setStyleSheet("color:#8b949e;font-size:12px;margin-bottom:4px")
        layout.addWidget(net_lbl)

        self.network_input = QLineEdit()
        self.network_input.setPlaceholderText("e.g. dd2e3f2349cf7751")
        self.network_input.setMaxLength(16)
        self.network_input.returnPressed.connect(self._do_zt_claim)
        layout.addWidget(self.network_input)

        hint = QLabel("16-character alphanumeric ID on the device package label.")
        hint.setStyleSheet("color:#8b949e;font-size:11px")
        layout.addWidget(hint)
        layout.addSpacing(20)

        self.zt_claim_btn = QPushButton("Claim ZeroTier Network")
        self.zt_claim_btn.setFixedHeight(40)
        self.zt_claim_btn.clicked.connect(self._do_zt_claim)
        layout.addWidget(self.zt_claim_btn)
        layout.addStretch()
        return w


    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()

    def _do_zt_claim(self):
        network_id = self.network_input.text().strip()
        if len(network_id) != 16:
            self._show_error("Network ID must be exactly 16 characters.")
            return
        self.zt_claim_btn.setText("Claiming…")
        self.zt_claim_btn.setEnabled(False)
        self.error_label.hide()
        try:
            self.api.claim_network(network_id)
            self.claim_success.emit()
        except httpx.HTTPStatusError as e:
            try:
                msg = e.response.json().get("detail", "Failed")
            except Exception:
                msg = "Failed to claim network"
            self._show_error(msg)
        except Exception as e:
            self._show_error(str(e))
        finally:
            self.zt_claim_btn.setText("Claim ZeroTier Network")
            self.zt_claim_btn.setEnabled(True)

