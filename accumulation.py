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


@dataclass(slots=True)
class SnowFragment:
    x: float
    y: float
    vx: float
    vy: float
    radius_x: float
    radius_y: float
    rotation: float
    spin: float
    gravity: float
    lifetime: float
    opacity: int
    age: float = 0.0


class AccumulatingSnowSimulation(SnowSimulation):
    MAX_FRAGMENTS = 1500
    FRAGMENT_FADE_TIME = 0.6

    def __init__(self, width, height):
        super().__init__(width, height)
        self.surface = None
        self.surface_visible = False
        self.fragments: list[SnowFragment] = []

    def set_surface(self, left, top, width):
        if self.surface is None:
            self.surface = SnowSurface(left, top, width)
        else:
            self.surface.move_and_resize(left, top, width)

        self.surface_visible = True

    def hide_surface(self):
        # Preserve the pile while its window is minimized/hidden.
        self.surface_visible = False

    def clear_surface(self):
        # Selecting another target starts a fresh pile.
        # Previously released fragments may finish falling.
        self.surface = None
        self.surface_visible = False

    def release_surface(self):
        surface = self.surface

        if surface is None:
            return

        spacing = surface.width / len(surface.heights)
        rng = self._rng

        for index, height in enumerate(surface.heights):
            if height < 0.5:
                continue

            center_x = (
                surface.left + (index + 0.5) * spacing
            )

            # Taller samples split into two chunks.
            chunk_count = 2 if height > 14 else 1
            chunk_height = height / chunk_count

            for piece in range(chunk_count):
                center_y = (
                    surface.top
                    - height
                    + (piece + 0.5) * chunk_height
                )

                self.fragments.append(
                    SnowFragment(
                        x=center_x + rng.uniform(-1.0, 1.0),
                        y=center_y,
                        vx=rng.uniform(-30.0, 30.0),
                        vy=rng.uniform(0.0, 25.0),
                        radius_x=max(1.0, spacing * 0.55),
                        radius_y=max(
                            0.8, chunk_height * 0.48
                        ),
                        rotation=rng.uniform(-8.0, 8.0),
                        spin=rng.uniform(-100.0, 100.0),
                        gravity=580.0,
                        lifetime=6.0,
                        opacity=245,
                    )
                )

            # A little loose powder around each chunk.
            for _ in range(2):
                radius = rng.uniform(0.8, 2.0)

                self.fragments.append(
                    SnowFragment(
                        x=center_x + rng.uniform(
                            -spacing / 2, spacing / 2
                        ),
                        y=surface.top - rng.uniform(0, height),
                        vx=rng.uniform(-65.0, 65.0),
                        vy=rng.uniform(-12.0, 20.0),
                        radius_x=radius,
                        radius_y=radius,
                        rotation=0.0,
                        spin=0.0,
                        gravity=360.0,
                        lifetime=rng.uniform(2.0, 3.5),
                        opacity=rng.randint(140, 215),
                    )
                )

        # Bound the workload if several piles are released quickly.
        if len(self.fragments) > self.MAX_FRAGMENTS:
            self.fragments = self.fragments[
                -self.MAX_FRAGMENTS:
            ]

        self.clear_surface()

    def step(self, dt):
        self._step_snowfall(dt)
        self._step_fragments(dt)

    def _step_snowfall(self, dt):
        surface = self.surface

        if surface is None or not self.surface_visible:
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

    def _step_fragments(self, dt):
        survivors = []

        for fragment in self.fragments:
            fragment.age += dt
            fragment.vy += fragment.gravity * dt

            fragment.x += fragment.vx * dt
            fragment.y += fragment.vy * dt
            fragment.rotation += fragment.spin * dt

            margin = max(
                fragment.radius_x, fragment.radius_y
            ) * 2

            if (
                fragment.age >= fragment.lifetime
                or fragment.y > self.height + margin
                or fragment.x < -margin
                or fragment.x > self.width + margin
            ):
                continue

            survivors.append(fragment)

        self.fragments = survivors