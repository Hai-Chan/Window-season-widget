from dataclasses import dataclass, field

from simulation import SnowSimulation


@dataclass
class SnowSurface:
    left: float
    top: float
    width: float
    heights: list[float] = field(default_factory=list)

    MAX_HEIGHT = 32.0

    def __post_init__(self):
        count = max(8, round(self.width / 12))
        self.heights = [0.0] * count

    def move_and_resize(self, left, top, width):
        # Preserve the profile during movement and resizing.
        # For now, resizing stretches the existing pile.
        self.left = left
        self.top = top
        self.width = width

    def index_at(self, x):
        position = (x - self.left) / self.width
        index = int(position * len(self.heights))
        return max(0, min(len(self.heights) - 1, index))

    def roof_at(self, x):
        return self.top - self.heights[self.index_at(x)]

    def deposit(self, x, radius):
        center = self.index_at(x)
        amount = radius * 1.4

        # Spread each deposit to produce softer mounds.
        for offset, weight in (
            (-2, 0.25),
            (-1, 0.65),
            (0, 1.0),
            (1, 0.65),
            (2, 0.25),
        ):
            index = center + offset

            if 0 <= index < len(self.heights):
                self.heights[index] = min(
                    self.MAX_HEIGHT,
                    self.heights[index] + amount * weight,
                )


class AccumulatingSnowSimulation(SnowSimulation):
    def __init__(self, width, height):
        super().__init__(width, height)
        self.surface = None

    def set_surface(self, left, top, width):
        if self.surface is None:
            self.surface = SnowSurface(left, top, width)
        else:
            self.surface.move_and_resize(left, top, width)

    def clear_surface(self):
        self.surface = None

    def step(self, dt):
        surface = self.surface

        if surface is None:
            super().step(dt)
            return

        previous_bottoms = [
            flake.y + flake.radius for flake in self.flakes
        ]

        super().step(dt)

        for index, flake in enumerate(self.flakes):
            if not (
                surface.left
                <= flake.x
                < surface.left + surface.width
            ):
                continue

            roof = surface.roof_at(flake.x)
            current_bottom = flake.y + flake.radius

            if previous_bottoms[index] <= roof <= current_bottom:
                surface.deposit(flake.x, flake.radius)
                self.flakes[index] = self._new_flake(
                    scattered=False
                )