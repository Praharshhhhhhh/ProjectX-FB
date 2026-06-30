import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from services.api_client import api
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
        self.qt_app.setStyle("Fusion")
        self._token_data = {}
        self._user_info  = {}
        
        from windows.root_window import RootWindow
        self.root = RootWindow()
        
        self._show_login()

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
