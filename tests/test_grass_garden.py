"""Focused host-side checks for the offline Grass Garden app."""

import errno
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


APP = Path(__file__).resolve().parents[1] / "badge" / "apps" / "grass_garden"
sys.path.insert(0, str(APP))

import garden_core


class GardenStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = garden_core.GardenStore(self.temp.name)
        self.path = Path(self.store.path)

    def test_growth_persists_and_stops_at_full(self):
        garden = garden_core.Garden(self.store)
        self.assertEqual(garden.grown, 0)
        with mock.patch.object(self.store, "save", wraps=self.store.save) as save:
            for _ in range(garden_core.TOTAL_CELLS):
                self.assertTrue(garden.water())
            self.assertFalse(garden.water())
        self.assertEqual(garden.grown, 49)
        self.assertEqual(save.call_count, 49)
        self.assertEqual(garden_core.Garden(self.store).grown, 49)

    def test_corrupt_state_is_reported_and_not_overwritten(self):
        for contents in ("not json", '{"version": true, "grown": 1}',
                         '{"version": 1, "grown": true}',
                         '{"version": 1, "grown": 50}', "x" * 257):
            with self.subTest(contents=contents[:30]):
                self.path.write_text(contents, encoding="utf-8")
                garden = garden_core.Garden(self.store)
                self.assertIsNotNone(garden.load_error)
                garden.water()
                self.assertEqual(self.path.read_text(encoding="utf-8"), contents)
                self.assertTrue(garden.dirty)

    def test_invalid_text_encoding_is_reported_without_overwriting(self):
        contents = b"\xff\xfe"
        self.path.write_bytes(contents)
        error = UnicodeDecodeError("utf-8", contents, 0, 1, "invalid byte")
        with mock.patch("builtins.open", side_effect=error):
            garden = garden_core.Garden(self.store)
        self.assertIn("Invalid garden save encoding", garden.load_error)
        garden.water()
        self.assertEqual(self.path.read_bytes(), contents)

    def test_simulator_missing_file_is_distinct_from_other_io_errors(self):
        with mock.patch.object(garden_core.sys, "platform", "webassembly"):
            with mock.patch("builtins.open", side_effect=OSError(44)):
                self.assertEqual(self.store.load(), 0)
            with mock.patch("builtins.open", side_effect=OSError(errno.EACCES)):
                with self.assertRaises(garden_core.StorageError):
                    self.store.load()

    def test_failed_replace_preserves_previous_save_and_retry_recovers(self):
        garden = garden_core.Garden(self.store)
        garden.water()
        with mock.patch.object(garden_core.os, "replace",
                               side_effect=OSError(errno.ENOSPC, "disk full")):
            garden.water()
        self.assertTrue(garden.dirty)
        self.assertIsNotNone(garden.save_error)
        self.assertEqual(json.loads(self.path.read_text())["grown"], 1)

        garden.water()
        self.assertFalse(garden.dirty)
        self.assertIsNone(garden.save_error)
        self.assertEqual(garden_core.Garden(self.store).grown, 3)

    def test_failed_last_growth_can_be_retried_after_full(self):
        self.store.save(48)
        garden = garden_core.Garden(self.store)
        with mock.patch.object(garden_core.os, "replace",
                               side_effect=OSError(errno.ENOSPC, "disk full")):
            garden.water()
        self.assertEqual(garden.grown, 49)
        self.assertTrue(garden.dirty)
        self.assertFalse(garden.water())
        self.assertFalse(garden.dirty)
        self.assertEqual(garden_core.Garden(self.store).grown, 49)


