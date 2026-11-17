from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath

from accumulation import AccumulatingSnowSimulation
from overlay import SnowOverlay
from window_tracking import WindowTracker


class WindowSnowOverlay(SnowOverlay):
    def __init__(self, screen):
        super().__init__(screen)

        self.target_screen = screen
        self.tracker = WindowTracker()

        self.simulation = AccumulatingSnowSimulation(
            self.width(), self.height()
        )

        # Keep window tracking active even while snow is paused.
        self.tracking_timer = QTimer(self)
        self.tracking_timer.setInterval(33)
        self.tracking_timer.timeout.connect(self.refresh_surface)
        self.tracking_timer.start()

    def select_foreground_window(self):
        if not self.tracker.capture_foreground():
            return False

        # Selecting a window starts a fresh pile.
        self.simulation.clear_surface()
        self.refresh_surface()
        return True

    def refresh_surface(self):
        rectangle = self.tracker.rectangle()

        if rectangle is None:
            if self.simulation.surface is not None:
                self.simulation.clear_surface()
                self.update()
            return

        left, top, right, bottom = rectangle
        ratio = self.target_screen.devicePixelRatio()

        # Primary-monitor physical coordinates → overlay coordinates.
        local_left = left / ratio - self.x()
        local_top = top / ratio - self.y()
        local_width = (right - left) / ratio

        self.simulation.set_surface(
            local_left, local_top, local_width
        )
        self.update()

    def paintEvent(self, event):
        # The existing implementation clears the frame and draws flakes.
        super().paintEvent(event)

        surface = self.simulation.surface

        if surface is None or not any(surface.heights):
            return

        count = len(surface.heights)
        spacing = surface.width / count

        points = [
            (
                surface.left + (index + 0.5) * spacing,
                surface.top - height,
            )
            for index, height in enumerate(surface.heights)
        ]

        path = QPainterPath()
        path.moveTo(surface.left, surface.top)

        path.lineTo(surface.left, points[0][1])
        path.lineTo(*points[0])

        # Smooth the upper outline with quadratic segments.
        for index in range(count - 1):
            x, y = points[index]
            next_x, next_y = points[index + 1]

            path.quadTo(
                x,
                y,
                (x + next_x) / 2,
                (y + next_y) / 2,
            )

        path.lineTo(*points[-1])
        path.lineTo(
            surface.left + surface.width, points[-1][1]
        )
        path.lineTo(
            surface.left + surface.width, surface.top
        )
        path.closeSubpath()

        painter = QPainter(self)

        try:
            painter.setRenderHint(
                QPainter.RenderHint.Antialiasing
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(245, 250, 255, 245))
            painter.drawPath(path)
        finally:
            painter.end()