from dataclasses import dataclass, field
import math

from simulation import SnowSimulation


@dataclass
class SnowSurface:
    left: float
    top: float
    width: float
    heights: list[float] = field(default_factory=list)

    CELL_WIDTH = 10.0

    def __post_init__(self):
        self.width = max(1.0, float(self.width))
        count = max(1, math.ceil(self.width / self.CELL_WIDTH))
        self.heights = [0.0] * count

    @property
    def spacing(self):
        return self.width / len(self.heights)

    @property
    def amount(self):
        """Approximate supported snow area in square screen units."""
        return sum(self.heights) * self.spacing

    def index_at(self, x):
        position = (x - self.left) / self.width
        index = int(position * len(self.heights))
        return max(0, min(len(self.heights) - 1, index))

    def roof_at(self, x):
        return self.top - self.heights[self.index_at(x)]

    def deposit(self, x, radius):
        center = self.index_at(x)

        # Visual deposit amount, not a real-world snow mass.
        area = 16.0 * radius * radius

        neighbors = []

        for offset, weight in (
            (-2, 0.25),
            (-1, 0.65),
            (0, 1.0),
            (1, 0.65),
            (2, 0.25),
        ):
            index = center + offset

            if 0 <= index < len(self.heights):
                neighbors.append((index, weight))

        total_weight = sum(weight for _, weight in neighbors)

        for index, weight in neighbors:
            self.heights[index] += (
                area * weight / total_weight / self.spacing
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
    # Existing renderer uses this setting.
    FRAGMENT_FADE_TIME = 0.6

    # Pile behavior. These are artistic tuning parameters.
    STABLE_SLOPE = 0.55
    COHESION_HEIGHT = 3.0
    SETTLING_RATE = 7.0

    EDGE_THRESHOLD_MIN = 10.0
    EDGE_THRESHOLD_MAX = 24.0
    EDGE_DELAY_MIN = 0.12
    EDGE_DELAY_MAX = 0.8

    # Physics substeps keep settling behavior reasonably consistent.
    PHYSICS_STEP = 1.0 / 120.0

    # Bound drawing work during repeated large collapses.
    # This is a visual particle budget, not a pile-height limit.
    MAX_FRAGMENTS = 1800

    def __init__(self, width, height):
        super().__init__(width, height)

        self.surface: SnowSurface | None = None
        self.surface_visible = False
        self.fragments: list[SnowFragment] = []

        self._reverse_settling = False
        self._edge_thresholds = [0.0, 0.0]
        self._edge_waits = [0.0, 0.0]
        self._reset_edge_behavior()

    def _reset_edge_behavior(self):
        for side in range(2):
            self._randomize_edge(side)

    def _randomize_edge(self, side):
        self._edge_thresholds[side] = self._rng.uniform(
            self.EDGE_THRESHOLD_MIN,
            self.EDGE_THRESHOLD_MAX,
        )
        self._edge_waits[side] = self._rng.uniform(
            self.EDGE_DELAY_MIN,
            self.EDGE_DELAY_MAX,
        )

    def set_surface(self, left, top, width):
        left = float(left)
        top = float(top)
        width = max(1.0, float(width))

        if self.surface is None:
            self.surface = SnowSurface(left, top, width)
            self._reset_edge_behavior()
        else:
            self._update_surface_geometry(left, top, width)

        self.surface_visible = True

    def hide_surface(self):
        # Preserve the pile while its window is minimized/hidden.
        self.surface_visible = False

    def clear_surface(self):
        self.surface = None
        self.surface_visible = False

    def release_surface(self):
        """Release all remaining supported snow."""
        surface = self.surface

        if surface is None:
            return

        spacing = surface.spacing

        for index, height in enumerate(surface.heights):
            if height <= 0:
                continue

            left = surface.left + index * spacing

            self._release_column(
                left=left,
                width=spacing,
                top=surface.top,
                height=height,
                direction=0,
            )

        self.clear_surface()

    def _update_surface_geometry(self, left, top, width):
        old = self.surface

        if old is None:
            return

        # A same-width change is treated as moving the window.
        if abs(width - old.width) < 0.001:
            old.left = left
            old.top = top
            return

        old_right = old.left + old.width
        new_right = left + width

        left_delta = left - old.left
        right_delta = new_right - old_right

        # Infer translation separately from resizing.
        #
        # Right edge resize: left edge stays fixed.
        # Left edge resize: right edge stays fixed.
        # Symmetric resize: center stays fixed.
        #
        # Simultaneous move + resize is inherently ambiguous from
        # rectangles alone; use the edge with the smaller movement.
        if abs(abs(left_delta) - abs(right_delta)) < 0.5:
            translation = (left_delta + right_delta) / 2.0
        elif abs(left_delta) < abs(right_delta):
            translation = left_delta
        else:
            translation = right_delta

        translated_left = old.left + translation
        old_spacing = old.spacing

        new_surface = SnowSurface(left, top, width)
        new_spacing = new_surface.spacing

        for index, height in enumerate(old.heights):
            if height <= 0:
                continue

            cell_left = translated_left + index * old_spacing
            cell_right = cell_left + old_spacing

            # Snow left of the new supporting interval falls.
            lost_left_end = min(cell_right, left)

            if lost_left_end > cell_left:
                self._release_column(
                    left=cell_left,
                    width=lost_left_end - cell_left,
                    top=top,
                    height=height,
                    direction=0,
                )

            # Snow right of the new supporting interval falls.
            lost_right_start = max(cell_left, new_right)

            if cell_right > lost_right_start:
                self._release_column(
                    left=lost_right_start,
                    width=cell_right - lost_right_start,
                    top=top,
                    height=height,
                    direction=0,
                )

            # Keep only the overlap with the new window top.
            overlap_left = max(cell_left, left)
            overlap_right = min(cell_right, new_right)

            if overlap_right <= overlap_left:
                continue

            first = max(
                0,
                int(math.floor(
                    (overlap_left - left) / new_spacing
                )),
            )
            last = min(
                len(new_surface.heights) - 1,
                int(math.floor(
                    (overlap_right - left) / new_spacing
                )),
            )

            # Area-preserving resampling.
            for new_index in range(first, last + 1):
                new_cell_left = left + new_index * new_spacing
                new_cell_right = new_cell_left + new_spacing

                overlap = max(
                    0.0,
                    min(overlap_right, new_cell_right)
                    - max(overlap_left, new_cell_left),
                )

                new_surface.heights[new_index] += (
                    height * overlap / new_spacing
                )

        self.surface = new_surface

    def step(self, dt):
        if dt <= 0:
            return

        self._step_snowfall(dt)

        steps = max(1, math.ceil(dt / self.PHYSICS_STEP))
        sub_dt = dt / steps

        for _ in range(steps):
            if self.surface is not None and self.surface_visible:
                self._settle_pile(sub_dt)
                self._shed_edges(sub_dt)
                self._handle_screen_top()

            self._step_fragments(sub_dt)

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

    def _settle_pile(self, dt):
        surface = self.surface

        if surface is None:
            return
        
        heights = surface.heights

        if len(heights) < 2:
            return

        allowed_difference = (
            self.STABLE_SLOPE * surface.spacing
            + self.COHESION_HEIGHT
        )

        # Alternate traversal direction to reduce directional bias.
        if self._reverse_settling:
            indices = range(len(heights) - 2, -1, -1)
        else:
            indices = range(len(heights) - 1)

        self._reverse_settling = not self._reverse_settling
        fraction = min(0.5, self.SETTLING_RATE * dt)

        for index in indices:
            difference = heights[index] - heights[index + 1]
            excess = abs(difference) - allowed_difference

            if excess <= 0:
                continue

            transfer = excess * fraction

            if difference > 0:
                transfer = min(transfer, heights[index])
                heights[index] -= transfer
                heights[index + 1] += transfer
            else:
                transfer = min(transfer, heights[index + 1])
                heights[index + 1] -= transfer
                heights[index] += transfer

    def _shed_edges(self, dt):
        surface = self.surface

        if surface is None:
            return

        for side, direction in ((0, -1), (1, 1)):
            self._edge_waits[side] = max(
                0.0, self._edge_waits[side] - dt
            )

            index = 0 if side == 0 else len(surface.heights) - 1
            height = surface.heights[index]
            threshold = self._edge_thresholds[side]

            if height <= threshold or self._edge_waits[side] > 0:
                continue

            # Release an irregular portion, not the entire edge.
            excess = height - threshold
            drop_height = min(
                height,
                self._rng.uniform(2.0, 6.0)
                + excess * self._rng.uniform(0.35, 0.8),
            )

            self._release_edge_slice(
                index=index,
                drop_height=drop_height,
                direction=direction,
            )
            self._randomize_edge(side)

    def _release_edge_slice(self, index, drop_height, direction):
        surface = self.surface

        if surface is None:
            return
        
        old_height = surface.heights[index]

        drop_height = min(old_height, max(0.0, drop_height))

        if drop_height <= 0:
            return

        surface.heights[index] -= drop_height

        # Bottom of the removed upper slice.
        slice_bottom = (
            surface.top - old_height + drop_height
        )

        spacing = surface.spacing

        # Position the released slice just beyond its support.
        if direction < 0:
            release_left = surface.left - spacing - 1.0
        else:
            release_left = surface.left + surface.width + 1.0

        self._release_column(
            left=release_left,
            width=spacing,
            top=slice_bottom,
            height=drop_height,
            direction=direction,
        )

    def _handle_screen_top(self):
        surface = self.surface

        if surface is None:
            return

        # The visible screen top is y=0 in overlay coordinates.
        # No arbitrary 32px cap, and no invisible snow reservoir.
        ceiling_height = max(0.0, surface.top)
        overflow_area = 0.0
        weighted_x = 0.0
        spacing = surface.spacing

        for index, height in enumerate(surface.heights):
            excess = height - ceiling_height

            if excess <= 0:
                continue

            area = excess * spacing
            overflow_area += area
            weighted_x += (
                surface.left + (index + 0.5) * spacing
            ) * area

            surface.heights[index] = ceiling_height

        if overflow_area <= 0:
            return

        # Redirect screen-top overflow to an edge.
        # This is a deliberate visual boundary rule, not a roof.
        center_x = weighted_x / overflow_area
        midpoint = surface.left + surface.width / 2.0

        if abs(center_x - midpoint) < spacing:
            direction = self._rng.choice((-1, 1))
        else:
            direction = -1 if center_x < midpoint else 1

        if direction < 0:
            release_left = surface.left - spacing - 1.0
            edge_height = surface.heights[0]
        else:
            release_left = surface.left + surface.width + 1.0
            edge_height = surface.heights[-1]

        release_height = overflow_area / spacing
        edge_roof = max(0.0, surface.top - edge_height)

        self._release_column(
            left=release_left,
            width=spacing,
            top=edge_roof + release_height,
            height=release_height,
            direction=direction,
        )

    def _release_column(self, left, width, top, height, direction):
        """Turn a rectangular amount of snow into visual fragments."""
        if width <= 0 or height <= 0:
            return

        rng = self._rng

        # Split tall portions into several pieces.
        # Limit piece count so a deep pile isn't thousands of objects.
        pieces = max(1, min(6, math.ceil(height / 12.0)))
        piece_height = height / pieces
        source_top = top - height

        for piece in range(pieces):
            center_x = left + width / 2.0
            center_y = (
                source_top + (piece + 0.5) * piece_height
            )

            area = width * piece_height

            # Most snow becomes a cohesive chunk; a little is powder.
            powder_fraction = rng.uniform(0.06, 0.14)
            chunk_area = area * (1.0 - powder_fraction)

            radius_x = max(0.25, width * rng.uniform(0.42, 0.58))
            radius_y = chunk_area / (math.pi * radius_x)

            if direction:
                vx = direction * rng.uniform(18.0, 65.0)
            else:
                vx = rng.uniform(-25.0, 25.0)

            self.fragments.append(
                SnowFragment(
                    x=center_x,
                    y=center_y,
                    vx=vx,
                    vy=rng.uniform(0.0, 22.0),
                    radius_x=radius_x,
                    radius_y=radius_y,
                    rotation=rng.uniform(-10.0, 10.0),
                    spin=rng.uniform(-110.0, 110.0),
                    gravity=580.0,
                    lifetime=8.0,
                    opacity=245,
                )
            )

            powder_count = 2
            powder_area = area * powder_fraction / powder_count
            powder_radius = math.sqrt(powder_area / math.pi)

            for _ in range(powder_count):
                self.fragments.append(
                    SnowFragment(
                        x=center_x + rng.uniform(
                            -width / 2.0, width / 2.0
                        ),
                        y=center_y + rng.uniform(
                            -piece_height / 2.0,
                            piece_height / 2.0,
                        ),
                        vx=(
                            direction * rng.uniform(20.0, 75.0)
                            + rng.uniform(-15.0, 15.0)
                        ),
                        vy=rng.uniform(-10.0, 25.0),
                        radius_x=powder_radius,
                        radius_y=powder_radius,
                        rotation=0.0,
                        spin=0.0,
                        gravity=360.0,
                        lifetime=rng.uniform(2.5, 4.0),
                        opacity=rng.randint(140, 215),
                    )
                )

        if len(self.fragments) > self.MAX_FRAGMENTS:
            # Retire oldest visual fragments under heavy load.
            # This doesn't alter the remaining supported pile.
            del self.fragments[
                :len(self.fragments) - self.MAX_FRAGMENTS
            ]

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
            ) * 2.0

            if (
                fragment.age >= fragment.lifetime
                or fragment.y > self.height + margin
                or fragment.x < -margin
                or fragment.x > self.width + margin
            ):
                continue

            survivors.append(fragment)

        self.fragments = survivors