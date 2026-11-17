from PySide6.QtCore import QPointF, Qt, QTimer
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

        self.tracking_timer = QTimer(self)
        self.tracking_timer.setInterval(33)
        self.tracking_timer.timeout.connect(self.refresh_surface)
        self.tracking_timer.start()

    def select_foreground_window(self):
        if not self.tracker.capture_foreground():
            return False

        self.simulation.clear_surface()
        self.refresh_surface()
        return True

    def refresh_surface(self):
        rectangle = self.tracker.rectangle()

        if rectangle is None:
            if self.tracker.hwnd is None:
                # The tracker has lost its target:
                # release the pile exactly once.
                self.simulation.release_surface()
            else:
                # The target still exists but isn't visible.
                self.simulation.hide_surface()

            self.update()
            return

        left, top, right, bottom = rectangle
        ratio = self.target_screen.devicePixelRatio()

        # Same primary-monitor conversion as Milestone 2.
        local_left = left / ratio - self.x()
        local_top = top / ratio - self.y()
        local_width = (right - left) / ratio

        self.simulation.set_surface(
            local_left, local_top, local_width
        )
        self.update()

    def paintEvent(self, event):
        # Clear the frame and draw the normal snowfall first.
        super().paintEvent(event)

        surface = self.simulation.surface
        draw_pile = (
            surface is not None
            and self.simulation.surface_visible
            and any(surface.heights)
        )

        if not draw_pile and not self.simulation.fragments:
            return

        painter = QPainter(self)

        try:
            painter.setRenderHint(
                QPainter.RenderHint.Antialiasing
            )
            painter.setPen(Qt.PenStyle.NoPen)

            if draw_pile:
                self._draw_pile(painter, surface)

            self._draw_fragments(painter)
        finally:
            painter.end()

    def _draw_pile(self, painter, surface):
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

        painter.setBrush(QColor(245, 250, 255, 245))
        painter.drawPath(path)

    def _draw_fragments(self, painter):
        fade_time = self.simulation.FRAGMENT_FADE_TIME

        for fragment in self.simulation.fragments:
            remaining = fragment.lifetime - fragment.age
            fade = max(0.0, min(1.0, remaining / fade_time))
            alpha = round(fragment.opacity * fade)

            if alpha <= 0:
                continue

            painter.save()

            try:
                painter.translate(fragment.x, fragment.y)
                painter.rotate(fragment.rotation)

                painter.setBrush(
                    QColor(245, 250, 255, alpha)
                )
                painter.drawEllipse(
                    QPointF(0.0, 0.0),
                    fragment.radius_x,
                    fragment.radius_y,
                )
            finally:
                painter.restore()