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
def is_tunnel_running():
    return True
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

        role = self.user.get("role", "")
        is_master = role in ("master", "second_master")
        tenant = self.user.get("company") or ""
        network = self.user.get("network_id") or ""
        subtitle = f"Role: {role.replace('_', ' ').title()}"

        hdr_row = QHBoxLayout()
        hdr = PageHeader("SetuLink Dashboard", subtitle)
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
        self._s_online  = StatCard("Claimed Routers",    "—", color="#16a34a", icon_path=asset_path(ICON_MONITOR))
        self._s_pending = StatCard("Pending Sync",  "—", color="#ea580c", icon_path=asset_path("clock.svg"))
        self._s_users   = StatCard("Total Users",       "—", color="#2563eb", icon_path=asset_path(ICON_USERS))
        self._s_offline = StatCard("Pending Sync",   "—", color="#dc2626", icon_path=asset_path("wifi-off.svg"))
        
        cards_to_add = [self._s_online]
        if is_master:
            cards_to_add.extend([self._s_pending, self._s_users])
        cards_to_add.append(self._s_offline)
        
        for c in cards_to_add:
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            stats_row.addWidget(c)
        lay.addLayout(stats_row)

        # Routers
        self._dev_card = CardWithHeader("Routers", "Manage All")
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
        
        # Desktops
        self._desk_card = CardWithHeader("Desktops", "Manage All")
        self._desk_list = QWidget(); self._desk_list.setStyleSheet("background:white")
        self._desk_vlay = QVBoxLayout(self._desk_list)
        self._desk_vlay.setContentsMargins(0, 0, 0, 0)
        self._desk_vlay.setSpacing(0)
        self._desk_vlay.addStretch()
        self._desk_card.add_widget(self._desk_list)
        
        if is_master:
            bottom.addWidget(self._users_card)
        bottom.addWidget(self._desk_card)
        
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
            self.api.get_routers(),
            [],
            self.api.get_users() if is_master else [],
            self.api.get_desktops() if is_master else [],
        ))
        self._w.result.connect(self._on_data)
        self._w.error.connect(lambda e: print("Dashboard error:", e))
        self._w.start()

    def _on_data(self, data):
        routers, pending, users, desktops = data
        active = [r for r in routers if r.get("status") == "claimed"]
        offline = [r for r in routers if r.get("status") == "pending_validation"]
        self._s_online.set_value(len(active))
        self._s_pending.set_value(len(offline))
        self._s_users.set_value(len(users))
        self._s_offline.set_value(len(offline))

        self._fill_list(self._dev_vlay, [
            {"main": r.get("name", ""), "sub": f"Serial: {r.get('serial_number','—')} · MAC: {r.get('mac_address','—')}",
             "dot": "active" if r.get("status") == "claimed" else "connecting"} for r in routers[:5]
        ], dot=True)

        if users:
            self._fill_list(self._users_vlay, [
                {"main": u.get("full_name", ""), "badge": u.get("role", ""), "badge_type": "role"}
                for u in users[:5]
            ])
            
        if desktops:
            self._fill_list(self._desk_vlay, [
                {"main": d.get("device_name", ""), "sub": f"User: {d.get('user_name', '')}", "dot": "active" if d.get("tunnel_state") == "connected" else "offline"}
                for d in desktops[:5]
            ], dot=True)

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
class ClaimDialog(QDialog):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Claim Prepared Router")
        self.setFixedSize(380, 240)
        self.setStyleSheet("QDialog{background:#f1f5f9;} QLabel{background:transparent;color:#0f172a;} QLineEdit{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px;font-size:13px;color:#0f172a;}")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        title = QLabel("Claim Router")
        title.setStyleSheet("font-size:15px;font-weight:700;color:#0f172a;")
        layout.addWidget(title)

        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("Serial Number (e.g. SN-XXXX)")
        layout.addWidget(self.serial_input)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Activation Key Code")
        layout.addWidget(self.key_input)

        layout.addSpacing(10)
        buttons = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("QPushButton{background:white;color:#475569;border:1px solid #cbd5e1;border-radius:6px;padding:6px 16px;} QPushButton:hover{background:#f1f5f9;}")
        self.cancel_btn.clicked.connect(self.reject)
        self.claim_btn = QPushButton("Claim Router")
        self.claim_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:6px;padding:6px 16px;font-weight:bold;} QPushButton:hover{background:#1d4ed8;}")
        self.claim_btn.clicked.connect(self.accept)

        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.claim_btn)
        layout.addLayout(buttons)

