"""A small offline garden tended by a friendly robot."""

import math
import os
import sys


APP_DIR = "/system/apps/grass_garden"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

from garden_core import AmbientLight, Garden, GardenStore, Motion, TOTAL_CELLS


badge.mode(HIRES | VSYNC)
screen.antialias = image.X2


def rgb(red, green, blue):
    return color.rgb(red, green, blue)


DAY = {
    "sky": rgb(172, 222, 220),
    "horizon": rgb(196, 235, 213),
    "cloud": rgb(232, 247, 232),
    "sun": rgb(255, 220, 137),
    "hill": rgb(142, 195, 154),
    "ground": rgb(108, 167, 127),
    "shadow": rgb(76, 128, 99),
    "panel_edge": rgb(48, 83, 64),
    "panel": rgb(76, 113, 78),
    "empty": rgb(111, 143, 102),
    "title": rgb(27, 68, 61),
    "label": rgb(235, 249, 224),
    "ground_text": rgb(24, 66, 49),
    "greens": (
        rgb(77, 185, 102), rgb(50, 165, 88),
        rgb(34, 142, 77), rgb(25, 119, 68),
    ),
    "blade": rgb(218, 255, 197),
}

NIGHT = {
    "sky": rgb(20, 38, 57),
    "horizon": rgb(35, 66, 76),
    "cloud": rgb(70, 104, 111),
    "sun": rgb(248, 231, 174),
    "hill": rgb(48, 91, 87),
    "ground": rgb(39, 78, 70),
    "shadow": rgb(25, 58, 55),
    "panel_edge": rgb(19, 51, 49),
    "panel": rgb(42, 78, 66),
    "empty": rgb(67, 102, 79),
    "title": rgb(226, 245, 230),
    "label": rgb(228, 245, 215),
    "ground_text": rgb(216, 240, 218),
    "greens": (
        rgb(70, 165, 94), rgb(44, 146, 81),
        rgb(31, 127, 72), rgb(24, 108, 65),
    ),
    "blade": rgb(212, 250, 190),
}

INK = rgb(39, 48, 51)
SHELL_SHADOW = rgb(180, 190, 185)
SHELL = rgb(232, 239, 230)
SHELL_LIGHT = rgb(250, 252, 244)
FACE_RIM = rgb(132, 145, 145)
FACE = rgb(34, 42, 48)
FACE_SHINE = rgb(68, 79, 84)
WHITE = rgb(248, 253, 245)
PINK = rgb(244, 151, 155)
BLUE = rgb(112, 214, 218)
CAN_DARK = rgb(39, 108, 121)
CAN_LIGHT = rgb(105, 207, 208)
ERROR_BG = rgb(117, 44, 52)


