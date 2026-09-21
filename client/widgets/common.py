from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QLabel, QFrame, QHBoxLayout, QVBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QTimer
from PyQt6.QtGui import QFont, QColor, QPixmap, QIcon, QPainter
import httpx
# pyrefly: ignore [missing-import]
from styles import ROLE_COLORS, STATUS_COLORS, LEVEL_COLORS


import sys

if getattr(sys, 'frozen', False):
    ASSET_DIR = Path(sys._MEIPASS) / "assets"
else:
    ASSET_DIR = Path(__file__).resolve().parent.parent / "assets"


def asset_path(name: str) -> Path:
    return ASSET_DIR / name


def _pixmap_from_path(path: str | Path, size: int) -> QPixmap:
    icon = QIcon(str(path))
    pix = icon.pixmap(size, size)
    if pix.isNull():
        pix = QPixmap(str(path))
    return pix


def load_icon(path: str | Path, size: int = 24, tint: str | None = None) -> QIcon:
    pix = _pixmap_from_path(path, size)
    if pix.isNull():
        return QIcon()
    if tint:
        tinted = QPixmap(pix.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, pix)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), QColor(tint))
        painter.end()
        pix = tinted
    return QIcon(pix)


def icon_label(
    text: str = "",
    *,
    path: str | Path | None = None,
    size: int = 44,
    icon_size: int = 24,
    bg: str = "rgba(37,99,235,0.1)",
    radius: int = 10,
    color: str = "#2563eb",
) -> QLabel:
    lbl = QLabel(text)
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"background:{bg};border-radius:{radius}px;font-size:18px;color:{color}"
    )
    if path:
        pix = _pixmap_from_path(path, icon_size)
        if not pix.isNull():
            lbl.setPixmap(
                pix.scaled(
                    icon_size,
                    icon_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            lbl.setStyleSheet(f"background:{bg};border-radius:{radius}px;padding:0px;")
    return lbl


# ── Worker thread for API calls ───────────────────────────────────────────────
_active_workers = set()

def cleanup_workers():
    for w in list(_active_workers):
        try:
            w.terminate()
            w.wait()
        except Exception:
            pass


class Worker(QThread):
    result = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def start(self, *args, **kwargs):
        _active_workers.add(self)
        self.finished.connect(self._cleanup)
        super().start(*args, **kwargs)

    def _cleanup(self):
        _active_workers.discard(self)
        self.deleteLater()

    def run(self):
        try:
            self.result.emit(self._fn(*self._args, **self._kwargs))
        except httpx.HTTPStatusError as e:
            try:
                msg = e.response.json().get("detail", "Request failed")
                if isinstance(msg, list):
                    msg = msg[0].get("msg", "Validation error")
            except Exception:
                msg = "Request failed"
            self.error.emit(str(msg))
        except Exception as e:
            self.error.emit(str(e))


# ── Stat card ────────────────────────────────────────────────────────────────
class StatCard(QFrame):
    def __init__(
        self,
        label: str,
        value: str = "—",
        icon: str = "",
        color: str = "#2563eb",
        icon_path: str | Path | None = None,
        tile: str = "#eff6ff",
    ):
        super().__init__()
        self.setObjectName("stat-card")
        self.setMinimumHeight(92)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        if tile == "#eff6ff":
            tile = {
                "#2563eb": "#eff6ff",
                "#3b82f6": "#eff6ff",
                "#16a34a": "#f0fdf4",
                "#22c55e": "#f0fdf4",
                "#ea580c": "#fff7ed",
                "#f59e0b": "#fffbeb",
                "#d97706": "#fffbeb",
                "#dc2626": "#fef2f2",
                "#7c3aed": "#f5f3ff",
            }.get(color, tile)

        if icon_path or icon:
            icon_lbl = QLabel()
            icon_lbl.setFixedSize(48, 48)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setStyleSheet(f"background:{tile};border-radius:12px")
            if icon_path:
                # pyrefly: ignore [bad-assignment]
                icon = load_icon(icon_path, 28, tint=color)
                # pyrefly: ignore [missing-attribute]
                pix = icon.pixmap(28, 28)
                if not pix.isNull():
                    icon_lbl.setPixmap(pix)
            else:
                icon_lbl.setText(icon)
                icon_lbl.setStyleSheet(f"background:{tile};border-radius:12px;font-size:20px")
            layout.addWidget(icon_lbl)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        # pyrefly: ignore [unnecessary-type-conversion]
        self._val_lbl = QLabel(str(value))
        self._val_lbl.setStyleSheet(f"font-size:28px;font-weight:800;color:{color};background:transparent")
        self._lbl_lbl = QLabel(label)
        self._lbl_lbl.setStyleSheet("font-size:13px;color:#64748b;background:transparent")
        text_col.addWidget(self._val_lbl)
        text_col.addWidget(self._lbl_lbl)
        layout.addLayout(text_col)
        layout.addStretch()

    def set_value(self, v):
        self._val_lbl.setText(str(v))


# ── Badge label ──────────────────────────────────────────────────────────────
class Badge(QLabel):
    def __init__(self, text: str, bg: str = "#dbeafe", fg: str = "#1d4ed8"):
        super().__init__(text)
        self.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:12px;"
            f"padding:3px 10px;font-size:12px;font-weight:600"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


def role_badge(role: str) -> Badge:
    bg, fg = ROLE_COLORS.get(role, ("#f1f5f9", "#64748b"))
    return Badge(role.replace("_", " ").title(), bg, fg)


def status_badge(status: str) -> Badge:
    bg, fg = STATUS_COLORS.get(status, ("#f1f5f9", "#64748b"))
    return Badge(status.title(), bg, fg)


def level_badge(level: str) -> Badge:
    bg, fg = LEVEL_COLORS.get(level, ("#dbeafe", "#1d4ed8"))
    return Badge(level.title(), bg, fg)


# ── Card frame ───────────────────────────────────────────────────────────────
class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")


# ── Card with header ─────────────────────────────────────────────────────────
class CardWithHeader(QFrame):
    def __init__(self, title: str, action_text: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 16, 0)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet(
            "QFrame{background:#f8fafc;border-bottom:1px solid #e2e8f0;"
            "border-top-left-radius:12px;border-top-right-radius:12px;}"
        )
        h = QHBoxLayout(header)
        h.setContentsMargins(20, 14, 20, 14)
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("font-size:15px;font-weight:600;color:#0f172a;background:transparent")
        h.addWidget(self.title_lbl)
        h.addStretch()
        self.action_btn = None
        if action_text:
            self.action_btn = QPushButton(action_text)
            self.action_btn.setObjectName("btn-sm")
            h.addWidget(self.action_btn)
        self._layout.addWidget(header)

    def add_widget(self, w):
        self._layout.addWidget(w)

    def add_layout(self, l):
        self._layout.addLayout(l)


# ── Standard table ──────────────────────────────────────────────────────────
def make_table(columns: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels(columns)
    # pyrefly: ignore [missing-attribute]
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    # pyrefly: ignore [missing-attribute]
    t.verticalHeader().setVisible(False)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setAlternatingRowColors(False)
    t.setShowGrid(False)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    # pyrefly: ignore [missing-attribute]
    t.verticalHeader().setDefaultSectionSize(50)
    # pyrefly: ignore [missing-attribute]
    t.horizontalHeader().setStretchLastSection(False)
    return t


def table_item(text: str, align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter) -> QTableWidgetItem:
    # pyrefly: ignore [unnecessary-type-conversion]
    item = QTableWidgetItem(str(text))
    item.setTextAlignment(align)
    return item


# ── Section title ────────────────────────────────────────────────────────────
class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", btn_text: str = ""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        t = QLabel(title)
        t.setStyleSheet("font-size:24px;font-weight:700;color:#0f172a;background:transparent")
        text_col.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet("font-size:14px;color:#64748b;background:transparent")
            text_col.addWidget(s)
        layout.addLayout(text_col)
        layout.addStretch()

        self.action_btn = None
        if btn_text:
            self.action_btn = QPushButton(btn_text)
            self.action_btn.setObjectName("btn-primary")
            self.action_btn.setFixedHeight(38)
            layout.addWidget(self.action_btn)


# ── Alert bar (animated toast) ───────────────────────────────────────────────
class AlertBar(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setVisible(False)
        self.setStyleSheet("padding:10px 14px;border-radius:8px;font-size:13px")

        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(1.0)
        self._anim = QPropertyAnimation(self._effect, b"opacity", self)
        self._anim.setDuration(220)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.clear)

    def _flash(self, msg: str, style: str, prefix: str = "", auto_ms: int = 3500):
        self.setText(f"{prefix}  {msg}" if prefix else msg)
        self.setStyleSheet(style)
        self.setVisible(True)
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._hide_timer.start(auto_ms)

    def show_error(self, msg: str):
        self._flash(
            msg,
            "background:#fee2e2;color:#b91c1c;border:1px solid #fecaca;"
            "padding:10px 14px;border-radius:8px;font-size:13px",
            prefix="⚠",
            auto_ms=5000,
        )

    def show_success(self, msg: str):
        self._flash(
            msg,
            "background:#dcfce7;color:#15803d;border:1px solid #bbf7d0;"
            "padding:10px 14px;border-radius:8px;font-size:13px",
            prefix="✓",
        )

    def clear(self):
        self._hide_timer.stop()
        self.setVisible(False)
        self.setText("")