class RenameDialog(QDialog):
    def __init__(self, current_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rename Router")
        self.setFixedSize(360, 160)
        self.setStyleSheet("QDialog{background:#f1f5f9;} QLabel{background:transparent;color:#0f172a;} QLineEdit{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px;font-size:13px;color:#0f172a;}")
        self._build_ui(current_name)

    def _build_ui(self, current_name):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        title = QLabel("Rename Router")
        title.setStyleSheet("font-size:14px;font-weight:700;color:#0f172a;")
        layout.addWidget(title)

        self.name_input = QLineEdit()
        self.name_input.setText(current_name)
        self.name_input.setPlaceholderText("New Name")
        layout.addWidget(self.name_input)

        layout.addSpacing(6)
        buttons = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("QPushButton{background:white;color:#475569;border:1px solid #cbd5e1;border-radius:6px;padding:6px 16px;} QPushButton:hover{background:#f1f5f9;}")
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:6px;padding:6px 16px;font-weight:bold;} QPushButton:hover{background:#1d4ed8;}")
        self.save_btn.clicked.connect(self.accept)

        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.save_btn)
        layout.addLayout(buttons)

class DevicesPage(QWidget):
    def __init__(self, api, user: dict):
        super().__init__()
        self.api = api
        self.user = user
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)

        self._alert = AlertBar()
        lay.addWidget(self._alert)

        role = self.user.get("role", "")
        is_master = role in ("master", "second_master")

        hdr_row = QHBoxLayout()
        hdr = PageHeader("Routers", "All claimed and pending routers for your tenant")
        hdr_row.addWidget(hdr, 1)
        if is_master:
            add_btn = QPushButton("+ Claim Router")
            add_btn.setObjectName("btn-primary")
            add_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600}")
            add_btn.setFixedHeight(38)
            add_btn.clicked.connect(self._show_claim_dialog)
            hdr_row.addWidget(add_btn)
        lay.addLayout(hdr_row)

        stats_row = QHBoxLayout(); stats_row.setSpacing(16)
        self._s_online  = StatCard("Claimed",     "—", color="#16a34a", icon_path=asset_path(ICON_MONITOR))
        self._s_conn    = StatCard("Pending Sync", "—", color="#d97706", icon_path=asset_path("clock.svg"))
        self._s_offline = StatCard("Offline Queue",    "—", color="#dc2626", icon_path=asset_path("wifi-off.svg"))
        
        cards_to_add = [self._s_online, self._s_conn, self._s_offline]
        for c in cards_to_add:
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            stats_row.addWidget(c)
        lay.addLayout(stats_row)

        self.card = CardWithHeader("Routers List")
        self.card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        is_admin = self.api._user.get("role") == "admin" if hasattr(self.api, "_user") and self.api._user else False

        if is_admin:
            headers = ["Router ID", "Name", "Status"]
            self._tbl = make_table(headers)
            self._tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            hh = self._tbl.horizontalHeader()
            for col in range(3):
                hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self._tbl.setColumnWidth(0, 200)
            self._tbl.setColumnWidth(2, 200)
        else:
            headers = ["Router ID", "Name", "Serial Number", "MAC Address", "ZeroTier ID", "Status", "Actions"]
            self._tbl = make_table(headers)
            self._tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            hh = self._tbl.horizontalHeader()
            for col in range(7):
                hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self._tbl.setColumnWidth(0, 100)
            self._tbl.setColumnWidth(2, 110)
            self._tbl.setColumnWidth(3, 140)
            self._tbl.setColumnWidth(4, 200)
            self._tbl.setColumnWidth(5, 110)
            self._tbl.setColumnWidth(6, 200)
        self.card.add_widget(self._tbl)
        lay.addWidget(self.card, 1)
        lay.addStretch()

    def refresh(self):
        if hasattr(self, "_w"):
            try:
                if self._w.isRunning():
                    return
            except RuntimeError:
                pass
        self._w = Worker(self.api.get_routers)
        self._w.result.connect(self._on_data)
        self._w.error.connect(self._alert.show_error)
        self._w.start()

    def _on_data(self, routers: list):
        from services.cache_service import cache_service
        actions = cache_service.get_offline_actions()
        
        # Inject offline claims if they aren't already in the list
        existing_sns = {r.get("serial_number") for r in routers}
        current_uid = self.api._user.get("id") if hasattr(self.api, "_user") and self.api._user else None
        
        offline_claims = []
        for a in actions:
            if a["action"] == "claim_router":
                payload_uid = a["payload"].get("_offline_user_id")
                # Fallback to None for old cache items
                if payload_uid == current_uid or payload_uid is None:
                    offline_claims.append(a)
        for claim in offline_claims:
            sn = claim["payload"].get("serial_number")
            if sn and sn not in existing_sns:
                import uuid
                mock_id = int(uuid.uuid4().int >> 96)
                routers.append({
                    "id": mock_id,
                    "router_id": "Offline-Prep",
                    "serial_number": sn,
                    "mac_address": "unknown",
                    "status": "pending_validation",
                    "name": f"Pending Claim: {sn}"
                })
                existing_sns.add(sn)
        
        self._routers = routers
        claimed = [r for r in routers if r.get("status") == "claimed"]
        pending = [r for r in routers if r.get("status") == "pending_validation"]
        
        self._s_online.set_value(len(claimed))
        self._s_conn.set_value(len(pending))
        self._s_offline.set_value(len(actions))

        t = self._tbl
        t.setUpdatesEnabled(False)
        t.setRowCount(0)
        
        for r in routers:
            row_idx = t.rowCount()
            t.insertRow(row_idx)
            is_admin = self.api._user.get("role") == "admin" if hasattr(self.api, "_user") and self.api._user else False

            if is_admin:
                t.setItem(row_idx, 0, table_item(r.get("router_id", "—")))
                t.setItem(row_idx, 1, table_item(r.get("name", "—")))
                
                status = r.get("status", "pending_validation")
                bg, fg = ("#dcfce7", "#166534") if status == "claimed" else ("#fef3c7", "#92400e")
                badge = Badge(status.replace("_", " ").title(), bg, fg)
                status_w = QWidget()
                sl = QHBoxLayout(status_w)
                sl.setContentsMargins(6, 6, 6, 6)
                sl.addStretch()
                sl.addWidget(badge)
                sl.addStretch()
                t.setCellWidget(row_idx, 2, status_w)
            else:
                t.setItem(row_idx, 0, table_item(r.get("router_id", "—")))
                t.setItem(row_idx, 1, table_item(r.get("name", "—")))
                t.setItem(row_idx, 2, table_item(r.get("serial_number", "—")))
                t.setItem(row_idx, 3, table_item(r.get("mac_address", "—")))
                t.setItem(row_idx, 4, table_item(r.get("zerotier_node_id", "—")))
                
                # Status badge
                status = r.get("status", "pending_validation")
                bg, fg = ("#dcfce7", "#166534") if status == "claimed" else ("#fef3c7", "#92400e")
                badge = Badge(status.replace("_", " ").title(), bg, fg)
                status_w = QWidget()
                sl = QHBoxLayout(status_w)
                sl.setContentsMargins(6, 6, 6, 6)
                sl.addStretch()
                sl.addWidget(badge)
                sl.addStretch()
                t.setCellWidget(row_idx, 5, status_w)

                # Actions row
                btn_w = QWidget()
                btn_l = QHBoxLayout(btn_w)
                btn_l.setContentsMargins(4, 4, 4, 4)
                btn_l.setSpacing(6)
                btn_l.addStretch()

                rename = QPushButton("Rename")
                rename.setStyleSheet("QPushButton{background:white;color:#374151;border:1px solid #cbd5e1;border-radius:6px;padding:4px 10px;font-size:12px} QPushButton:hover{background:#f3f4f6}")
                rename.clicked.connect(lambda _, rid=r["id"], nm=r.get("name",""): self._rename(rid, nm))
                btn_l.addWidget(rename)

                if status == "pending_validation":
                    sync = QPushButton("Sync")
                    sync.setStyleSheet("QPushButton{background:#dcfce7;color:#15803d;border:1px solid #bbf7d0;border-radius:6px;padding:4px 10px;font-size:12px} QPushButton:hover{background:#bbf7d0}")
                    sync.clicked.connect(lambda _, rid=r["id"]: self._sync(rid))
                    btn_l.addWidget(sync)

                btn_l.addStretch()
                t.setCellWidget(row_idx, 6, btn_w)
            
        t.setUpdatesEnabled(True)

        row_height = 54
        header_height = 42
        num_rows = len(routers)
        total_height = header_height + (num_rows * row_height) + 2
        t.setFixedHeight(total_height)

    def _show_claim_dialog(self):
        dlg = ClaimDialog(self.api, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            serial = dlg.serial_input.text().strip()
            key = dlg.key_input.text().strip()
            if not serial or not key:
                return
            self._cw = Worker(self.api.claim_router, serial, key)
            self._cw.result.connect(lambda _: (self.refresh(), self._alert.show_success("Router claimed successfully")))
            self._cw.error.connect(self._alert.show_error)
            self._cw.start()

    def _rename(self, rid: int, current_name: str):
        dlg = RenameDialog(current_name, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_name = dlg.name_input.text().strip()
            if not new_name:
                return
            self._rnw = Worker(self.api.rename_router, rid, new_name)
            self._rnw.result.connect(lambda _: (self.refresh(), self._alert.show_success("Router rename queued")))
            self._rnw.error.connect(self._alert.show_error)
            self._rnw.start()

    def _sync(self, rid: int):
        self._syw = Worker(self.api.sync_router, rid)
        self._syw.result.connect(lambda _: (self.refresh(), self._alert.show_success("Router sync complete")))
        self._syw.error.connect(self._alert.show_error)
        self._syw.start()

    def _share(self, rid: int, name: str):
        dlg = ShareDeviceDialog(rid, name, self.api, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            uid = dlg.user_in.currentData()
            if not uid:
                return
            self._shw = Worker(self.api.share_router, rid, uid)
            self._shw.result.connect(lambda _: (self.refresh(), self._alert.show_success(f"Router shared with user")))
            self._shw.error.connect(self._alert.show_error)
            self._shw.start()


class ShareDeviceDialog(QDialog):
    def __init__(self, device_id: int, device_name: str, api, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self.device_name = device_name
        self.api = api
        self.setWindowTitle("Share Device")
        self.setFixedSize(360, 180)
        self.setStyleSheet("QDialog{background:white;} QLabel{background:transparent;color:#0f172a;} QComboBox{background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:8px;font-size:13px;}")
        self._build_ui()
        self._load_users()

    def _load_users(self):
        self._tw = Worker(self.api.get_users)
        self._tw.result.connect(self._on_users)
        self._tw.error.connect(lambda e: self.user_in.setItemText(0, "Failed to load users"))
        self._tw.start()

    def _on_users(self, users: list):
        self.user_in.clear()
        if not users:
            self.user_in.addItem("No users found", None)
            return
            
        current_user_id = self.api._user.get("id") if self.api._user else None
        valid_users = [u for u in users if u.get("id") != current_user_id]
        
        if not valid_users:
            self.user_in.addItem("No other users found", None)
            return
            
        self.user_in.addItem("— Select a User —", None)
        for u in valid_users:
            self.user_in.addItem(f"{u.get('full_name')} ({u.get('role')})", u["id"])

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        
        lbl = QLabel(f"Share <b>{self.device_name}</b> with another user.")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        
        lay.addWidget(QLabel("Target User:"))
        self.user_in = QComboBox()
        self.user_in.addItem("Loading...", None)
        lay.addWidget(self.user_in)
        
        lay.addStretch()
        
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet("QPushButton{background:white;color:#475569;border:1px solid #cbd5e1;border-radius:6px;padding:6px 16px;} QPushButton:hover{background:#f1f5f9;}")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        
        self.ok_btn = QPushButton("Share")
        self.ok_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:6px;padding:6px 16px;font-weight:bold;} QPushButton:hover{background:#1d4ed8;}")
        self.ok_btn.clicked.connect(self.accept)
        btns.addWidget(self.ok_btn)
        
        lay.addLayout(btns)



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
            devs = self.api.get_routers()
            assigned = self.api.get_user_shares(self.user_id)
            return devs, assigned
        self._w = Worker(fetch)
        self._w.result.connect(self._populate)
        self._w.start()

    def _populate(self, data):
        self.devices, self.assigned_ids = data
        self.devices = [d for d in self.devices if d.get("status") == "claimed"]
        
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
            self._sw = Worker(self.api.revoke_router_share, device_id, self.user_id)
        else:
            self._sw = Worker(self.api.share_router, device_id, self.user_id)
            
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
        self._tbl = make_table(["NAME", "EMAIL", "ROLE", "2FA", "TRUSTED", "ACTIONS"])
        self._tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        hh = self._tbl.horizontalHeader()
        for c in range(6):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(True)
        
        self._tbl.setColumnWidth(0, 160) # NAME
        self._tbl.setColumnWidth(1, 200) # EMAIL
        self._tbl.setColumnWidth(2, 120) # ROLE
        self._tbl.setColumnWidth(3, 150)  # 2FA
        self._tbl.setColumnWidth(4, 125) # TRUSTED
        self._tbl.setColumnWidth(5, 320) # ACTIONS
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

        if role == "master":
            t.setItem(r, 5, table_item("-", Qt.AlignmentFlag.AlignCenter))
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



            rem = QPushButton("Remove")
            rem.setObjectName("btn-danger")
            rem.setFixedSize(75, 30)
            rem.clicked.connect(lambda _, uid=u["id"], nm=u.get("full_name",""): self._remove_user(uid, nm))
            btn_l.addWidget(fa_btn)
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
            elif role == "admin":
                assign_btn = QPushButton("Assign")
                assign_btn.setObjectName("btn-sm")
                assign_btn.setFixedSize(75, 30)
                assign_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                assign_btn.setStyleSheet(
                    "QPushButton { background: #dbeafe; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 6px; font-weight: 600; }"
                    "QPushButton:hover { background: #bfdbfe; }"
                )
                assign_btn.clicked.connect(lambda _, uid=u["id"], nm=u.get("full_name",""): self._open_assign_dialog(uid, nm))
                btn_l.addWidget(assign_btn)

            btn_l.addWidget(rem)
            btn_l.addStretch()
            t.setCellWidget(r, 5, btn_w)


    def _toggle_trust(self, user_id: int, is_trusted: bool):
        self._tw = Worker(self.api.toggle_trust, user_id, is_trusted)
        self._tw.result.connect(lambda _: self.refresh())
        self._tw.error.connect(self._alert.show_error)
        self._tw.start()

    def _toggle_force_2fa(self, user_id: int, current_force: bool):
        self._tf = Worker(self.api.toggle_force_otp, user_id, not current_force)
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
            self._cuw = Worker(self.api.create_user, email_in.text(), name_in.text(), role_key)
            def on_ok(data):
                QMessageBox.information(dlg, "Success", f"User created!\n\nAn email has been sent to {data['email']} with their temporary password.\n\nPlease instruct the user to check their inbox.")
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
        if QMessageBox.question(self.window(), "Confirm Removal", f"Are you sure you want to remove {name}?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._rw = Worker(self.api.delete_user, uid)
        self._rw.result.connect(lambda _: self.refresh())
        self._rw.error.connect(self._alert.show_error)
        self._rw.start()

    def _demote_user(self, uid: int, name: str):
        if QMessageBox.question(self.window(), "Confirm Demotion", f"Are you sure you want to demote {name} to Admin User?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._dw = Worker(self.api.update_user_role, uid, "admin")
        self._dw.result.connect(lambda _: self.refresh())
        self._dw.error.connect(self._alert.show_error)
        self._dw.start()


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

        lay.addLayout(grid)

        grid2 = QHBoxLayout(); grid2.setSpacing(20)

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

    def refresh(self):
        pass

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
        if hasattr(self, "_w"):
            try:
                if self._w.isRunning():
                    return
            except RuntimeError:
                pass
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
#  DESKTOPS PAGE
# ═══════════════════════════════════════════════════════════════════════════════
class DesktopsPage(QWidget):
    def __init__(self, api, user: dict):
        super().__init__()
        self.api = api
        self.user = user
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)

        self._alert = AlertBar()
        lay.addWidget(self._alert)

        hdr_row = QHBoxLayout()
        hdr = PageHeader("Desktops", "All connected desktops for your tenant")
        hdr_row.addWidget(hdr, 1)
        lay.addLayout(hdr_row)

        self.card = CardWithHeader("Desktops List")
        self.card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        headers = ["Desktop Name", "User", "Email", "WG IP", "Status", "Last Seen"]
        self._tbl = make_table(headers)
        self._tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hh = self._tbl.horizontalHeader()
        for col in range(6):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tbl.setColumnWidth(1, 150)
        self._tbl.setColumnWidth(2, 200)
        self._tbl.setColumnWidth(3, 110)
        self._tbl.setColumnWidth(4, 110)
        self._tbl.setColumnWidth(5, 140)
        
        self.card.add_widget(self._tbl)
        lay.addWidget(self.card, 1)
        lay.addStretch()

    def refresh(self):
        self._w = Worker(self.api.get_desktops)
        self._w.result.connect(self._on_data)
        self._w.error.connect(self._alert.show_error)
        self._w.start()

    def _on_data(self, desktops: list):
        t = self._tbl
        t.setUpdatesEnabled(False)
        t.setRowCount(0)
        
        for d in desktops:
            row_idx = t.rowCount()
            t.insertRow(row_idx)
            
            t.setItem(row_idx, 0, table_item(d.get("device_name", "—")))
            t.setItem(row_idx, 1, table_item(d.get("user_name", "—")))
            t.setItem(row_idx, 2, table_item(d.get("user_email", "—")))
            t.setItem(row_idx, 3, table_item(d.get("wg_ip", "—")))
            
            status = d.get("tunnel_state", "disconnected")
            bg, fg = ("#dcfce7", "#166534") if status == "connected" else ("#f1f5f9", "#64748b")
            badge = Badge(status.title(), bg, fg)
            status_w = QWidget()
            sl = QHBoxLayout(status_w)
            sl.setContentsMargins(6, 6, 6, 6)
            sl.addStretch()
            sl.addWidget(badge)
            sl.addStretch()
            t.setCellWidget(row_idx, 4, status_w)
            
            seen = d.get("last_seen", "")
            t.setItem(row_idx, 5, table_item(_fmt_date(seen) if seen else "Never"))

        t.setUpdatesEnabled(True)

        row_height = 54
        header_height = 42
        num_rows = len(desktops)
        total_height = header_height + (num_rows * row_height) + 2
        t.setFixedHeight(total_height)


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

        self._build()
        if self.is_master:
            self._nav("dashboard")
        else:
            self._nav("devices")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._do_refresh)
        self._timer.start(30000)

        self._banner_timer = QTimer(self)
        self._banner_timer.timeout.connect(self._update_offline_banner)
        self._banner_timer.start(60000)
        self._init_wireguard()

    def _init_wireguard(self):
        from services.wireguard_local import wireguard_local
        import socket
        try:
            pubkey, _ = wireguard_local.generate_or_load_keys()
            hostname = socket.gethostname()
            config = self.api.register_desktop(pubkey, hostname)
            wireguard_local.start_tunnel(
                wg_ip=config["wg_ip"],
                endpoint=config["endpoint"],
                gateway_pubkey="gw_pubkey_placeholder",
                allowed_ips=config["allowed_ips"]
            )
            self._hb_timer = QTimer(self)
            self._hb_timer.timeout.connect(self._send_heartbeat)
            self._hb_timer.start(60000)
        except Exception as e:
            print(f"Failed to initialize WireGuard: {e}")

    def _send_heartbeat(self):
        from services.wireguard_local import wireguard_local
        try:
            pubkey, _ = wireguard_local.generate_or_load_keys()
            self.api.heartbeat_desktop(pubkey)
        except Exception as e:
            print(f"Failed to send heartbeat: {e}")

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
        
        # WireGuard smart reconnect: wait 5s then verify handshake
        from services.wireguard_local import wireguard_local
        QTimer.singleShot(5000, wireguard_local.reconnect_if_stale)

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

    def _update_tunnel_status(self):
        if not hasattr(self, 'tunnel_status_lbl'):
            return
        tun_name = "WireGuard" if TUNNEL_MODE == "wireguard" else "ZeroTier"
        is_running = is_tunnel_running()
        self.tunnel_status_lbl.setText(f"● {tun_name} Active" if is_running else f"○ {tun_name} Inactive")
        color = "#4ade80" if is_running else "#f87171"
        self.tunnel_status_lbl.setStyleSheet(f"color:{color};font-size:12px;padding:8px 18px")

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
                ("devices", asset_path(ICON_MONITOR), "Routers"),
                ("desktops", asset_path("monitor.svg"), "Desktops"),
                ("users", asset_path(ICON_USERS), "Users"),
                ("settings", asset_path("settings.svg"), "Settings")
            ]
        else:
            nav_items = [
                ("devices", asset_path(ICON_MONITOR), "Routers"),
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
            "settings":  SettingsPage(self.api, self.user),
        }
        self._pages["dashboard"].manage_devices_requested.connect(lambda: self._nav("devices"))
        self._pages["settings"].profile_updated.connect(self.update_sidebar_user)
        if self.is_master:
            # pyrefly: ignore [bad-typed-dict-key]
            self._pages["users"] = UsersPage(self.api)
            self._pages["desktops"] = DesktopsPage(self.api, self.user)
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
        from services.wireguard_local import wireguard_local
        try:
            wireguard_local.stop_tunnel()
        except Exception:
            pass
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
