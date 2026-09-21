from PyQt6.QtWidgets import QMainWindow, QStackedWidget

class RootWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProjectX")
        self.setStyleSheet("QMainWindow { background: #f8fafc; }")
        
        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)
        
    def set_view(self, widget):
        """
        Add the widget to the stacked widget (if not already added),
        switch to it, and remove the previous widget to free memory.
        """
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
        from PyQt6.QtCore import Qt
        
        current = self.stacked_widget.currentWidget()
        
        # Check if the widget wants to be centered on the full screen
        if getattr(widget, 'is_centered_view', False) or (widget.maximumWidth() == widget.minimumWidth() and widget.maximumWidth() < 16777215):
            wrapper = QWidget()
            wrapper.setObjectName("centered_wrapper")
            wrapper.setStyleSheet("QWidget#centered_wrapper { background: #f1f5f9; }")
            
            vbox = QVBoxLayout(wrapper)
            vbox.setContentsMargins(0,0,0,0)
            hbox = QHBoxLayout()
            hbox.addStretch()
            
            # Ensure the widget itself has a visible background if needed
            widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            
            hbox.addWidget(widget)
            hbox.addStretch()
            vbox.addStretch()
            vbox.addLayout(hbox)
            vbox.addStretch()
            widget_to_add = wrapper
        else:
            widget_to_add = widget
        
        # Add new widget to stack
        self.stacked_widget.addWidget(widget_to_add)
        self.stacked_widget.setCurrentWidget(widget_to_add)
        
        # Cleanup the old widget
        if current is not None:
            self.stacked_widget.removeWidget(current)
            current.deleteLater()
