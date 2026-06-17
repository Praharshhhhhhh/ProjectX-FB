from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QStackedWidget, QScrollArea, QTableWidget, QTableWidgetItem,
    QDialog, QLineEdit, QComboBox, QMessageBox, QSizePolicy, QHeaderView,
    QAbstractItemView, QCheckBox, QApplication, QStyle
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QUrl
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush, QPen, QDesktopServices

try:
    # pyrefly: ignore [missing-import]
    from client.styles import APP_STYLE, SIDEBAR_W, LEVEL_COLORS
except ImportError:
    # pyrefly: ignore [missing-import]
    from styles import APP_STYLE, SIDEBAR_W, LEVEL_COLORS
# pyrefly: ignore [missing-import]
from config import TUNNEL_MODE
if TUNNEL_MODE == "wireguard":
    # pyrefly: ignore [missing-import]
    from services.wireguard_local import is_wireguard_running as is_tunnel_running
else:
    # pyrefly: ignore [missing-import]
    from services.zerotier_local import is_zerotier_running as is_tunnel_running
# pyrefly: ignore [missing-import]
from services.network_monitor import NetworkMonitor
# pyrefly: ignore [missing-import]
from widgets.common import (
    Worker, StatCard, Badge, Card, CardWithHeader, make_table,
    table_item, PageHeader, AlertBar, asset_path, load_icon
)
# pyrefly: ignore [missing-import]
from windows.owner_window import _lbl, _fmt_date

ICON_MONITOR = "monitor.svg"
ICON_USERS = "users.svg"
TITLE_ADD_USER = "Add User"


