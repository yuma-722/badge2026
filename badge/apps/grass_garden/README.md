# Grass Garden

Grow a tiny offline garden with a friendly robot.

## Play

Tilt the badge to sway the grass, then give it a gentle back-and-forth shake
and hold it still to water one square. Tap the Select touch pad or press
Select to greet the robot. The robot wanders, blinks, and tends the garden.
The garden changes between day and night as the light sensor detects its
surroundings.

The following controls also work on the badge and in the Badge Simulator:

| Control | Action |
| --- | --- |
| Select | Greet the robot |
| Up | Water the garden |
| Hold Left / Right | Sway the grass without tilting |
| Menu | Cycle automatic, day, and night lighting |
| Home | Return to the launcher |

Each watering grows one of 49 squares. Once the garden is full, watering and
the robot's reactions continue without changing the saved progress. The
garden never withers.

## Requirements and saved progress

This app runs offline and does not read or change GitHub contributions. No
Wi-Fi, credentials, or additional hardware are needed. Progress is saved in
`/state/grass_garden.json` and restored when the app is reopened.

If a save fails, the screen shows **SAVE FAILED**; water again to retry. If
the existing save is invalid, **LOAD ERROR - SAVE LOCKED** appears and the
file is not overwritten. To start over, back up that file and remove it only
after deciding you no longer need its contents; see
[`hardware/USB_SERIAL.md`](../../../hardware/USB_SERIAL.md) for access to
`/state`.

The PC simulator supplies fixed motion and light values, so use the button
alternatives there. Real-device verification is needed to tune the shake and
light thresholds for your badge and surroundings. A sensor error is shown on
screen; the button alternatives remain available.
