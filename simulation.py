from dataclasses import dataclass
import math
import random


@dataclass(slots=True)
class Flake:
    x: float
    y: float
    radius: float
    speed: float
    drift: float
    phase: float
    opacity: int


class SnowSimulation:
    MAX_FLAKES = 650

    def __init__(self, width: float, height: float):
        self.width = max(1.0, float(width))
        self.height = max(1.0, float(height))
        self.intensity = 35
        self.time = 0.0
        self.flakes: list[Flake] = []
        self._rng = random.Random()
        self._sync_population()

    def set_intensity(self, value: int):
        self.intensity = max(0, min(100, int(value)))
        self._sync_population()

    def resize(self, width: float, height: float):
        self.width = max(1.0, float(width))
        self.height = max(1.0, float(height))

        for flake in self.flakes:
            flake.x %= self.width
            flake.y %= self.height

    def _new_flake(self, scattered: bool) -> Flake:
        radius = self._rng.uniform(1.0, 3.4)

        return Flake(
            x=self._rng.uniform(0, self.width),
            y=(
                self._rng.uniform(0, self.height)
                if scattered
                else -radius * 2
            ),
            radius=radius,
            speed=35.0 + radius * 24.0,
            drift=self._rng.uniform(-12.0, 12.0),
            phase=self._rng.uniform(0, math.tau),
            opacity=self._rng.randint(120, 235),
        )

    def _sync_population(self):
        target = round(self.MAX_FLAKES * self.intensity / 100)

        while len(self.flakes) < target:
            self.flakes.append(self._new_flake(scattered=True))

        if len(self.flakes) > target:
            del self.flakes[target:]

    def step(self, dt: float):
        self.time += dt

        for index, flake in enumerate(self.flakes):
            sway = math.sin(self.time * 1.2 + flake.phase) * 16.0

            flake.x += (flake.drift + sway) * dt
            flake.y += flake.speed * dt

            margin = flake.radius * 2
            span = self.width + margin * 2

            flake.x = (flake.x + margin) % span - margin

            if flake.y > self.height + margin:
                self.flakes[index] = self._new_flake(scattered=False)