# ═══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD PAGE
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardPage(QWidget):
    add_user_requested = pyqtSignal()
    manage_devices_requested = pyqtSignal()
    manage_users_requested = pyqtSignal()
    view_logs_requested = pyqtSignal()

    def __init__(self, api, user: dict):
        super().__init__()
        self.api = api
        self.user = user
        self._build()
        # pyrefly: ignore [missing-import]
        from services.websocket_client import ws_client
        ws_client.alert_received.connect(self._show_ws_alert)

    def _show_ws_alert(self, message: str):
        if hasattr(self, "_alert"):
            self._alert.show_error(message)

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)

        self._alert = AlertBar()
        lay.addWidget(self._alert)

        role = self.user.get("role", "")
        is_master = role in ("master", "second_master")
        tenant = self.user.get("company") or ""
        network = self.user.get("network_id") or ""
        subtitle = f"{tenant}  ·  Network: {network}" if network else tenant

        hdr_row = QHBoxLayout()
        hdr = PageHeader("Master Dashboard", subtitle)
        hdr_row.addWidget(hdr, 1)
        if is_master:
            add_btn = QPushButton("+ Add User")
            add_btn.setObjectName("btn-primary")
            add_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600}")
            add_btn.setFixedHeight(38)
            add_btn.clicked.connect(self.add_user_requested.emit)
            hdr_row.addWidget(add_btn)
        lay.addLayout(hdr_row)

        stats_row = QHBoxLayout(); stats_row.setSpacing(16)
        self._s_online  = StatCard("Online Devices",    "—", color="#16a34a", icon_path=asset_path(ICON_MONITOR))
        self._s_pending = StatCard("Pending Approval",  "—", color="#ea580c", icon_path=asset_path("clock.svg"))
        self._s_users   = StatCard("Total Users",       "—", color="#2563eb", icon_path=asset_path(ICON_USERS))
        self._s_offline = StatCard("Offline Devices",   "—", color="#dc2626", icon_path=asset_path("wifi-off.svg"))
        
        cards_to_add = [self._s_online]
        if is_master:
            cards_to_add.extend([self._s_pending, self._s_users])
        cards_to_add.append(self._s_offline)
        
        for c in cards_to_add:
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            stats_row.addWidget(c)
        lay.addLayout(stats_row)

        # Devices
        self._dev_card = CardWithHeader("Active Devices", "Manage All")
        if self._dev_card.action_btn:
            self._dev_card.action_btn.clicked.connect(self.manage_devices_requested.emit)
        self._dev_list = QWidget(); self._dev_list.setStyleSheet("background:white")
        self._dev_vlay = QVBoxLayout(self._dev_list)
        self._dev_vlay.setContentsMargins(0, 0, 0, 0)
        self._dev_vlay.setSpacing(0)
        self._dev_vlay.addStretch()
        self._dev_card.add_widget(self._dev_list)
        lay.addWidget(self._dev_card)

        bottom = QHBoxLayout(); bottom.setSpacing(16)

        # Users
        self._users_card = CardWithHeader("Users", "Manage All")
        if self._users_card.action_btn:
            self._users_card.action_btn.clicked.connect(self.manage_users_requested.emit)
        self._users_list = QWidget(); self._users_list.setStyleSheet("background:white")
        self._users_vlay = QVBoxLayout(self._users_list)
        self._users_vlay.setContentsMargins(0, 0, 0, 0)
        self._users_vlay.setSpacing(0)
        self._users_vlay.addStretch()
        self._users_card.add_widget(self._users_list)
        if is_master:
            bottom.addWidget(self._users_card, alignment=Qt.AlignmentFlag.AlignTop)

        # Activity
        self._act_card = CardWithHeader("Activity Log", "Full Log")
        if self._act_card.action_btn:
            self._act_card.action_btn.clicked.connect(self.view_logs_requested.emit)
        self._act_list = QWidget(); self._act_list.setStyleSheet("background:white")
        self._act_vlay = QVBoxLayout(self._act_list)
        self._act_vlay.setContentsMargins(0, 0, 0, 0)
        self._act_vlay.setSpacing(0)
        self._act_vlay.addStretch()
        self._act_card.add_widget(self._act_list)
        bottom.addWidget(self._act_card, alignment=Qt.AlignmentFlag.AlignTop)

        lay.addLayout(bottom)
        lay.addStretch()

        scroll.setWidget(inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    def refresh(self):
        role = self.user.get("role", "")
        is_master = role in ("master", "second_master")
        self._w = Worker(lambda: (
            self.api.get_devices(),
            self.api.get_pending_devices() if is_master else [],
            self.api.get_users() if is_master else [],
            self.api.get_audit_logs(),
        ))
        self._w.result.connect(self._on_data)
        self._w.error.connect(lambda e: print("Dashboard error:", e))
        self._w.start()

    def _on_data(self, data):
        devices, pending, users, logs = data
        active = [d for d in devices if d.get("is_approved") and d.get("status") == "active"]
        offline = [d for d in devices if d.get("is_approved") and d.get("status") == "offline"]
        self._s_online.set_value(len(active))
        self._s_pending.set_value(len(pending))
        self._s_users.set_value(len(users))
        self._s_offline.set_value(len(offline))

        self._fill_list(self._dev_vlay, [
            {"main": d.get("name", ""), "sub": f"LAN: {d.get('lan_ip','—')} · {d.get('connection_info', {}).get('tunnel_type', 'zerotier')[:2].upper()}: {d.get('connection_info', {}).get('virtual_ip', '—')}",
             "dot": d.get("status", "offline")} for d in devices[:5]
        ], dot=True)

        if users:
            self._fill_list(self._users_vlay, [
                {"main": u.get("full_name", ""), "badge": u.get("role", ""), "badge_type": "role"}
                for u in users[:5]
            ])

        self._fill_list(self._act_vlay, [
            {"main": l.get("description", ""),
             "sub": f"By {l.get('user_name','System')} · {_fmt_date(l.get('created_at',''))}",
             "level": l.get("level","info")}
            for l in logs[:6]
        ], level=True)

    def _fill_list(self, vlay, items, dot=False, level=False):
        while vlay.count() > 1:
            item = vlay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not items:
            empty = QLabel("No data yet")
            empty.setStyleSheet("color:#64748b;padding:20px;background:transparent")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vlay.insertWidget(0, empty)
            return
        for item in items:
            row_w = QWidget()
            row_w.setStyleSheet("border-bottom:1px solid #f1f5f9")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(16, 12, 16, 12)
            rl.setSpacing(10)

            if dot:
                d = QLabel("●")
                dot_c = {"active": "#16a34a", "offline": "#dc2626", "connecting": "#d97706"}
                d.setStyleSheet(f"color:{dot_c.get(item.get('dot','offline'),'#64748b')};font-size:10px;background:transparent")
                rl.addWidget(d)

            text_c = QVBoxLayout(); text_c.setSpacing(2)
            main_lbl = QLabel(item.get("main", ""))
            main_lbl.setStyleSheet("font-size:13px;color:#0f172a;font-weight:600;background:transparent")
            text_c.addWidget(main_lbl)
            if item.get("sub"):
                sub_lbl = QLabel(item["sub"])
                sub_lbl.setStyleSheet("font-size:11px;color:#64748b;background:transparent")
                text_c.addWidget(sub_lbl)
            rl.addLayout(text_c)
            rl.addStretch()

            if item.get("badge"):
                role = item["badge"]
                # pyrefly: ignore [missing-import]
                from styles import ROLE_COLORS
                bg, fg = ROLE_COLORS.get(role, ("#f1f5f9", "#64748b"))
                b = QLabel(role.replace("_"," ").title())
                b.setStyleSheet(f"background:{bg};color:{fg};padding:3px 9px;border-radius:12px;font-size:11px;font-weight:600")
                rl.addWidget(b)

            if level and item.get("level"):
                lvl = item["level"]
                bg, fg = LEVEL_COLORS.get(lvl, ("#dbeafe", "#1d4ed8"))
                b = QLabel(lvl.title())
                b.setStyleSheet(f"background:{bg};color:{fg};padding:3px 9px;border-radius:12px;font-size:11px;font-weight:600")
                rl.addWidget(b)

            vlay.insertWidget(vlay.count() - 1, row_w)


# ═══════════════════════════════════════════════════════════════════════════════
#  DEVICES PAGE
# ═══════════════════════════════════════════════════════════════════════════════
class DevicesPage(QWidget):
    def __init__(self, api, user: dict):
        super().__init__()
        self.api = api
        self.user = user
        self._build()
        # pyrefly: ignore [missing-import]
        from services.websocket_client import ws_client
        ws_client.device_updated.connect(self._safe_refresh)
        ws_client.device_removed.connect(self._safe_refresh)
        ws_client.sync_toggle_received.connect(self._on_sync_toggle)
        ws_client.lan_device_renamed.connect(self._on_lan_device_renamed)

    def _safe_refresh(self, *args):
        try:
            self.refresh()
        except RuntimeError:
            pass


    def _on_sync_toggle(self, device_id: int, network_id: str, connect: bool):
        # We need to find the DeviceCard for this device_id
        if not hasattr(self, "_dev_layout"):
            return
        for i in range(self._dev_layout.count()):
            item = self._dev_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                # pyrefly: ignore [missing-attribute]
                if hasattr(w, "device") and w.device.get("id") == device_id:
                    # Sync the toggle visually and locally connect
                    if w.toggle_sw.isChecked() != connect:
                        w.toggle_sw.setChecked(connect)
                        
                        from services.tunnel_manager import TunnelManager
                        is_local = TunnelManager.is_local_device(w.device)
                        
                        if is_local:
                            w._on_toggle(connect, is_sync=True)
                        else:
                            w._update_status("connecting" if connect else "disconnected")
                    break

    def _on_lan_device_renamed(self, device_id: int, lan_device_id: int, new_name: str):
        if not hasattr(self, "_dev_layout"):
            return
        for i in range(self._dev_layout.count()):
            item = self._dev_layout.itemAt(i)
            if item and item.widget():
                w = item.widget()
                if hasattr(w, "device") and w.device.get("id") == device_id:
                    for lan in w.device.get("lan_devices", []):
                        if lan.get("id") == lan_device_id:
                            lan["name"] = new_name
                            # pyrefly: ignore [missing-attribute]
                            w._rebuild_expanded_panel()
                            break
                    break

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)

        self._alert = AlertBar()
        lay.addWidget(self._alert)
        tun_name = "WireGuard" if TUNNEL_MODE == "wireguard" else "ZeroTier"
        lay.addWidget(PageHeader("Devices", f"All devices on your {tun_name} network"))

        role = self.user.get("role", "")
        is_master = role in ("master", "second_master")

        stats_row = QHBoxLayout(); stats_row.setSpacing(16)
        self._s_online  = StatCard("Online",     "—", color="#16a34a", icon_path=asset_path(ICON_MONITOR))
        self._s_conn    = StatCard("Connecting", "—", color="#d97706", icon_path=asset_path("refresh.svg"))
        self._s_offline = StatCard("Offline",    "—", color="#dc2626", icon_path=asset_path("wifi-off.svg"))
        self._s_waiting = StatCard("Waiting",    "—", color="#2563eb", icon_path=asset_path("clock.svg"))
        
        cards_to_add = [self._s_online, self._s_conn, self._s_offline]
        if is_master:
            cards_to_add.append(self._s_waiting)
            
        for c in cards_to_add:
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            stats_row.addWidget(c)
        lay.addLayout(stats_row)

        # Auto-reconnect banner
        banner = QLabel("↻  Auto-reconnect enabled — connections restore automatically if your network changes")
        banner.setStyleSheet("background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:8px;padding:10px 14px;font-size:13px")
        lay.addWidget(banner)
        
        if is_master:
            mode_lay = QHBoxLayout()
            mode_lay.addWidget(QLabel("<b>Network Routing Mode:</b>"))
            self.mode_combo = QComboBox()
            self.mode_combo.addItems(["Layer 3 (Routed - Default)", "Layer 2 (Bridged - Broadcasts)"])
            self.mode_combo.setStyleSheet("QComboBox{background:white;border:1px solid #cbd5e1;border-radius:6px;padding:4px;font-size:13px;}")
            self.mode_combo.currentIndexChanged.connect(self._change_network_mode)
            mode_lay.addWidget(self.mode_combo)
            mode_lay.addStretch()
            lay.addLayout(mode_lay)

        self.card = CardWithHeader("Active Devices")
        if is_master:
            headers = ["Device Name", "LAN IP", "Tunnel IP", "Network", "Status", "Actions"]
            self._tbl = make_table(headers)
            self._tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            hh = self._tbl.horizontalHeader()
            for col in range(6):
                hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self._tbl.setColumnWidth(0, 170)
            self._tbl.setColumnWidth(1, 130)
            self._tbl.setColumnWidth(2, 200)
            self._tbl.setColumnWidth(3, 160)
            self._tbl.setColumnWidth(4, 90)
            self._tbl.setColumnWidth(5, 300)
            self.card.add_widget(self._tbl)
        else:
            self._dev_scroll = QScrollArea()
            self._dev_scroll.setWidgetResizable(True)
            self._dev_scroll.setFrameShape(QFrame.Shape.NoFrame)
            self._dev_scroll.setMinimumHeight(200)
            self._dev_scroll.setStyleSheet("background:transparent;border:none")
            self._dev_container = QWidget()
            self._dev_container.setStyleSheet("background:transparent")
            self._dev_layout = QVBoxLayout(self._dev_container)
            self._dev_layout.setContentsMargins(16, 12, 16, 12)
            self._dev_layout.setSpacing(10)
            self._dev_layout.addStretch()
            self._dev_scroll.setWidget(self._dev_container)
            self.card.add_widget(self._dev_scroll)
        lay.addWidget(self.card)
        lay.addStretch()

    def _change_network_mode(self, index: int):
        is_layer2 = (index == 1)
        devices = getattr(self, "_devices", [])
        for d in devices:
            if d.get("network_id") and not d.get("is_shared"):
                self._nw = Worker(self.api.change_network_mode, d["id"], is_layer2)
                self._nw.result.connect(lambda _: None)
                self._nw.error.connect(lambda e: print("Mode change failed:", e))
                self._nw.start()
                break

    def refresh(self):
        if hasattr(self, "_w") and self._w.isRunning():
            return  # Wait for current refresh to finish
        
        role = self.user.get("role", "")
        is_master = role in ("master", "second_master")
        self._w = Worker(lambda: (
            self.api.get_devices(),
            self.api.get_pending_devices() if is_master else []
        ))
        self._w.result.connect(self._on_data)
        self._w.error.connect(self._alert.show_error)
        self._w.start()

    def _on_data(self, data):
        devices, pending = data
        self._devices = devices
        self._s_online.set_value(len([d for d in devices if d.get("status") == "active"]))
        self._s_conn.set_value(len([d for d in devices if d.get("status") == "connecting"]))
        self._s_offline.set_value(len([d for d in devices if d.get("status") == "offline"]))
        role = self.user.get("role", "")
        is_master = role in ("master", "second_master")
        if is_master:
            self._s_waiting.set_value(len(pending))

        all_devs = [{"_pending": True, **p} for p in pending] + [d for d in devices if d.get("is_approved")]

        if is_master:
            t = self._tbl
            t.setUpdatesEnabled(False)
            t.setRowCount(0)
            for dev in all_devs:
                r = t.rowCount(); t.insertRow(r)
                name = dev.get("name", dev.get("zerotier_node_id", "Unknown"))
                if dev.get("_pending"):
                    # pyrefly: ignore [unsupported-operation]
                    name += "  [Pending]"
                
                name_w = QWidget()
                name_l = QHBoxLayout(name_w)
                name_l.setContentsMargins(0, 0, 0, 0)
                name_l.setSpacing(6)
                name_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
                name_lbl = QLabel(name)
                name_lbl.setStyleSheet("background:transparent; border:none;")
                name_l.addWidget(name_lbl)
                
                if dev.get("has_conflict"):
                    conflict_lbl = QLabel("Overmapping Conflict")
                    conflict_lbl.setStyleSheet("background:#fee2e2;color:#ef4444;padding:2px 4px;border-radius:4px;font-size:10px;font-weight:bold;")
                    name_l.addWidget(conflict_lbl)
                t.setCellWidget(r, 0, name_w)
                
                lan_ip_val = dev.get("lan_ip") or "—"
                if lan_ip_val != "—":
                    # pyrefly: ignore [no-matching-overload]
                    ip_btn = QPushButton(lan_ip_val)
                    ip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    ip_btn.setStyleSheet("""
                        QPushButton { background: transparent; color: #2563eb; border: none; font-size: 13px; text-align: left; padding-left: 2px; }
                        QPushButton:hover { color: #1d4ed8; text-decoration: underline; }
                    """)
                    ip_btn.clicked.connect(lambda _, a=lan_ip_val: QDesktopServices.openUrl(QUrl(f"http://{a}")))
                    ip_container = QWidget()
                    ip_lay = QHBoxLayout(ip_container)
                    ip_lay.setContentsMargins(0, 0, 0, 0)
                    ip_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    ip_lay.addWidget(ip_btn)
                    t.setCellWidget(r, 1, ip_container)
                else:
                    t.setItem(r, 1, table_item("—", Qt.AlignmentFlag.AlignCenter))

                conn_info = dev.get("connection_info", {})
                ttype = conn_info.get("tunnel_type", "zerotier")
                tun_ip = conn_info.get("virtual_ip") or "—"
                badge = "WG" if ttype == "wireguard" else "ZT"
                t.setItem(r, 2, table_item(f"[{badge}] {tun_ip}", Qt.AlignmentFlag.AlignCenter))
                
                t.setItem(r, 3, table_item(dev.get("network_id") or "—", Qt.AlignmentFlag.AlignCenter))
                status = "pending" if dev.get("_pending") else dev.get("status", "offline")
                # pyrefly: ignore [missing-attribute]
                t.setItem(r, 4, table_item(status.title(), Qt.AlignmentFlag.AlignCenter))

                btn_w = QWidget()
                btn_l = QHBoxLayout(btn_w)
                btn_l.setContentsMargins(4, 4, 4, 4)
                btn_l.setSpacing(4)
                if dev.get("_pending"):
                    appr = QPushButton("Approve")
                    appr.setObjectName("btn-sm")
                    appr.setStyleSheet("QPushButton{background:#dcfce7;color:#15803d;border:1px solid #bbf7d0;border-radius:6px;padding:5px 12px;font-size:13px} QPushButton:hover{background:#bbf7d0}")
                    appr.setFixedSize(75, 28)
                    appr.clicked.connect(lambda _, did=dev["id"]: self._approve(did))
                    btn_l.addWidget(appr)
                    
                    rej = QPushButton("Reject")
                    rej.setObjectName("btn-danger")
                    rej.setStyleSheet("QPushButton{background:#fee2e2;color:#ef4444;border:1px solid #fecaca;border-radius:6px;padding:5px 12px;font-size:13px} QPushButton:hover{background:#fecaca}")
                    rej.setFixedSize(75, 28)
                    rej.clicked.connect(lambda _, did=dev["id"]: self._remove(did))
                    btn_l.addWidget(rej)
                else:
                    if not dev.get("is_shared"):
                        share_btn = QPushButton("Share")
                        share_btn.setObjectName("btn-sm")
                        share_btn.setStyleSheet("QPushButton{background:#dbeafe;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:6px;padding:5px 12px;font-size:13px} QPushButton:hover{background:#bfdbfe}")
                        share_btn.setFixedSize(65, 30)
                        share_btn.clicked.connect(lambda _, did=dev["id"], nm=dev.get("name", ""): self._open_share_dialog(did, nm))
                        btn_l.addWidget(share_btn)

                        shares_btn = QPushButton("Shares")
                        shares_btn.setObjectName("btn-sm")
                        shares_btn.setStyleSheet("QPushButton{background:#f3f4f6;color:#374151;border:1px solid #e5e7eb;border-radius:6px;padding:5px 12px;font-size:13px} QPushButton:hover{background:#e5e7eb}")
                        shares_btn.setFixedSize(70, 30)
                        shares_btn.clicked.connect(lambda _, did=dev["id"], nm=dev.get("name", ""): self._open_shares_view(did, nm))
                        btn_l.addWidget(shares_btn)
                    
                    dl_btn = QPushButton("↓")
                    dl_btn.setObjectName("btn-sm")
                    dl_btn.setStyleSheet("QPushButton{background:#f1f5f9;color:#0f172a;border:1px solid #cbd5e1;border-radius:6px;padding:5px 8px;font-size:14px;font-weight:bold;} QPushButton:hover{background:#e2e8f0}")
                    dl_btn.setFixedSize(30, 30)
                    dl_btn.setToolTip("Download .conf")
                    dl_btn.clicked.connect(lambda _, did=dev["id"], nm=dev.get("name", "wg_client"): self._download_conf(did, nm))
                    btn_l.addWidget(dl_btn)
                    
                    rem = QPushButton("Remove")
                    rem.setObjectName("btn-danger")
                    rem.setFixedSize(75, 30)
                    rem.clicked.connect(lambda _, did=dev["id"]: self._remove(did))
                    btn_l.addWidget(rem)
                t.setCellWidget(r, 5, btn_w)
            t.setUpdatesEnabled(True)
        else:
            existing_cards = {}
            for i in range(self._dev_layout.count()):
                item = self._dev_layout.itemAt(i)
                if item and item.widget():
                    w = item.widget()
                    # pyrefly: ignore [missing-attribute]
                    if hasattr(w, "device"):
                        existing_cards[w.device["id"]] = w
            
            approved_devs = [d for d in devices if d.get("is_approved")]
            approved_ids = {d["id"] for d in approved_devs}
            
            for dev_id, w in existing_cards.items():
                if dev_id not in approved_ids:
                    w.deleteLater()
            
            # pyrefly: ignore [missing-import]
            from widgets.device_card import DeviceCard
            for dev in approved_devs:
                if dev["id"] in existing_cards:
                    existing_cards[dev["id"]].update_data(dev)
                else:
                    card = DeviceCard(dev, self.api, user=self.user)
                    self._dev_layout.insertWidget(self._dev_layout.count() - 1, card)
            
            pass
        if is_master:
            row_height = 50
            header_height = 42
            num_rows = len(all_devs)
            total_height = header_height + (num_rows * row_height) + 2
            self._tbl.setFixedHeight(total_height)

    def _approve(self, did: int):
        self._aw = Worker(self.api.approve_device, did)
        self._aw.result.connect(lambda _: (self.refresh(), self._alert.show_success("Device approved")))
        self._aw.error.connect(self._alert.show_error)
        self._aw.start()

    def _remove(self, did: int):
        def do_delete(totp_code):
            self._rw = Worker(self.api.remove_device, did, totp_code)
            self._rw.result.connect(lambda _: (self.refresh(), self._alert.show_success("Device removed")))
            self._rw.error.connect(self._alert.show_error)
            self._rw.start()

        user_info = {}
        p = self
        while p:
            if hasattr(p, "user"): user_info = p.user; break
            p = p.parent()
        _prompt_sensitive_action(
            self, user_info, "Remove Device",
            "Please confirm device removal",
            do_delete
        )

    def _open_share_dialog(self, did: int, name: str):
        dlg = ShareDeviceDialog(did, name, self.api, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _download_conf(self, did: int, name: str):
        from PyQt6.QtWidgets import QFileDialog
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        path, _ = QFileDialog.getSaveFileName(self, "Save WireGuard Config", f"{safe_name}.conf", "Conf Files (*.conf)")
        if not path:
            return
            
        self._dl_w = Worker(self.api.download_conf, did)
        self._dl_w.result.connect(lambda data, p=path: self._save_conf_file(data, p))
        self._dl_w.error.connect(self._alert.show_error)
        self._dl_w.start()
        
    def _save_conf_file(self, data: str, path: str):
        try:
            with open(path, "w") as f:
                f.write(data)
            self._alert.show_success("Config downloaded successfully")
        except Exception as e:
            self._alert.show_error(f"Failed to save: {e}")

    def _open_shares_view(self, did: int, name: str):
        dlg = ViewSharesDialog(did, name, self.api, self)
        dlg.exec()

class ShareDeviceDialog(QDialog):
    def __init__(self, device_id: int, device_name: str, api, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.device_name = device_name
        self.api = api
        self.setWindowTitle("Share Device")
        self.setFixedSize(360, 180)
        self.setStyleSheet("QDialog{background:white;} QLabel{background:transparent;color:#0f172a;} QLineEdit{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px;font-size:13px;}")
        self._build_ui()
        self._load_tenants()

    def _load_tenants(self):
        self._tw = Worker(self.api.get_tenant_directory)
        self._tw.result.connect(self._on_tenants)
        self._tw.error.connect(lambda e: self.tenant_in.setItemText(0, "Failed to load tenants"))
        self._tw.start()

    def _on_tenants(self, tenants: list):
        self.tenant_in.clear()
        if not tenants:
            self.tenant_in.addItem("No other tenants found", None)
            return
        self.tenant_in.addItem("— Select a Tenant —", None)
        for t in tenants:
            self.tenant_in.addItem(t.get("company_name", f"Tenant #{t['id']}"), t["id"])

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        
        lbl = QLabel(f"Share <b>{self.device_name}</b> with another tenant.")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        
        lay.addWidget(QLabel("Target Tenant:"))
        self.tenant_in = QComboBox()
        self.tenant_in.setStyleSheet("QComboBox{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:4px;font-size:13px;}")
        self.tenant_in.addItem("Loading...", None)
        lay.addWidget(self.tenant_in)
        
        lay.addStretch()
        
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet("QPushButton{background:white;color:#475569;border:1px solid #cbd5e1;border-radius:6px;padding:6px 16px;} QPushButton:hover{background:#f1f5f9;}")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        
        self.ok_btn = QPushButton("Share")
        self.ok_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:6px;padding:6px 16px;font-weight:bold;} QPushButton:hover{background:#1d4ed8;}")
        self.ok_btn.clicked.connect(self._do_share)
        btns.addWidget(self.ok_btn)
        
        lay.addLayout(btns)

    def _do_share(self):
        tid = self.tenant_in.currentData()
        if tid is None:
            QMessageBox.warning(self, "Invalid Selection", "Please select a valid tenant from the list.")
            return
            
        self.ok_btn.setEnabled(False)
        self.ok_btn.setText("Sharing...")
        
        self._w = Worker(self.api.create_device_share, self.device_id, tid)
        self._w.result.connect(self._on_success)
        self._w.error.connect(self._on_error)
        self._w.start()
        
    def _on_success(self, _):
        QMessageBox.information(self, "Success", "Device shared successfully.")
        self.accept()
        
    def _on_error(self, err):
        self.ok_btn.setEnabled(True)
        self.ok_btn.setText("Share")
        QMessageBox.warning(self, "Error", f"Failed to share device: {err}")

class ViewSharesDialog(QDialog):
    def __init__(self, device_id: int, device_name: str, api, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.device_name = device_name
        self.api = api
        self.setWindowTitle(f"Shares for {device_name}")
        self.setFixedSize(450, 300)
        self.setStyleSheet("QDialog{background:white;} QLabel{background:transparent;color:#0f172a;}")
        self._build_ui()
        self._load()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(3)
        self.tbl.setHorizontalHeaderLabels(["Share ID", "Shared With", "Action"])
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(2, 120)
        self.tbl.setStyleSheet("QTableWidget{border:1px solid #e2e8f0;border-radius:4px;}")
        lay.addWidget(self.tbl)
        
        bot = QHBoxLayout()
        bot.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("QPushButton{background:white;color:#475569;border:1px solid #cbd5e1;border-radius:6px;padding:6px 16px;} QPushButton:hover{background:#f1f5f9;}")
        close_btn.clicked.connect(self.accept)
        bot.addWidget(close_btn)
        lay.addLayout(bot)

    def _load(self):
        self._w = Worker(lambda: (self.api.get_device_shares(self.device_id), self.api.get_tenant_directory()))
        self._w.result.connect(self._on_data)
        self._w.error.connect(lambda e: QMessageBox.warning(self, "Error", f"Could not load shares: {e}"))
        self._w.start()

    def _on_data(self, data):
        shares, tenants = data
        tenant_map = {t["id"]: t.get("company_name", f"Tenant #{t['id']}") for t in tenants}
        
        self.tbl.setRowCount(0)
        for sh in shares:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            
            tid = sh.get("target_tenant_id")
            t_name = tenant_map.get(tid, f"Tenant #{tid}")
            
            self.tbl.setItem(r, 0, table_item(str(sh.get("id", ""))))
            self.tbl.setItem(r, 1, table_item(t_name))
            
            btn = QPushButton("Revoke")
            btn.setStyleSheet("QPushButton{background:white;color:#dc2626;border:1px solid #fecaca;border-radius:4px;padding:4px 8px;} QPushButton:hover{background:#fee2e2;}")
            btn.clicked.connect(lambda _, sid=sh["id"]: self._revoke(sid))
            
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(4, 2, 4, 2)
            l.addWidget(btn)
            self.tbl.setCellWidget(r, 2, w)

    def _revoke(self, sid: int):
        if QMessageBox.question(self, "Confirm", "Revoke this share?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._rw = Worker(self.api.revoke_device_share, sid)
            self._rw.result.connect(lambda _: self._load())
            self._rw.error.connect(lambda e: QMessageBox.warning(self, "Error", f"Failed to revoke: {e}"))
            self._rw.start()


# ═══════════════════════════════════════════════════════════════════════════════
#  USERS PAGE
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════

class AssignDevicesDialog(QDialog):
    def __init__(self, user_id: int, user_name: str, user_role: str, api, parent=None):
        super().__init__(parent)
        self.user_id = user_id
        self.user_name = user_name
        self.user_role = user_role
        self.api = api
        self.devices = []
        self.assigned_ids = []
        self.setWindowTitle(f"Assign Devices — {user_name}")
        self.setFixedSize(650, 520)
        self.setStyleSheet("""
            QDialog {
                background: white;
            }
            QLabel {
                background: transparent;
            }
        """)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # Header Row
        hdr_row = QHBoxLayout()
        title = QLabel(f"Assign Devices — {self.user_name}")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #0f172a;")
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                color: #475569;
                border: none;
                border-radius: 14px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e2e8f0;
            }
        """)
        close_btn.clicked.connect(self.reject)
        
        hdr_row.addWidget(title)
        hdr_row.addStretch()
        hdr_row.addWidget(close_btn)
        lay.addLayout(hdr_row)

        # Subtitle
        sub = QLabel(f"Select which devices this {self.user_role} can access. Only assigned devices will be visible to them.")
        sub.setWordWrap(True)
        sub.setStyleSheet("font-size: 13px; color: #64748b; line-height: 1.4;")
        lay.addWidget(sub)

        # Table
        self.tbl = QTableWidget()
        self.tbl.setColumnCount(4)
        self.tbl.setHorizontalHeaderLabels(["DEVICE", "LAN IP", "STATUS", "ACCESS"])
        # pyrefly: ignore [missing-attribute]
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tbl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tbl.setShowGrid(False)
        
        # Stylesheet for Table
        self.tbl.setStyleSheet("""
            QTableWidget {
                background: white;
                border: none;
            }
            QHeaderView::section {
                background: white;
                color: #64748b;
                border: none;
                border-bottom: 1px solid #f1f5f9;
                font-size: 11px;
                font-weight: 700;
                padding-bottom: 8px;
                text-align: left;
            }
        """)
        
        hh = self.tbl.horizontalHeader()
        # pyrefly: ignore [missing-attribute]
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        # pyrefly: ignore [missing-attribute]
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        # pyrefly: ignore [missing-attribute]
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(1, 140)
        # pyrefly: ignore [missing-attribute]
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(2, 110)
        # pyrefly: ignore [missing-attribute]
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(3, 100)
        
        lay.addWidget(self.tbl)

        # Bottom Row
        bot = QHBoxLayout()
        bot.addStretch()
        
        close_win_btn = QPushButton("Close")
        close_win_btn.setFixedSize(90, 36)
        close_win_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_win_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #2563eb;
                border: 1.5px solid #2563eb;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #eff6ff;
            }
        """)
        close_win_btn.clicked.connect(self.accept)
        bot.addWidget(close_win_btn)
        lay.addLayout(bot)

    def _load_data(self):
        def fetch():
            devs = self.api.get_devices()
            assigned = self.api.get_user_assigned_devices(self.user_id)
            return devs, assigned
        self._w = Worker(fetch)
        self._w.result.connect(self._populate)
        self._w.start()

    def _populate(self, data):
        self.devices, self.assigned_ids = data
        self.devices = [d for d in self.devices if d.get("is_approved")]
        
        self.tbl.setRowCount(0)
        for d in self.devices:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setRowHeight(r, 48)

            # Device Name
            name_lbl = QLabel(d.get("name", d.get("zerotier_node_id", "Unknown")))
            name_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #0f172a; padding-left: 4px;")
            self.tbl.setCellWidget(r, 0, name_lbl)

            # LAN IP
            ip_val = d.get("lan_ip") or "—"
            ip_container = QWidget()
            ip_lay = QHBoxLayout(ip_container)
            ip_lay.setContentsMargins(0, 0, 0, 0)
            ip_lay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            if ip_val != "—":
                ip_btn = QPushButton(ip_val)
                ip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                ip_btn.setStyleSheet("""
                    QPushButton {
                        background: #f1f5f9;
                        color: #2563eb;
                        border: none;
                        border-radius: 4px;
                        padding: 3px 8px;
                        font-family: 'Consolas', 'Courier New', monospace;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background: #e2e8f0;
                        color: #1d4ed8;
                        text-decoration: underline;
                    }
                """)
                ip_btn.clicked.connect(lambda _, a=ip_val: QDesktopServices.openUrl(QUrl(f"http://{a}")))
                ip_lay.addWidget(ip_btn)
            else:
                ip_lbl = QLabel("—")
                ip_lbl.setStyleSheet("color: #94a3b8; font-size: 13px;")
                ip_lay.addWidget(ip_lbl)
                
            self.tbl.setCellWidget(r, 1, ip_container)

            # Status Badge
            status_val = d.get("status", "offline")
            status_container = QWidget()
            status_lay = QHBoxLayout(status_container)
            status_lay.setContentsMargins(0, 0, 0, 0)
            status_lay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            status_lbl = QLabel(status_val.lower())
            if status_val.lower() == "active" or status_val.lower() == "online":
                status_lbl.setStyleSheet("background: #dcfce7; color: #15803d; border-radius: 10px; padding: 2px 10px; font-size: 11px; font-weight: 600;")
            elif status_val.lower() == "connecting":
                status_lbl.setStyleSheet("background: #fef9c3; color: #a16207; border-radius: 10px; padding: 2px 10px; font-size: 11px; font-weight: 600;")
            else:
                status_lbl.setStyleSheet("background: #fee2e2; color: #b91c1c; border-radius: 10px; padding: 2px 10px; font-size: 11px; font-weight: 600;")
            status_lay.addWidget(status_lbl)
            self.tbl.setCellWidget(r, 2, status_container)

            # Access Action Button
            btn_container = QWidget()
            btn_lay = QHBoxLayout(btn_container)
            btn_lay.setContentsMargins(0, 0, 8, 0)
            btn_lay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            is_assigned = d["id"] in self.assigned_ids
            act_btn = QPushButton("Revoke" if is_assigned else "Assign")
            act_btn.setFixedSize(76, 28)
            act_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            if is_assigned:
                act_btn.setStyleSheet("""
                    QPushButton {
                        background: white;
                        color: #dc2626;
                        border: 1px solid #fca5a5;
                        border-radius: 6px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background: #fee2e2;
                    }
                """)
            else:
                act_btn.setStyleSheet("""
                    QPushButton {
                        background: white;
                        color: #16a34a;
                        border: 1px solid #86efac;
                        border-radius: 6px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background: #dcfce7;
                    }
                """)
                
            act_btn.clicked.connect(lambda _, did=d["id"], state=is_assigned: self._toggle_device_assignment(did, state))
            btn_lay.addWidget(act_btn)
            self.tbl.setCellWidget(r, 3, btn_container)

    def _toggle_device_assignment(self, device_id: int, currently_assigned: bool):
        if currently_assigned:
            new_list = [did for did in self.assigned_ids if did != device_id]
        else:
            new_list = self.assigned_ids + [device_id]
            
        self._sw = Worker(self.api.assign_devices, self.user_id, new_list)
        def on_done(res):
            self._load_data()
        self._sw.result.connect(on_done)
        self._sw.error.connect(lambda e: print("Error updating assignment:", e))
        self._sw.start()

class UsersPage(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)

        self._alert = AlertBar()
        lay.addWidget(self._alert)

        hdr = PageHeader("User Management", "Roles, trust, 2FA, and device access", "+ Add User")
        if hdr.action_btn:
            hdr.action_btn.clicked.connect(self._add_user)
        lay.addWidget(hdr)

        stats_row = QHBoxLayout(); stats_row.setSpacing(16)
        self._s_total   = StatCard("Total Users",    "-", color="#2563eb", icon_path=asset_path(ICON_USERS))
        self._s_sm      = StatCard("Second Masters", "-", color="#5b21b6", icon_path=asset_path("star.svg"))
        self._s_trusted = StatCard("Trusted Users",  "-", color="#7c3aed", icon_path=asset_path("check.svg"))
        for c in [self._s_total, self._s_sm, self._s_trusted]:
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            stats_row.addWidget(c)
        lay.addLayout(stats_row)

        card = CardWithHeader("Team Members")
        self._tbl = make_table(["NAME", "EMAIL", "ROLE", "2FA", "TRUSTED", "DEVICE ACCESS", "ACTIONS"])
        self._tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        hh = self._tbl.horizontalHeader()
        for c in range(7):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(True)
        
        self._tbl.setColumnWidth(0, 160) # NAME
        self._tbl.setColumnWidth(1, 200) # EMAIL
        self._tbl.setColumnWidth(2, 120) # ROLE
        self._tbl.setColumnWidth(3, 150)  # 2FA
        self._tbl.setColumnWidth(4, 125) # TRUSTED
        self._tbl.setColumnWidth(5, 135) # DEVICE ACCESS
        self._tbl.setColumnWidth(6, 320) # ACTIONS
        card.add_widget(self._tbl)
        lay.addWidget(card)
        lay.addStretch()

    def refresh(self):
        self._w = Worker(self.api.get_users)
        self._w.result.connect(self._on_data)
        self._w.error.connect(self._alert.show_error)
        self._w.start()

    def _on_data(self, users: list):
        self._users = users
        self._s_total.set_value(len(users))
        self._s_sm.set_value(f"{len([u for u in users if u.get('role')=='second_master'])}/2")
        self._s_trusted.set_value(len([u for u in users if u.get("is_trusted")]))

        t = self._tbl
        t.setUpdatesEnabled(False)
        t.setRowCount(0)
        for u in users:
            r = t.rowCount(); t.insertRow(r)
            self._add_user_row(t, r, u)
        t.setUpdatesEnabled(True)

        row_height = 50
        header_height = 42
        num_rows = len(users)
        total_height = header_height + (num_rows * row_height) + 2
        t.setFixedHeight(total_height)

    def _add_user_row(self, t, r, u):
        try:
            # pyrefly: ignore [missing-import]
            from client.styles import ROLE_COLORS
        except ImportError:
            # pyrefly: ignore [missing-import]
            from styles import ROLE_COLORS
        nw = QWidget()
        nl = QHBoxLayout(nw)
        nl.setContentsMargins(8, 4, 8, 4)
        av = QLabel(u.get("full_name", "U")[0].upper())
        av.setFixedSize(26, 26)
        av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.setStyleSheet("background:#3b82f6;color:white;border-radius:13px;font-weight:700;font-size:12px;border:none;")
        n_lbl = QLabel(u.get("full_name", ""))
        n_lbl.setStyleSheet("font-size:13px;font-weight:600;color:#1e293b;border:none;background:transparent;")
        nl.addWidget(av); nl.addWidget(n_lbl); nl.addStretch()
        t.setCellWidget(r, 0, nw)
        
        t.setItem(r, 1, table_item(u.get("email", "")))

        role = u.get("role", "")
        bg, fg = ROLE_COLORS.get(role, ("#f1f5f9", "#64748b"))
        role_w = QWidget()
        role_l = QHBoxLayout(role_w)
        role_l.setContentsMargins(8, 4, 8, 4)
        role_badge_lbl = QLabel(role.replace("_"," ").title())
        role_badge_lbl.setStyleSheet(f"background:{bg};color:{fg};padding:3px 9px;border-radius:12px;font-size:12px;font-weight:600")
        role_l.addWidget(role_badge_lbl); role_l.addStretch()
        t.setCellWidget(r, 2, role_w)

        fa_w = QWidget()
        fa_l = QHBoxLayout(fa_w)
        fa_l.setContentsMargins(8, 4, 8, 4)
        if u.get("totp_enabled"):
            fa_lbl = QLabel("✓ Active")
            fa_lbl.setStyleSheet("background:#dcfce7;color:#16a34a;padding:3px 9px;border-radius:12px;font-size:12px;font-weight:600")
        else:
            fa_lbl = QLabel("Off")
            fa_lbl.setStyleSheet("background:#f1f5f9;color:#64748b;padding:3px 9px;border-radius:12px;font-size:12px;font-weight:600")
        fa_l.addWidget(fa_lbl); fa_l.addStretch()
        t.setCellWidget(r, 3, fa_w)

        tr_w = QWidget()
        tr_l = QHBoxLayout(tr_w)
        tr_l.setContentsMargins(8, 4, 8, 4)
        if role in ("master", "second_master", "trusted"):
            tr_lbl = QLabel("-")
            tr_lbl.setStyleSheet("color:#94a3b8;border:none;background:transparent;")
        elif u.get("is_trusted"):
            tr_lbl = QPushButton("Revoke Trust")
            tr_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            tr_lbl.setStyleSheet("color:#dc2626;font-size:13px;font-weight:600;border:none;text-align:left;background:transparent;")
            tr_lbl.setFixedSize(110, 30)
            tr_lbl.clicked.connect(lambda _, uid=u["id"]: self._toggle_trust(uid, False))
        else:
            tr_lbl = QPushButton("Set Trusted")
            tr_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            tr_lbl.setStyleSheet("color:#3b82f6;font-size:13px;font-weight:600;border:none;text-align:left;background:transparent;")
            tr_lbl.setFixedSize(110, 30)
            tr_lbl.clicked.connect(lambda _, uid=u["id"]: self._toggle_trust(uid, True))
        tr_l.addWidget(tr_lbl); tr_l.addStretch()
        t.setCellWidget(r, 4, tr_w)

        da_w = QWidget()
        da_l = QHBoxLayout(da_w)
        da_l.setContentsMargins(8, 4, 8, 4)
        if role in ("master", "second_master", "trusted") or u.get("is_trusted"):
            da_lbl = QLabel("All Devices")
            da_lbl.setStyleSheet("background:#dbeafe;color:#2563eb;padding:3px 9px;border-radius:12px;font-size:12px;font-weight:600")
        else:
            da_lbl = QLabel("Restricted")
            da_lbl.setStyleSheet("background:#f1f5f9;color:#64748b;padding:3px 9px;border-radius:12px;font-size:12px;font-weight:600")
        da_l.addWidget(da_lbl); da_l.addStretch()
        t.setCellWidget(r, 5, da_w)

        if role == "master":
            t.setItem(r, 6, table_item("-", Qt.AlignmentFlag.AlignCenter))
        else:
            btn_w = QWidget()
            btn_l = QHBoxLayout(btn_w)
            btn_l.setContentsMargins(4, 4, 4, 4)
            btn_l.setSpacing(6)
            btn_l.addStretch()
            is_forced = u.get("force_2fa", False)
            if role == "second_master":
                fa_btn = QPushButton("Required")
                fa_btn.setObjectName("btn-sm")
                fa_btn.setFixedSize(110, 30)
                fa_btn.setEnabled(False)
                fa_btn.setStyleSheet("""
                    QPushButton {
                        background: #f1f5f9;
                        color: #94a3b8;
                        border: 1px solid #e2e8f0;
                        border-radius: 6px;
                        font-weight: 600;
                    }
                """)
            else:
                fa_btn = QPushButton("Disable 2FA" if is_forced else "Force 2FA")
                fa_btn.setObjectName("btn-sm")
                fa_btn.setFixedSize(110, 30)
                fa_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                if is_forced:
                    fa_btn.setStyleSheet("""
                        QPushButton {
                            background: white;
                            color: #dc2626;
                            border: 1px solid #fca5a5;
                            border-radius: 6px;
                            font-weight: 600;
                        }
                        QPushButton:hover {
                            background: #fee2e2;
                            border-color: #ef4444;
                        }
                    """)
                else:
                    fa_btn.setStyleSheet("""
                        QPushButton {
                            background: white;
                            color: #2563eb;
                            border: 1px solid #bfdbfe;
                            border-radius: 6px;
                            font-weight: 600;
                        }
                        QPushButton:hover {
                            background: #eff6ff;
                            color: #1d4ed8;
                            border-color: #3b82f6;
                        }
                    """)
                fa_btn.clicked.connect(lambda _, uid=u["id"], cur=is_forced: self._toggle_force_2fa(uid, cur))



            assign_btn = QPushButton("Assign")
            assign_btn.setObjectName("btn-sm")
            assign_btn.setFixedSize(65, 30)
            assign_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            assign_btn.setStyleSheet(
                "QPushButton { background: white; color: #2563eb; border: 1px solid #bfdbfe; border-radius: 6px; font-weight: 600; }"
                "QPushButton:hover { background: #eff6ff; color: #1d4ed8; border-color: #3b82f6; }"
            )
            assign_btn.clicked.connect(lambda _, uid=u["id"], nm=u.get("full_name",""): self._open_assign_dialog(uid, nm))
            if role in ("second_master", "trusted") or u.get("is_trusted"):
                assign_btn.setVisible(False)
            rem = QPushButton("Remove")
            rem.setObjectName("btn-danger")
            rem.setFixedSize(75, 30)
            rem.clicked.connect(lambda _, uid=u["id"], nm=u.get("full_name",""): self._remove_user(uid, nm))
            btn_l.addWidget(fa_btn)
            btn_l.addWidget(assign_btn)
            if role == "second_master":
                demote_btn = QPushButton("Demote")
                demote_btn.setObjectName("btn-sm")
                demote_btn.setFixedSize(75, 30)
                demote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                demote_btn.setStyleSheet(
                    "QPushButton { background: white; color: #d97706; border: 1px solid #fcd34d; border-radius: 6px; font-weight: 600; }"
                    "QPushButton:hover { background: #fef3c7; color: #b45309; border-color: #fbbf24; }"
                )
                demote_btn.clicked.connect(lambda _, uid=u["id"], nm=u.get("full_name",""): self._demote_user(uid, nm))
                btn_l.addWidget(demote_btn)
            btn_l.addWidget(rem)
            btn_l.addStretch()
            t.setCellWidget(r, 6, btn_w)


    def _toggle_trust(self, user_id: int, is_trusted: bool):
        self._tw = Worker(self.api.toggle_trust, user_id, is_trusted)
        self._tw.result.connect(lambda _: self.refresh())
        self._tw.error.connect(self._alert.show_error)
        self._tw.start()

    def _toggle_force_2fa(self, user_id: int, current_force: bool):
        self._tf = Worker(self.api.toggle_force_2fa, user_id, not current_force)
        self._tf.result.connect(lambda _: self.refresh())
        self._tf.error.connect(self._alert.show_error)
        self._tf.start()

    def _open_assign_dialog(self, user_id: int, user_name: str):
        user_role = "Admin User"
        for u in getattr(self, "_users", []):
            if u.get("id") == user_id:
                user_role = u.get("role", "admin").replace("_", " ").title()
                break
        dlg = AssignDevicesDialog(user_id, user_name, user_role, self.api, self.window())
        dlg.exec()
        self.refresh()

    def _add_user(self):
        dlg = QDialog(self.window())
        dlg.setWindowTitle(TITLE_ADD_USER)
        dlg.setFixedSize(440, 480)
        dlg.setStyleSheet("QDialog{background:#f1f5f9} QLabel{background:transparent;color:#0f172a} QLineEdit,QComboBox{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:9px;font-size:14px;color:#0f172a}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(12)
        lay.addWidget(_lbl("Full Name", bold=True))
        name_in = QLineEdit(); name_in.setPlaceholderText("John Smith")
        lay.addWidget(name_in)
        lay.addWidget(_lbl("Email Address", bold=True))
        email_in = QLineEdit(); email_in.setPlaceholderText("john@example.com")
        lay.addWidget(email_in)
        lay.addWidget(_lbl("Password (min 8 chars)", bold=True))
        pass_in = QLineEdit(); pass_in.setPlaceholderText("Leave blank for auto-generated")
        pass_in.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(pass_in)

        btns = QHBoxLayout(); btns.setContentsMargins(0,16,0,0)
        cancel_btn = QPushButton("Cancel"); cancel_btn.setObjectName("btn-ghost"); cancel_btn.setFixedSize(100,36)
        cancel_btn.clicked.connect(dlg.reject)
        ok_btn = QPushButton(TITLE_ADD_USER); ok_btn.setObjectName("btn-primary"); ok_btn.setFixedHeight(36)
        btns.addStretch(); btns.addWidget(cancel_btn); btns.addWidget(ok_btn)

        lay.addWidget(_lbl("Role", bold=True))
        role_cb = QComboBox()
        role_cb.addItems(["Second Master", "Admin User", "Trusted User"])
        lay.addWidget(role_cb)
        lay.addLayout(btns)

        role_map = {"Second Master": "second_master", "Admin User": "admin", "Trusted User": "trusted"}

        def do_create():
            ok_btn.setEnabled(False); ok_btn.setText("Creating…")
            role_key = role_map.get(role_cb.currentText(), "admin")
            self._cuw = Worker(self.api.create_user, email_in.text(), name_in.text(), role_key, pass_in.text())
            def on_ok(data):
                QMessageBox.information(dlg, "Success", f"User created!\n\nEmail: {data['email']}\nTemp Password: {data.get('temp_password')}")
                dlg.accept()
                self.refresh()
            def on_err(e):
                ok_btn.setEnabled(True); ok_btn.setText(TITLE_ADD_USER)
                QMessageBox.warning(dlg, "Error", str(e))
            self._cuw.result.connect(on_ok)
            self._cuw.error.connect(on_err)
            self._cuw.start()

        ok_btn.clicked.connect(do_create)
        dlg.exec()

    def _remove_user(self, uid: int, name: str):
        def do_delete(totp_code):
            self._rw = Worker(self.api.remove_user, uid, totp_code)
            self._rw.result.connect(lambda _: self.refresh())
            self._rw.error.connect(self._alert.show_error)
            self._rw.start()

        user_info = {}
        p = self
        while p:
            if hasattr(p, "user"): user_info = p.user; break
            p = p.parent()
        _prompt_sensitive_action(
            self, user_info, "Confirm Removal 2FA",
            "Please confirm user removal",
            do_delete
        )

    def _demote_user(self, uid: int, name: str):
        def do_demote(totp_code):
            self._dw = Worker(self.api.demote_user, uid, totp_code)
            self._dw.result.connect(lambda _: self.refresh())
            self._dw.error.connect(self._alert.show_error)
            self._dw.start()

        user_info = {}
        p = self
        while p:
            if hasattr(p, "user"): user_info = p.user; break
            p = p.parent()
        _prompt_sensitive_action(
            self, user_info, "Demote to Admin",
            f"Demote {name} to Admin? They will lose access to user management.",
            do_demote
        )

# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIT PAGE
# ═══════════════════════════════════════════════════════════════════════════════
class AuditPage(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)
        lay.addWidget(PageHeader("Audit Log", "All actions on your tenant — who did what and when"))
        card = CardWithHeader("Activity History")
        
        from PyQt6.QtWidgets import QDateEdit, QComboBox, QLineEdit
        from PyQt6.QtCore import QDate

        top_row = QHBoxLayout()
        top_row.setContentsMargins(16, 12, 16, 0)
        top_row.addStretch()
        
        self._level_filter = QComboBox()
        self._level_filter.addItems(["All Levels", "info", "success", "warning", "error"])
        self._level_filter.setStyleSheet("QComboBox{background:white;border:1px solid #cbd5e1;border-radius:6px;padding:4px;font-size:13px;}")
        
        self._from_date = QDateEdit()
        self._from_date.setCalendarPopup(True)
        self._from_date.setDate(QDate.currentDate().addDays(-30))
        self._from_date.setStyleSheet("QDateEdit{background:white;border:1px solid #cbd5e1;border-radius:6px;padding:4px;font-size:13px;}")
        self._from_date.dateChanged.connect(self.refresh)
        
        self._to_date = QDateEdit()
        self._to_date.setCalendarPopup(True)
        self._to_date.setDate(QDate.currentDate())
        self._to_date.setStyleSheet("QDateEdit{background:white;border:1px solid #cbd5e1;border-radius:6px;padding:4px;font-size:13px;}")
        self._to_date.dateChanged.connect(self.refresh)
        
        top_row.addWidget(self._level_filter)
        top_row.addWidget(QLabel("From:"))
        top_row.addWidget(self._from_date)
        top_row.addWidget(QLabel("To:"))
        top_row.addWidget(self._to_date)
        
        self._filter_in = QLineEdit()
        self._filter_in.setPlaceholderText("Filter logs...")
        self._filter_in.setFixedWidth(200)
        
        # Connect filters to the filter logic
        # For simplicity, we delay connecting them until `_apply_filter` is defined
        
        top_row.addWidget(self._filter_in)
        card.add_layout(top_row)
        self._tbl = make_table(["Description", "By", "Date", "Level"])
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._tbl.setColumnWidth(1, 140)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._tbl.setColumnWidth(2, 180)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._tbl.setColumnWidth(3, 120)
        card.add_widget(self._tbl)
        lay.addWidget(card)
        lay.addStretch()

    def refresh(self):
        from_date = None
        to_date = None
        if hasattr(self, '_from_date'):
            from_date = self._from_date.date().toString("yyyy-MM-dd") + "T00:00:00"
            to_date = self._to_date.date().toString("yyyy-MM-dd") + "T23:59:59"
        self._w = Worker(self.api.get_audit_logs, from_date, to_date)
        self._w.result.connect(self._on_data)
        self._w.error.connect(lambda e: print("Audit error:", e))
        self._w.start()

    def _on_data(self, logs: list):
        self._logs = logs
        
        # Ensure signals are connected once
        if hasattr(self, "_filter_in") and not getattr(self, "_filter_connected", False):
            self._filter_in.textChanged.connect(self._apply_filter)
            self._level_filter.currentTextChanged.connect(self._apply_filter)
            self._filter_connected = True
            
        self._apply_filter()

    def _apply_filter(self, *args):
        logs = getattr(self, "_logs", [])
        query = (self._filter_in.text() if hasattr(self, "_filter_in") else "").strip().lower()
        level_filter = (self._level_filter.currentText() if hasattr(self, "_level_filter") else "All Levels")
        
        t = self._tbl
        t.setUpdatesEnabled(False)
        t.setRowCount(0)
        for log in logs:
            lvl = log.get("level", "info")
            if level_filter != "All Levels" and lvl.lower() != level_filter.lower():
                continue
                
            haystack = " ".join([
                str(log.get("description", "")),
                str(log.get("user_name", "")),
                str(lvl),
            ]).lower()
            if query and query not in haystack:
                continue
            r = t.rowCount(); t.insertRow(r)
            t.setItem(r, 0, table_item(log.get("description", "")))
            t.setItem(r, 1, table_item(log.get("user_name") or "System"))
            t.setItem(r, 2, table_item(_fmt_date(log.get("created_at", ""))))
            lvl = log.get("level", "info")
            bg, fg = LEVEL_COLORS.get(lvl, ("#dbeafe", "#1d4ed8"))
            lbl_w = QWidget()
            ll = QHBoxLayout(lbl_w)
            ll.setContentsMargins(8, 0, 8, 0)
            b = QLabel(lvl.title())
            b.setFixedHeight(22)
            b.setContentsMargins(10, 2, 10, 2)
            b.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
            b.setStyleSheet(
                f"QLabel{{background:{bg};color:{fg};border-radius:11px;"
                f"font-size:12px;font-weight:600}}"
            )
            ll.addWidget(b); ll.addStretch()
            t.setCellWidget(r, 3, lbl_w)
        t.setUpdatesEnabled(True)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: t.horizontalHeader().resizeSection(3, 120))


# ═══════════════════════════════════════════════════════════════════════════════
#  SETTINGS PAGE
# ═══════════════════════════════════════════════════════════════════════════════
class SettingsPage(QWidget):
    profile_updated = pyqtSignal(str)

    def __init__(self, api, user: dict):
        super().__init__()
        self.api = api
        self.user = user
        self._build()

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)

        self._alert = AlertBar()
        lay.addWidget(self._alert)
        lay.addWidget(PageHeader("Settings", "Account, security, and platform configuration"))

        grid = QHBoxLayout(); grid.setSpacing(20)

        # Profile
        pc = QFrame(); pc.setObjectName("card")
        pl = QVBoxLayout(pc); pl.setContentsMargins(24, 24, 24, 24); pl.setSpacing(12)
        pl.addWidget(_lbl("Profile", bold=True, size=15))
        pl.addWidget(_lbl("Full Name", muted=True))
        self._name_in = QLineEdit()
        self._name_in.setText(self.user.get("full_name", ""))
        pl.addWidget(self._name_in)
        pl.addWidget(_lbl("Email", muted=True))
        self._email_in = QLineEdit()
        self._email_in.setText(self.user.get("email", ""))
        pl.addWidget(self._email_in)
        
        warn_lbl = QLabel("Note: Changing your email will compulsorily disable your 2FA.")
        warn_lbl.setStyleSheet("color: #b45309; font-size: 11px;")
        pl.addWidget(warn_lbl)

        pl.addWidget(_lbl("Role", muted=True))
        role_in = QLineEdit(self.user.get("role", "").replace("_", " ").title())
        role_in.setEnabled(False)
        pl.addWidget(role_in)
        save_btn = QPushButton("Save Changes")
        save_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600} QPushButton:hover{background:#1d4ed8}")
        save_btn.clicked.connect(self._save_profile)
        pl.addWidget(save_btn)
        pl.addStretch()
        grid.addWidget(pc)

        # 2FA
        self.tfa_c = QFrame(); self.tfa_c.setObjectName("card")
        self.tfa_l = QVBoxLayout(self.tfa_c); self.tfa_l.setContentsMargins(24, 24, 24, 24); self.tfa_l.setSpacing(12)
        self.tfa_l.addWidget(_lbl("Two-Factor Authentication (2FA)", bold=True, size=15))
        self.tfa_info = _lbl("2FA is mandatory for Master and Second Master accounts.", muted=True)
        self.tfa_info.setWordWrap(True)
        self.tfa_l.addWidget(self.tfa_info)
        
        self.tfa_status_lbl = QLabel()
        self.tfa_l.addWidget(self.tfa_status_lbl)
        
        self.reconf_btn = QPushButton()
        self.reconf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reconf_btn.clicked.connect(self._configure_2fa)
        self.tfa_l.addWidget(self.reconf_btn)
        self.tfa_l.addStretch()
        grid.addWidget(self.tfa_c)
        lay.addLayout(grid)
        self._update_2fa_ui()

        grid2 = QHBoxLayout(); grid2.setSpacing(20)

        # Network Configuration
        zt_c = QFrame(); zt_c.setObjectName("card")
        zt_l = QVBoxLayout(zt_c); zt_l.setContentsMargins(24, 24, 24, 24); zt_l.setSpacing(12)
        
        if TUNNEL_MODE == "wireguard":
            zt_l.addWidget(_lbl("WireGuard Identity", bold=True, size=15))
            from services.wireguard_local import get_or_create_keypair
            priv, pub = get_or_create_keypair()
            zt_l.addWidget(_lbl("Private Key", muted=True))
            self._wg_priv_in = QLineEdit()
            self._wg_priv_in.setText(priv)
            self._wg_priv_in.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
            zt_l.addWidget(self._wg_priv_in)
            
            zt_l.addWidget(_lbl("Public Key", muted=True))
            self._wg_pub_lbl = QLineEdit()
            self._wg_pub_lbl.setText(pub)
            self._wg_pub_lbl.setReadOnly(True)
            self._wg_pub_lbl.setStyleSheet("background:#f1f5f9;color:#64748b")
            zt_l.addWidget(self._wg_pub_lbl)
            
            save_wg_btn = QPushButton("Save Key")
            save_wg_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600} QPushButton:hover{background:#1d4ed8}")
            save_wg_btn.clicked.connect(self._save_wg_key)
            zt_l.addWidget(save_wg_btn)
            
            info = _lbl("If you change your key, you must Remove and re-Approve this device from the dashboard.", muted=True)
            info.setWordWrap(True)
            info.setStyleSheet("color:#f59e0b;font-size:11px;margin-top:8px;")
            zt_l.addWidget(info)
            zt_l.addStretch()
        else:
            zt_l.addWidget(_lbl("ZeroTier Network", bold=True, size=15))
            zt_l.addSpacing(14)
            for label, val in [("Network ID", self.user.get("network_id") or "—"), ("Status", "Connected"), ("Auto-Reconnect", "✓ Enabled")]:
                rw = QWidget(); rw.setStyleSheet("border-bottom:1px solid #f1f5f9")
                rl = QHBoxLayout(rw); rl.setContentsMargins(0, 10, 0, 10)
                rl.addWidget(_lbl(label, muted=True)); rl.addStretch()
                if val == "Connected":
                    v = QLabel(val); v.setStyleSheet("background:#dcfce7;color:#15803d;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600")
                else:
                    v = _lbl(val)
                rl.addWidget(v)
                zt_l.addWidget(rw)
            zt_l.addStretch()
            
        grid2.addWidget(zt_c)

        # Change password
        pw_c = QFrame(); pw_c.setObjectName("card")
        pw_l = QVBoxLayout(pw_c); pw_l.setContentsMargins(24, 24, 24, 24); pw_l.setSpacing(12)
        pw_l.addWidget(_lbl("Change Password", bold=True, size=15))
        pw_l.addWidget(_lbl("Current Password", muted=True))
        self._cur_pw = QLineEdit(); self._cur_pw.setEchoMode(QLineEdit.EchoMode.Password)
        pw_l.addWidget(self._cur_pw)
        pw_l.addWidget(_lbl("New Password", muted=True))
        self._new_pw = QLineEdit(); self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        pw_l.addWidget(self._new_pw)
        pw_l.addWidget(_lbl("Confirm New Password", muted=True))
        self._conf_pw = QLineEdit(); self._conf_pw.setEchoMode(QLineEdit.EchoMode.Password)
        pw_l.addWidget(self._conf_pw)
        upd_btn = QPushButton("Update Password")
        upd_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600} QPushButton:hover{background:#1d4ed8}")
        upd_btn.clicked.connect(self._change_password)
        pw_l.addWidget(upd_btn)
        pw_l.addStretch()
        grid2.addWidget(pw_c)
        lay.addLayout(grid2)

        # Version
        v_c = QFrame(); v_c.setObjectName("card")
        v_l = QVBoxLayout(v_c); v_l.setContentsMargins(24, 24, 24, 24); v_l.setSpacing(0)
        v_l.addWidget(_lbl("Version & Updates", bold=True, size=15))
        v_l.addSpacing(14)
        # pyrefly: ignore [missing-import]
        from config import APP_VERSION
        for label, val in [("Current Version", APP_VERSION), ("Platform", "ProjectX Desktop"), ("Developer", "Celestial Infosoft"), ("Support", "info@celestialinfosoft.com")]:
            rw = QWidget(); rw.setStyleSheet("border-bottom:1px solid #f1f5f9")
            rl = QHBoxLayout(rw); rl.setContentsMargins(0, 10, 0, 10)
            rl.addWidget(_lbl(label, muted=True)); rl.addStretch(); rl.addWidget(_lbl(val))
            v_l.addWidget(rw)
        v_l.addStretch()
        lay.addWidget(v_c)
        lay.addStretch()

        scroll.setWidget(inner)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    def _save_wg_key(self):
        new_priv = self._wg_priv_in.text().strip()
        if not new_priv:
            self._alert.show_error("Private key cannot be empty")
            return
        try:
            from services.wireguard_local import WG_CMD, WG_KEY_STORAGE
            import subprocess, json, os, sys
            cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            pub = subprocess.run([WG_CMD, "pubkey"], input=new_priv, capture_output=True, text=True, check=True, creationflags=cflags).stdout.strip()
            os.makedirs(os.path.dirname(WG_KEY_STORAGE), exist_ok=True)
            with open(WG_KEY_STORAGE, "w") as f:
                json.dump({"private_key": new_priv, "public_key": pub}, f)
            self._wg_pub_lbl.setText(pub)
            self._alert.show_success("WireGuard key saved! Please restart the client.")
        except Exception as e:
            self._alert.show_error(f"Failed to save WireGuard key: {e}")

    def refresh(self):
        pass

    def _configure_2fa(self):
        try:
            # pyrefly: ignore [missing-import]
            from client.windows.setup_2fa_window import Setup2FAWindow
        except ImportError:
            # pyrefly: ignore [missing-import]
            from windows.setup_2fa_window import Setup2FAWindow
        self.setup_2fa_win = Setup2FAWindow(self.api)
        self.setup_2fa_win.setup_complete.connect(self._on_2fa_setup_complete)
        self.setup_2fa_win.show()

    def _on_2fa_setup_complete(self):
        if hasattr(self, "setup_2fa_win"):
            self.setup_2fa_win.hide()
        self._refresh_user_info()

    def _refresh_user_info(self):
        self._ref_worker = Worker(self.api.get_me)
        def on_result(user_info):
            self.user = user_info
            p = self
            while p:
                if hasattr(p, "user") and p is not self:
                    # pyrefly: ignore [missing-attribute]
                    p.user = user_info
                    break
                p = p.parent()
            self._update_2fa_ui()
        self._ref_worker.result.connect(on_result)
        self._ref_worker.error.connect(self._alert.show_error)
        self._ref_worker.start()

    def _update_2fa_ui(self):
        if self.user.get("totp_enabled"):
            self.tfa_status_lbl.setText("✓  2FA is Active on this account")
            self.tfa_status_lbl.setStyleSheet("background:#dcfce7;color:#15803d;border:1px solid #bbf7d0;border-radius:8px;padding:10px 14px;font-size:13px")
            self.reconf_btn.setText("Re-configure 2FA")
            self.reconf_btn.setStyleSheet("""
                QPushButton {
                    background: white;
                    color: #dc2626;
                    border: 1px solid #fca5a5;
                    border-radius: 8px;
                    padding: 9px 18px;
                    font-size: 14px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #fee2e2;
                    border-color: #ef4444;
                }
            """)
        else:
            role = self.user.get("role", "")
            if role in ("master", "second_master"):
                self.tfa_status_lbl.setText("⚠  2FA not yet enabled — required for this account")
                self.tfa_status_lbl.setStyleSheet("background:#fee2e2;color:#b91c1c;border:1px solid #fecaca;border-radius:8px;padding:10px 14px;font-size:13px")
            else:
                self.tfa_status_lbl.setText("⚠  2FA not yet enabled — optional for this account")
                self.tfa_status_lbl.setStyleSheet("background:#fffbeb;color:#b45309;border:1px solid #fde68a;border-radius:8px;padding:10px 14px;font-size:13px")
            self.reconf_btn.setText("Configure 2FA")
            self.reconf_btn.setStyleSheet("""
                QPushButton {
                    background: #2563eb;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 9px 18px;
                    font-size: 14px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #1d4ed8;
                }
            """)

    def _change_password(self):
        np = self._new_pw.text()
        cp = self._conf_pw.text()
        if np != cp:
            self._alert.show_error("Passwords do not match")
            return
        self._pw = Worker(self.api.change_password, np)
        self._pw.result.connect(lambda _: self._alert.show_success("Password changed successfully"))
        self._pw.error.connect(self._alert.show_error)
        self._pw.start()

    def _save_profile(self):
        new_name = self._name_in.text().strip()
        new_email = self._email_in.text().strip()
        if not new_name or not new_email:
            self._alert.show_error("Name and Email cannot be empty")
            return
        
        self._pw_w = Worker(self.api.update_user_profile, self.user["id"], new_email, new_name)
        def on_ok(res):
            self._alert.show_success("Profile saved")
            self.profile_updated.emit(new_name)
        self._pw_w.result.connect(on_ok)
        self._pw_w.error.connect(self._alert.show_error)
        self._pw_w.start()

# ═══════════════════════════════════════════════════════════════════════════════
#  WG TUNNEL PAGE
# ═══════════════════════════════════════════════════════════════════════════════
class WgTunnelPage(QWidget):
    def __init__(self, api, user_info):
        super().__init__()
        self.api = api
        self.user = user_info
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(24)

        # Header
        top_h = QHBoxLayout()
        title_v = QVBoxLayout()
        self.title_lbl = QLabel("WireGuard Tunnel")
        self.title_lbl.setStyleSheet("font-size:24px;font-weight:700;color:#0f172a;margin-bottom:4px")
        self.sub_lbl = QLabel("No server claimed yet")
        self.sub_lbl.setStyleSheet("font-size:14px;color:#8b949e")
        title_v.addWidget(self.title_lbl)
        title_v.addWidget(self.sub_lbl)
        top_h.addLayout(title_v)
        top_h.addStretch()

        self.claim_btn = QPushButton("Claim / Change Server")
        self.claim_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.claim_btn.setStyleSheet("""
            QPushButton { background:#2f81f7; color:white; border-radius:6px; padding:8px 16px; font-weight:600; }
            QPushButton:hover { background:#388bfd; }
        """)
        self.claim_btn.clicked.connect(self._show_claim_window)
        top_h.addWidget(self.claim_btn)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet("""
            QPushButton { background:#21262d; color:#e6edf3; border:1px solid #30363d; border-radius:6px; padding:8px 16px; font-weight:600; }
            QPushButton:hover { background:#30363d; border-color:#8b949e; }
        """)
        self.refresh_btn.clicked.connect(self.refresh)
        top_h.addWidget(self.refresh_btn)

        self.disconnect_btn = QPushButton("Disconnect Tunnel")
        self.disconnect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.disconnect_btn.setStyleSheet("""
            QPushButton { background:#dc2626; color:white; border-radius:6px; padding:8px 16px; font-weight:600; }
            QPushButton:hover { background:#ef4444; }
        """)
        self.disconnect_btn.clicked.connect(self._disconnect_tunnel)
        top_h.addWidget(self.disconnect_btn)

        root.addLayout(top_h)

        # Error state for unclaimed
        self.empty_w = QWidget()
        ev = QVBoxLayout(self.empty_w)
        ev.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ev.setContentsMargins(0, 60, 0, 60)
        em = QLabel("No WireGuard server claimed yet. Click 'Claim / Change Server' to get started.")
        em.setStyleSheet("color:#8b949e;font-size:14px")
        ev.addWidget(em, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.empty_w)

        self.content_w = QWidget()
        cv = QVBoxLayout(self.content_w)
        cv.setContentsMargins(0,0,0,0)
        cv.setSpacing(24)

        stats_h = QHBoxLayout()
        stats_h.setSpacing(16)
        
        try:
            # pyrefly: ignore [missing-import]
            from widgets.common import StatCard
            self.total_card = StatCard("Total Peers", "0")
            self.active_card = StatCard("Active Peers", "0")
            stats_h.addWidget(self.total_card)
            stats_h.addWidget(self.active_card)
        except ImportError:
            self.total_card = QLabel("Total: 0")
            self.active_card = QLabel("Active: 0")
            stats_h.addWidget(self.total_card)
            stats_h.addWidget(self.active_card)
        
        stats_h.addStretch()
        cv.addLayout(stats_h)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "WG IP", "LAN IP", "Status", "Public Key"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStyleSheet("QHeaderView::section { background-color:#161b22; color:#8b949e; padding:4px; border:none; border-bottom:1px solid #30363d; font-weight:600; font-size:12px; }")
        cv.addWidget(self.table)

        root.addWidget(self.content_w)
        self.content_w.hide()

    def _disconnect_tunnel(self):
        try:
            # pyrefly: ignore [missing-import]
            from services.wireguard_local import disconnect
            # pyrefly: ignore [missing-import]
            from config import WG_INTERFACE
            disconnect(WG_INTERFACE)
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Disconnected", "WireGuard tunnel stopped locally. Restart the app to re-register.")
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Failed to disconnect: {e}")

    def refresh(self):
        if hasattr(self, "_w") and self._w.isRunning():
            return
        self.refresh_btn.setText("Refreshing...")
        self.refresh_btn.setEnabled(False)
        self._w = Worker(self.api.get_wg_tunnel_peers)
        self._w.result.connect(self._on_data)
        self._w.error.connect(self._on_error)
        self._w.start()

    def _on_data(self, data):
        self.refresh_btn.setText("Refresh")
        self.refresh_btn.setEnabled(True)
        self.empty_w.hide()
        self.content_w.show()

        ep = data.get("server_endpoint", "Unknown")
        self.sub_lbl.setText(f"Server Endpoint: {ep}")

        total = data.get("total", 0)
        active = data.get("active", 0)
        
        try:
            self.total_card.set_value(str(total))
            self.active_card.set_value(str(active))
        except AttributeError:
            self.total_card.setText(f"Total: {total}")
            self.active_card.setText(f"Active: {active}")

        peers = data.get("peers", [])
        self.table.setRowCount(len(peers))
        
        # pyrefly: ignore [missing-import]
        from widgets.common import status_badge
        
        for r, p in enumerate(peers):
            self.table.setItem(r, 0, QTableWidgetItem(p.get("name", "Unknown")))
            self.table.setItem(r, 1, QTableWidgetItem(p.get("wg_ip", "-")))
            self.table.setItem(r, 2, QTableWidgetItem(p.get("lan_ip", "-")))
            
            status_w = QWidget()
            sl = QHBoxLayout(status_w)
            sl.setContentsMargins(4, 0, 0, 0)
            
            st = p.get("status", "offline")
            if st == "active":
                sl.addWidget(status_badge("active"))
                lbl = QLabel("Active")
                lbl.setStyleSheet("color:#3fb950;font-size:12px")
            else:
                sl.addWidget(status_badge("offline"))
                lbl = QLabel("Offline")
                lbl.setStyleSheet("color:#8b949e;font-size:12px")
            
            sl.addWidget(lbl)
            sl.addStretch()
            self.table.setCellWidget(r, 3, status_w)
            
            pub = p.get("wg_public_key", "")
            trunc_pub = f"{pub[:8]}...{pub[-8:]}" if len(pub) > 16 else pub
            self.table.setItem(r, 4, QTableWidgetItem(trunc_pub))

    def _on_error(self, err):
        self.refresh_btn.setText("Refresh")
        self.refresh_btn.setEnabled(True)
        if "No WireGuard server claimed" in err:
            self.content_w.hide()
            self.empty_w.show()
            self.sub_lbl.setText("No server claimed yet")
        else:
            # pyrefly: ignore [missing-import]
            from widgets.common import AlertBar
            if not hasattr(self, "_alert"):
                self._alert = AlertBar(self)
                self.layout().insertWidget(0, self._alert)
            self._alert.show_error(err)

    def _show_claim_window(self):
        # pyrefly: ignore [missing-import]
        from windows.claim_network_window import ClaimNetworkWindow
        self._claim_win = ClaimNetworkWindow(self.api)
        self._claim_win.claim_success.connect(self._on_claim_success)
        self._claim_win.show()

    def _on_claim_success(self):
        self._claim_win.close()
        self.refresh()


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW (Master / Admin / Trusted)
# ═══════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    logged_out = pyqtSignal()

    def __init__(self, api, user_info: dict):
        super().__init__()
        self.api = api
        self.user = user_info
        role = user_info.get("role", "")
        self.is_master = role in ("master", "second_master")

        self.setMinimumSize(1100, 700)
        self.setStyleSheet(APP_STYLE)

        self._net_monitor = NetworkMonitor(self._on_network_change)
        self._net_monitor.start()

        # pyrefly: ignore [missing-import]
        from services.websocket_client import ws_client
        # pyrefly: ignore [missing-attribute]
        ws_client.user_updated.connect(self._check_user_compliance)

        self._build()
        if self.is_master:
            self._nav("dashboard")
        else:
            self._nav("devices")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._do_refresh)
        self._timer.start(30000)

        # Keep the banner text updated every minute
        self._banner_timer = QTimer(self)
        self._banner_timer.timeout.connect(self._update_offline_banner)
        self._banner_timer.start(60000)

    def _do_refresh(self):
        page = getattr(self, "_pages", {}).get(self._current_page, getattr(self, "_pages", {}).get("devices"))
        if page:
            page.refresh()
        QTimer.singleShot(1000, self._update_offline_banner)

        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._run_offline_sync)
        self._sync_timer.start(15000)

    def _run_offline_sync(self):
        from widgets.common import Worker
        self._sync_worker = Worker(self.api.sync_offline_queue)
        self._sync_worker.error.connect(self._on_sync_error)
        self._sync_worker.start()

    def _on_sync_error(self, e):
        if "Token expired while offline" in str(e):
            from PyQt6.QtWidgets import QMessageBox
            self._sync_timer.stop()
            QMessageBox.critical(self, "Session Expired", "Your session has expired while offline. Please log in again to sync your changes.")
            self._logout()

    def _check_user_compliance(self):
        try:
            me = self.api.get_me()
            if me.get("force_2fa") and not me.get("totp_enabled"):
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "2FA Required", "Two-factor authentication is now required globally. You have been logged out.")
                self._logout()
        except Exception:
            pass

    def _on_network_change(self):
        QTimer.singleShot(0, self._handle_network_change)

    def _handle_network_change(self):
        # pyrefly: ignore [missing-import]
        from services.network_monitor import _get_active_interface
        ip = _get_active_interface()
        page = getattr(self, "_pages", {}).get(self._current_page, getattr(self, "_pages", {}).get("devices"))
        if page:
            page.refresh()
            
        # Give the API request a moment to resolve and populate last_cached_at
        QTimer.singleShot(500, self._update_offline_banner)
        
        # Give the API request a moment to resolve and populate last_cached_at
        QTimer.singleShot(500, self._update_offline_banner)

    def _update_offline_banner(self):
        import time
        is_offline = getattr(self.api, "is_offline", False)
        if is_offline:
            cached_at = getattr(self.api, "last_cached_at", 0)
            if cached_at > 0:
                mins = int((time.time() - cached_at) / 60)
                self._offline_banner.setText(f"Offline Mode — Last synced: {mins} mins ago")
            else:
                self._offline_banner.setText("Offline Mode — No cached data available")
            self._offline_banner.show()
        else:
            self._offline_banner.hide()

    def _build(self):
        root = QWidget(); root.setObjectName("root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # ── Sidebar ─────────────────────────────────────────────
        sidebar = QFrame(); sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_W)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)

        logo_w = QWidget()
        logo_w.setStyleSheet("background:#0d1b2a;border-bottom:1px solid rgba(255,255,255,0.06)")
        ll = QHBoxLayout(logo_w); ll.setContentsMargins(18, 20, 18, 18)
        icon = QLabel()
        icon.setFixedSize(32, 32)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(load_icon(asset_path("logo-square.svg"), 32).pixmap(32, 32))
        logo_name = QLabel("ProjectX"); logo_name.setStyleSheet("font-weight:700;font-size:18px;color:#fff")
        ll.addWidget(icon); ll.addWidget(logo_name); ll.addStretch()
        sb.addWidget(logo_w)

        user_w = QWidget(); user_w.setStyleSheet("border-bottom:1px solid rgba(255,255,255,0.06)")
        ul = QHBoxLayout(user_w); ul.setContentsMargins(18, 14, 18, 14); ul.setSpacing(12)
        self._sidebar_av = QLabel((self.user.get("full_name") or "U")[0].upper())
        self._sidebar_av.setFixedSize(38, 38); self._sidebar_av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sidebar_av.setStyleSheet("background:#2563eb;color:white;border-radius:19px;font-weight:700;font-size:15px")
        ul.addWidget(self._sidebar_av)
        uc = QVBoxLayout(); uc.setSpacing(2)
        self._sidebar_uname = QLabel(self.user.get("full_name", ""))
        self._sidebar_uname.setStyleSheet("font-weight:600;font-size:14px;color:#fff")
        try:
            # pyrefly: ignore [missing-import]
            from client.styles import ROLE_COLORS
        except ImportError:
            # pyrefly: ignore [missing-import]
            from styles import ROLE_COLORS
        role = self.user.get("role", "")
        bg, fg = ROLE_COLORS.get(role, ("#f1f5f9", "#64748b"))
        urole = QLabel(role.replace("_"," ").title())
        urole.setStyleSheet(f"background:{bg};color:{fg};padding:2px 8px;border:1px solid transparent;border-radius:10px;font-size:11px;font-weight:600")
        uc.addWidget(self._sidebar_uname)
        uc.addWidget(urole, alignment=Qt.AlignmentFlag.AlignLeft)
        ul.addLayout(uc); ul.addStretch()
        sb.addWidget(user_w)

        if self.is_master:
            nav_items = [
                ("dashboard", asset_path("grid.svg"), "Dashboard"),
                ("devices", asset_path(ICON_MONITOR), "Devices"),
                ("wgtunnel", asset_path("shield.svg"), "WG Tunnel"),
                ("users", asset_path(ICON_USERS), "Users"),
                ("audit", asset_path("file.svg"), "Audit Log"),
                ("settings", asset_path("settings.svg"), "Settings")
            ]
        else:
            nav_items = [
                ("devices", asset_path(ICON_MONITOR), "Devices"),
                ("settings", asset_path("settings.svg"), "Settings")
            ]

        self._nav_btns = {}
        for key, icon_src, label in nav_items:
            btn = QPushButton(f"  {label}")
            btn.setObjectName("nav-btn")
            btn.setProperty("active", False)
            if icon_src:
                btn.setProperty("icon_src", str(icon_src))
                btn.setIcon(load_icon(icon_src, 20, tint="#94a3b8"))
                btn.setIconSize(QSize(20, 20))
            btn.clicked.connect(lambda _, k=key: self._nav(k))
            sb.addWidget(btn)
            self._nav_btns[key] = btn

        sb.addStretch()
        tun_name = "WireGuard" if TUNNEL_MODE == "wireguard" else "ZeroTier"
        is_running = is_tunnel_running()
        zt_lbl = QLabel(f"● {tun_name} Active" if is_running else f"○ {tun_name} Inactive")
        color = "#4ade80" if is_running else "#f87171"
        zt_lbl.setStyleSheet(f"color:{color};font-size:12px;padding:8px 18px")
        sb.addWidget(zt_lbl)

        logout_btn = QPushButton("  Logout")
        logout_btn.setObjectName("nav-logout")
        logout_btn.setProperty("icon_src", str(asset_path("logout.svg")))
        logout_btn.setIcon(load_icon(asset_path("logout.svg"), 20, tint="#f87171"))
        logout_btn.setIconSize(QSize(20, 20))
        logout_btn.clicked.connect(self._logout)
        sb.addWidget(logout_btn)
        h.addWidget(sidebar)

        # ── Content ─────────────────────────────────────────────
        content = QWidget()
        content.setObjectName("main-content")
        content.setStyleSheet("QWidget#main-content { background: #f0f4f8; }")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(36, 32, 36, 32)
        cl.setSpacing(16)
        
        self._offline_banner = QLabel("Offline — showing cached data")
        self._offline_banner.setStyleSheet("background:#f59e0b; color:white; padding:10px; font-weight:bold; font-size:13px; border-radius:6px;")
        self._offline_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_banner.hide()
        cl.addWidget(self._offline_banner)

        nav_bar = QHBoxLayout()
        nav_bar.setContentsMargins(0, 0, 0, 0)
        self._back_btn = QPushButton("Back")
        self._back_btn.setObjectName("btn-ghost")
        self._back_btn.setIcon(load_icon(asset_path("back.svg"), 18, tint="#64748b"))
        self._back_btn.setFixedHeight(36)
        self._back_btn.clicked.connect(self._go_back)
        nav_bar.addWidget(self._back_btn)
        nav_bar.addStretch()
        cl.addLayout(nav_bar)

        self._stack = QStackedWidget()
        self._pages = {
            "dashboard": DashboardPage(self.api, self.user),
            "devices":   DevicesPage(self.api, self.user),
            "audit":     AuditPage(self.api),
            "settings":  SettingsPage(self.api, self.user),
            "wgtunnel":  WgTunnelPage(self.api, self.user),
        }
        self._pages["dashboard"].manage_devices_requested.connect(lambda: self._nav("devices"))
        self._pages["dashboard"].view_logs_requested.connect(lambda: self._nav("audit"))
        self._pages["settings"].profile_updated.connect(self.update_sidebar_user)
        if self.is_master:
            # pyrefly: ignore [bad-typed-dict-key]
            self._pages["users"] = UsersPage(self.api)
            self._pages["dashboard"].add_user_requested.connect(
                # pyrefly: ignore [missing-attribute]
                lambda: (self._nav("users"), self._pages["users"]._add_user())
            )
            self._pages["dashboard"].manage_users_requested.connect(lambda: self._nav("users"))

        for p in self._pages.values():
            self._stack.addWidget(p)

        cl.addWidget(self._stack)
        h.addWidget(content)
        self._nav_history = []

    def _nav(self, key: str, push_history: bool = True):
        current = getattr(self, "_current_page", None)
        if push_history and current and current != key:
            self._nav_history.append(current)
        self._current_page = key
        for k, btn in self._nav_btns.items():
            btn.setProperty("active", k == key)
            icon_src = btn.property("icon_src")
            if icon_src:
                tint = "#ffffff" if k == key else "#94a3b8"
                btn.setIcon(load_icon(icon_src, 20, tint=tint))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._back_btn.setEnabled(bool(self._nav_history))
        self._stack.setCurrentWidget(self._pages[key])
        self._pages[key].refresh()

    def _go_back(self):
        if not self._nav_history:
            return
        previous = self._nav_history.pop()
        self._nav(previous, push_history=False)

    def _logout(self):
        if hasattr(self, '_timer'):
            self._timer.stop()
        if hasattr(self, '_net_monitor'):
            self._net_monitor.stop()
        self.api.token = None
        self.logged_out.emit()
        self.close()

    def update_sidebar_user(self, full_name: str):
        self.user["full_name"] = full_name
        self._sidebar_uname.setText(full_name)
        if full_name:
            self._sidebar_av.setText(full_name[0].upper())

