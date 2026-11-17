import time

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from simulation import SnowSimulation


class SnowOverlay(QWidget):
    def __init__(self, screen):
        super().__init__()

        self.setWindowTitle("Desktop Snow Overlay")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground, True
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating, True
        )
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        geometry = screen.geometry()
        self.setGeometry(geometry)

        self.simulation = SnowSimulation(
            geometry.width(), geometry.height()
        )

        self.paused = False
        self._last_tick = time.perf_counter()

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        screen.geometryChanged.connect(self._screen_geometry_changed)

    def _screen_geometry_changed(self, geometry):
        self.setGeometry(geometry)
        self.simulation.resize(
            geometry.width(), geometry.height()
        )
        self.update()

    def set_intensity(self, value: int):
        self.simulation.set_intensity(value)
        self.update()

    def set_paused(self, paused: bool):
        self.paused = paused

        if paused:
            self.timer.stop()
        else:
            self._last_tick = time.perf_counter()
            self.timer.start()

    def _tick(self):
        now = time.perf_counter()

        # Avoid a large jump after a stall or machine suspension.
        dt = min(now - self._last_tick, 0.05)
        self._last_tick = now

        self.simulation.step(dt)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        try:
            # Explicitly erase the previous frame to transparency.
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_Source
            )
            painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            painter.setRenderHint(
                QPainter.RenderHint.Antialiasing, True
            )
            painter.setPen(Qt.PenStyle.NoPen)

            for flake in self.simulation.flakes:
                painter.setBrush(
                    QColor(245, 250, 255, flake.opacity)
                )
                painter.drawEllipse(
                    QPointF(flake.x, flake.y),
                    flake.radius,
                    flake.radius,
                )
        finally:
            painter.end()