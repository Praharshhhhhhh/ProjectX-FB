import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import pyqtSignal, Qt
from services.api_client import api
from services.tunnel_manager import tunnel_manager
from windows.login_window import LoginWindow
from windows.activate_key_window import ActivateKeyWindow
from windows.verify_otp_window import VerifyOtpWindow
from windows.main_window import MainWindow
from windows.owner_window import OwnerWindow
from windows.home_window import HomeWindow
from config import APP_NAME


class App:
    def __init__(self):
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.qt_app.setStyle("Fusion")
        self._token_data = {}
        self._user_info  = {}
        
        from windows.root_window import RootWindow
        self.root = RootWindow()
        self.root.closeEvent = self._on_root_close
        
        self._setup_tray()
        
        self._show_login()

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon()
        from widgets.common import load_icon, asset_path
        icon = load_icon(asset_path("logo-square.svg"), 32)
        if icon:
            self.tray_icon.setIcon(icon)
        else:
            # Fallback if no icon
            from PyQt6.QtGui import QPixmap
            pm = QPixmap(32, 32)
            pm.fill(Qt.GlobalColor.transparent)
            self.tray_icon.setIcon(QIcon(pm))
            
        self.tray_menu = QMenu()
        
        self.action_status = QAction("Status: Disconnected", self.qt_app)
        self.action_status.setEnabled(False)
        self.tray_menu.addAction(self.action_status)
        
        self.tray_menu.addSeparator()
        
        self.action_show = QAction("Show Dashboard", self.qt_app)
        self.action_show.triggered.connect(self.root.showNormal)
        self.tray_menu.addAction(self.action_show)
        
        self.action_reconnect = QAction("Reconnect", self.qt_app)
        self.action_reconnect.triggered.connect(lambda: tunnel_manager.start(self._get_device_name()))
        self.tray_menu.addAction(self.action_reconnect)
        
        self.action_disconnect = QAction("Disconnect", self.qt_app)
        self.action_disconnect.triggered.connect(tunnel_manager.stop)
        self.tray_menu.addAction(self.action_disconnect)
        
        self.action_rotate = QAction("Rotate Keys", self.qt_app)
        self.action_rotate.triggered.connect(self._rotate_keys)
        self.tray_menu.addAction(self.action_rotate)
        
        self.tray_menu.addSeparator()
        
        self.action_quit = QAction("Quit", self.qt_app)
        self.action_quit.triggered.connect(self.quit_app)
        self.tray_menu.addAction(self.action_quit)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()
        
        tunnel_manager.status_changed.connect(self._on_tunnel_status)

    def _get_device_name(self):
        import socket
        return socket.gethostname()

    def _on_tunnel_status(self, status: str):
        self.action_status.setText(f"Status: {status}")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.root.showNormal()

    def _on_root_close(self, event):
        # Minimize to tray
        event.ignore()
        self.root.hide()
        self.tray_icon.showMessage(APP_NAME, "Application is running in the background.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def _rotate_keys(self):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(None, 'Rotate Keys', 
                                     'Are you sure you want to rotate your WireGuard keys?\nThis will briefly interrupt your connection.',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            tunnel_manager.rotate_keys()

    def quit_app(self):
        tunnel_manager.stop()
        self.qt_app.quit()

    # ── Home ──────────────────────────────────────────────────────
    def _show_home(self):
        self._home = HomeWindow()
        self._home.goto_login.connect(self._show_login)
        self._home.goto_activate.connect(self._show_activate_from_home)
        self.root.set_view(self._home)

    # ── Login ─────────────────────────────────────────────────────
    def _show_login(self):
        self._login = LoginWindow(api)
        self._login.login_success.connect(self._on_login_success)
        self._login.otp_required.connect(self._show_otp_verification)
        self._login.goto_activate.connect(self._show_activate)
        self.root.set_view(self._login)

    def _show_activate_from_home(self):
        self._show_activate()

    def _show_activate(self):
        self._activate = ActivateKeyWindow(api)
        self._activate.activation_success.connect(self._on_activation_success)
        self._activate.goto_login.connect(self._back_to_login)
        self.root.set_view(self._activate)

    def _back_to_login(self):
        self._show_login()

    def _on_login_success(self, token_data: dict, me: dict):
        self._token_data = token_data
        self._user_info  = me
        self._show_main()
        
        # Start the background tunnel manager
        tunnel_manager.start(self._get_device_name())

    def _show_otp_verification(self, email: str):
        self._otp = VerifyOtpWindow(api, email)
        self._otp.otp_verified.connect(self._on_login_success)
        self._otp.goto_login.connect(self._show_login)
        self.root.set_view(self._otp)

    def _on_activation_success(self, token_data: dict):
        self._token_data = token_data
        # Once activated, key returns token directly, go fetch user info and show main
        self._user_info = api.get_me()
        self._show_main()

    # ── Main portal ───────────────────────────────────────────────
    def _show_main(self):
        self._user_info = api.get_me()
        role = self._user_info.get("role", "")
        
        if role == "system_owner":
            self._main = OwnerWindow(api, self._user_info)
        else:
            self._main = MainWindow(api, self._user_info)
            
        self._main.logged_out.connect(self._on_logout)
        self.root.set_view(self._main)

    def _on_logout(self):
        tunnel_manager.stop()
        self._user_info = {}
        self._token_data = {}
        api.logout()
        self._show_login()

    def run(self) -> int:
        self.root.showMaximized()
        from widgets.common import cleanup_workers
        
        def _on_quit():
            cleanup_workers()
            
        self.qt_app.aboutToQuit.connect(_on_quit)
        return self.qt_app.exec()


if __name__ == "__main__":
    sys.exit(App().run())