def _confirm_delete(parent, title: str, body: str) -> bool:
    from PyQt6.QtWidgets import QMessageBox
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(body)
    box.setIcon(QMessageBox.Icon.Warning)
    yes_btn = box.addButton("Yes, remove", QMessageBox.ButtonRole.DestructiveRole)
    no_btn  = box.addButton("Cancel",      QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(no_btn)
    box.exec()
    return box.clickedButton() == yes_btn

def _prompt_sensitive_action(parent: QWidget, user_info: dict, title: str, message: str, worker_callback) -> None:
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox

    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setFixedSize(400, 240)
    dlg.setStyleSheet("QDialog{background:#f1f5f9} QLabel{background:transparent;color:#0f172a} QLineEdit{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:9px;font-size:14px;color:#0f172a}")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(28, 28, 28, 28)
    lay.setSpacing(14)
    
    msg_lbl = QLabel(message)
    msg_lbl.setStyleSheet("font-size:14px;font-weight:400;color:#0f172a;background:transparent")
    lay.addWidget(msg_lbl)
    
    code_in = None
    if user_info and user_info.get("totp_enabled"):
        lbl = QLabel("Enter 6-digit 2FA Code to confirm:")
        lbl.setStyleSheet("font-size:13px;font-weight:700;color:#0f172a;background:transparent")
        lay.addWidget(lbl)
        code_in = QLineEdit()
        code_in.setPlaceholderText("123456")
        code_in.setMaxLength(6)
        lay.addWidget(code_in)
    
    lay.addStretch()
    
    btns = QHBoxLayout()
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setStyleSheet("QPushButton{background:white;color:#0f172a;border:1px solid #e2e8f0;border-radius:8px;padding:9px 18px;font-size:14px} QPushButton:hover{background:#f8fafc} QPushButton:focus{border:2px solid #2563eb; outline:none;}")
    cancel_btn.clicked.connect(dlg.reject)
    
    ok_btn = QPushButton("Yes, Confirm")
    ok_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600} QPushButton:hover{background:#1d4ed8}")
    
    def on_ok():
        if code_in:
            code = code_in.text().strip()
            if not code:
                QMessageBox.warning(dlg, "Error", "2FA code is required.")
                return
            worker_callback(code)
        else:
            worker_callback(None)
        dlg.accept()
        
    ok_btn.clicked.connect(on_ok)
    
    btns.addWidget(cancel_btn)
    btns.addWidget(ok_btn)
    lay.addLayout(btns)
    
    cancel_btn.setDefault(True)
    ok_btn.setAutoDefault(False)
    cancel_btn.setFocus()
    
    dlg.exec()
