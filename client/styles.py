SIDEBAR_W = 248

APP_STYLE = """
QMainWindow, QWidget#root {
    background: #f0f4f8;
    color: #0f172a;
    font-family: 'Plus Jakarta Sans', 'IBM Plex Sans', 'Segoe UI';
    font-size: 15px;
}
QScrollArea  { background: transparent; border: none; }
QScrollBar:vertical   { background: rgba(148,163,184,0.18); width: 8px;  border-radius: 4px; }
QScrollBar:horizontal { background: rgba(148,163,184,0.18); height: 8px; border-radius: 4px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: rgba(100,116,139,0.8); border-radius: 4px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QLabel  { background: transparent; }
QFrame  { color: #0f172a; }
QToolTip { background: #0d1b2a; color: white; border: 1px solid rgba(255,255,255,0.12); }

/* ── Sidebar ── */
QFrame#sidebar { background: #0d1b2a; border-right: 1px solid rgba(255,255,255,0.06); }

QPushButton#nav-btn {
    background: transparent; border: none; border-radius: 10px;
    color: #94a3b8; text-align: left; padding: 11px 14px;
    margin: 4px 12px; font-size: 14px; font-family: 'Plus Jakarta Sans', 'IBM Plex Sans', 'Segoe UI';
}
QPushButton#nav-btn:hover  { background: rgba(255,255,255,0.06); color: #e2e8f0; }
QPushButton#nav-btn[active="true"] { color: white; background: rgba(37,99,235,0.20); }
QPushButton#nav-logout {
    background: transparent; border: none; border-radius: 10px;
    color: #f87171; text-align: left; padding: 11px 14px;
    margin: 4px 12px; font-size: 14px; font-family: 'Plus Jakarta Sans', 'IBM Plex Sans', 'Segoe UI';
}
QPushButton#nav-logout:hover { background: rgba(248,71,71,0.08); color: #fca5a5; }

/* ── Buttons ── */
QPushButton#btn-primary {
    background: #2563eb; color: white; border: none; border-radius: 8px;
    padding: 9px 18px; font-size: 14px; font-weight: 600;
}
QPushButton#btn-primary:hover    { background: #1d4ed8; }
QPushButton#btn-primary:disabled { background: #93c5fd; color: #eff6ff; }

QPushButton#btn-ghost {
    background: white; color: #0f172a; border: 1px solid #e2e8f0;
    border-radius: 8px; padding: 9px 18px; font-size: 14px;
}
QPushButton#btn-ghost:hover { background: #f8fafc; }

QPushButton#btn-danger {
    background: white; color: #dc2626; border: 1px solid #fecaca;
    border-radius: 8px; padding: 6px 14px; font-size: 13px;
}
QPushButton#btn-danger:hover { background: #fee2e2; }

QPushButton#btn-sm {
    background: white; color: #0f172a; border: 1px solid #e2e8f0;
    border-radius: 6px; padding: 5px 12px; font-size: 13px;
}
QPushButton#btn-sm:hover { background: #f8fafc; }

/* ── Inputs ── */
QLineEdit, QComboBox {
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
    padding: 10px 14px; color: #0f172a; font-size: 15px;
}
QLineEdit:focus, QComboBox:focus { border-color: #2563eb; }
QLineEdit::placeholder { color: #94a3b8; }
QComboBox::drop-down { border: none; padding-right: 10px; }
QComboBox QAbstractItemView { background: white; color: #0f172a; border: 1px solid #e2e8f0; selection-background-color: #dbeafe; }

/* ── Tables ── */
QTableWidget {
    background: white; color: #0f172a; gridline-color: #f1f5f9;
    border: none; font-size: 14px;
}
QTableWidget::item          { padding: 0px 18px; border-bottom: 1px solid #f1f5f9; }
QTableWidget::item:selected { background: #dbeafe; color: #0f172a; }
QHeaderView::section {
    background: #f8fafc; color: #64748b; border: none;
    border-bottom: 1px solid #e2e8f0; padding: 11px 18px;
    font-size: 11px; font-weight: 700; text-transform: uppercase;
}

/* ── Cards ── */
QFrame#card {
    background: white; border: 1px solid #e2e8f0; border-radius: 12px;
}
QFrame#stat-card {
    background: white; border: 1px solid #e2e8f0; border-radius: 12px;
}
"""

AUTH_STYLE = """
QWidget { background: #f0f4f8; color: #0f172a; font-family: 'Plus Jakarta Sans', 'IBM Plex Sans', 'Segoe UI'; font-size: 14px; }
QFrame#auth-card {
    background: white; border: 1px solid #e2e8f0; border-radius: 14px;
}
QLineEdit {
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
    padding: 10px 13px; color: #0f172a; font-size: 14px;
}
QLineEdit:focus { border-color: #2563eb; }
QLineEdit::placeholder { color: #94a3b8; }
QPushButton#btn-primary {
    background: #2563eb; color: white; border: none; border-radius: 8px;
    padding: 11px 20px; font-size: 14px; font-weight: 600;
}
QPushButton#btn-primary:hover    { background: #1d4ed8; }
QPushButton#btn-primary:disabled { background: #93c5fd; }
QPushButton#btn-ghost {
    background: white; color: #0f172a; border: 1px solid #e2e8f0;
    border-radius: 8px; padding: 11px 20px; font-size: 14px;
}
QPushButton#btn-ghost:hover { background: #f8fafc; }
QLabel { background: transparent; }
QLabel#error   { color: #dc2626; font-size: 13px; }
QLabel#success { color: #16a34a; font-size: 13px; }
QLabel#muted   { color: #64748b; font-size: 13px; }
"""

ROLE_COLORS = {
    "master":        ("#fff7ed", "#c2410c"),
    "second_master": ("#f0fdf4", "#15803d"),
    "admin":         ("#eff6ff", "#1d4ed8"),
    "trusted":       ("#f5f3ff", "#6d28d9"),
    "system_owner":  ("#fffbeb", "#b45309"),
}

STATUS_COLORS = {
    "active":   ("#dcfce7", "#15803d"),
    "pending":  ("#fef9c3", "#a16207"),
    "inactive": ("#f1f5f9", "#64748b"),
    "online":   ("#dcfce7", "#15803d"),
    "offline":  ("#fee2e2", "#b91c1c"),
    "connecting": ("#fef9c3", "#a16207"),
}

LEVEL_COLORS = {
    "success": ("#dcfce7", "#15803d"),
    "info":    ("#dbeafe", "#1d4ed8"),
    "warning": ("#fef9c3", "#a16207"),
    "error":   ("#fee2e2", "#b91c1c"),
}
