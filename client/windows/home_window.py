from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QFont

# pyrefly: ignore [missing-import]
from widgets.common import asset_path, load_icon


class HomeWindow(QWidget):
    goto_login    = pyqtSignal()
    goto_activate = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setMinimumSize(1000, 660)
        self.setStyleSheet("QWidget { font-family: 'Segoe UI'; } QLabel { background: transparent; }")
        self._build()

    # ── build ──────────────────────────────────────────────────────────────────
    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: #0a0f1e; } QScrollBar:vertical { background: #0a0f1e; width: 7px; } QScrollBar::handle:vertical { background: #1e293b; border-radius: 3px; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        page = QWidget()
        page.setStyleSheet("background: #0a0f1e;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._navbar())
        lay.addWidget(self._hero())
        lay.addWidget(self._stats_bar())
        lay.addWidget(self._exposure_section())
        lay.addWidget(self._features_section())
        lay.addWidget(self._footer())

        scroll.setWidget(page)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    # ── Navbar ─────────────────────────────────────────────────────────────────
    def _navbar(self):
        bar = QWidget()
        bar.setFixedHeight(62)
        bar.setStyleSheet("background: rgba(10,15,30,0.98); border-bottom: 1px solid rgba(255,255,255,0.07);")
        h = QHBoxLayout(bar)
        h.setContentsMargins(48, 0, 48, 0)
        h.setSpacing(0)

        # Logo
        icon = QLabel()
        icon.setFixedSize(32, 32)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(load_icon(asset_path("logo-square.svg"), 32).pixmap(32, 32))
        name = QLabel("ProjectX")
        name.setStyleSheet("color:#fff;font-weight:700;font-size:18px;margin-left:10px;margin-right:36px")
        h.addWidget(icon)
        h.addWidget(name)

        for lnk in ["Company", "Solutions", "Platform", "Pricing", "Contact"]:
            l = QLabel(lnk)
            l.setStyleSheet("color:#94a3b8;font-size:14px;margin:0 14px;")
            h.addWidget(l)

        h.addStretch()
        si = QPushButton("Sign In")
        si.setStyleSheet("QPushButton{background:transparent;color:#cbd5e1;border:none;font-size:14px;padding:8px 18px;} QPushButton:hover{color:#fff;}")
        si.clicked.connect(self.goto_login.emit)
        bd = QPushButton("Book a Demo")
        bd.setFixedHeight(38)
        bd.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:8px;font-size:14px;font-weight:600;padding:0 22px;} QPushButton:hover{background:#1d4ed8;}")
        bd.clicked.connect(self.goto_login.emit)
        h.addWidget(si)
        h.addWidget(bd)
        return bar

    # ── Hero ───────────────────────────────────────────────────────────────────
    def _hero(self):
        hero = QWidget()
        hero.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #0a0f1e,stop:0.5 #0d1a3a,stop:1 #0a0f1e);")
        hero.setMinimumHeight(520)
        h = QHBoxLayout(hero)
        h.setContentsMargins(80, 72, 60, 72)
        h.setSpacing(60)

        # ── Left ──────────────────────────────────────────────────────────────
        left = QWidget(); left.setStyleSheet("background:transparent")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        ll.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Eyebrow
        ey = QLabel("  🔒  OT Network Security Platform  ")
        ey.setFixedHeight(30)
        ey.setStyleSheet("background:rgba(37,99,235,0.18);color:#60a5fa;border:1px solid rgba(37,99,235,0.4);border-radius:15px;font-size:11px;font-weight:700;letter-spacing:1px;padding:0 6px")
        ey_row = QHBoxLayout(); ey_row.setContentsMargins(0,0,0,0)
        ey_row.addWidget(ey); ey_row.addStretch()
        ll.addLayout(ey_row)
        ll.addSpacing(24)

        # Headline
        h1 = QLabel("Your Industrial")
        h1.setStyleSheet("color:#ffffff;font-size:52px;font-weight:800;letter-spacing:-1.5px;line-height:1")
        h2 = QLabel("Network.")
        h2.setStyleSheet("color:#ffffff;font-size:52px;font-weight:800;letter-spacing:-1.5px")
        h3 = QLabel("Secured. Visible.")
        h3.setStyleSheet("color:#3b82f6;font-size:52px;font-weight:800;letter-spacing:-1.5px")
        h4 = QLabel("Fully Under Control.")
        h4.setStyleSheet("color:#ffffff;font-size:52px;font-weight:800;letter-spacing:-1.5px")
        for lbl in [h1, h2, h3, h4]:
            lbl.setStyleSheet(lbl.styleSheet() + "background:transparent;")
            ll.addWidget(lbl)
        ll.addSpacing(20)

        desc = QLabel("Secure, encrypted access to every OT device from anywhere.\nNo open ports. No legacy VPN. Trusted by 14k+ industrial sites.")
        desc.setStyleSheet("color:#94a3b8;font-size:15px;line-height:1.6;background:transparent")
        desc.setWordWrap(True)
        ll.addWidget(desc)
        ll.addSpacing(32)

        # Buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(14); btn_row.setContentsMargins(0,0,0,0)
        demo_btn = QPushButton("→  Sign In to Dashboard")
        demo_btn.setFixedHeight(50)
        demo_btn.setStyleSheet("QPushButton{background:#2563eb;color:white;border:none;border-radius:10px;font-size:15px;font-weight:700;padding:0 28px;} QPushButton:hover{background:#1d4ed8;}")
        demo_btn.clicked.connect(self.goto_login.emit)
        plat_btn = QPushButton("Activate Master Account")
        plat_btn.setFixedHeight(50)
        plat_btn.setStyleSheet("QPushButton{background:transparent;color:#fff;border:2px solid rgba(255,255,255,0.3);border-radius:10px;font-size:15px;font-weight:600;padding:0 28px;} QPushButton:hover{background:rgba(255,255,255,0.07);border-color:rgba(255,255,255,0.6);}")
        plat_btn.clicked.connect(self.goto_activate.emit)
        btn_row.addWidget(demo_btn); btn_row.addWidget(plat_btn); btn_row.addStretch()
        ll.addLayout(btn_row)
        ll.addSpacing(16)

        note = QLabel("In 2000+ sites worldwide  ·  No credit card required")
        note.setStyleSheet("color:#475569;font-size:12px;background:transparent")
        ll.addWidget(note)

        h.addWidget(left, 5)

        # ── Right: Dashboard Mockup ────────────────────────────────────────────
        mockup = self._dashboard_mockup()
        h.addWidget(mockup, 4)

        return hero

    def _dashboard_mockup(self):
        card = QFrame()
        card.setStyleSheet("""
            QFrame { background:#111827; border:1px solid rgba(255,255,255,0.1);
                     border-radius:14px; }
        """)
        card.setMinimumWidth(380)
        card.setMaximumWidth(480)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Title bar
        tbar = QWidget()
        tbar.setFixedHeight(44)
        tbar.setStyleSheet("background:#0f172a;border-radius:14px 14px 0 0;border-bottom:1px solid rgba(255,255,255,0.06)")
        tb = QHBoxLayout(tbar); tb.setContentsMargins(14, 0, 14, 0); tb.setSpacing(6)
        for c, cs in [("#ef4444",""), ("#eab308","margin-left:2px"), ("#22c55e","margin-left:2px")]:
            d = QLabel("●"); d.setStyleSheet(f"color:{c};font-size:11px;{cs}")
            tb.addWidget(d)
        tb.addStretch()
        url = QLabel("localhost:8000/dashboard")
        url.setStyleSheet("background:rgba(255,255,255,0.06);color:#475569;font-size:11px;border-radius:4px;padding:2px 12px")
        tb.addWidget(url)
        tb.addStretch()
        lay.addWidget(tbar)

        # Stats row
        stats_w = QWidget(); stats_w.setStyleSheet("background:transparent")
        sr = QHBoxLayout(stats_w); sr.setContentsMargins(14,12,14,8); sr.setSpacing(8)
        for val, lbl, color in [("6","Online","#22c55e"),("2","Pending","#f59e0b"),("4","Users","#60a5fa"),("1","Offline","#ef4444")]:
            sc = QFrame(); sc.setStyleSheet(f"background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);border-radius:8px")
            sl = QVBoxLayout(sc); sl.setContentsMargins(10,8,10,8); sl.setSpacing(2)
            vl = QLabel(val); vl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vl.setStyleSheet(f"font-size:22px;font-weight:800;color:{color};background:transparent")
            ll2 = QLabel(lbl); ll2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ll2.setStyleSheet("font-size:10px;color:#475569;background:transparent")
            sl.addWidget(vl); sl.addWidget(ll2)
            sr.addWidget(sc)
        lay.addWidget(stats_w)

        # Device rows
        devices = [
            ("Gateway — Floor A",     "192.168.1.3 · ZT: 10.147.17.1", "#22c55e", True),
            ("Gateway — Warehouse B", "192.168.2.1 · ZT: 10.147.17.2", "#22c55e", True),
            ("Gateway — Office C",    "192.168.3.1 · ZT: 10.147.17.3", "#eab308", False),
            ("Gateway — Remote D",    "192.168.4.1 · ZT: 10.147.17.4", "#ef4444", False),
        ]
        dev_w = QWidget(); dev_w.setStyleSheet("background:rgba(255,255,255,0.02);border-radius:8px;margin:0 12px 12px 12px")
        dv = QVBoxLayout(dev_w); dv.setContentsMargins(0,0,0,0); dv.setSpacing(0)
        for name, meta, dot_c, on in devices:
            row = QWidget(); row.setStyleSheet("border-bottom:1px solid rgba(255,255,255,0.04);background:transparent")
            rl = QHBoxLayout(row); rl.setContentsMargins(14,10,14,10); rl.setSpacing(10)
            dot = QLabel("●"); dot.setStyleSheet(f"color:{dot_c};font-size:10px;background:transparent")
            rl.addWidget(dot)
            info = QWidget(); info.setStyleSheet("background:transparent")
            il = QVBoxLayout(info); il.setContentsMargins(0,0,0,0); il.setSpacing(1)
            nl = QLabel(name); nl.setStyleSheet("color:#e2e8f0;font-size:13px;font-weight:600;background:transparent")
            ml = QLabel(meta); ml.setStyleSheet("color:#475569;font-size:10px;font-family:monospace;background:transparent")
            il.addWidget(nl); il.addWidget(ml)
            rl.addWidget(info, 1)
            tog = QLabel("ON" if on else "OFF")
            bg = "#22c55e" if on else "#374151"
            tog.setFixedSize(40, 20)
            tog.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tog.setStyleSheet(f"background:{bg};color:white;border-radius:10px;font-size:9px;font-weight:700")
            rl.addWidget(tog)
            dv.addWidget(row)
        lay.addWidget(dev_w)

        # ZT badge
        zt = QLabel("  ● ZeroTier Active")
        zt.setFixedHeight(32)
        zt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zt.setStyleSheet("background:rgba(34,197,94,0.1);color:#22c55e;font-size:12px;font-weight:600;border-top:1px solid rgba(255,255,255,0.06);border-radius:0 0 14px 14px")
        lay.addWidget(zt)
        return card

    # ── Stats bar ──────────────────────────────────────────────────────────────
    def _stats_bar(self):
        bar = QWidget()
        bar.setFixedHeight(90)
        bar.setStyleSheet("background:#fff;border-top:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;")
        h = QHBoxLayout(bar)
        h.setContentsMargins(80, 0, 80, 0)
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)

        stats = [("90%","Deployment Success Rate"),("70%","Faster Incident Response"),("12mo","Average Payback"),("14k+","OT Sites Secured"),("256-bit","AES Encryption")]
        for i, (val, lbl) in enumerate(stats):
            if i > 0:
                div = QFrame(); div.setFixedSize(1,36)
                div.setStyleSheet("background:#e2e8f0")
                h.addStretch(1); h.addWidget(div); h.addStretch(1)
            col = QWidget(); col.setStyleSheet("background:transparent")
            cl = QVBoxLayout(col); cl.setContentsMargins(20,0,20,0); cl.setSpacing(3)
            vl = QLabel(val); vl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vl.setStyleSheet("font-size:26px;font-weight:800;color:#0f172a;background:transparent")
            ll = QLabel(lbl); ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ll.setStyleSheet("font-size:11px;color:#64748b;background:transparent")
            cl.addWidget(vl); cl.addWidget(ll)
            h.addWidget(col)
        return bar

    # ── Exposure section ───────────────────────────────────────────────────────
    def _exposure_section(self):
        sec = QWidget(); sec.setStyleSheet("background:#f8fafc;")
        lay = QVBoxLayout(sec); lay.setContentsMargins(80,64,80,64); lay.setSpacing(0)

        eyebrow = QLabel("THE PROBLEM")
        eyebrow.setStyleSheet("color:#2563eb;font-size:11px;font-weight:700;letter-spacing:1.5px;background:transparent")
        lay.addWidget(eyebrow); lay.addSpacing(10)

        title = QLabel("Your OT Environment Is\nMore Exposed Than You Think")
        title.setStyleSheet("color:#0f172a;font-size:34px;font-weight:800;background:transparent;line-height:1.2")
        lay.addWidget(title); lay.addSpacing(36)

        cards_row = QHBoxLayout(); cards_row.setSpacing(20)
        for pct, desc in [
            ("64%", "of industrial organizations experienced a cyberattack on OT systems in the past year"),
            ("83%", "of OT vulnerabilities are accessible through legacy VPNs and shared credentials"),
            ("1 in 3", "industrial breaches could have been prevented with proper network segmentation"),
        ]:
            c = QFrame(); c.setStyleSheet("QFrame{background:white;border:1px solid #e2e8f0;border-radius:12px}")
            cl = QVBoxLayout(c); cl.setContentsMargins(28,28,28,28); cl.setSpacing(10)
            vl = QLabel(pct); vl.setStyleSheet("font-size:44px;font-weight:800;color:#2563eb;background:transparent")
            dl = QLabel(desc); dl.setWordWrap(True)
            dl.setStyleSheet("font-size:14px;color:#64748b;line-height:1.6;background:transparent")
            cl.addWidget(vl); cl.addWidget(dl)
            cards_row.addWidget(c)
        lay.addLayout(cards_row)
        return sec

    # ── Features section ───────────────────────────────────────────────────────
    def _features_section(self):
        sec = QWidget(); sec.setStyleSheet("background:white;")
        lay = QVBoxLayout(sec); lay.setContentsMargins(80,64,80,64); lay.setSpacing(0)

        ey = QLabel("THE SOLUTION")
        ey.setStyleSheet("color:#2563eb;font-size:11px;font-weight:700;letter-spacing:1.5px;background:transparent")
        lay.addWidget(ey); lay.addSpacing(10)

        title = QLabel("Connect. Visualize. Control.")
        title.setStyleSheet("color:#0f172a;font-size:34px;font-weight:800;background:transparent")
        lay.addWidget(title); lay.addSpacing(36)

        cards_row = QHBoxLayout(); cards_row.setSpacing(20)
        feats = [
            ("⚡", "Instant Connectivity", "Encrypted zero-trust connections to any industrial device. No VPN complexity, no open ports."),
            ("🔒", "Zero-Trust Security", "Mandatory 2FA, role-based access, automated compliance for TSA, NIST, and NERC."),
            ("📊", "Real-Time Visibility", "Live visibility into every device and connection. Get alerted before customers call you."),
        ]
        for icon, title_f, desc in feats:
            c = QFrame()
            c.setStyleSheet("QFrame{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px}")
            cl = QVBoxLayout(c); cl.setContentsMargins(24,24,24,24); cl.setSpacing(12)
            ic = QLabel(icon); ic.setFixedSize(46,46); ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic.setStyleSheet("background:#dbeafe;border-radius:10px;font-size:20px")
            tl = QLabel(title_f); tl.setStyleSheet("font-size:16px;font-weight:700;color:#0f172a;background:transparent")
            dl = QLabel(desc); dl.setWordWrap(True)
            dl.setStyleSheet("font-size:13px;color:#64748b;line-height:1.6;background:transparent")
            cl.addWidget(ic); cl.addWidget(tl); cl.addWidget(dl)
            cards_row.addWidget(c)
        lay.addLayout(cards_row)
        return sec

    # ── Footer ─────────────────────────────────────────────────────────────────
    def _footer(self):
        footer = QWidget(); footer.setFixedHeight(52)
        footer.setStyleSheet("background:#050810;border-top:1px solid rgba(255,255,255,0.06)")
        h = QHBoxLayout(footer); h.setContentsMargins(48,0,48,0)
        copy_ = QLabel("© 2026 ProjectX by Celestial Infosoft. All rights reserved.")
        copy_.setStyleSheet("color:#334155;font-size:12px;background:transparent")
        h.addWidget(copy_); h.addStretch()
        for lnk in ["Privacy Policy","Terms of Service","Security"]:
            l = QLabel(lnk); l.setStyleSheet("color:#334155;font-size:12px;margin-left:24px;background:transparent")
            h.addWidget(l)
        return footer
