"""Garden progress, motion gestures, and ambient-light interpretation."""

import errno
import json
import math
import os
import sys


GRID_SIZE = 7
TOTAL_CELLS = GRID_SIZE * GRID_SIZE


class StorageError(Exception):
    pass


def _missing(error):
    if not error.args:
        return False
    # The WebAssembly simulator exposes WASI errno values rather than POSIX ones.
    return error.args[0] == errno.ENOENT or (
        sys.platform == "webassembly" and error.args[0] == 44
    )


class GardenStore:
    def __init__(self, directory="/state"):
        self.directory = directory.rstrip("/\\")
        self.path = self.directory + "/grass_garden.json"
        self.temporary = self.path + ".tmp"

    def load(self):
        try:
            with open(self.path, "r") as file:
                contents = file.read(256)
                if file.read(1):
                    raise StorageError("Garden save is too large")
        except OSError as error:
            if _missing(error):
                return 0
            raise StorageError("Cannot read garden: %s" % error)
        except UnicodeError as error:
            raise StorageError("Invalid garden save encoding: %s" % error)

        try:
            data = json.loads(contents)
        except ValueError as error:
            raise StorageError("Invalid garden save: %s" % error)

        if (not isinstance(data, dict) or
                type(data.get("version")) is not int or data["version"] != 1):
            raise StorageError("Invalid garden save format")
        grown = data.get("grown")
        if type(grown) is not int or not 0 <= grown <= TOTAL_CELLS:
            raise StorageError("Invalid garden progress")
        return grown

    def save(self, grown):
        if type(grown) is not int or not 0 <= grown <= TOTAL_CELLS:
            raise ValueError("Invalid garden progress")
        try:
            try:
                os.stat(self.directory)
            except OSError as error:
                if _missing(error):
                    os.mkdir(self.directory)
                else:
                    raise
            with open(self.temporary, "w") as file:
                file.write(json.dumps({"version": 1, "grown": grown}))
                file.flush()
            replace = getattr(os, "replace", None)
            if replace is None:
                os.rename(self.temporary, self.path)
            else:
                replace(self.temporary, self.path)
        except OSError as error:
            raise StorageError("Cannot save garden: %s" % error)


class Garden:
    def __init__(self, store):
        self.store = store
        self.grown = 0
        self.dirty = False
        self.load_error = None
        self.save_error = None
        try:
            self.grown = store.load()
        except StorageError as error:
            self.load_error = str(error)
            print("Grass Garden: " + self.load_error)

    def water(self):
        grew = self.grown < TOTAL_CELLS
        if grew:
            self.grown += 1
            self.dirty = True
        if self.dirty and self.load_error is None:
            try:
                self.store.save(self.grown)
            except StorageError as error:
                self.save_error = str(error)
                print("Grass Garden: " + self.save_error)
            else:
                self.dirty = False
                self.save_error = None
        return grew


def _length(x, y, z):
    return math.sqrt(x * x + y * y + z * z)


