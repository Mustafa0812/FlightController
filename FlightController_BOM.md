# Flight Controller — Finalized Component BOM (Rev A)

**Assumptions:** quadcopter, brushless motors via 4-in-1 ESC, 4S LiPo (14.8V nominal / 16.8V max, 6-30V design range). Stabilized flight + GPS waypoint missions — no onboard companion computer. STM32 runs the full nav/control stack; ROS2 tooling (if used) connects as a ground-station agent over the existing USB link, not onboard compute.

---

## 1. MCU & Programming

| Component | Part Number | Package | Notes |
|---|---|---|---|
| MCU | **STM32F411CEU6** | UQFN48, 7x7mm | Same die as your Nucleo's F411RE (512KB Flash / 128KB RAM), just the 48-pin package every real F411 FC uses (Matek, Kakute, community Black Pill boards). Your FreeRTOS/micro-ROS code ports over; you'll just have fewer GPIO than the 64-pin Nucleo — worth a pin budget pass (see §12) before committing footprint. |
| — alternative | STM32F411RCT6 | LQFP64, 10x10mm | Pick this instead if you want more GPIO headroom or easier hand-soldering/rework (0.5mm QFN pitch on the CEU6 needs hot air + flux, doable but less forgiving). Bigger, heavier board. |
| Clock source | **External 8 MHz crystal (HSE) — required, not optional.** CP2102N (and its internal 48MHz osc) has been dropped in favor of native USB on the F411, and native full-speed USB needs a ±0.25% clock. The F411 has no HSI48/CRS to trim HSI against USB SOF packets (that block only exists on F0/L0/L4/G4 parts), so HSI alone (~±1%) can't drive USB reliably. **Y1: TXC AA-8.000MALV-T** (8 MHz, 8pF load, 150Ω max ESR, AEC-Q200, -40 to +125°C, 2-pin SMD ~5x3.2mm) on PH0/PH1 (OSC_IN/OSC_OUT). **CL1 = CL2 = 10pF** C0G/NP0 0402 (Cx = 2×(CL − C_stray), CL = 8pF per datasheet, C_stray ≈ 3pF assumed for a tight layout — confirm/adjust after bring-up if frequency is off-tolerance), R_EXT footprint (0Ω, populated not DNP, see below) in series with OSC_OUT, per the datasheet's Figure 24 typical application circuit. *Note: AA-8.000MALV-T is a bare 2-pin crystal, not a 3-pin integrated-cap ceramic resonator (e.g. Murata CSTCE) — CL1/CL2 are real discrete external components here, not already built into Y1, even though ST's Figure 24 template covers both resonator types.* R_F (the oscillator's internal feedback resistor, ~200kΩ typ per Table 37) is fixed silicon inside the MCU, not a component you place — don't confuse it with R_EXT, which is external and crystal-dependent. **Margin check (AN2867 gm_crit):** at 150Ω ESR / 8pF CL / ~5pF stray, gm_crit ≈ 0.26 mA/V against the F411's Gm_crit_max = 1 mA/V ceiling (Table 37) — about 3.9x margin, comfortably near AN2867's ~5x target. (The tempting automotive-spec NDK NX3225GD-STD-CRA-3 alternative has 500Ω max ESR, which works out to gm_crit ≈ 0.85 mA/V — only ~1.2x margin, too tight for reliable cold-start across a production batch. Don't use it here.) This also gives SysTick/TIM/SPI/I2C/UART a tighter reference than HSI, which is a bonus, not the reason it's there. |
| SWD/debug header | 4-pin 0.1" or Tag-Connect TC2030-IDC footprint | — | Native USB DFU gives you bootloader entry and flashing, but not breakpoints, register watch, or live debugging. Keep this header for your existing ST-Link + OpenOCD + VS Code workflow. |
| USB connector | USB-C receptacle (e.g. GCT USB4085 or Amphenol 12401548E4#2A) | SMD | Native USB straight to PA11/PA12 (D-/D+). Add USBLC6-2SC6 (SOT23-6) ESD protection on D+/D-, and 5.1kΩ CC1/CC2 pull-downs for device-mode detection. |
| BOOT0 control | Momentary push-button (or 2-pin jumper) to 3.3V, plus a 10kΩ pull-down on BOOT0 | SMD button, e.g. Panasonic EVQ-PE | **Deliberate, not automatic.** Don't wire an auto-reset circuit off USB enumeration. On a flight controller, you do not want anything capable of resetting the MCU without a physical action from you — a button you have to hold means a reset can't happen from a stray USB re-enumeration or noise mid-bench-test. |
| Reset button | Momentary push-button to GND on NRST, 10kΩ pull-up | SMD button | Standard manual reset, same reasoning as above. |

---

## 2. IMU / AHRS

| Component | Part Number | Package | Notes |
|---|---|---|---|
| IMU (primary) | **ICM-42688-P** | LGA-14, 2.5x3mm | Current gold-standard FC IMU — lower noise density than MPU-9250/6000, 32kHz ODR, SPI up to 24MHz. This is what you should design in, **not** MPU-9250 (discontinued, TDK's own successor ICM-20948 isn't even register-compatible with your existing driver — you'd be rewriting it anyway, so may as well rewrite against the better part). |
| Magnetometer | **IST8310** | QFN, 2x2mm | Now recommended, not optional. Without vision/optical-flow heading correction, GPS course-over-ground is your only other heading source — and that's unusable at hover or low speed (no ground track to derive heading from). You need this for stable yaw during waypoint loiter, takeoff, and landing. Keep it away from power traces / high-current motor leads. |

> Note: ICM-42688-P is a bare LGA part — not hand-solderable without hot air/reflow. Factor that into your assembly plan (JLCPCB/PCBWay assembly, or reflow oven + stencil).

## 3. Barometer

| Component | Part Number | Package | Notes |
|---|---|---|---|
| Barometer | **BMP390** | LGA-10, 2x2.5mm | Keep — you already have a working bare-metal driver for this, still in active production, no reason to change it. |

## 4. GPS

| Component | Part Number | Package | Notes |
|---|---|---|---|
| GPS module | **u-blox MAX-M10S** | 9.7x10.1mm SMD module | Current standard low-cost choice for hobby/research drones — UART or I2C, integrated patch antenna option. |
| — upgrade path | u-blox NEO-M9N | 12.2x16mm | If you later want multi-band/RTK precision for the autonomy work. Drop-in swap on the UART interface, not needed for v1. |

---

## 5. Power System

| Component | Part Number | Package | Notes |
|---|---|---|---|
| Reverse polarity protection | P-channel MOSFET, e.g. DMG3415U | SOT23 | Near-zero voltage drop vs a series diode — worth it since your FC draw is small (a few hundred mA) but every mV of headroom matters for the 3.3V rail. |
| 5V buck (BEC) | TPS563201DDCR | SOT23-6 | 2A, wide input range — powers GPS, receiver, peripherals off battery voltage directly. |
| 3.3V LDO (clean analog rail) | AP2112K-3.3TRG1 | SOT23-5 | Feeds MCU + IMU + baro. Isolate from any digital/noisy 3.3V domain with a ferrite bead near the MCU — small detail, real payoff on SPI noise to the IMU. |
| Battery voltage sense | Resistor divider, e.g. 100kΩ/10kΩ 1% | 0603/0805 | Into an ADC pin, scaled for your max pack voltage (6S headroom = 25.2V → well under 3.3V after divide). |
| Battery current sense (optional) | INA226AIDGSR + shunt (0.5–2mΩ depending on current rating) | I2C power monitor | Optional for v1 — useful once you're doing endurance/power budgeting for the autonomy stack. |
| Bulk input protection | TVS diode, e.g. SMBJ30A | SMB/DO-214AA | Basic overvoltage transient protection on the battery input. |

---

## 6. RC Input & Telemetry

| Component | Notes |
|---|---|
| ExpressLRS receiver port | 3-pin JST-GH (5V, GND, UART). Run ELRS 3.5+'s **native MAVLink mode** — since ELRS 3.5 it does full bidirectional MAVLink (RC control uplink + telemetry downlink) over the *same single UART*, straight from their docs: "only one UART is needed on the flight controller for both RC and telemetry." No separate telemetry radio, no separate UART, no piggyback scheme needed — the RX you already need for RC control does the whole job. This is what makes it fit onto USART1, the one spare UART this board has left (see §12). |
| MAVLink implementation | No new hardware — this is firmware. I'm assuming your own FreeRTOS firmware implements the MAVLink protocol (using the open-source `mavlink/c_library_v2` header-only C library) on that UART, so it's interoperable with Mission Planner/QGroundControl while your control/nav code stays yours. **Different thing entirely** if you meant flashing stock ArduPilot firmware onto this board — ArduPilot's STM32F411 support exists but is tight on a 512KB-flash part (full-feature ArduPilot generally wants 1MB+); some F411 targets run a stripped build. Worth confirming which of these you mean before you're deep in firmware — doesn't change hardware, changes your whole software plan. |
| — if you want a redundant/independent link later | A dedicated radio (RFD900x/SiK) is still an option for range/redundancy separate from the RC link, but that needs its own UART and this chip doesn't have a spare one (see §12) — would mean dropping GPS to softserial or moving to RET6/a bigger F4 part. Not needed for v1. |

## 7. Ground-Station ROS2 Link (optional)

| Component | Notes |
|---|---|
| No onboard hardware needed | If you still want this to look like a ROS2 node for tooling/logging consistency with the rover, run the micro-ROS agent on your laptop over the existing native USB link — no extra pins, no onboard compute, no weight penalty. Bench/tethered only, not usable mid-flight, but fine for testing and log pulls. |

## 8. Motor / ESC Output

| Component | Notes |
|---|---|
| Motor signal pads | 4x DShot/PWM outputs to a 4-in-1 ESC (BLHeli32/AM32 compatible). JST-GH 1.25mm, 4-pin (signal, 5V, GND — or just signal+GND if ESC is separately powered from the PDB). Wire for bidirectional DShot if you want RPM telemetry back — same pad, no extra pin needed. |

## 9. Storage / Logging

| Component | Part Number | Notes |
|---|---|---|
| microSD slot | Molex 104031-0812 (push-push) or equivalent | SPI-connected, for blackbox-style logging alongside your micro-ROS bag files — useful for correlating low-level control loop data with SLAM output post-flight. |

## 10. Housekeeping

| Component | Notes |
|---|---|
| Power LED | Hardwired (not firmware-driven) — e.g. 0603 green LED + 680Ω resistor off the 3.3V rail (~2mA continuous, ~(3.3V−2.1Vf)/2mA≈600Ω). Confirms the board is actually powered before any firmware runs — genuinely useful during bring-up when you're debugging whether a dead board is a power problem or a code problem. |
| Status LED | WS2812 addressable, single-wire, for arm/mode/error state. |
| Buzzer | Passive piezo (e.g. CMT-1206S) via MOSFET drive — lost-aircraft/status alerts. |
| Arm safety | Software-gated arm (RC stick command or companion-computer command) — no extra hardware required, just a firmware state machine. |

---

## 11. Connectors & Mechanical

- **Mounting pattern:** 30.5x30.5mm (M3, standard FC hole spacing) so it's compatible with off-the-shelf frames if you want to bench-test on real hardware before your own frame is ready. Use rubber grommets for vibration isolation on the IMU-carrying layer if you're not doing a soft-mounted stack.
- **Connector standard:** JST-GH 1.25mm throughout — matches the modern FC/ELRS ecosystem, smaller and more vibration-resistant than JST-SH or Dupont.

---

## 12. Finalized Pin Assignment (conflict-checked against the datasheet AF table)

| Peripheral | Signal | Pin | Pin # | Notes |
|---|---|---|---|---|
| Crystal (HSE) | OSC_IN / OSC_OUT | PH0 / PH1 | 5 / 6 | Y1 8MHz + CL1/CL2 + R_EXT, per §1 |
| SPI1 — IMU | CS / SCK / MISO / MOSI | PA4 / PA5 / PA6 / PA7 | 20-23 | Fixed, no alternate location, no conflicts |
| SPI2 — microSD | CS / SCK / MISO / MOSI | PB12 / PB13 / PB14 / PB15 | 26-29 | Fixed, no conflicts |
| I2C1 — GPS (DDC), BMP390, IST8310, INA226 | SCL / SDA | PB8 / PB9 | 45 / 46 | GPS moved here from USART6 — USART6 is gone now that USB owns PA11/PA12 |
| USART1 — ELRS (RC + MAVLink) | TX / RX | PB6 / PB7 | 42 / 43 | Only remaining UART once USART2 (motors) and USART6 (USB) are gone; moved here so PA9/PA10 stay free/spare |
| USB (native) | D- / D+ | PA11 / PA12 | 32 / 33 | Replaces CP2102N; needs HSE (see §1), not usable with USART6 |
| Motors 1–4 (DShot) | TIM5_CH1/2/3/4 | PA0 / PA1 / PA2 / PA3 | 10-13 | All four on one timer (was TIM1 CH1-3 + TIM3 CH1) — shorter traces to this corner, and fixes the TIM3 period clash with the WS2812 status LED below |
| Status LED (WS2812) | TIM3_CH2 | PB5 | 41 | No longer shares TIM3 with a motor channel |
| Buzzer | GPIO | PB2 | 39 | |
| Battery voltage sense | ADC1_IN9 | PB1 | 19 | Moved off PA0 — PA0 is now Motor 1 |
| SWD | SWDIO / SWCLK | PA13 / PA14 | 34 / 37 | Standard debug pins |
| BOOT0 | — | dedicated BOOT0 pin | 44 | Not a GPIO — separate physical pin, sampled by boot ROM |
| NRST | — | dedicated NRST pin | 7 | Not a GPIO — separate physical pin |

**Spare pins for later** (RSSI analog in, arm switch, second buzzer, etc.): PA8, PA9, PA10, PB0, PB3, PB4, PB10.

**What changed and why:** dropping the CP2102N moves USB onto the MCU's own PA11/PA12, which kills USART6 — so GPS moves to I2C1 (DDC mode on the MAX-M10S), sharing the bus with BMP390/IST8310/INA226 without address conflicts. Motors no longer use a UART at all (see below), so USART1 is the only UART left, and ELRS takes it on PB6/PB7. Motors move off the old TIM1 (3 channels only, PA8-10) + TIM3 (PB4, sharing a period with the WS2812 on PB5) split onto TIM5_CH1-4 on PA0-PA3 — one timer, four channels, and physically the pin range you asked for (10-13) to shorten the ESC traces. Battery sense moves off PA0 (now Motor 1) to PB1.

**Check before layout:** TIM5_CH2 (Motor 2, PA1) and SPI2_TX (microSD) both use DMA1 Stream 4 on the F411 — either service the SD card by interrupt instead of DMA, or confirm an alternate stream in RM0383 before finalizing firmware DMA assignments. This wasn't an issue with the old TIM1/TIM3 motor mapping.

Verified against the datasheet's Table 8 pin definitions and AF table for PA0-PA3 (TIM5), PA11/PA12 (USB), PH0/PH1 (OSC), and PB6/PB7/PB8/PB9. The remaining PB-side assignments (PB2, PB5, PB12-15) carry over from the prior revision unchanged.

---

## 13. Pull-Up / Pull-Down Requirements

Internal GPIO PUPDR pull-ups (~30–50kΩ on F4, check exact value per pin in the datasheet) are too weak and too late for most of these nets — don't rely on them.

| Net | External resistor | Why internal isn't enough |
|---|---|---|
| I2C1 (SDA/SCL — BMP390, IST8310) | 2.2–4.7kΩ to 3.3V, both lines | Internal pull-ups can't charge bus capacitance fast enough for I2C rise-time spec, especially Fast-mode with two devices. This is mandatory, not a robustness margin. |
| SPI1 CS (IMU), SPI2 CS (SD) | 10kΩ pull-up, idle-high | Internal PUPDR only activates once firmware configures the pin — floats during power-up/reset before that. External resistor guarantees deselected state from power-on, independent of init timing. |
| BOOT0 | 10kΩ pull-down (already in §1) | Sampled by the boot ROM before any firmware runs — internal pull config isn't even active at that point in the boot sequence. Mandatory. |
| NRST | Keep 100nF decoupling + external pull-up despite the internal one | STM32 has a permanent weak internal pull-up on NRST, but it's weak and this board sits next to brushless motor EMI. A reset glitch mid-flight is the worst-case failure — don't rely on the weak internal one alone. |
| SPI clock/MOSI/MISO, GPS/CRSF/telemetry UART RX/TX | None needed | Actively driven push-pull by whichever side is transmitting. |

## 14. Stackup & Layout Notes

**Stackup:** Top=Signal, L2=Ground (solid), L3=Power (split 3.3V/5V), Bottom=Signal. Standard, legitimate 4-layer choice.

**The one real gotcha:** bottom layer (L4) references L3 (the nearest plane), not ground — L3 is split, so any bottom-layer net crossing the 3.3V/5V boundary has an interrupted return path. Top layer is fine (references solid L2).

Mitigation, in priority order:
1. **Floorplan discipline** — group the power section (battery input, both regulators) in one physical zone so no bottom-layer net needs to cross the split at all.
2. **Route genuinely sensitive nets on top layer only** where they'd otherwise cross — SPI1 to the IMU especially. Don't drop it to the bottom layer to dodge congestion.
3. **Stitching caps** (0.1µF, several) across the split if anything unavoidably crosses it.

**Top-layer power pour:** via-stitch down to L3 at reasonable spacing (a handful of 0.3–0.5mm vias covers the 5V/2A rail easily). Keep it physically away from the IMU's local ground/decoupling area — don't let switching regulator pour sit next to the one sensor you specifically chose for low noise.

**Crystal (Y1) placement:** keep clearance from the 5V buck regulator (TPS563201) and other switching/high-current heat sources — confirmed at ≥13mm in the current layout. At that spacing, board-level self-heating won't push Y1 meaningfully outside its ±50ppm-guaranteed -40 to +85°C stability band; the crystal's own -40 to +125°C operating range still holds even if ambient runs hotter, just without the tight stability guarantee above 85°C (which doesn't matter for USB's ±0.25% requirement either way).

**Ground stitching:** tie top-layer ground fill down to L2 with vias at ~5-10mm spacing, tighter around the IMU and MCU ground pins specifically.

---

## Open Decisions (all resolved)

1. ~~MCU package~~ — resolved: CEU6, hot air assembly.
2. ~~Telemetry link~~ — resolved: ELRS native MAVLink on USART1, no separate radio.
3. ~~Assembly method~~ — resolved: hot air at home. Stencil + paste recommended for the QFN and the IMU's LGA pads.
4. ~~MAVLink implementation~~ — resolved: your own FreeRTOS firmware speaking MAVLink via `mavlink/c_library_v2`, not stock ArduPilot. Flash-size concern is moot — the library is header-only, no meaningful flash cost beyond the messages you actually pack.

**All open decisions closed. BOM is locked for schematic capture.**
