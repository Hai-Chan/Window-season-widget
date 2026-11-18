import math
import unittest

from accumulation import AccumulatingSnowSimulation, SnowSurface


class ResizeTests(unittest.TestCase):
    def get_surface(
        self,
        simulation: AccumulatingSnowSimulation,
    ) -> SnowSurface:
        surface = simulation.surface
        assert surface is not None, "Expected a supported snow surface"
        return surface

    def make_simulation(self):
        simulation = AccumulatingSnowSimulation(1920, 1080)
        simulation.set_surface(100, 300, 200)

        surface = self.get_surface(simulation)

        # Seed the surface with a uniform 20px-deep pile.
        surface.heights = [20.0] * len(surface.heights)

        # 200px wide × 20px deep = 4000 area units.
        self.assertAlmostEqual(surface.amount, 4000.0)

        return simulation

    def fragment_area(self, simulation):
        return sum(
            math.pi * fragment.radius_x * fragment.radius_y
            for fragment in simulation.fragments
        )

    def test_moving_preserves_amount(self):
        simulation = self.make_simulation()

        simulation.set_surface(250, 350, 200)
        surface = self.get_surface(simulation)

        self.assertAlmostEqual(surface.amount, 4000.0)
        self.assertEqual(len(simulation.fragments), 0)

    def test_shrink_right_releases_removed_snow(self):
        simulation = self.make_simulation()

        # Left edge stays at x=100; right edge moves inward.
        simulation.set_surface(100, 300, 150)
        surface = self.get_surface(simulation)

        self.assertAlmostEqual(surface.amount, 3000.0)
        self.assertAlmostEqual(
            self.fragment_area(simulation), 1000.0
        )

    def test_shrink_left_releases_removed_snow(self):
        simulation = self.make_simulation()

        # Right edge stays at x=300; left edge moves inward.
        simulation.set_surface(150, 300, 150)
        surface = self.get_surface(simulation)

        self.assertAlmostEqual(surface.amount, 3000.0)
        self.assertAlmostEqual(
            self.fragment_area(simulation), 1000.0
        )

    def test_widening_does_not_create_snow(self):
        simulation = self.make_simulation()

        simulation.set_surface(100, 300, 300)
        surface = self.get_surface(simulation)

        self.assertAlmostEqual(surface.amount, 4000.0)
        self.assertEqual(len(simulation.fragments), 0)

        # The newly added right-hand support starts empty.
        self.assertAlmostEqual(surface.heights[-1], 0.0)

    def test_full_collapse_releases_remaining_amount(self):
        simulation = self.make_simulation()

        simulation.release_surface()

        self.assertIsNone(simulation.surface)
        self.assertAlmostEqual(
            self.fragment_area(simulation), 4000.0
        )


if __name__ == "__main__":
    unittest.main()