class Motion:
    GRAVITY_SMOOTH_MS = 250
    IMPULSE = 0.48
    REVERSE = 0.28
    REST = 0.18
    REARM_MS = 220
    RELEASE_MS = 140
    COOLDOWN_MS = 900
    GESTURE_LIMIT_MS = 1800

    def __init__(self):
        self.gravity = None
        self.quiet_ms = 0
        self.cooldown_ms = 0
        self.armed = False
        self.pending = False
        self.reversed = False
        self.gesture_ms = 0
        self.impulse = (0.0, 0.0, 0.0)

    def sample(self, reading, elapsed_ms, upside_down=False):
        if not isinstance(reading, (tuple, list)) or len(reading) < 3:
            raise ValueError("Invalid IMU reading")
        x, y, z = reading[:3]
        if any(type(value) not in (int, float) or value != value or abs(value) > 1000000
               for value in (x, y, z)):
            raise ValueError("Invalid IMU reading")
        dt = max(0, min(200, elapsed_ms))
        if self.gravity is None:
            if _length(x, y, z) < 64:
                raise ValueError("IMU has no gravity reading")
            self.gravity = [float(x), float(y), float(z)]
            return self._tilt(upside_down), False

        gx, gy, gz = self.gravity
        dx, dy, dz = x - gx, y - gy, z - gz
        residual = _length(dx, dy, dz)
        intensity = residual / max(64.0, _length(gx, gy, gz))
        smoothing = dt / (self.GRAVITY_SMOOTH_MS + dt)
        self.gravity[0] += dx * smoothing
        self.gravity[1] += dy * smoothing
        self.gravity[2] += dz * smoothing
        self.cooldown_ms = max(0, self.cooldown_ms - dt)
        watered = False

        if self.pending:
            self.gesture_ms += dt
            ix, iy, iz = self.impulse
            if (intensity >= self.REVERSE and
                    dx * ix + dy * iy + dz * iz <
                    -0.25 * residual * _length(ix, iy, iz)):
                self.reversed = True
            self.quiet_ms = self.quiet_ms + dt if intensity < self.REST else 0
            if self.quiet_ms >= self.RELEASE_MS:
                watered = self.reversed
                self.pending = False
                self.armed = False
                self.quiet_ms = 0
                if watered:
                    self.cooldown_ms = self.COOLDOWN_MS
            elif self.gesture_ms >= self.GESTURE_LIMIT_MS:
                self.pending = False
                self.armed = False
                self.quiet_ms = 0
        elif intensity < self.REST:
            self.quiet_ms += dt
            if self.cooldown_ms == 0 and self.quiet_ms >= self.REARM_MS:
                self.armed = True
        else:
            self.quiet_ms = 0
            if self.armed and self.cooldown_ms == 0 and intensity >= self.IMPULSE:
                self.pending = True
                self.armed = False
                self.reversed = False
                self.gesture_ms = 0
                self.impulse = (dx, dy, dz)

        return self._tilt(upside_down), watered

    def _tilt(self, upside_down):
        gx, gy, gz = self.gravity
        tilt = max(-1.0, min(1.0, -gx * 1.5 / max(1.0, _length(gx, gy, gz))))
        return -tilt if upside_down else tilt


class AmbientLight:
    AUTO = 0
    DAY = 1
    NIGHT = 2
    MODE_NAMES = ("AUTO", "DAY", "NIGHT")
    DARK_ENTER = 2500
    DAY_ENTER = 4500
    FILTER_MS = 350
    CONFIRM_MS = 450

    def __init__(self):
        self.mode = self.AUTO
        self.level = None
        self.dark = False
        self.candidate = None
        self.candidate_ms = 0

    @property
    def night(self):
        if self.mode == self.DAY:
            return False
        if self.mode == self.NIGHT:
            return True
        return self.dark

    @property
    def mode_name(self):
        return self.MODE_NAMES[self.mode]

    def cycle(self):
        self.mode = (self.mode + 1) % len(self.MODE_NAMES)

    def sample(self, reading, elapsed_ms):
        if type(reading) is not int or not 0 <= reading <= 65535:
            raise ValueError("Invalid light reading")
        dt = max(0, min(1000, elapsed_ms))
        if self.level is None:
            self.level = float(reading)
            self.dark = reading <= self.DARK_ENTER
            return

        self.level += (reading - self.level) * dt / (self.FILTER_MS + dt)
        target = self.dark
        if self.dark and self.level >= self.DAY_ENTER:
            target = False
        elif not self.dark and self.level <= self.DARK_ENTER:
            target = True

        if target == self.dark:
            self.candidate = None
            self.candidate_ms = 0
        elif target != self.candidate:
            self.candidate = target
            self.candidate_ms = dt
        else:
            self.candidate_ms += dt
            if self.candidate_ms >= self.CONFIRM_MS:
                self.dark = target
                self.candidate = None
                self.candidate_ms = 0