class GardenScene:
    def __init__(self):
        self.scale = min(screen.width / 320, screen.height / 240)
        self.left = (screen.width - 320 * self.scale) / 2
        self.top = (screen.height - 240 * self.scale) / 2
        self.viewport = mat3().translate(self.left, self.top).scale(self.scale, self.scale)

        self.sun = self.static(shape.circle(284, 44, 17))
        self.moon_cutout = self.static(shape.circle(290, 38, 15))
        self.clouds = [
            self.static(shape.ellipse(172, 56, 20, 6)),
            self.static(shape.ellipse(187, 51, 13, 9)),
            self.static(shape.ellipse(215, 72, 16, 5)),
            self.static(shape.ellipse(226, 68, 10, 7)),
        ]
        self.stars = [
            self.static(shape.circle(x, y, radius))
            for x, y, radius in ((180, 42, 1.5), (216, 30, 1),
                                 (247, 64, 1.5), (307, 74, 1))
        ]
        self.hills = [
            self.static(shape.ellipse(53, 146, 116, 37)),
            self.static(shape.ellipse(244, 146, 111, 31)),
        ]
        self.panel_shadow = self.static(shape.rounded_rectangle(12, 61, 143, 151, 10))
        self.panel_edge = self.static(shape.rounded_rectangle(12, 57, 143, 151, 10))
        self.panel = self.static(shape.rounded_rectangle(15, 60, 137, 145, 8))
        self.tiles = []
        for column in range(7):
            for row in range(7):
                x = 21 + column * 17
                y = 83 + row * 17
                tile = self.static(shape.rounded_rectangle(x, y, 14, 14, 3))
                self.tiles.append((x, y, tile))
        self.footer = self.static(shape.rounded_rectangle(8, 217, 304, 18, 8))
        self.error_box = self.static(shape.rounded_rectangle(10, 37, 300, 18, 5))

        self.ground_shadow = shape.ellipse(0, 0, 39, 6)
        self.base_parts = (
            (shape.rounded_rectangle(-37, -8, 74, 21, 9), INK),
            (shape.rounded_rectangle(-34, -6, 68, 15, 7), SHELL_SHADOW),
            (shape.rounded_rectangle(-31, -5, 62, 9, 5), FACE_RIM),
            (shape.rounded_rectangle(-23, -19, 46, 15, 6), INK),
            (shape.rounded_rectangle(-20, -17, 40, 11, 5), SHELL_SHADOW),
        )
        self.head_parts = (
            (shape.rounded_rectangle(-42, -40, 84, 68, 17), INK),
            (shape.rounded_rectangle(-39, -37, 78, 62, 15), SHELL_SHADOW),
            (shape.rounded_rectangle(-38, -37, 76, 56, 14), SHELL),
            (shape.rounded_rectangle(-35, -35, 70, 50, 13), SHELL_LIGHT),
            (shape.rounded_rectangle(-31, -31, 64, 46, 11), FACE_RIM),
            (shape.rounded_rectangle(-28, -29, 58, 41, 9), INK),
            (shape.rounded_rectangle(-26, -27, 54, 37, 8), FACE),
            (shape.rounded_rectangle(-22, -24, 16, 3, 2), FACE_SHINE),
            (shape.circle(-35, -19, 1.3), FACE_RIM),
            (shape.circle(-35, -13, 1.3), FACE_RIM),
            (shape.circle(-35, -7, 1.3), FACE_RIM),
            (shape.circle(0, 19, 4), INK),
            (shape.circle(0, 19, 2.3), BLUE),
        )
        self.open_eyes = (shape.ellipse(-13, -12, 3.5, 4),
                          shape.ellipse(13, -12, 3.5, 4))
        self.blink_eyes = (shape.line(-17, -12, -9, -12, 2),
                           shape.line(9, -12, 17, -12, 2))
        self.happy_eyes = (shape.line(-17, -10, -13, -13, 2),
                           shape.line(-13, -13, -9, -10, 2),
                           shape.line(9, -10, 13, -13, 2),
                           shape.line(13, -13, 17, -10, 2))
        self.cheeks = (shape.line(-23, -3, -21, -7, 2),
                       shape.line(-19, -3, -17, -7, 2),
                       shape.line(17, -3, 19, -7, 2),
                       shape.line(21, -3, 23, -7, 2))
        self.neutral_mouth = (shape.line(-6, -2, 6, -2, 2),)
        self.happy_mouth = (shape.line(-6, -3, 0, 0, 2),
                            shape.line(0, 0, 6, -3, 2))
        self.arm = shape.line(-38, 11, -51, 20, 5)
        self.can_parts = (
            (shape.rounded_rectangle(-10, -7, 20, 14, 4), CAN_DARK),
            (shape.rounded_rectangle(-8, -5, 16, 10, 3), CAN_LIGHT),
            (shape.line(-5, -8, 0, -13, 2), CAN_DARK),
            (shape.line(0, -13, 6, -8, 2), CAN_DARK),
            (shape.line(-9, -3, -16, -8, 3), CAN_DARK),
        )
        self.drop = shape.ellipse(0, 0, 2, 3)

    def static(self, element):
        element.transform = self.viewport
        return element

    def matrix(self, x, y, angle=0):
        return (mat3().translate(self.left + x * self.scale, self.top + y * self.scale)
                .rotate(angle).scale(self.scale, self.scale))

    def draw_shape(self, element, pen, transform=None):
        if transform is not None:
            element.transform = transform
        screen.pen = pen
        screen.shape(element)

    def rectangle(self, x, y, width, height, pen):
        screen.pen = pen
        screen.rectangle(round(self.left + x * self.scale),
                         round(self.top + y * self.scale),
                         max(1, round(width * self.scale)),
                         max(1, round(height * self.scale)))

    def line(self, x1, y1, x2, y2, pen):
        screen.pen = pen
        screen.line(round(self.left + x1 * self.scale),
                    round(self.top + y1 * self.scale),
                    round(self.left + x2 * self.scale),
                    round(self.top + y2 * self.scale))

    def text(self, value, x, y, face, pen):
        screen.font = face
        screen.pen = pen
        screen.text(value, round(self.left + x * self.scale),
                    round(self.top + y * self.scale))

    def draw(self, app):
        palette = NIGHT if app.light.night else DAY
        screen.pen = palette["sky"]
        screen.rectangle(screen.clip)
        self.rectangle(0, 82, 320, 80, palette["horizon"])
        self.draw_shape(self.sun, palette["sun"])
        if app.light.night:
            self.draw_shape(self.moon_cutout, palette["sky"])
            for star in self.stars:
                self.draw_shape(star, palette["label"])
        else:
            for cloud in self.clouds:
                self.draw_shape(cloud, palette["cloud"])
        for hill in self.hills:
            self.draw_shape(hill, palette["hill"])
        self.rectangle(0, 150, 320, 90, palette["ground"])

        self.text("Grass Garden", 12, 7, font.ziplock, palette["title"])
        self.text("OFFLINE", 14, 29, font.sins, palette["title"])
        self.text(app.light.mode_name, 266, 12, font.ark, palette["title"])
        self.draw_garden(app, palette)
        self.draw_robot(app, palette)
        self.draw_shape(self.footer, palette["hill"])
        self.text("SELECT PET   UP WATER   L/R TILT   MENU LIGHT",
                  17, 220, font.sins, palette["ground_text"])

        messages = []
        if app.garden.load_error is not None:
            messages.append("LOAD ERROR - SAVE LOCKED")
        if app.garden.save_error is not None:
            messages.append("SAVE FAILED - WATER TO RETRY")
        if app.motion_error is not None:
            messages.append("MOTION ERROR - USE BUTTONS")
        if app.light_error is not None:
            messages.append("LIGHT ERROR - USE MENU")
        if messages:
            self.draw_shape(self.error_box, ERROR_BG)
            self.text(messages[(app.elapsed_ms // 2500) % len(messages)],
                      17, 41, font.ark, WHITE)

    def draw_garden(self, app, palette):
        self.draw_shape(self.panel_shadow, palette["shadow"])
        self.draw_shape(self.panel_edge, palette["panel_edge"])
        self.draw_shape(self.panel, palette["panel"])
        self.text("YOUR GARDEN", 21, 65, font.sins, palette["label"])
        self.text("%02d / %02d" % (app.garden.grown, TOTAL_CELLS),
                  112, 65, font.sins, palette["label"])

        sway = app.tilt * 3 + math.sin(app.elapsed_ms / 800) * 0.7
        for index, (x, y, tile) in enumerate(self.tiles):
            grown = index < app.garden.grown
            pen = palette["greens"][(index * 5 + index // 7) % 4] if grown else palette["empty"]
            self.draw_shape(tile, pen)
            if grown:
                self.line(x + 7, y + 11, x + 7 + sway, y + 4, palette["blade"])
                self.line(x + 7 + sway * 0.6, y + 8,
                          x + 4 + sway, y + 6, palette["blade"])
                self.line(x + 7 + sway * 0.6, y + 9,
                          x + 10 + sway, y + 6, palette["blade"])

    def draw_robot(self, app, palette):
        x = app.robot_x
        bob = math.sin(app.elapsed_ms / 250) * 1.2
        angle = math.sin(app.elapsed_ms / 850) * 4
        if app.pet_ms > 0:
            angle += 5
        base = self.matrix(x, 195)
        self.draw_shape(self.ground_shadow, palette["shadow"], self.matrix(x, 207))
        for element, pen in self.base_parts:
            self.draw_shape(element, pen, base)

        head = self.matrix(x + math.sin(app.elapsed_ms / 1100) * 2, 151 + bob, angle)
        for element, pen in self.head_parts:
            self.draw_shape(element, pen, head)
        happy = app.pet_ms > 0 or app.water_ms > 0
        eyes = self.happy_eyes if happy else (
            self.blink_eyes if app.elapsed_ms % 4100 < 150 else self.open_eyes)
        for eye in eyes:
            self.draw_shape(eye, WHITE, head)
        for cheek in self.cheeks:
            self.draw_shape(cheek, PINK, head)
        for mouth in self.happy_mouth if happy else self.neutral_mouth:
            self.draw_shape(mouth, WHITE, head)

        if app.water_ms > 0:
            self.draw_shape(self.arm, SHELL_SHADOW, head)
            can_x, can_y = x - 53, 172
            can = self.matrix(can_x, can_y, -15)
            for element, pen in self.can_parts:
                self.draw_shape(element, pen, can)
            index = max(0, app.garden.grown - 1)
            tile_x, tile_y, _ = self.tiles[index]
            elapsed = app.WATER_MS - app.water_ms
            for number in range(3):
                progress = ((elapsed / 450) + number / 3) % 1
                drop_x = can_x - 14 + (tile_x + 7 - (can_x - 14)) * progress
                drop_y = can_y - 8 + (tile_y + 7 - (can_y - 8)) * progress
                drop_y -= math.sin(progress * math.pi) * 13
                self.draw_shape(self.drop, BLUE, self.matrix(drop_x, drop_y))
        elif app.pet_ms > 0:
            heart_y = 103 - (app.PET_MS - app.pet_ms) / 140
            self.rectangle(x + 43, heart_y, 4, 4, PINK)
            self.rectangle(x + 48, heart_y, 4, 4, PINK)
            self.rectangle(x + 42, heart_y + 3, 11, 4, PINK)
            self.rectangle(x + 44, heart_y + 7, 7, 3, PINK)
            self.rectangle(x + 46, heart_y + 10, 3, 2, PINK)


class GrassGarden:
    WATER_MS = 1500
    PET_MS = 1500
    LIGHT_SAMPLE_MS = 250

    def __init__(self):
        self.garden = Garden(GardenStore())
        self.motion = Motion()
        self.light = AmbientLight()
        self.scene = GardenScene()
        self.motion_error = None
        self.light_error = None
        self.light_elapsed = self.LIGHT_SAMPLE_MS
        self.sensor_tilt = 0.0
        self.tilt = 0.0
        self.elapsed_ms = 0
        self.robot_x = 220.0
        self.robot_direction = 1
        self.water_ms = 0
        self.pet_ms = 0

    def water(self):
        self.garden.water()
        self.water_ms = self.WATER_MS

    def read_sensors(self, dt):
        shaken = False
        try:
            self.sensor_tilt, shaken = self.motion.sample(
                badge.imu(), dt, badge.upside_down())
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
            if self.motion_error is None:
                print("Grass Garden: motion sensor unavailable: %s" % error)
                self.motion = Motion()
            self.motion_error = str(error)
            self.sensor_tilt = 0.0
        else:
            if self.motion_error is not None:
                print("Grass Garden: motion sensor recovered")
            self.motion_error = None

        self.light_elapsed += dt
        if self.light_elapsed >= self.LIGHT_SAMPLE_MS:
            try:
                self.light.sample(badge.light_level(), self.light_elapsed)
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as error:
                if self.light_error is None:
                    print("Grass Garden: light sensor unavailable: %s" % error)
                self.light_error = str(error)
            else:
                if self.light_error is not None:
                    print("Grass Garden: light sensor recovered")
                self.light_error = None
            self.light_elapsed = 0
        return shaken

    def update(self):
        dt = max(0, min(1000, badge.ticks_delta))
        self.elapsed_ms = (self.elapsed_ms + dt) % 120000
        self.water_ms = max(0, self.water_ms - dt)
        self.pet_ms = max(0, self.pet_ms - dt)

        if badge.pressed(BUTTON_SELECT):
            self.pet_ms = self.PET_MS
        if badge.pressed(BUTTON_MENU):
            self.light.cycle()
        water_pressed = badge.pressed(BUTTON_UP)
        shaken = self.read_sensors(dt)
        if water_pressed or shaken:
            self.water()

        left = badge.held(BUTTON_LEFT)
        right = badge.held(BUTTON_RIGHT)
        self.tilt = (-1.0 if left else 1.0) if left != right else self.sensor_tilt

        self.robot_x += self.robot_direction * 11 * dt / 1000
        if self.robot_x >= 263:
            self.robot_x = 263
            self.robot_direction = -1
        elif self.robot_x <= 184:
            self.robot_x = 184
            self.robot_direction = 1
        self.scene.draw(self)


app = GrassGarden()


def update():
    return app.update()


run(update)
