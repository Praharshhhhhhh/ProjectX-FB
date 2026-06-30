from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QStackedWidget, QScrollArea, QTableWidget, QTableWidgetItem,
    QDialog, QLineEdit, QFormLayout, QComboBox, QMessageBox, QSizePolicy,
    QHeaderView, QAbstractItemView, QGridLayout, QApplication, QStyle
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QClipboard

# pyrefly: ignore [missing-import]
from styles import APP_STYLE, SIDEBAR_W, LEVEL_COLORS
# pyrefly: ignore [missing-import]
from widgets.common import (
    Worker, StatCard, Badge, Card, CardWithHeader, make_table,
    table_item, PageHeader, AlertBar, role_badge, status_badge, level_badge,
    asset_path, load_icon
)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGES
# ═══════════════════════════════════════════════════════════════════════════════

class OwnerDashboardPage(QWidget):
    def __init__(self, api, on_new_tenant=None, on_view_tenants=None, on_manage_keys=None):
        super().__init__()
        self.api = api
        self._on_new_tenant = on_new_tenant
        self._on_view_tenants = on_view_tenants
        self._on_manage_keys = on_manage_keys
        self._build()

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self._layout = QVBoxLayout(inner)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(20)

        self._alert = AlertBar()
        self._layout.addWidget(self._alert)

        # Header
        self._header = PageHeader("System Owner Panel", "Platform overview — all tenants and activity", "+ New Tenant")
        if self._header.action_btn and self._on_new_tenant:
            self._header.action_btn.clicked.connect(self._on_new_tenant)
        self._layout.addWidget(self._header)

        act_row = QHBoxLayout()
        self._force_2fa_btn = QPushButton("Force 2FA Globally")
        self._force_2fa_btn.setStyleSheet("QPushButton{background:#ea580c;color:white;border:none;border-radius:6px;padding:8px 16px;font-weight:bold;} QPushButton:hover{background:#c2410c;}")
        # pyrefly: ignore [missing-attribute]
        self._force_2fa_btn.clicked.connect(self._do_force_2fa_all)
        act_row.addStretch()
        act_row.addWidget(self._force_2fa_btn)
        self._layout.addLayout(act_row)

        # Stat cards
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        self._s_tenants  = StatCard("Total Tenants",  "—", color="#2563eb", icon_path=asset_path("users.svg"))
        self._s_keys     = StatCard("Pending Keys",   "—", color="#ea580c", icon_path=asset_path("key.svg"))
        self._s_devices  = StatCard("Total Routers",  "—", color="#2563eb", icon_path=asset_path("monitor.svg"))
        self._s_active   = StatCard("Active Tenants", "—", color="#16a34a", icon_path=asset_path("check.svg"))
        for c in [self._s_tenants, self._s_keys, self._s_devices, self._s_active]:
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            stats_row.addWidget(c)
        self._layout.addLayout(stats_row)

        # Recent tenants
        self._tenants_card = CardWithHeader("Recent Tenants", "View all")
        if getattr(self._tenants_card, "action_btn", None) and self._on_view_tenants:
            self._tenants_card.action_btn.clicked.connect(self._on_view_tenants)
        self._tenants_tbl = make_table(["ID", "Company Name", "Master User", "Users Count", "Status", "Action"])
        self._tenants_tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tenants_tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hh = self._tenants_tbl.horizontalHeader()
        hh.setMinimumSectionSize(44)
        for col in range(6):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._tenants_tbl.setColumnWidth(0, 60)
        self._tenants_tbl.setColumnWidth(2, 200)
        self._tenants_tbl.setColumnWidth(3, 100)
        self._tenants_tbl.setColumnWidth(4, 120)
        self._tenants_tbl.setColumnWidth(5, 120)
        self._tenants_card.add_widget(self._tenants_tbl)
        self._layout.addWidget(self._tenants_card)

        # Bottom row
        bottom = QHBoxLayout()
        bottom.setSpacing(16)
        bottom.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._keys_card = CardWithHeader("Latest Keys", "Manage")
        if getattr(self._keys_card, "action_btn", None) and self._on_manage_keys:
            self._keys_card.action_btn.clicked.connect(self._on_manage_keys)
        self._keys_list = QWidget()
        self._keys_list.setStyleSheet("background:white; border-bottom-left-radius:12px; border-bottom-right-radius:12px;")
        self._keys_vlay = QVBoxLayout(self._keys_list)
        self._keys_vlay.setContentsMargins(0, 0, 0, 0)
        self._keys_vlay.setSpacing(0)
        self._keys_vlay.addStretch()
        self._keys_card.add_widget(self._keys_list)
        bottom.addWidget(self._keys_card, alignment=Qt.AlignmentFlag.AlignTop)
        self._layout.addLayout(bottom)
        self._layout.addStretch()

        scroll.setWidget(inner)
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.addWidget(scroll)

    def refresh(self):
        self._w1 = Worker(lambda: (
            self.api.get_admin_stats(),
            self.api.get_admin_tenants(),
            self.api.get_pending_keys(),
        ))
        self._w1.result.connect(self._on_data)
        self._w1.error.connect(lambda e: print("Dashboard error:", e))
        self._w1.start()

    def _on_data(self, data):
        stats, tenants, keys = data
        self._s_tenants.set_value(stats.get("total_tenants", 0))
        self._s_keys.set_value(stats.get("pending_keys", 0))
        self._s_devices.set_value(stats.get("total_routers", 0))
        self._s_active.set_value(stats.get("active_tenants", 0))

        # Tenants table
        t = self._tenants_tbl
        t.setRowCount(0)
        for row in tenants[:8]:
            r = t.rowCount(); t.insertRow(r)
            t.setItem(r, 0, table_item(str(row.get("id"))))
            t.setItem(r, 1, table_item(row.get("company_name", "")))
            t.setItem(r, 2, table_item(row.get("master_email") or "—"))
            t.setItem(r, 3, table_item(str(row.get("user_count", 0))))
            t.setItem(r, 4, table_item(row.get("status", "pending").title()))

            cell_w = QWidget()
            cell_w.setStyleSheet("background:white")
            cell_l = QHBoxLayout(cell_w)
            cell_l.setContentsMargins(6, 6, 6, 6)
            cell_l.setSpacing(6)
            del_btn = QPushButton("Delete")
            del_btn.setFixedSize(62, 28)
            del_btn.setStyleSheet(
                "QPushButton{background:white;color:#dc2626;border:1px solid #fecaca;"
                "border-radius:6px;padding:0px;font-size:12px} QPushButton:hover{background:#fee2e2}"
            )
            del_btn.clicked.connect(lambda _, tid=row["id"], nm=row["company_name"]: self._delete_tenant(tid, nm))
            cell_l.addWidget(del_btn)
            t.setCellWidget(r, 5, cell_w)

        for rr in range(t.rowCount()):
            t.setRowHeight(rr, 54)
            
        row_height = 54
        header_height = 42
        num_rows = len(tenants[:8])
        total_height = header_height + (num_rows * row_height) + 2 if num_rows > 0 else header_height + 2
        t.setFixedHeight(total_height)

        # Keys table
        while self._keys_vlay.count() > 1:
            item = self._keys_vlay.takeAt(0)
            # pyrefly: ignore [missing-attribute]
            if item.widget():
                # pyrefly: ignore [missing-attribute]
                item.widget().deleteLater()

        for row in keys[:3]:
            row_w = QWidget()
            row_w.setStyleSheet("border-bottom:1px solid #f1f5f9")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(16, 12, 16, 12)
            rl.setSpacing(10)
            text_col = QVBoxLayout()
            key_lbl = QLabel(row.get("key_code", ""))
            key_lbl.setStyleSheet("font-size:13px;color:#0f172a;font-weight:600;background:transparent")
            meta = QLabel(f"{row.get('company_name', '—')} · {_fmt_date(row.get('created_at', ''))}")
            meta.setStyleSheet("font-size:11px;color:#64748b;background:transparent")
            text_col.addWidget(key_lbl)
            text_col.addWidget(meta)
            rl.addLayout(text_col)
            rl.addStretch()
            used = row.get("is_used")
            bg, fg = ("#f1f5f9", "#64748b") if used else ("#dbeafe", "#1d4ed8")
            status = QLabel("Used" if used else "Unused")
            status.setStyleSheet(f"background:{bg};color:{fg};padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600")
            rl.addWidget(status)
            self._keys_vlay.insertWidget(self._keys_vlay.count() - 1, row_w)

    def _delete_tenant(self, tid: int, name: str):
        if QMessageBox.question(self.window(), "Confirm Delete", f"Are you sure you want to delete tenant '{name}'? This will delete all associated data.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._dtw = Worker(self.api.delete_tenant, tid)
        # pyrefly: ignore [missing-attribute]
        self._dtw.result.connect(lambda _: (self.refresh(), self._alert.show_success("Tenant deleted")))
        # pyrefly: ignore [missing-attribute]
        self._dtw.error.connect(self._alert.show_error)
        self._dtw.start()

    def _do_force_2fa_all(self):
        if QMessageBox.question(
            self.window(), "Force 2FA Globally",
            "This will enable email OTP for ALL master and second master users across every tenant. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        self._fw = Worker(self.api.force_2fa_all)
        self._fw.result.connect(lambda r: (self.refresh(), self._alert.show_success(r.get("message", "Done"))))
        self._fw.error.connect(self._alert.show_error)
        self._fw.start()

class TenantsPage(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._tenants = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)

        self._alert = AlertBar()
        lay.addWidget(self._alert)

        hdr_row = QHBoxLayout()
        hdr = PageHeader("Tenants", "All companies using the ProjectX platform")
        hdr_row.addWidget(hdr, 1)
        hdr_btn = QPushButton("+ New Tenant")
        hdr_btn.setObjectName("btn-primary")
        hdr_btn.setFixedHeight(38)
        hdr_btn.clicked.connect(self._add_tenant)
        hdr_row.addWidget(hdr_btn)
        lay.addLayout(hdr_row)

        card = CardWithHeader("All Companies")
        top_row = QHBoxLayout()
        top_row.setContentsMargins(16, 12, 16, 0)
        top_row.addStretch()
        self._search_in = QLineEdit()
        self._search_in.setPlaceholderText("Search...")
        self._search_in.setFixedWidth(200)
        self._search_in.textChanged.connect(self._apply_filter)
        top_row.addWidget(self._search_in)
        card.add_layout(top_row)
        self._tbl = make_table(["No.", "Company", "City", "Master User", "Devices", "ZeroTier ID", "Status", "Max 2nd", "Actions"])
        self._tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hh = self._tbl.horizontalHeader()
        hh.setMinimumSectionSize(44)
        for col in range(9):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._tbl.setColumnWidth(0, 55)
        self._tbl.setColumnWidth(1, 150)
        self._tbl.setColumnWidth(2, 120)
        self._tbl.setColumnWidth(3, 200)
        self._tbl.setColumnWidth(4, 90)
        self._tbl.setColumnWidth(5, 120)
        self._tbl.setColumnWidth(6, 110)
        self._tbl.setColumnWidth(7, 80)
        self._tbl.setColumnWidth(8, 168)
        card.add_widget(self._tbl)
        lay.addWidget(card)
        lay.addStretch()

    def refresh(self):
        self._w = Worker(self.api.get_admin_tenants)
        self._w.result.connect(self._on_data)
        self._w.error.connect(self._alert.show_error)
        self._w.start()

    def _on_data(self, tenants: list):
        self._tenants = tenants
        self._apply_filter(self._search_in.text() if hasattr(self, "_search_in") else "")

    def _apply_filter(self, text: str):
        tenants = getattr(self, "_tenants", [])
        query = (text or "").strip().lower()
        t = self._tbl
        t.setUpdatesEnabled(False)
        t.setRowCount(0)
        visible = 0
        for i, row in enumerate(tenants):
            if query and query not in " ".join([
                str(row.get("company_name", "")),
                str(row.get("city", "")),
                str(row.get("zerotier_network_id", "")),
                str(row.get("status", "")),
            ]).lower():
                continue
            visible += 1
            r = t.rowCount(); t.insertRow(r)
            t.setItem(r, 0, table_item(str(visible)))
            t.setItem(r, 1, table_item(row.get("company_name", "")))
            t.setItem(r, 2, table_item(row.get("city") or "—"))
            t.setItem(r, 3, table_item(row.get("master_email") or "—",Qt.AlignmentFlag.AlignCenter))
            t.setItem(r, 4, table_item(str(row.get("device_count", 0)),Qt.AlignmentFlag.AlignCenter))
            net_id = row.get("zerotier_network_id") or "—"
            if net_id != "—" and not row.get("network_owner_id"):
                lbl = QLabel(f"⚠ {net_id}")
                lbl.setStyleSheet("color:#dc2626; font-weight:bold; background:#fee2e2; padding:2px 6px; border-radius:6px;")
                w = QWidget()
                l = QHBoxLayout(w)
                l.setContentsMargins(0, 0, 0, 0)
                l.setAlignment(Qt.AlignmentFlag.AlignCenter)
                l.addWidget(lbl)
                t.setCellWidget(r, 5, w)
            else:
                t.setItem(r, 5, table_item(net_id, Qt.AlignmentFlag.AlignCenter))
            s = row.get("status", "pending")
            t.setItem(r, 6, table_item(s.title(),Qt.AlignmentFlag.AlignCenter))

            from PyQt6.QtWidgets import QSpinBox
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(row.get("max_second_masters", 2))
            spin.setStyleSheet("QSpinBox{background:white; border:1px solid #e2e8f0; border-radius:4px; padding:2px;}")
            spin.valueChanged.connect(lambda val, tid=row["id"]: self._update_max_masters(tid, val))
            t.setCellWidget(r, 7, spin)

            cell_w = QWidget()
            cell_w.setStyleSheet("background:transparent" if (net_id != "—" and not row.get("network_owner_id")) else "background:white")
            cell_l = QHBoxLayout(cell_w)
            cell_l.setContentsMargins(14, 11, 10, 11)
            cell_l.setSpacing(8)
            del_btn = QPushButton("Delete")
            del_btn.setFixedSize(76, 30)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.setStyleSheet(
                "QPushButton{background:white;color:#dc2626;border:1px solid #fecaca;"
                "border-radius:6px;font-size:13px;padding:0px;outline:none}"
                "QPushButton:hover{background:#fee2e2}"
            )
            del_btn.clicked.connect(lambda _, tid=row["id"], nm=row["company_name"]: self._delete(tid, nm))
            cell_l.addWidget(del_btn)
            cell_l.addStretch()
            t.setCellWidget(r, 8, cell_w)
            
            if net_id != "—" and not row.get("network_owner_id"):
                from PyQt6.QtGui import QBrush, QColor
                bg_brush = QBrush(QColor("#fef3c7"))
                for c in range(t.columnCount()):
                    it = t.item(r, c)
                    if it:
                        it.setBackground(bg_brush)
        # Guarantee every row is tall enough for the 30px action buttons
        # (button 30px + 11px top + 11px bottom = 52px; row 54px adds 2px slack)
        for rr in range(t.rowCount()):
            t.setRowHeight(rr, 54)
        t.setUpdatesEnabled(True)
        t.setFixedHeight(44 + (visible * 54) + 2)

    def _add_tenant(self):
        dlg = QDialog(self.window())
        dlg.setWindowTitle("New Tenant")
        dlg.setFixedSize(420, 420)
        dlg.setStyleSheet("QDialog{background:#f1f5f9} QLabel{background:transparent;color:#0f172a} QLineEdit{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:9px;font-size:14px;color:#0f172a}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(14)

        lay.addWidget(_lbl("Company Name", bold=True))
        name_in = QLineEdit(); name_in.setPlaceholderText("Acme Corp")
        lay.addWidget(name_in)

        lay.addWidget(_lbl("Master User Email", bold=True))
        master_email_in = QLineEdit(); master_email_in.setPlaceholderText("john@acme.com")
        lay.addWidget(master_email_in)

        btns = QHBoxLayout()
        ok_btn = QPushButton("Create Tenant")
        ok_btn.setObjectName("btn-primary")
        ok_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600} QPushButton:hover{background:#1d4ed8}")
        cancel = QPushButton("Cancel")
        cancel.setObjectName("btn-ghost")
        cancel.setStyleSheet("QPushButton{background:white;color:#0f172a;border:1px solid #e2e8f0;border-radius:8px;padding:9px 18px;font-size:14px} QPushButton:hover{background:#f8fafc}")
        cancel.clicked.connect(dlg.reject)
        btns.addWidget(ok_btn); btns.addWidget(cancel)
        lay.addLayout(btns)

        def do_create():
            nm = name_in.text().strip()
            m_email = master_email_in.text().strip()
            if not nm or not m_email:
                self._alert.show_error("All fields are required.")
                return
            ok_btn.setEnabled(False); ok_btn.setText("Creating…")
            self._cw = Worker(self.api.create_tenant, nm, m_email)
            self._cw.result.connect(lambda _: (dlg.accept(), self.refresh(), self._alert.show_success("Tenant created and Activation Key emailed")))
            self._cw.error.connect(lambda e: (self._alert.show_error(e), ok_btn.setEnabled(True), ok_btn.setText("Create Tenant")))
            self._cw.start()

        ok_btn.clicked.connect(do_create)
        dlg.exec()

    def open_create_dialog(self):
        self._add_tenant()

    def _update_max_masters(self, tid: int, val: int):
        # We start a worker to update it via API
        self._uw = Worker(self.api.update_tenant, tid, val)
        self._uw.result.connect(lambda _: self._alert.show_success("Limit updated"))
        self._uw.error.connect(self._alert.show_error)
        self._uw.start()

    def _delete(self, tid: int, name: str):
        if QMessageBox.question(self.window(), "Confirm Delete", f"Are you sure you want to delete tenant '{name}'? This will delete all associated data.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self._dw = Worker(self.api.delete_tenant, tid)
        self._dw.result.connect(lambda _: (self.refresh(), self._alert.show_success("Tenant deleted")))
        self._dw.error.connect(self._alert.show_error)
        self._dw.start()


class KeysPage(QWidget):
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

        lay.addWidget(PageHeader("Router Preparation", "Prepare routers and send activation keys to customers"))

        card = CardWithHeader("Prepare Router Form")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        
        form_w = QWidget()
        form_w.setStyleSheet("background:white; border-radius:12px; padding:20px;")
        form = QFormLayout(form_w)
        form.setSpacing(14)
        
        self.router_id_in = QLineEdit()
        self.router_id_in.setPlaceholderText("e.g. router-01")
        self.router_id_in.setStyleSheet("QLineEdit{background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:8px; font-size:13px; color:#0f172a;}")
        
        self.serial_in = QLineEdit()
        self.serial_in.setPlaceholderText("e.g. SN-0001")
        self.serial_in.setStyleSheet("QLineEdit{background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:8px; font-size:13px; color:#0f172a;}")
        
        self.mac_in = QLineEdit()
        self.mac_in.setPlaceholderText("e.g. 00:11:22:33:44:55")
        self.mac_in.setStyleSheet("QLineEdit{background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:8px; font-size:13px; color:#0f172a;}")
        
        self.email_in = QLineEdit()
        self.email_in.setPlaceholderText("e.g. customer@company.com")
        self.email_in.setStyleSheet("QLineEdit{background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:8px; font-size:13px; color:#0f172a;}")
        
        self.zt_in = QLineEdit()
        self.zt_in.setPlaceholderText("e.g. 17d7094a3b")
        self.zt_in.setStyleSheet("QLineEdit{background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px; padding:8px; font-size:13px; color:#0f172a;}")

        form.addRow(_lbl("Router ID:", bold=True), self.router_id_in)
        form.addRow(_lbl("Serial Number:", bold=True), self.serial_in)
        form.addRow(_lbl("MAC Address:", bold=True), self.mac_in)
        form.addRow(_lbl("ZeroTier Node ID:", bold=True), self.zt_in)
        form.addRow(_lbl("Recipient Email:", bold=True), self.email_in)

        self.prep_btn = QPushButton("Prepare Router & Send Key")
        self.prep_btn.setStyleSheet("QPushButton{background:#2563eb; color:white; border:none; border-radius:8px; padding:10px 20px; font-size:14px; font-weight:bold;} QPushButton:hover{background:#1d4ed8;}")
        self.prep_btn.clicked.connect(self._prepare)
        form.addRow("", self.prep_btn)

        card.add_widget(form_w)
        lay.addWidget(card)
        
        warn = QLabel("Note: Preparing a router registers it on the database and generates an Activation Key. This key is emailed to the recipient and is required to onboard a new Master user.")
        warn.setWordWrap(True)
        warn.setStyleSheet("background:#eff6ff; color:#1e40af; border:1px solid #bfdbfe; border-radius:8px; padding:12px; font-size:13px;")
        lay.addWidget(warn)
        lay.addStretch()

    def refresh(self):
        pass

    def _prepare(self):
        router_id = self.router_id_in.text().strip()
        serial = self.serial_in.text().strip()
        mac = self.mac_in.text().strip()
        zt_id = self.zt_in.text().strip()
        email = self.email_in.text().strip()
        
        if not router_id or not serial or not mac or not zt_id or not email:
            self._alert.show_error("All fields are required")
            return
            
        self.prep_btn.setEnabled(False)
        self.prep_btn.setText("Preparing...")
        
        self._w = Worker(self.api.prepare_router, router_id, serial, mac, email, zt_id)
        self._w.result.connect(self._on_success)
        self._w.error.connect(self._on_error)
        self._w.start()

    def _on_success(self, data):
        self.prep_btn.setEnabled(True)
        self.prep_btn.setText("Prepare Router & Send Key")
        
        # Clear fields
        self.router_id_in.clear()
        self.serial_in.clear()
        self.mac_in.clear()
        self.zt_in.clear()
        self.email_in.clear()
        
        # Show key popup
        key_code = data.get("key_code", "PXKEY-...")
        # Since prepare_router backend response doesn't always contain key_code in stats (it sends it via email),
        # but wait, let's verify if the key_code is in database activation_key table: yes, the backend prepare_router endpoint
        # returns the router info. Oh, does the backend endpoint return key_code?
        # Let's check admin.py prepare_router response:
        # return { "id": new_router.id, "router_id": new_router.router_id, ... }
        # Ah! It does NOT return key_code in the JSON response to prevent exposing it if emailed!
        # Wait, but wait: the backend can return key_code or we can display a success notification.
        # Let's see: yes! "Router prepared successfully. Activation key has been sent to customer's email."
        self._alert.show_success("Router prepared successfully! Activation key sent via email.")
        
        QMessageBox.information(self, "Success", "Router prepared successfully!\n\nThe activation key has been dispatched to the recipient's email address.")

    def _on_error(self, err):
        self.prep_btn.setEnabled(True)
        self.prep_btn.setText("Prepare Router & Send Key")
        self._alert.show_error(err)



class ActivationKeysPage(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._keys = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)

        self._alert = AlertBar()
        lay.addWidget(self._alert)

        lay.addWidget(PageHeader("Activation Keys", "View and manage all router activation keys"))

        card = CardWithHeader("All Keys")
        
        self._tbl = make_table(["KEY CODE", "ROUTER ID", "SERIAL NUMBER", "STATUS", "PREPARED AT", "ACTIONS"])
        hh = self._tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._tbl.setColumnWidth(1, 140)
        self._tbl.setColumnWidth(2, 140)
        self._tbl.setColumnWidth(3, 100)
        self._tbl.setColumnWidth(4, 160)
        self._tbl.setColumnWidth(5, 200)

        card.add_widget(self._tbl)
        lay.addWidget(card)
        lay.addStretch()

    def refresh(self):
        self._w = Worker(self.api.get_all_activation_keys)
        self._w.result.connect(self._on_data)
        self._w.error.connect(lambda e: self._alert.show_error(str(e)))
        self._w.start()

    def _on_data(self, keys: list):
        self._keys = keys
        t = self._tbl
        t.setUpdatesEnabled(False)
        t.setRowCount(0)
        for key in keys:
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, table_item(key.get("key_code", "")))
            t.setItem(r, 1, table_item(key.get("router_id", "—")))
            t.setItem(r, 2, table_item(key.get("serial_number", "—")))
            is_used = key.get("is_used", False)
            t.setItem(r, 3, table_item("Used" if is_used else "Unused"))
            t.setItem(r, 4, table_item(_fmt_date(key.get("prepared_at", ""))))

            btn_w = QWidget()
            btn_w.setStyleSheet("background:white")
            btn_l = QHBoxLayout(btn_w)
            btn_l.setContentsMargins(6, 6, 6, 6)
            btn_l.setSpacing(6)
            
            if not is_used:
                resend_btn = QPushButton("Resend")
                resend_btn.setFixedSize(60, 28)
                resend_btn.setStyleSheet(
                    "QPushButton{background:white;color:#2563eb;border:1px solid #bfdbfe;"
                    "border-radius:6px;padding:0px;font-size:12px} QPushButton:hover{background:#eff6ff}"
                )
                resend_btn.clicked.connect(lambda _, kid=key["id"], kc=key["key_code"]: self._resend_key(kid, kc))
                btn_l.addWidget(resend_btn)
                
            del_btn = QPushButton("Delete")
            del_btn.setFixedSize(60, 28)
            del_btn.setStyleSheet(
                "QPushButton{background:white;color:#dc2626;border:1px solid #fecaca;"
                "border-radius:6px;padding:0px;font-size:12px} QPushButton:hover{background:#fee2e2}"
            )
            del_btn.clicked.connect(lambda _, kid=key["id"]: self._delete_key(kid))
            btn_l.addWidget(del_btn)
            
            btn_l.addStretch()
            t.setCellWidget(r, 5, btn_w)

        for rr in range(t.rowCount()):
            t.setRowHeight(rr, 54)
        t.setUpdatesEnabled(True)

        row_height = 54
        header_height = 42
        num_rows = len(keys)
        total_height = header_height + (num_rows * row_height) + 2 if num_rows > 0 else header_height + 2
        t.setFixedHeight(total_height)

    def _resend_key(self, key_id: int, key_code: str):
        from PyQt6.QtWidgets import QInputDialog
        email, ok = QInputDialog.getText(
            self, "Resend Activation Key", 
            f"Enter recipient email for key {key_code}:"
        )
        if not ok or not email.strip():
            return

        self._alert.show_success("Resending key...")
        self._rw = Worker(self.api.resend_activation_key, key_id, email.strip())
        self._rw.result.connect(lambda data: self._alert.show_success("Activation key email resent successfully!"))
        self._rw.error.connect(lambda err: self._alert.show_error(str(err)))
        self._rw.start()

    def _delete_key(self, key_id: int):
        if not _confirm_delete(self, "Delete Key", "Are you sure you want to delete this activation key?"):
            return
        self._alert.show_success("Deleting key...")
        self._dw = Worker(self.api.delete_activation_key, key_id)
        def on_done(_):
            self._alert.show_success("Key deleted")
            self.refresh()
        self._dw.result.connect(on_done)
        self._dw.error.connect(lambda err: self._alert.show_error(str(err)))
        self._dw.start()
class OwnerUsersPage(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._users = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(20)

        self._alert = AlertBar()
        lay.addWidget(self._alert)

        lay.addWidget(PageHeader("Platform Users", "Manage 2FA for all Master and Second Master users across all tenants"))

        card = CardWithHeader("Master Users")
        top_row = QHBoxLayout()
        top_row.setContentsMargins(16, 12, 16, 0)
        top_row.addStretch()
        self._search_in = QLineEdit()
        self._search_in.setPlaceholderText("Search...")
        self._search_in.setFixedWidth(200)
        self._search_in.textChanged.connect(self._apply_filter)
        top_row.addWidget(self._search_in)
        card.add_layout(top_row)
        
        self._tbl = make_table(["NAME", "EMAIL", "COMPANY", "ROLE", "2FA", "ACTIONS"])
        self._tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        hh = self._tbl.horizontalHeader()
        for col in range(6):
            hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(True)
        
        self._tbl.setColumnWidth(0, 160)
        self._tbl.setColumnWidth(1, 200)
        self._tbl.setColumnWidth(2, 140)
        self._tbl.setColumnWidth(3, 160)
        self._tbl.setColumnWidth(4, 150)
        self._tbl.setColumnWidth(5, 200)
        card.add_widget(self._tbl)
        lay.addWidget(card)
        lay.addStretch()

    def refresh(self):
        self._w = Worker(self.api.get_admin_users)
        self._w.result.connect(self._on_data)
        self._w.error.connect(self._alert.show_error)
        self._w.start()

    def _on_data(self, users: list):
        self._users = users
        self._apply_filter(self._search_in.text() if hasattr(self, "_search_in") else "")

    def _apply_filter(self, text: str):
        users = getattr(self, "_users", [])
        query = (text or "").strip().lower()
        t = self._tbl
        t.setUpdatesEnabled(False)
        t.setRowCount(0)
        
        for row in users:
            if query and query not in " ".join([
                str(row.get("full_name", "")),
                str(row.get("email", "")),
                str(row.get("company_name", ""))
            ]).lower():
                continue
                
            r = t.rowCount(); t.insertRow(r)
            
            try:
                # pyrefly: ignore [missing-import]
                from client.styles import ROLE_COLORS
            except ImportError:
                # pyrefly: ignore [missing-import]
                from styles import ROLE_COLORS

            nw = QWidget()
            nl = QHBoxLayout(nw)
            nl.setContentsMargins(8, 4, 8, 4)
            av = QLabel(row.get("full_name", "U")[0].upper())
            av.setFixedSize(26, 26)
            av.setAlignment(Qt.AlignmentFlag.AlignCenter)
            av.setStyleSheet("background:#3b82f6;color:white;border-radius:13px;font-weight:700;font-size:12px;border:none;")
            n_lbl = QLabel(row.get("full_name", ""))
            n_lbl.setStyleSheet("font-size:13px;font-weight:600;color:#1e293b;border:none;background:transparent;")
            nl.addWidget(av); nl.addWidget(n_lbl); nl.addStretch()
            t.setCellWidget(r, 0, nw)
            
            t.setItem(r, 1, table_item(row.get("email", "")))
            
            t.setItem(r, 2, table_item(row.get("company_name", "—")))
            
            role = row.get("role", "")
            bg, fg = ROLE_COLORS.get(role, ("#f1f5f9", "#64748b"))
            role_w = QWidget()
            role_l = QHBoxLayout(role_w)
            role_l.setContentsMargins(8, 4, 8, 4)
            role_badge_lbl = QLabel(role.replace("_"," ").title())
            role_badge_lbl.setStyleSheet(f"background:{bg};color:{fg};padding:3px 9px;border-radius:12px;font-size:12px;font-weight:600")
            role_l.addWidget(role_badge_lbl); role_l.addStretch()
            t.setCellWidget(r, 3, role_w)
            
            fa_w = QWidget()
            fa_l = QHBoxLayout(fa_w)
            fa_l.setContentsMargins(8, 4, 8, 4)
            if row.get("totp_enabled"):
                fa_lbl = QLabel("✓ Active")
                fa_lbl.setStyleSheet("background:#dcfce7;color:#16a34a;padding:3px 9px;border-radius:12px;font-size:12px;font-weight:600")
            else:
                fa_lbl = QLabel("Off")
                fa_lbl.setStyleSheet("background:#f1f5f9;color:#64748b;padding:3px 9px;border-radius:12px;font-size:12px;font-weight:600")
            fa_l.addWidget(fa_lbl); fa_l.addStretch()
            t.setCellWidget(r, 4, fa_w)
            
            # Actions
            btn_w = QWidget()
            btn_w.setStyleSheet("background:white")
            btn_l = QHBoxLayout(btn_w)
            btn_l.setContentsMargins(4, 4, 4, 4)
            btn_l.setSpacing(6)
            btn_l.addStretch()
            
            is_forced = row.get("force_2fa", False)
            btn_txt = "Disable 2FA" if is_forced else "Force 2FA"
            
            toggle_btn = QPushButton(btn_txt)
            toggle_btn.setObjectName("btn-sm")
            toggle_btn.setFixedSize(110, 30)
            toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if is_forced:
                toggle_btn.setStyleSheet("""
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
                toggle_btn.setStyleSheet("""
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
            toggle_btn.clicked.connect(lambda _, uid=row["id"], nxt=not is_forced: self._toggle_force_2fa(uid, nxt))
            btn_l.addWidget(toggle_btn)
            
            if row.get("role") == "second_master":
                demote_btn = QPushButton("Demote")
                demote_btn.setObjectName("btn-sm")
                demote_btn.setFixedSize(75, 30)
                demote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                demote_btn.setStyleSheet(
                    "QPushButton { background: white; color: #d97706; border: 1px solid #fcd34d; border-radius: 6px; font-weight: 600; }"
                    "QPushButton:hover { background: #fef3c7; color: #b45309; border-color: #fbbf24; }"
                )
                demote_btn.clicked.connect(lambda _, uid=row["id"], nm=row.get("full_name",""): self._demote_user(uid, nm))
                btn_l.addWidget(demote_btn)
                
            rem = QPushButton("Remove")
            rem.setObjectName("btn-danger")
            rem.setFixedSize(78, 30)
            rem.setStyleSheet(
                "QPushButton { background: white; color: #ef4444; border: 1px solid #fca5a5; border-radius: 6px; font-weight: 600; }"
                "QPushButton:hover { background: #fef2f2; color: #b91c1c; border-color: #f87171; }"
            )
            rem.clicked.connect(lambda _, uid=row["id"], nm=row.get("full_name",""): self._remove_user(uid, nm))
            btn_l.addWidget(rem)
            
            btn_l.addStretch()
            t.setCellWidget(r, 5, btn_w)
            
        for rr in range(t.rowCount()):
            t.setRowHeight(rr, 54)
        t.setUpdatesEnabled(True)

    def _toggle_force_2fa(self, uid: int, force: bool):
        self._fw = Worker(self.api.toggle_force_2fa, uid, force)
        self._fw.result.connect(lambda _: (self.refresh(), self._alert.show_success("2FA settings updated")))
        self._fw.error.connect(self._alert.show_error)
        self._fw.start()

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
            self, user_info, "Confirm Removal",
            f"Remove {name}? This cannot be undone.",
            do_delete
        )

class OwnerSettingsPage(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
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
        lay.addWidget(PageHeader("Settings", "Platform configuration"))

        # 2-col grid
        grid = QHBoxLayout()
        grid.setSpacing(20)

        # Account card
        acc_card = QFrame(); acc_card.setObjectName("card")
        acc_lay = QVBoxLayout(acc_card)
        acc_lay.setContentsMargins(24, 24, 24, 24)
        acc_lay.setSpacing(14)
        acc_lay.addWidget(_lbl("Account Details", bold=True, size=15))
        acc_lay.addWidget(_lbl("Full Name", muted=True))
        self._name_in = QLineEdit()
        acc_lay.addWidget(self._name_in)
        acc_lay.addWidget(_lbl("Email", muted=True))
        self._email_in = QLineEdit(); self._email_in.setEnabled(False)
        acc_lay.addWidget(self._email_in)
        acc_lay.addWidget(_lbl("Role", muted=True))
        role_in = QLineEdit("System Owner"); role_in.setEnabled(False)
        acc_lay.addWidget(role_in)
        save_btn = QPushButton("Save Changes")
        save_btn.setObjectName("btn-primary")
        save_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600} QPushButton:hover{background:#1d4ed8}")
        save_btn.setFixedHeight(38)
        save_btn.clicked.connect(lambda: self._alert.show_success("Profile saved"))
        acc_lay.addWidget(save_btn)
        acc_lay.addStretch()
        grid.addWidget(acc_card)

        # Security card
        sec_card = QFrame(); sec_card.setObjectName("card")
        sec_lay = QVBoxLayout(sec_card)
        sec_lay.setContentsMargins(24, 24, 24, 24)
        sec_lay.setSpacing(14)
        sec_lay.addWidget(_lbl("Security", bold=True, size=15))
        sec_lay.addWidget(_lbl("Current Password", muted=True))
        self._cur_pass = QLineEdit(); self._cur_pass.setEchoMode(QLineEdit.EchoMode.Password)
        sec_lay.addWidget(self._cur_pass)
        sec_lay.addWidget(_lbl("New Password", muted=True))
        self._new_pass = QLineEdit(); self._new_pass.setEchoMode(QLineEdit.EchoMode.Password)
        sec_lay.addWidget(self._new_pass)
        sec_lay.addWidget(_lbl("Confirm New Password", muted=True))
        self._conf_pass = QLineEdit(); self._conf_pass.setEchoMode(QLineEdit.EchoMode.Password)
        sec_lay.addWidget(self._conf_pass)
        upd_btn = QPushButton("Update Password")
        upd_btn.setObjectName("btn-primary")
        upd_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600} QPushButton:hover{background:#1d4ed8}")
        upd_btn.setFixedHeight(38)
        upd_btn.clicked.connect(self._change_password)
        sec_lay.addWidget(upd_btn)
        
        sec_lay.addSpacing(16)
        sec_lay.addWidget(_lbl("Two-Factor Authentication", bold=True, size=15))
        fa_btn = QPushButton("Reconfigure 2FA")
        fa_btn.setObjectName("btn-ghost")
        fa_btn.setStyleSheet("QPushButton{background:white;color:#2563eb;border:1px solid #bfdbfe;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600} QPushButton:hover{background:#eff6ff}")
        fa_btn.setFixedHeight(38)
        fa_btn.clicked.connect(self._reconfigure_2fa)
        sec_lay.addWidget(fa_btn)
        
        sec_lay.addStretch()
        grid.addWidget(sec_card)
        lay.addLayout(grid)

        # Platform info card
        info_card = QFrame(); info_card.setObjectName("card")
        info_lay = QVBoxLayout(info_card)
        info_lay.setContentsMargins(24, 24, 24, 24)
        info_lay.setSpacing(0)
        info_lay.addWidget(_lbl("Platform Info", bold=True, size=15))
        info_lay.addSpacing(16)
        for label, val in [("Version", "1.0.0"), ("Company", "Celestial Infosoft"), ("Website", "celestialinfosoft.com"), ("Support", "info@celestialinfosoft.com")]:
            row_w = QWidget()
            row_w.setStyleSheet("border-bottom:1px solid #f1f5f9")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(0, 10, 0, 10)
            rl.addWidget(_lbl(label, muted=True))
            rl.addStretch()
            rl.addWidget(_lbl(val))
            info_lay.addWidget(row_w)
        lay.addWidget(info_card)
        lay.addStretch()

        scroll.setWidget(inner)
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.addWidget(scroll)

    def refresh(self):
        self._w = Worker(self.api.get_me)
        def on_ok(me):
            self._name_in.setText(me.get("full_name", ""))
            self._email_in.setText(me.get("email", ""))
            p = self
            while p:
                if hasattr(p, "user") and p is not self:
                    # pyrefly: ignore [missing-attribute]
                    p.user = me
                    break
                p = p.parent()
        self._w.result.connect(on_ok)
        self._w.start()

    def _change_password(self):
        np = self._new_pass.text()
        cp = self._conf_pass.text()
        if np != cp:
            self._alert.show_error("Passwords do not match")
            return
        self._pw = Worker(self.api.change_password, np)
        self._pw.result.connect(lambda _: self._alert.show_success("Password changed successfully"))
        self._pw.error.connect(self._alert.show_error)
        self._pw.start()

    def _reconfigure_2fa(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QImage, QPixmap
        import base64

        class Setup2FADialog(QDialog):
            def __init__(self, parent, qr_b64, secret, api):
                super().__init__(parent)
                self.api = api
                self.setWindowTitle("Reconfigure 2FA")
                self.setFixedSize(380, 480)
                self.setStyleSheet("QDialog{background:#f1f5f9} QLabel{background:transparent;color:#0f172a} QLineEdit{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:9px;font-size:14px;color:#0f172a}")
                
                lay = QVBoxLayout(self)
                lay.setContentsMargins(28, 28, 28, 28)
                lay.setSpacing(14)
                
                lbl = QLabel("Scan the QR code with your authenticator app:")
                lbl.setStyleSheet("font-size:13px;font-weight:600;color:#0f172a")
                lay.addWidget(lbl)
                
                qr_lbl = QLabel()
                qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                qr_lbl.setStyleSheet("background:white; border-radius:8px; padding:10px;")
                img_data = base64.b64decode(qr_b64)
                img = QImage.fromData(img_data)
                pix = QPixmap.fromImage(img).scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                qr_lbl.setPixmap(pix)
                lay.addWidget(qr_lbl)
                
                sec_lbl = QLabel(f"Manual Entry: {secret}")
                sec_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sec_lbl.setStyleSheet("font-size:12px;color:#64748b;font-family:monospace")
                lay.addWidget(sec_lbl)
                
                lay.addWidget(QLabel("Enter 6-digit code:"))
                self.code_in = QLineEdit()
                self.code_in.setPlaceholderText("123456")
                self.code_in.setMaxLength(6)
                lay.addWidget(self.code_in)
                
                self.err_lbl = QLabel("")
                self.err_lbl.setStyleSheet("color:#dc2626;font-size:12px;")
                self.err_lbl.hide()
                lay.addWidget(self.err_lbl)
                
                btn = QPushButton("Verify & Save")
                btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:8px;padding:9px 18px;font-size:14px;font-weight:600} QPushButton:hover{background:#1d4ed8}")
                btn.clicked.connect(self._verify)
                lay.addWidget(btn)
                
            def _verify(self):
                code = self.code_in.text().strip()
                if len(code) != 6:
                    self.err_lbl.setText("Enter a 6-digit code.")
                    self.err_lbl.show()
                    return
                try:
                    self.api.verify_2fa(code)
                    self.accept()
                except Exception as e:
                    self.err_lbl.setText(str(e))
                    self.err_lbl.show()

        self._tw = Worker(self.api.setup_2fa)
        def on_setup(data):
            dlg = Setup2FADialog(self.window(), data["qr_code"], data["secret"], self.api)
            if dlg.exec():
                self._alert.show_success("2FA reconfigured successfully!")
        self._tw.result.connect(on_setup)
        self._tw.error.connect(self._alert.show_error)
        self._tw.start()


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN OWNER WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class OwnerWindow(QMainWindow):
    logged_out = pyqtSignal()

    def __init__(self, api, user_info: dict):
        super().__init__()
        self.api = api
        self.user = user_info
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(APP_STYLE)
        self._build()
        self._nav("dashboard")

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # ── Sidebar ─────────────────────────────────────────────
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_W)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)

        # Logo
        logo_w = QWidget()
        logo_w.setStyleSheet("background:#0d1b2a;border-bottom:1px solid rgba(255,255,255,0.06);padding:0")
        ll = QHBoxLayout(logo_w)
        ll.setContentsMargins(18, 20, 18, 18)
        icon = QLabel()
        icon.setFixedSize(32, 32)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(load_icon(asset_path("logo-square.svg"), 32).pixmap(32, 32))
        logo_name = QLabel("ProjectX")
        logo_name.setStyleSheet("font-weight:700;font-size:18px;color:#fff")
        ll.addWidget(icon); ll.addWidget(logo_name); ll.addStretch()
        sb.addWidget(logo_w)

        # User info
        user_w = QWidget()
        user_w.setStyleSheet("border-bottom:1px solid rgba(255,255,255,0.06)")
        ul = QHBoxLayout(user_w)
        ul.setContentsMargins(18, 14, 18, 14)
        ul.setSpacing(12)
        av = QLabel((self.user.get("full_name") or "S")[0].upper())
        av.setFixedSize(38, 38)
        av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.setStyleSheet("background:#2563eb;color:white;border-radius:19px;font-weight:700;font-size:15px")
        ul.addWidget(av)
        uc = QVBoxLayout(); uc.setSpacing(2)
        uname = QLabel(self.user.get("full_name", "System Owner"))
        uname.setStyleSheet("font-weight:600;font-size:14px;color:#fff")
        urole = QLabel("System Owner")
        urole.setStyleSheet("background:#fffbeb;color:#b45309;padding:2px 8px;border:1px solid transparent;border-radius:10px;font-size:11px;font-weight:600")
        uc.addWidget(uname)
        uc.addWidget(urole, alignment=Qt.AlignmentFlag.AlignLeft)
        ul.addLayout(uc); ul.addStretch()
        sb.addWidget(user_w)

        # Nav
        nav_items = [
            ("dashboard", asset_path("grid.svg"), "Dashboard"),
            ("tenants",   asset_path("users.svg"), "Tenants"),
            ("keys",      asset_path("key.svg"), "Router Preparation"),
            ("activation_keys", asset_path("key.svg"), "Activation Keys"),
            ("settings",  asset_path("settings.svg"), "Settings"),
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
        content_frame = QWidget()
        content_frame.setObjectName("owner-content")
        content_frame.setStyleSheet("QWidget#owner-content { background: #f0f4f8; }")
        cl = QVBoxLayout(content_frame)
        cl.setContentsMargins(36, 32, 36, 32)
        cl.setSpacing(16)

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
            "dashboard": OwnerDashboardPage(
                self.api,
                on_new_tenant=self._open_new_tenant,
                on_view_tenants=lambda: self._nav("tenants"),
                on_manage_keys=lambda: self._nav("activation_keys"),
            ),
            "tenants":      TenantsPage(self.api),
            "keys":         KeysPage(self.api),
            "activation_keys": ActivationKeysPage(self.api),
            "settings":     OwnerSettingsPage(self.api),
        }
        for p in self._pages.values():
            self._stack.addWidget(p)

        cl.addWidget(self._stack)
        h.addWidget(content_frame)
        self._nav_history = []

    def _nav(self, key: str, push_history: bool = True):
        current = getattr(self, "_current_page", None)
        if push_history and current and current != key:
            self._nav_history.append(current)
        for k, btn in self._nav_btns.items():
            btn.setProperty("active", k == key)
            icon_src = btn.property("icon_src")
            if icon_src:
                tint = "#ffffff" if k == key else "#94a3b8"
                btn.setIcon(load_icon(icon_src, 20, tint=tint))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._current_page = key
        self._back_btn.setEnabled(bool(self._nav_history))
        self._stack.setCurrentWidget(self._pages[key])
        self._pages[key].refresh()

    def _open_new_tenant(self):
        self._pages["tenants"].open_create_dialog()

    def _go_back(self):
        if not self._nav_history:
            return
        previous = self._nav_history.pop()
        self._nav(previous, push_history=False)

    def _logout(self):
        self.api.token = None
        self.logged_out.emit()
        self.close()


# ── Helpers ────────────────────────────────────────────────────────────────────
def _lbl(text: str, bold: bool = False, muted: bool = False, size: int = 14) -> QLabel:
    l = QLabel(text)
    color = "#64748b" if muted else "#0f172a"
    weight = "700" if bold else "400"
    l.setStyleSheet(f"font-size:{size}px;font-weight:{weight};color:{color};background:transparent")
    return l


def _fmt_date(iso: str) -> str:
    if not iso:
        return "—"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%b %d, %Y  %I:%M %p")
    except Exception:
        # pyrefly: ignore [unnecessary-type-conversion]
        return str(iso)[:16]

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
    print(f"DEBUG: _prompt_sensitive_action called with user_info={user_info}")
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