class MotionTests(unittest.TestCase):
    REST = (0, -16384, 0, 0, 0, 0)

    def settle(self, motion, count=20, reading=REST):
        return sum(motion.sample(reading, 40)[1] for _ in range(count))

    def shake(self, motion):
        sequence = ([(10000, -16384, 0)] * 2 +
                    [(-10000, -16384, 0)] * 2 + [self.REST] * 30)
        return sum(motion.sample(reading, 40)[1] for reading in sequence)

    def test_a_shake_waters_once_and_rearms_after_rest(self):
        motion = garden_core.Motion()
        self.assertEqual(self.settle(motion), 0)
        self.assertEqual(self.shake(motion), 1)
        self.settle(motion)
        self.assertEqual(self.shake(motion), 1)

    def test_tilting_and_a_single_impulse_do_not_water(self):
        motion = garden_core.Motion()
        self.settle(motion)
        events = 0
        for x in range(0, 8001, 200):
            events += motion.sample((x, -16384, 0), 40)[1]
        events += self.settle(motion, reading=(8000, -16384, 0))
        self.assertEqual(events, 0)

        motion = garden_core.Motion()
        self.settle(motion)
        events = motion.sample((12000, -16384, 0), 40)[1]
        events += self.settle(motion, count=35, reading=(12000, -16384, 0))
        self.assertEqual(events, 0)

    def test_continuous_shaking_does_not_repeat_before_rest(self):
        motion = garden_core.Motion()
        self.settle(motion)
        events = 0
        for _ in range(15):
            events += motion.sample((10000, -16384, 0), 40)[1]
            events += motion.sample((-10000, -16384, 0), 40)[1]
        events += self.settle(motion, count=30)
        self.assertEqual(events, 1)

    def test_cooldown_ignores_an_immediate_second_shake(self):
        motion = garden_core.Motion()
        self.settle(motion)
        sequence = ([(10000, -16384, 0)] * 2 +
                    [(-10000, -16384, 0)] * 2)
        for reading in sequence:
            motion.sample(reading, 40)
        for _ in range(30):
            if motion.sample(self.REST, 40)[1]:
                break
        else:
            self.fail("First shake did not water")
        self.assertEqual(motion.cooldown_ms, motion.COOLDOWN_MS)

        events = sum(motion.sample(reading, 40)[1] for reading in sequence)
        events += self.settle(motion, count=10)
        self.assertEqual(events, 0)
        self.settle(motion)
        self.assertEqual(self.shake(motion), 1)

    def test_tilt_smoothing_depends_on_elapsed_time_not_frame_count(self):
        results = []
        for dt in (20, 50):
            motion = garden_core.Motion()
            motion.sample(self.REST, dt)
            for _ in range(1000 // dt):
                lean, _ = motion.sample((4000, -16384, 0), dt)
            results.append(lean)
        self.assertAlmostEqual(results[0], results[1], delta=0.01)

    def test_tilt_respects_orientation_and_invalid_values(self):
        upright = garden_core.Motion()
        inverted = garden_core.Motion()
        upright.sample(self.REST, 40)
        inverted.sample(self.REST, 40)
        for _ in range(25):
            lean, _ = upright.sample((6000, -16384, 0), 40)
            flipped, _ = inverted.sample((6000, -16384, 0), 40, True)
        self.assertLess(lean, 0)
        self.assertAlmostEqual(lean, -flipped)
        for bad in (None, (), (0, 0, 0), ("bad", 0, 0)):
            with self.subTest(reading=bad), self.assertRaises(ValueError):
                garden_core.Motion().sample(bad, 40)


class AmbientLightTests(unittest.TestCase):
    def test_darkness_and_light_transition_with_hysteresis(self):
        light = garden_core.AmbientLight()
        light.sample(40000, 100)
        self.assertFalse(light.night)
        for _ in range(40):
            light.sample(0, 100)
        self.assertTrue(light.night)
        for _ in range(30):
            light.sample(3000, 100)
        self.assertTrue(light.night)
        for _ in range(30):
            light.sample(40000, 100)
        self.assertFalse(light.night)

    def test_manual_modes_and_invalid_readings(self):
        light = garden_core.AmbientLight()
        light.sample(0, 100)
        self.assertTrue(light.night)
        light.cycle()
        self.assertEqual(light.mode_name, "DAY")
        self.assertFalse(light.night)
        light.cycle()
        self.assertTrue(light.night)
        light.cycle()
        self.assertEqual(light.mode_name, "AUTO")
        self.assertTrue(light.night)
        for reading in (-1, 65536, None, True):
            with self.subTest(reading=reading), self.assertRaises(ValueError):
                light.sample(reading, 100)


class AppControlsTests(unittest.TestCase):
    def setUp(self):
        self.pressed = set()
        self.held = set()
        self.badge = mock.Mock()
        self.badge.ticks_delta = 50
        self.badge.imu.return_value = (0, -16384, 0, 0, 0, 0)
        self.badge.upside_down.return_value = False
        self.badge.light_level.return_value = 40000
        self.badge.pressed.side_effect = lambda button: button in self.pressed
        self.badge.held.side_effect = lambda button: button in self.held

        self.screen = mock.Mock()
        self.screen.width = 320
        self.screen.height = 240
        self.screen.clip = (0, 0, 320, 240)
        self.store = mock.Mock()
        self.store.load.return_value = 0
        namespace = {
            "badge": self.badge,
            "screen": self.screen,
            "color": mock.Mock(),
            "shape": mock.Mock(),
            "mat3": mock.Mock(),
            "font": types.SimpleNamespace(ziplock=1, sins=2, ark=3),
            "image": types.SimpleNamespace(X2=2),
            "HIRES": 1,
            "VSYNC": 2,
            "BUTTON_SELECT": "select",
            "BUTTON_MENU": "menu",
            "BUTTON_UP": "up",
            "BUTTON_LEFT": "left",
            "BUTTON_RIGHT": "right",
        }
        source = (APP / "__init__.py").read_text(encoding="utf-8")
        source = source.split("\napp = GrassGarden()", 1)[0]
        with mock.patch("os.chdir"), mock.patch.object(sys, "path", list(sys.path)):
            exec(compile(source, str(APP / "__init__.py"), "exec"), namespace)
        namespace["GardenStore"] = lambda: self.store
        self.app = namespace["GrassGarden"]()

    def test_manual_controls_water_pet_tilt_and_change_light(self):
        self.pressed.update(("select", "up", "menu"))
        self.held.add("left")
        self.app.update()
        self.assertEqual(self.app.garden.grown, 1)
        self.store.save.assert_called_once_with(1)
        self.assertEqual(self.app.water_ms, self.app.WATER_MS)
        self.assertEqual(self.app.pet_ms, self.app.PET_MS)
        self.assertEqual(self.app.light.mode_name, "DAY")
        self.assertEqual(self.app.tilt, -1.0)

        self.pressed.clear()
        self.held = {"right"}
        self.app.update()
        self.assertEqual(self.app.tilt, 1.0)
        self.held.clear()
        self.app.update()
        self.assertEqual(self.app.tilt, self.app.sensor_tilt)

    def test_full_garden_still_animates_without_another_save(self):
        self.app.garden.grown = garden_core.TOTAL_CELLS
        self.pressed.add("up")
        self.app.update()
        self.assertEqual(self.app.water_ms, self.app.WATER_MS)
        self.store.save.assert_not_called()

    def test_sensor_failures_are_visible_and_buttons_still_work(self):
        self.badge.imu.side_effect = OSError(errno.EIO, "IMU unavailable")
        self.badge.light_level.side_effect = RuntimeError("Light unavailable")
        self.pressed.update(("up", "menu"))
        self.app.update()
        self.assertEqual(self.app.garden.grown, 1)
        self.assertEqual(self.app.light.mode_name, "DAY")
        self.assertIsNotNone(self.app.motion_error)
        self.assertIsNotNone(self.app.light_error)
        labels = [call.args[0] for call in self.screen.text.call_args_list]
        self.assertIn("MOTION ERROR - USE BUTTONS", labels)

        self.pressed.clear()
        self.app.elapsed_ms = 2500
        self.app.update()
        labels = [call.args[0] for call in self.screen.text.call_args_list]
        self.assertIn("LIGHT ERROR - USE MENU", labels)

        self.badge.imu.side_effect = None
        self.badge.light_level.side_effect = None
        for _ in range(5):
            self.app.update()
        self.assertIsNone(self.app.motion_error)
        self.assertIsNone(self.app.light_error)


if __name__ == "__main__":
    unittest.main()
