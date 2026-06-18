import sys
from PyQt6.QtWidgets import QApplication, QWidget, QFrame, QVBoxLayout, QTableWidget, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt

app = QApplication(sys.argv)

card = QFrame()
card.setStyleSheet("background: white;")
lay = QVBoxLayout(card)
lay.setContentsMargins(0, 0, 0, 0)
lay.setSpacing(0)

header = QFrame()
header.setStyleSheet("background: #f8fafc; border-bottom: 1px solid red;")
# header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
hl = QHBoxLayout(header)
hl.addWidget(QLabel("Active Devices"))
lay.addWidget(header)

t = QTableWidget(2, 6)
t.setHorizontalHeaderLabels(["A", "B", "C", "D", "E", "F"])
t.setStyleSheet("background: blue;")
lay.addWidget(t)

card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
lay.setStretch(1, 1)

card.show()
card.resize(800, 600)
app.processEvents()

print("Header y:", header.y(), "height:", header.height())
print("Table y:", t.y(), "height:", t.height())
