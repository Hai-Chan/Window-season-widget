import math
import sys

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from window_overlay import WindowSnowOverlay


def make_snow_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)

    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#17364a"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 60, 60)

        painter.setPen(QPen(QColor("#e9f7ff"), 3))

        center = QPointF(32, 32)

        for index in range(6):
            angle = index * math.pi / 3
            tip = QPointF(
                32 + math.cos(angle) * 21,
                32 + math.sin(angle) * 21,
            )
            painter.drawLine(center, tip)

            branch = QPointF(
                32 + math.cos(angle) * 13,
                32 + math.sin(angle) * 13,
            )

            for offset in (-math.pi / 3, math.pi / 3):
                endpoint = QPointF(
                    branch.x() - math.cos(angle + offset) * 7,
                    branch.y() - math.sin(angle + offset) * 7,
                )
                painter.drawLine(branch, endpoint)
    finally:
        painter.end()

    return QIcon(pixmap)


class ControlPanel(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.setWindowTitle("Desktop Snow")
        self.setWindowIcon(controller.icon)
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Desktop Snow")
        title.setObjectName("title")
        layout.addWidget(title)

        description = QLabel(
            "Prototype 2 · Falling snow + Window Accumulation\n"
            "Select a window to see snow accumulate."
        )
        layout.addWidget(description)

        self.intensity_label = QLabel("Intensity: 35%")
        layout.addWidget(self.intensity_label)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(35)
        self.slider.valueChanged.connect(self.change_intensity)
        layout.addWidget(self.slider)
        self.target_label = QLabel("No window selected")
        self.target_label.setWordWrap(True)
        layout.addWidget(self.target_label)

        self.select_button = QPushButton("Select a window")
        self.select_button.clicked.connect(
            controller.begin_window_selection
        )
        layout.addWidget(self.select_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(controller.toggle_pause)
        layout.addWidget(self.pause_button)

        hide_button = QPushButton("Hide controls")
        hide_button.clicked.connect(self.hide)
        layout.addWidget(hide_button)

        quit_button = QPushButton("Quit application")
        quit_button.clicked.connect(controller.quit)
        layout.addWidget(quit_button)

        self.setStyleSheet("""
            QWidget {
                background: #152330;
                color: #eaf4fb;
                font-size: 14px;
            }
            QLabel#title {
                font-size: 24px;
                font-weight: bold;
            }
            QPushButton {
                background: #263d50;
                border: 1px solid #3c5669;
                border-radius: 7px;
                padding: 10px;
            }
            QPushButton:hover {
                background: #34536b;
            }
        """)

    def change_intensity(self, value):
        self.intensity_label.setText(f"Intensity: {value}%")
        self.controller.overlay.set_intensity(value)

    def closeEvent(self, event):
        if self.controller.tray.isVisible():
            # Closing the panel leaves snow running in the tray.
            event.ignore()
            self.hide()
        else:
            # Keep a reliable exit if a tray is unavailable.
            event.accept()
            self.controller.quit()


class SnowApplication:
    def __init__(self, app):
        self.app = app
        self.paused = False
        self.icon = make_snow_icon()

        self.overlay = WindowSnowOverlay(app.primaryScreen())
        self.tray = QSystemTrayIcon(self.icon, app)
        self.panel = ControlPanel(self)

        self.menu = QMenu()

        show_action = QAction("Show controls", self.menu)
        show_action.triggered.connect(self.show_controls)
        self.menu.addAction(show_action)

        self.pause_action = QAction("Pause", self.menu)
        self.pause_action.triggered.connect(self.toggle_pause)
        self.menu.addAction(self.pause_action)

        self.menu.addSeparator()

        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self.quit)
        self.menu.addAction(quit_action)

        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip("Desktop Snow")
        self.tray.activated.connect(self.on_tray_activated)

        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        self.overlay.show()
        self.show_controls()

    def show_controls(self):
        self.panel.showNormal()
        self.panel.raise_()
        self.panel.activateWindow()

    def on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_controls()

    def toggle_pause(self):
        self.paused = not self.paused
        self.overlay.set_paused(self.paused)

        text = "Resume" if self.paused else "Pause"
        self.pause_action.setText(text)
        self.panel.pause_button.setText(text)

    def begin_window_selection(self):
        self.panel.select_button.setEnabled(False)
        self.panel.target_label.setText(
            "Switch to your target window within 3 seconds."
        )

        self.tray.setToolTip(
            "Desktop Snow: select a window within 3 seconds"
        )

        self.panel.hide()

        QTimer.singleShot(3000, self.finish_window_selection)

    def finish_window_selection(self):
        selected = self.overlay.select_foreground_window()

        self.panel.select_button.setEnabled(True)

        if selected:
            message = "Window selected — snow will collect on top."
        else:
            message = (
                "Selection failed. Try again and click "
                "inside CMD before the 3 seconds finish."
            )

        self.panel.target_label.setText(message)
        self.tray.setToolTip("Desktop Snow")
        self.show_controls()

    def quit(self):
        self.overlay.timer.stop()
        self.overlay.tracking_timer.stop()
        self.tray.hide()
        self.app.quit()


def main():
    if sys.platform != "win32":
        raise SystemExit("This prototype targets Windows.")

    app = QApplication(sys.argv)
    app.setApplicationName("Desktop Snow")
    app.setQuitOnLastWindowClosed(False)

    controller = SnowApplication(app)
    exit_code = app.exec()

    # Keep the controller alive throughout the event loop.
    del controller
    return exit_code


if __name__ == "__main__":
    sys.exit(main())