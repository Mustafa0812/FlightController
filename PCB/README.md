# Flight Controller PCB

Custom flight controller PCB for a quadcopter build: STM32F411-based FC with IMU/AHRS,
barometer, GPS, ExpressLRS-based RC/telemetry link (MAVLink over UART), 4-in-1 ESC
output, microSD blackbox logging, and USB-C programming/console via CP2102N.

See [`FlightController_BOM.md`](FlightController_BOM.md) for the full component list,
part numbers, and design rationale (power system, MCU/debug, sensors, connectors, etc.).

## Folder contents

| Path | Contents |
|---|---|
| `FlightController_BOM.md` | Finalized Rev A bill of materials with part numbers, packages, and design notes |
| `Symbols/` | Custom schematic symbols |
| `Footprints/` | Custom PCB footprints |
| `3D Model/` | 3D models for mechanical fit checks |

## Status

Rev A — BOM finalized, schematic/layout in progress.
