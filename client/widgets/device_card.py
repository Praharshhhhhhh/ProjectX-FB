from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QSizePolicy, QDialog, QLineEdit, QComboBox, QScrollArea
)
# pyrefly: ignore [missing-module-attribute]
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QRectF, pyqtProperty, QUrl, QThread
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QDesktopServices
from services import zerotier_local
from config import TUNNEL_MODE

class ConnectWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, device: dict, api, connect: bool=False):
        super().__init__()
        self.device = device
        self.api = api
        self.connect_flag = connect

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
            from services.tunnel_manager import TunnelManager
            manager = TunnelManager(self.device)
            if hasattr(self, 'connect_flag') and self.connect_flag:
                ok = manager.connect(self.api)
                self.done.emit(ok, "connected" if ok else "error")
            else:
                ok = manager.disconnect()
                self.done.emit(ok, "disconnected")
        except Exception:
            pass

class ShareDeviceDialog(QDialog):
    def __init__(self, device: dict, api, parent=None):
        super().__init__(parent)
        self.device = device
        self.api = api
        self.setWindowTitle(f"Share Device: {device.get('name')}")
        self.setFixedSize(500, 400)
        self.setStyleSheet("QDialog{background:#f1f5f9} QLabel{background:transparent;color:#0f172a} QLineEdit{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:9px;font-size:14px;color:#0f172a}")
        self._build_ui()
        self.refresh_shares()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        lay.addWidget(QLabel("<b>Active Shares</b>"))
        self.shares_list = QListWidget()
        self.shares_list.setStyleSheet("QListWidget{background:white; border:1px solid #e2e8f0; border-radius:8px; outline:none;}")
        lay.addWidget(self.shares_list)

        lay.addWidget(QLabel("<b>Share with new Tenant</b>"))
        add_lay = QHBoxLayout()
        self.tenant_in = QLineEdit()
        self.tenant_in.setPlaceholderText("Enter Target Tenant ID")
        add_lay.addWidget(self.tenant_in)
        
        add_btn = QPushButton("Share")
        add_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:6px;padding:8px 16px;font-weight:bold;} QPushButton:hover{background:#1d4ed8;}")
        add_btn.clicked.connect(self._create_share)
        add_lay.addWidget(add_btn)
        lay.addLayout(add_lay)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("QPushButton{background:white;color:#0f172a;border:1px solid #e2e8f0;border-radius:8px;padding:9px 18px;font-size:14px} QPushButton:hover{background:#f8fafc}")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def refresh_shares(self):
        self.shares_list.clear()
        try:
            shares = self.api.get_device_shares(self.device["id"])
            for s in shares:
                item = QListWidgetItem()
                w = QWidget()
                l = QHBoxLayout(w)
                l.setContentsMargins(10, 5, 10, 5)
                l.addWidget(QLabel(f"Tenant ID: {s['target_tenant_id']}"))
                l.addStretch()
                rev_btn = QPushButton("Revoke")
                rev_btn.setStyleSheet("QPushButton{background:#fee2e2;color:#dc2626;border:none;border-radius:4px;padding:4px 8px;} QPushButton:hover{background:#fecaca;}")
                rev_btn.clicked.connect(lambda _, sid=s['id']: self._revoke_share(sid))
                l.addWidget(rev_btn)
                item.setSizeHint(w.sizeHint())
                self.shares_list.addItem(item)
                self.shares_list.setItemWidget(item, w)
        except Exception as e:
            print("Failed to get shares:", e)

    def _create_share(self):
        tid = self.tenant_in.text().strip()
        if not tid.isdigit():
            return
        try:
            self.api.create_device_share(self.device["id"], int(tid))
            self.tenant_in.clear()
            self.refresh_shares()
        except Exception as e:
            print("Failed to share:", e)

    def _revoke_share(self, share_id: int):
        try:
            self.api.revoke_device_share(share_id)
            self.refresh_shares()
        except Exception as e:
            print("Failed to revoke:", e)

class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(38, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._checked = False
        self._thumb_pos = 2.0
        self._interactable = True
        
        self.anim = QPropertyAnimation(self, b"thumbPos", self)
        self.anim.setDuration(150)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked == checked:
            return
        self._checked = checked
        self.anim.setEndValue(18.0 if checked else 2.0)
        self.anim.start()
        self.update()

    def set_interactable(self, enabled: bool):
        self._interactable = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update()

    @pyqtProperty(float)
    def thumbPos(self):
        return self._thumb_pos

    @thumbPos.setter
    def thumbPos(self, pos):
        self._thumb_pos = pos
        self.update()

    # pyrefly: ignore [bad-override-param-name]
    def mouseReleaseEvent(self, event):
        if not self._interactable:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)
        super().mouseReleaseEvent(event)

    # pyrefly: ignore [bad-override-param-name]
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        if not self._interactable:
            bg_color = QColor("#f1f5f9")  # Very light gray for disabled
        else:
            bg_color = QColor("#10b981") if self._checked else QColor("#cbd5e1")
            
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(0, 0, self.width(), self.height(), int(self.height()/2), int(self.height()/2))

        # Thumb
        if not self._interactable:
            thumb_color = QColor("white")
            pen_color = QColor(0, 0, 0, 15)
        else:
            thumb_color = QColor("white")
            pen_color = QColor(0, 0, 0, 30)
            
        painter.setBrush(QBrush(thumb_color))
        painter.setPen(QPen(pen_color, 1))
        painter.drawEllipse(QRectF(self._thumb_pos, 2.0, 18.0, 18.0))
        painter.end()


class ScanWorker(QThread):
    done = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, api, device_id: int, local_ip: str):
        super().__init__()
        self.api = api
        self.device_id = device_id
        self.local_ip = local_ip

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
            import subprocess
            import re
            import socket
            from concurrent.futures import ThreadPoolExecutor

            if not self.local_ip:
                self.done.emit([])
                return
            
            parts = self.local_ip.split(".")
            if len(parts) != 4:
                self.done.emit([])
                return
            
            subnet_prefix = ".".join(parts[:3])
            ips = [f"{subnet_prefix}.{i}" for i in range(1, 255)]
            
            def ping_ip(ip):
                try:
                    subprocess.run(["ping", "-n", "1", "-w", "250", ip], 
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass

            with ThreadPoolExecutor(max_workers=50) as executor:
                executor.map(ping_ip, ips)
                
            devices = []
            output = subprocess.check_output(["arp", "-a"]).decode("utf-8", errors="ignore")
            ip_mac_pattern = re.compile(
                r"([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})\s+([0-9a-fA-F:-]{17})"
            )
            for line in output.splitlines():
                match = ip_mac_pattern.search(line)
                if match:
                    ip, mac = match.groups()
                    if not ip.startswith(subnet_prefix + "."):
                        continue
                    if ip == self.local_ip:
                        continue
                    name = "Unknown Device"
                    try:
                        name = socket.gethostbyaddr(ip)[0]
                    except Exception:
                        pass
                    devices.append({
                        "ip_address": ip,
                        "mac_address": mac.replace("-", ":").lower(),
                        "name": name
                    })
            
            # Sync with the backend API
            self.api.sync_lan_devices(self.device_id, devices)
            self.done.emit(devices)
        except Exception as e:
            self.error.emit(str(e))


class DeviceCard(QFrame):
    def __init__(self, device: dict, api, parent=None, user: dict = None):
        super().__init__(parent)
        self.device = device
        self.api = api
        self.user = user or {}
        self.expanded = False
        from services.tunnel_manager import TunnelManager
        self.tunnel_manager = TunnelManager(device)
        self.local_status = self.tunnel_manager.get_status()
        
        # Debug write
        try:
            with open("C:/Users/Harsh Patel/Desktop/ProjectX_py/projectxdev-main/client_debug.log", "a") as f:
                f.write(f"DeviceCard init. Device: {self.device.get('name')}. lan_devices count: {len(device.get('lan_devices', []))}\\n")
                f.write(f"Device data: {str(device)}\\n\\n")
        except Exception as e:
            pass

        self.setStyleSheet("""
            DeviceCard {
                background: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._build_ui()

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 12)
        self.main_layout.setSpacing(0)

        # Top row
        top = QHBoxLayout()
        top.setSpacing(12)

        # Status Dot
        self.dot = QLabel("●")
        self.dot.setFixedWidth(16)
        self.dot.setStyleSheet("color:#94a3b8;font-size:12px;background:transparent;border:none;")
        top.addWidget(self.dot)

        # Name and IPs
        info = QVBoxLayout()
        info.setSpacing(2)
        
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.setContentsMargins(0, 0, 0, 0)
        self.name_label = QLabel(self.device.get("name") or "Gateway")
        self.name_label.setStyleSheet("font-weight:700;font-size:14px;color:#0f172a;background:transparent;border:none;")
        name_row.addWidget(self.name_label)
        
        # Tunnel Badge
        ttype = self.device.get("connection_info", {}).get("tunnel_type", "zerotier")
        badge_text = "WG" if ttype == "wireguard" else "ZT"
        badge_color = "#3b82f6" if ttype == "wireguard" else "#f59e0b"
        self.tunnel_badge = QLabel(badge_text)
        self.tunnel_badge.setStyleSheet(f"background:{badge_color};color:white;padding:2px 4px;border-radius:4px;font-size:10px;font-weight:bold;")
        name_row.addWidget(self.tunnel_badge)

        self.conflict_badge = QLabel("Overmapping Conflict")
        self.conflict_badge.setStyleSheet("background:#fee2e2;color:#ef4444;padding:2px 4px;border-radius:4px;font-size:10px;font-weight:bold;")
        self.conflict_badge.setVisible(bool(self.device.get("has_conflict")))
        name_row.addWidget(self.conflict_badge)
        
        edit_btn = QPushButton("✎")
        edit_btn.setFixedSize(20, 20)
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setStyleSheet("QPushButton{background:transparent;color:#94a3b8;border:none;font-size:12px} QPushButton:hover{color:#3b82f6}")
        edit_btn.clicked.connect(self._rename_device)
        
        # Only show edit button if we are not a recipient of a share
        if not self.device.get("is_shared"):
            name_row.addWidget(edit_btn)
            
        if self.device.get("is_shared"):
            shared_badge = QLabel("Shared")
            shared_badge.setStyleSheet("background:#fef3c7;color:#b45309;padding:2px 6px;border-radius:6px;font-size:10px;font-weight:bold;")
            name_row.addWidget(shared_badge)
            
        is_owner = self.user.get("id") == self.device.get("owner_id")
        is_master = self.user.get("role") in ("master", "second_master")
        
        if is_owner or is_master:
            self.menu_btn = QPushButton("⋮")
            self.menu_btn.setFixedSize(20, 20)
            self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.menu_btn.setStyleSheet("QPushButton{background:transparent;color:#94a3b8;border:none;font-size:16px} QPushButton:hover{color:#3b82f6}")
            self.menu_btn.clicked.connect(self._show_device_menu)
            name_row.addWidget(self.menu_btn)
            
        name_row.addStretch()
        
        info.addLayout(name_row)

        self.meta_row = QHBoxLayout()
        self.meta_row.setSpacing(4)
        self.meta_row.setContentsMargins(0, 0, 0, 0)
        
        lbl_lan = QLabel("LAN:")
        lbl_lan.setStyleSheet("font-size:11px;color:#94a3b8;background:transparent;border:none;")
        self.meta_row.addWidget(lbl_lan)
        
        self.lan_btn = QPushButton()
        self.lan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lan_btn.setStyleSheet("QPushButton { background: transparent; color: #2563eb; border: none; font-size: 11px; text-align: left; } QPushButton:hover { color: #1d4ed8; text-decoration: underline; }")
        self.lan_btn.clicked.connect(self._open_lan_ip)
        self.meta_row.addWidget(self.lan_btn)
        
        self.zt_label = QLabel()
        self.zt_label.setStyleSheet("font-size:11px;color:#94a3b8;background:transparent;border:none;")
        self.meta_row.addWidget(self.zt_label)
        
        self.meta_row.addStretch()
        info.addLayout(self.meta_row)
        
        self._update_meta_labels()

        top.addLayout(info)
        top.addStretch()

        # Expansion Button and Share Button
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)
        
        lan_count = len(self.device.get("lan_devices", []))
        self.expand_btn = QPushButton(f"▼ LAN ({lan_count})")
        self.expand_btn.setFixedSize(80, 26)
        self.expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_btn.setStyleSheet("""
            QPushButton {
                background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 12px; font-weight: 500;
            }
            QPushButton:hover { background: #e2e8f0; }
        """)
        self.expand_btn.clicked.connect(self._toggle_expand)
        btn_layout.addWidget(self.expand_btn)
        
        # Share Button (Only if the user is the owner or master)
        is_owner = self.user.get("id") == self.device.get("owner_id")
        is_master = self.user.get("role") in ("master", "second_master")
        if (is_owner or is_master) and not self.device.get("is_shared"):
            self.share_btn = QPushButton("Share")
            self.share_btn.setFixedSize(80, 26)
            self.share_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.share_btn.setStyleSheet("""
                QPushButton {
                    background: white; color: #2563eb; border: 1px solid #2563eb; border-radius: 4px; font-size: 12px; font-weight: 500;
                }
                QPushButton:hover { background: #eff6ff; }
            """)
            self.share_btn.clicked.connect(self._open_share_dialog)
            btn_layout.addWidget(self.share_btn)
            
        self.router_btn = QPushButton("Open Router UI ↗")
        self.router_btn.setFixedSize(120, 26)
        self.router_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.router_btn.setStyleSheet("""
            QPushButton {
                background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; border-radius: 4px; font-size: 11px; font-weight: 600;
            }
            QPushButton:hover { background: #dbeafe; }
        """)
        self.router_btn.clicked.connect(self._open_lan_ip)
        self.router_btn.setVisible(bool(self.device.get("lan_ip") and self.device.get("lan_ip") != "—"))
        btn_layout.addWidget(self.router_btn)
            
        self.dl_btn = QPushButton("↓")
        self.dl_btn.setFixedSize(26, 26)
        self.dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dl_btn.setToolTip("Download .conf")
        self.dl_btn.setStyleSheet("""
            QPushButton {
                background: white; color: #475569; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background: #f8fafc; }
        """)
        self.dl_btn.clicked.connect(self._download_conf)
        btn_layout.addWidget(self.dl_btn)
            
        top.addLayout(btn_layout)

        # Toggle Switch
        self.toggle_sw = ToggleSwitch()
        
        self.toggle_sw.toggled.connect(self._on_toggle)
        top.addWidget(self.toggle_sw)

        self._update_status(self.local_status)

        self.main_layout.addLayout(top)

        # Expanded Panel
        self.expanded_panel = QWidget()
        self.expanded_panel.setVisible(False)
        self.expanded_layout = QVBoxLayout(self.expanded_panel)
        self.expanded_layout.setContentsMargins(0, 16, 0, 0)
        self.expanded_layout.setSpacing(0)
        
        self._rebuild_expanded_panel()

        self.main_layout.addWidget(self.expanded_panel)

    def _rebuild_expanded_panel(self):
        # Clear layout first
        while self.expanded_layout.count() > 0:
            item = self.expanded_layout.takeAt(0)
            # pyrefly: ignore [missing-attribute]
            w = item.widget()
            if w:
                w.deleteLater()
            # pyrefly: ignore [missing-attribute]
            l = item.layout()
            if l:
                while l.count() > 0:
                    li = l.takeAt(0)
                    if li.widget():
                        li.widget().deleteLater()
        
        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color:#e2e8f0;background:transparent;border:none;border-top:1px solid #e2e8f0;")
        self.expanded_layout.addWidget(div)
        
        # Nested Table Headers
        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 12, 0, 8)
        
        hdr_name = QLabel("NAME")
        hdr_ip = QLabel("IP ADDRESS")
        hdr_mac = QLabel("MAC ADDRESS")
        for lbl in (hdr_name, hdr_ip, hdr_mac):
            lbl.setStyleSheet("font-size:10px;font-weight:700;color:#64748b;background:transparent;border:none;")
            
        hdr_row.addWidget(hdr_name, 2)
        hdr_row.addWidget(hdr_ip, 2)
        hdr_row.addWidget(hdr_mac, 2)
        self.expanded_layout.addLayout(hdr_row)
        
        # Nested Table Rows
        lan_devs = self.device.get("lan_devices", [])
        if not lan_devs:
            none_label = QLabel("No devices found on this network.")
            none_label.setStyleSheet("color:#94a3b8;font-size:12px;padding:8px 0;background:transparent;border:none;")
            self.expanded_layout.addWidget(none_label)
        else:
            for ld in lan_devs:
                row_w = QWidget()
                row_w.setStyleSheet("border-top:1px solid #f1f5f9;background:transparent;")
                row_l = QHBoxLayout(row_w)
                row_l.setContentsMargins(0, 12, 0, 12)
                
                n_lbl = QLabel(ld.get("name") or "Unknown")
                n_lbl.setStyleSheet("font-size:13px;color:#334155;border:none;")
                
                ip_val = ld.get("ip_address") or "—"
                ip_btn = QPushButton(ip_val)
                ip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                ip_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #2563eb;
                        border: none;
                        font-size: 13px;
                        text-align: left;
                    }
                    QPushButton:hover {
                        color: #1d4ed8;
                        text-decoration: underline;
                    }
                """)
                if ip_val != "—":
                    ip_btn.clicked.connect(lambda _, a=ip_val: QDesktopServices.openUrl(QUrl(f"http://{a}")))
                
                mac_val = ld.get("mac_address") or "—"
                mac_lbl = QLabel(f" {mac_val} ")
                mac_lbl.setStyleSheet("background:#f1f5f9;color:#64748b;border-radius:4px;font-family:monospace;font-size:12px;padding:2px 4px;border:none;")
                mac_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                
                mac_w = QWidget()
                mac_l = QHBoxLayout(mac_w)
                mac_l.setContentsMargins(0,0,0,0)
                mac_l.addWidget(mac_lbl)
                mac_l.addStretch()
                mac_w.setStyleSheet("border:none;")
                
                row_l.addWidget(n_lbl, 2)
                row_l.addWidget(ip_btn, 2)
                row_l.addWidget(mac_w, 2)
                
                self.expanded_layout.addWidget(row_w)

        # Rescan Button
        rescan_w = QWidget()
        rescan_l = QHBoxLayout(rescan_w)
        rescan_l.setContentsMargins(0, 12, 0, 4)
        self.rescan_btn = QPushButton("↻ Rescan Network")
        self.rescan_btn.setFixedSize(130, 30)
        self.rescan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rescan_btn.setStyleSheet("""
            QPushButton {
                background: white;
                color: #64748b;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #f8fafc;
                color: #0f172a;
            }
        """)
        self.rescan_btn.clicked.connect(self._rescan_network)
        rescan_l.addWidget(self.rescan_btn)
        rescan_l.addStretch()
        rescan_w.setStyleSheet("background:transparent;border:none;")
        self.expanded_layout.addWidget(rescan_w)

    def _download_conf(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from widgets.common import Worker
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', self.device.get("name", "wg_client"))
        path, _ = QFileDialog.getSaveFileName(self, "Save WireGuard Config", f"{safe_name}.conf", "Conf Files (*.conf)")
        if not path:
            return
            
        self._dl_w = Worker(self.api.download_conf, self.device["id"])
        self._dl_w.result.connect(lambda data, p=path: self._save_conf_file(data, p))
        self._dl_w.error.connect(lambda e: QMessageBox.warning(self, "Error", f"Download failed: {e}"))
        self._dl_w.start()

    def _save_conf_file(self, data: str, path: str):
        from PyQt6.QtWidgets import QMessageBox
        try:
            with open(path, "w") as f:
                f.write(data)
            QMessageBox.information(self, "Success", "Config downloaded successfully!")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save: {e}")

    def _rescan_network(self):
        self.rescan_btn.setText("Scanning…")
        self.rescan_btn.setEnabled(False)
        
        # Scan the physical LAN network subnet
        local_ip = self.device.get("lan_ip") or self.device.get("zerotier_ip")
        
        # pyrefly: ignore [bad-argument-type]
        self._scan_worker = ScanWorker(self.api, self.device["id"], local_ip)
        def on_done(devices):
            try:
                self.rescan_btn.setText("↻ Rescan Network")
                self.rescan_btn.setEnabled(True)
                self.device["lan_devices"] = devices
                lan_count = len(devices)
                self.expand_btn.setText(f"▲ LAN ({lan_count})" if self.expanded else f"▼ LAN ({lan_count})")
                self._rebuild_expanded_panel()
            except RuntimeError:
                pass

        def on_error(err):
            try:
                self.rescan_btn.setText("↻ Rescan Network")
                self.rescan_btn.setEnabled(True)
                print("Scan error:", err)
            except RuntimeError:
                pass

        self._scan_worker.done.connect(on_done)
        self._scan_worker.error.connect(on_error)
        self._scan_worker.start()

    def _toggle_expand(self):
        self.expanded = not self.expanded
        self.expanded_panel.setVisible(self.expanded)
        lan_count = len(self.device.get("lan_devices", []))
        if self.expanded:
            self.expand_btn.setText(f"▲ LAN ({lan_count})")
        else:
            self.expand_btn.setText(f"▼ LAN ({lan_count})")

    def _open_share_dialog(self):
        dlg = ShareDeviceDialog(self.device, self.api, self.window())
        dlg.exec()

    def _rename_device(self):
        from PyQt6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(self, "Rename Device", "Enter new name:", text=self.device.get("name", ""))
        if ok and new_name.strip():
            # Fire and forget rename via API
            try:
                import threading
                threading.Thread(target=self.api.rename_device, args=(self.device["id"], new_name.strip()), daemon=True).start()
                self.name_label.setText(new_name.strip())
            except Exception:
                pass

    def _open_lan_ip(self):
        lan = self.device.get("lan_ip")
        if lan and lan != "—":
            QDesktopServices.openUrl(QUrl(f"http://{lan}"))

    def _show_device_menu(self):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:white;border:1px solid #e2e8f0;border-radius:4px;} QMenu::item{padding:6px 20px;} QMenu::item:selected{background:#f1f5f9;}")
        
        reprov_action = menu.addAction("Re-provision Tunnel")
        action = menu.exec(self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomLeft()))
        
        if action == reprov_action:
            self._open_reprovision_dialog()
            
    def _open_reprovision_dialog(self):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QHBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("Re-provision Tunnel")
        dlg.setFixedSize(300, 150)
        dlg.setStyleSheet("QDialog{background:#f1f5f9} QLabel{color:#0f172a}")
        lay = QVBoxLayout(dlg)
        
        lay.addWidget(QLabel("Force tunnel to:"))
        cb = QComboBox()
        cb.addItems(["auto", "wireguard", "zerotier"])
        lay.addWidget(cb)
        
        btn_lay = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        submit_btn = QPushButton("Submit")
        submit_btn.setStyleSheet("background:#2563eb;color:white;border:none;border-radius:4px;padding:6px;")
        
        def on_submit():
            try:
                self.api.reprovision_device(self.device["id"], cb.currentText())
                dlg.accept()
            except Exception as e:
                print("Failed to reprovision:", e)
                
        submit_btn.clicked.connect(on_submit)
        btn_lay.addWidget(cancel_btn)
        btn_lay.addWidget(submit_btn)
        lay.addLayout(btn_lay)
        dlg.exec()

    def _update_meta_labels(self):
        lan = self.device.get("lan_ip") or "—"
        conn_info = self.device.get("connection_info", {})
        ttype = conn_info.get("tunnel_type", "zerotier")
        tun_ip = conn_info.get("virtual_ip") or "—"
        
        if ttype == "wireguard":
            prefix = "WG"
        else:
            prefix = "ZT"
            
        if lan != "—":
            self.lan_btn.setText(lan)
            self.lan_btn.setStyleSheet("QPushButton { background: transparent; color: #2563eb; border: none; font-size: 11px; text-align: left; } QPushButton:hover { color: #1d4ed8; text-decoration: underline; }")
            self.lan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if hasattr(self, 'router_btn'): self.router_btn.setVisible(True)
        else:
            self.lan_btn.setText("—")
            self.lan_btn.setStyleSheet("QPushButton { background: transparent; color: #94a3b8; border: none; font-size: 11px; text-align: left; }")
            self.lan_btn.setCursor(Qt.CursorShape.ArrowCursor)
            if hasattr(self, 'router_btn'): self.router_btn.setVisible(False)
            
        nat_pool = self.device.get("nat_virtual_pool")
        if nat_pool:
            self.zt_label.setText(f"  ·  {prefix}: {tun_ip}  ·  NAT Pool: {nat_pool}.0/24")
            self.zt_label.setStyleSheet("font-size:11px;color:#ef4444;background:transparent;border:none;font-weight:bold;")
        else:
            self.zt_label.setText(f"  ·  {prefix}: {tun_ip}")
            self.zt_label.setStyleSheet("font-size:11px;color:#94a3b8;background:transparent;border:none;")

    def update_data(self, device: dict):
        self.device = device
        self.name_label.setText(self.device.get("name") or "Gateway")
        self.conflict_badge.setVisible(bool(self.device.get("has_conflict")))
        self._update_meta_labels()
        lan_count = len(self.device.get("lan_devices", []))
        if self.expanded:
            self.expand_btn.setText(f"▲ LAN ({lan_count})")
        else:
            self.expand_btn.setText(f"▼ LAN ({lan_count})")
        self._update_status(self.local_status)

    def _update_status(self, status: str):
        self.local_status = status
        remote_status = self.device.get("status", "offline")
        if remote_status == "active":
            dot_color = "#10b981"  # green
        elif remote_status in ("connecting", "pending"):
            dot_color = "#f59e0b"  # orange/yellow
        else:
            dot_color = "#94a3b8"  # gray
            
        self.dot.setStyleSheet(f"color:{dot_color};font-size:12px;background:transparent;border:none;")
        self.toggle_sw.setChecked(status in ("connected", "connecting"))
        
        if status == "connecting":
            self.toggle_sw.set_interactable(False)
        else:
            self.toggle_sw.set_interactable(True)

    def _on_toggle(self, checked: bool, is_sync: bool = False):
        self._update_status("connecting" if checked else "disconnected")

        from services.tunnel_manager import TunnelManager
        is_local = TunnelManager.is_local_device(self.device)

        if is_local:
            if not hasattr(self, "_workers"):
                self._workers = []
                
            worker = ConnectWorker(self.device, self.api, checked)
            worker.done.connect(self._on_connect_done)
            worker.finished.connect(lambda w=worker: self._workers.remove(w) if w in getattr(self, "_workers", []) else None)
            self._workers.append(worker)
            worker.start()

        if not is_sync:
            # Tell backend so other sessions of this user sync the toggle
            device_id = self.device.get("id")
            if device_id:
                try:
                    import threading
                    net_id = self.device.get("connection_info", {}).get("network_id", "")
                    threading.Thread(target=self.api.sync_device_toggle, args=(device_id, net_id, checked), daemon=True).start()
                except Exception:
                    pass

    def _on_connect_done(self, ok: bool, status: str):
        if not ok:
            self._update_status("disconnected")
        else:
            self._update_status(status)
            
        device_id = self.device.get("id")
        if device_id and not getattr(self, "_is_syncing", False):
            try:
                import threading
                threading.Thread(target=self.api.sync_device_status, args=(device_id, "active" if ok else "offline"), daemon=True).start()
            except Exception:
                pass
