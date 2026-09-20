# Flight Controller — Finalized Component BOM (Rev A)

**Assumptions:** small 4-inch class quadcopter (proof-of-concept build), T-Motor Velox V45A 4-in-1 ESC (3-6S, 45A, confirmed 5V/2A BEC — FC powers from regulated ESC output, see §5), lighter-duty 2207-class motors. Stabilized flight + GPS waypoint missions — no onboard companion computer. STM32 runs the full nav/control stack; ROS2 tooling (if used) connects as a ground-station agent over the existing USB link, not onboard compute.

---

## 1. MCU & Programming

| Component | Part Number | Package | Notes |
|---|---|---|---|
| MCU | **STM32F411CEU6** | UQFN48, 7x7mm | Same die as your Nucleo's F411RE (512KB Flash / 128KB RAM), just the 48-pin package every real F411 FC uses (Matek, Kakute, community Black Pill boards). Your FreeRTOS/micro-ROS code ports over; you'll just have fewer GPIO than the 64-pin Nucleo — worth a pin budget pass (see §12) before committing footprint. |
| — alternative | STM32F411RCT6 | LQFP64, 10x10mm | Pick this instead if you want more GPIO headroom or easier hand-soldering/rework (0.5mm QFN pitch on the CEU6 needs hot air + flux, doable but less forgiving). Bigger, heavier board. |
| Clock source | **None — running HSI internal RC, no external crystal.** USB timing is handled entirely by the CP2102N's own internal 48MHz oscillator (±0.25%, no crystal needed per its datasheet) — the STM32 never touches native USB, it just talks UART to the bridge chip. Nothing else on this board (SysTick, TIM/DShot, SPI, I2C, UART baud rates) needs tighter accuracy than HSI's ~±1% provides. One less crystal, two less load caps, one less layout constraint. |
| SWD/debug header | 4-pin 0.1" or Tag-Connect TC2030-IDC footprint | — | **Keep this even though CP2102N is on the board.** CP2102N only gives you a UART bootloader/console — it does NOT give you breakpoints, register watch, or live debugging in OpenOCD. Your existing ST-Link + OpenOCD + VS Code workflow needs this header to keep working on the custom board. |
| USB-UART bridge | **CP2102N-A02-GQFN28** | QFN28, 5x5mm | Confirmed in production, in stock (LCSC/Digikey/Mouser). Bootloader entry + serial console/telemetry over USB. |
| USB connector | USB-C receptacle (e.g. GCT USB4085 or Amphenol 12401548E4#2A) | SMD | Add USBLC6-2SC6 (SOT23-6) ESD protection on D+/D-, and 5.1kΩ CC1/CC2 pull-downs for device-mode detection. |
| BOOT0 control | Momentary push-button (or 2-pin jumper) to 3.3V, plus a 10kΩ pull-down on BOOT0 | SMD button, e.g. Panasonic EVQ-PE | **Deliberate, not automatic.** Arduino/Black-Pill-style boards use an auto-reset circuit (DTR/RTS from the USB-UART chip toggling BOOT0/NRST on every serial connection) — don't do that here. On a flight controller, you do not want anything capable of resetting the MCU without a physical action from you. A button you have to hold means a reset can't happen from a stray serial-port open, a flaky ground-station connection, or noise on the CP2102N's control lines mid-bench-test. |
| Reset button | Momentary push-button to GND on NRST, 10kΩ pull-up | SMD button | Standard manual reset, same reasoning as above. |

---

## 2. IMU / AHRS

| Component | Part Number | Package | Notes |
|---|---|---|---|
| IMU (primary) | **ICM-42688-P** | LGA-14, 2.5x3mm | Current gold-standard FC IMU — lower noise density than MPU-9250/6000, 32kHz ODR, SPI up to 24MHz. This is what you should design in, **not** MPU-9250 (discontinued, TDK's own successor ICM-20948 isn't even register-compatible with your existing driver — you'd be rewriting it anyway, so may as well rewrite against the better part). |
| Magnetometer | **Not on this board.** Moved to the GPS module — see §4. Putting a magnetometer this close to the power regulators and motor/ESC current on the FC itself would give you unreliable heading data regardless of part choice; every real GPS module solves this by mounting the compass on the same external mast as the GPS antenna. |

> Note: ICM-42688-P is a bare LGA part — not hand-solderable without hot air/reflow. Factor that into your assembly plan (JLCPCB/PCBWay assembly, or reflow oven + stencil).

## 3. Barometer

| Component | Part Number | Package | Notes |
|---|---|---|---|
| Barometer | **BMP581** | LGA-10, 2x2.5mm | Capacitive sensing (vs BMP390's resistive) — ~1cm altitude noise vs BMP390's ~10cm, genuine upgrade not just an availability fallback. Outputs pressure directly in Pa, no compensation formula needed. **Different register map from BMP390** (confirmed on Bosch's own forum — BMP580/581/585 share a map with each other, not with the BMP3xx series) — this needs its own driver, not a reuse of any BMP390 code. Arguably less driver code overall since there's no compensation math to implement. |

## 4. GPS

| Component | Part Number | Package | Notes |
|---|---|---|---|
| GPS module | **Combined GPS + Compass module**, budget M10-chipset clone (~$8-15) recommended over name-brand (~$30) — see §15 sourcing for the trade-off | External puck on a mast | Mounts externally, away from the FC board entirely — needs sky view for the GPS antenna. Keep compass **≥10cm from power lines/ESC/motors** (Matek's published spec). |
| GPS/Compass connector on FC | 6-pin JST-GH: VCC, GND, GPS TX, GPS RX, compass SCL, compass SDA | On the FC board | Compass still logically rides I2C1 alongside BMP581, just via a ~10-15cm cable to the mast instead of a board trace — short enough that I2C timing isn't a concern. |

---

## 5. Power System

**Switched to T-Motor Velox V45A (30.5x30.5mm, 45A/55A burst, 3-6S, AM32/BLHeli_32) — confirmed 5V/2A + 10V/2A onboard BEC.** Much cheaper than the original F55A PRO III (~$30-35 vs $115, or ~$23 for the "Lite" BLHeli_S variant if you want to save further), and this one actually regulates power before handing it to the FC — the 10V rail is for VTX, not relevant here; the 5V/2A rail is your FC's logic supply. This brings the simplified power design back.

| Component | Part Number | Package | Notes |
|---|---|---|---|
| 5V input | From ESC's 5V/2A BEC, via stack connector | — | Confirmed regulated output, not raw battery — verified from the ESC's own spec sheet this time. |
| 3.3V LDO (clean analog rail) | AP2112K-3.3TRG1 | SOT23-5 | Only regulation stage the FC still needs — cascades from the ESC's 5V. Feeds MCU + IMU + baro. Isolate from any noisy digital 3.3V domain with a ferrite bead near the MCU. |
| Battery voltage sense | Resistor divider, e.g. 100kΩ/10kΩ 1% | 0603/0805 | Reads a VBAT sense tap from the ESC/stack connector into an ADC pin — low-current sense only, never carries real power. |
| Battery current sense — CUT for v1 | INA226AIDGSR | Dropped to save cost/complexity. You keep voltage sensing (the resistor divider above, basically free) — just no live current/mAh-remaining telemetry. Easy rev2 add if you want it later. |
| USB power OR-ing | 2x Schottky diode, **SS110** (SMA, 1A/100V) — SS12 or SS14 (20V/40V) would shave a few tens of mV off forward drop if equally available, but SS110 is a fine choice as-is | One in series from ESC BEC → 5V rail, one from USB VBUS → same 5V rail. Lets you power the whole board off USB alone for bench debugging — no battery/ESC needed, motors physically can't spin since they have no power at all in this mode. Diodes prevent backfeed between sources if both are connected at once. 1A rating sized against the ~500mA USB host limit with real margin. |

**No buck converter, reverse-polarity MOSFET, or TVS needed on the FC board** — all upstream of the FC now, on the ESC itself.


## 6. RC Input & Telemetry

| Component | Notes |
|---|---|
| ExpressLRS receiver port | 3-pin JST-GH (5V, GND, single-wire half-duplex data). Run ELRS 3.5+'s **native MAVLink mode** — since ELRS 3.5 it does full bidirectional MAVLink (RC control uplink + telemetry downlink) over that *same single wire*, straight from their docs: "only one UART is needed on the flight controller for both RC and telemetry." No separate telemetry radio, no separate UART, no piggyback scheme needed — the RX you already need for RC control does the whole job. This is what actually makes the 3-USART budget work (see §12). |
| MAVLink implementation | No new hardware — this is firmware. I'm assuming your own FreeRTOS firmware implements the MAVLink protocol (using the open-source `mavlink/c_library_v2` header-only C library) on that UART, so it's interoperable with Mission Planner/QGroundControl while your control/nav code stays yours. **Different thing entirely** if you meant flashing stock ArduPilot firmware onto this board — ArduPilot's STM32F411 support exists but is tight on a 512KB-flash part (full-feature ArduPilot generally wants 1MB+); some F411 targets run a stripped build. Worth confirming which of these you mean before you're deep in firmware — doesn't change hardware, changes your whole software plan. |
| — if you want a redundant/independent link later | A dedicated radio (RFD900x/SiK) is still an option for range/redundancy separate from the RC link, but that needs its own UART and this chip doesn't have a spare one (see §12) — would mean dropping GPS to softserial or moving to RET6/a bigger F4 part. Not needed for v1. |

## 7. Ground-Station ROS2 Link (optional)

| Component | Notes |
|---|---|
| No onboard hardware needed | If you still want this to look like a ROS2 node for tooling/logging consistency with the rover, run the micro-ROS agent on your laptop over the existing CP2102N USB-UART link — no extra pins, no onboard compute, no weight penalty. Bench/tethered only, not usable mid-flight, but fine for testing and log pulls. |

## 8. Motor / ESC Output

| Component | Notes |
|---|---|
| Motor signal pads | 4x DShot/PWM outputs to a 4-in-1 ESC (BLHeli32/AM32 compatible). JST-GH 1.25mm, 4-pin (signal, 5V, GND — or just signal+GND if ESC is separately powered from the PDB). Wire for bidirectional DShot if you want RPM telemetry back — same pad, no extra pin needed. |

## 9. Storage / Logging — CUT for v1

Dropped microSD blackbox logging to keep cost/complexity down. Not flight-critical — you already have live MAVLink telemetry, and this is an easy rev2 add if you actually miss it once flying.

## 10. Housekeeping

| Component | Notes |
|---|---|
| Power LED | Hardwired (not firmware-driven) — e.g. 0603 green LED + 680Ω resistor off the 3.3V rail (~2mA continuous, ~(3.3V−2.1Vf)/2mA≈600Ω). Confirms the board is actually powered before any firmware runs — genuinely useful during bring-up when you're debugging whether a dead board is a power problem or a code problem. |
| Status LED | 2x plain discrete LEDs (or one bicolor) instead of WS2812 | Same arm/mode/error signaling job without addressable-LED firmware (no DMA-PWM bit-banging). Cheaper and simpler for what you actually need. |
| Buzzer | Passive piezo (e.g. CMT-1206S) via MOSFET drive — lost-aircraft/status alerts. |
| Arm safety | Software-gated arm (RC stick command or companion-computer command) — no extra hardware required, just a firmware state machine. |

---

## 11. Connectors & Mechanical

- **Mounting pattern:** 30.5x30.5mm (M3, standard FC hole spacing) — now doing real work, not just bench-test compatibility, since this is what lets the board actually stack on the off-the-shelf ESC. Use rubber grommets for vibration isolation.
- **Connector standard:** JST-GH 1.25mm throughout — matches the modern FC/ELRS ecosystem, smaller and more vibration-resistant than JST-SH or Dupont.
- **ESC connection:** T-Motor Velox V45A provides regulated 5V, GND, VBAT sense, 4x motor signal, and telemetry — standard stack interface. Check the specific cable/pinout that ships with it once ordered.

---

## 12. Finalized Pin Assignment (conflict-checked against the datasheet AF table)

| Peripheral | Signal | Pin | Notes |
|---|---|---|---|
| SPI1 — IMU | CS / SCK / MISO / MOSI | PA4 / PA5 / PA6 / PA7 | Fixed, no alternate location, no conflicts |
| SPI2 — microSD | CS / SCK / MISO / MOSI | PB12 / PB13 / PB14 / PB15 | Fixed, no conflicts |
| I2C1 — BMP581 (local) + compass (via GPS mast cable) | SCL / SDA | PB8 / PB9 | Moved here (not PB6/7) to make room for USART1 |
| USART1 — CP2102N | TX / RX | PB6 / PB7 | Moved off default PA9/10 to free TIM1 for motors |
| USART2 — ELRS (RC + MAVLink) | Single-wire, half-duplex | PA2 only | CRSF is single-wire — TX and RX share one physical pin (STM32's HDSEL half-duplex mode). PA3 is genuinely free, not just theoretically spare — see updated spare list below. |
| USART6 — GPS | TX / RX | PA11 / PA12 | Only available since native USB is unused (CP2102N handles USB externally) |
| Motor 1–3 (DShot) | TIM1_CH1/2/3 | PA8 / PA9 / PA10 | Freed by moving USART1 off these pins |
| Motor 4 (DShot) | TIM3_CH1 | PB4 | TIM1 only has 3 clean channels here — CH4 (PA11) collides with USART6 |
| Status LEDs (2x discrete) | GPIO | PB5, PB0 | Plain digital output, no timer/DMA needed now that WS2812 is cut |
| Buzzer | GPIO | PB2 | |
| Battery voltage sense | ADC1_IN0 | PA0 | |
| SWD | SWDIO / SWCLK | PA13 / PA14 | Standard debug pins |
| BOOT0 | — | dedicated BOOT0 pin | Not a GPIO — separate physical pin, sampled by boot ROM |
| NRST | — | dedicated NRST pin | Not a GPIO — separate physical pin |

**Spare pins for later** (RSSI analog in, arm switch, second buzzer, etc.): PA1, PA3, PB1, PB3, PB10.

**The real conflict this resolves:** PA9/PA10 are shared between USART1 and TIM1_CH2/CH3 — can't have both. Moving USART1 to its alternate location (PB6/7) frees PA9/10 for motor timer channels, which in turn displaced I2C1 to its other option (PB8/9). TIM1 only yields 3 usable motor channels regardless, since CH4 lives on PA11 which USART6/GPS needs — motor 4 goes on TIM3 instead, which is exactly what real F411-based flight controllers do for this reason.

Verified directly against the datasheet's Table 8 pin definitions for the PA8–PA15 region and PA2/PA3. The PB-side assignments (PB2, PB4, PB5, PB8, PB9) rely on well-established, cross-referenced knowledge of this chip rather than a fresh table pull this session — worth a quick visual check against the KiCad symbol once placed, low risk but cheap to confirm.

---

## 13. Pull-Up / Pull-Down Requirements

Internal GPIO PUPDR pull-ups (~30–50kΩ on F4, check exact value per pin in the datasheet) are too weak and too late for most of these nets — don't rely on them.

| Net | External resistor | Why internal isn't enough |
|---|---|---|
| I2C1 (SDA/SCL — BMP581 local + compass via cable) | 2.2–4.7kΩ to 3.3V, both lines | Internal pull-ups can't charge bus capacitance fast enough for I2C rise-time spec, especially Fast-mode with two devices. This is mandatory, not a robustness margin. |
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

**Ground stitching:** tie top-layer ground fill down to L2 with vias at ~5-10mm spacing, tighter around the IMU and MCU ground pins specifically.

## 15. Sourcing

| Part | Primary source | Backup | Note |
|---|---|---|---|
| STM32F411CEU6TR | LCSC | DigiKey / Mouser | High-demand part, check current stock before committing. |
| CP2102N-A02-GQFN28 | DigiKey / Mouser | LCSC / Arrow | In stock everywhere. |
| ICM-42688-P | DigiKey / Mouser | LCSC | In stock now; flagged as high long-term supply-chain risk, popular FC IMU. |
| BMP581 | DigiKey / Mouser | LCSC | Newer part than BMP390, better stock situation. Adafruit and Bosch's own shuttle-board listings confirm both distributors carry it — worth a quick stock check at order time regardless, same as anything else. |
| GPS + Compass combo module | **Budget M10-chipset clone** (~$8-15, e.g. BZGNSS-style modules on AliExpress) | Matek M10Q-5883 (~$30) if you want the QC/warranty | Real-world testing (Oscar Liang's GPS review) shows clones perform comparably — same u-blox M10 chipset in many cases, just without brand markup. Trade-off: looser QC, occasional dud unit. Given the price, consider ordering two from a well-reviewed seller as a hedge — still cheaper than one name-brand unit. Mount compass **≥10cm from power lines/ESC/motors** (Matek's own spec, not just "far away"). |
| AP2112K-3.3TRG1, INA226AIDGSR, USBLC6-2SC6 | DigiKey / Mouser | LCSC / manufacturer direct | All mainstream, no sourcing issues. |
| ESC (budget option, pending mount confirmation) | HAKRC 4in1 40A, BLHeli-S, DShot600, 2-6S, **BEC 5V/2A confirmed** (from board silkscreen) | €20 secondhand | Confirms the simplified power design still holds — real 5V/2A BEC. Trade-off vs the Velox: BLHeli-S (8-bit) caps at DShot600, weaker bidirectional telemetry than AM32/BLHeli_32. **Mounting pattern not confirmed** — looks like standard 30.5x30.5mm from photo proportions but verify with calipers or ask the seller before finalizing. |
| ESC (fallback if HAKRC's mount doesn't match) | T-Motor Velox V45A, AM32/BLHeli_32, 3-6S, BEC 5V/2A + 10V/2A | $55, T-Motor official store / GetFPV / Pyrodrone | Confirmed 30.5x30.5mm, confirmed BEC. Costs more but removes the mounting-pattern uncertainty entirely. |
| USB-C receptacle, BOOT0/reset buttons, microSD slot, buzzer | DigiKey / Mouser | — | Standard connectors/passives. |
| WS2812B LED | DigiKey / Mouser (authorized) | — | Buy authorized, not marketplace — this part gets counterfeited heavily. |
| ExpressLRS receiver | BetaFPV / Happymodel / RadioMaster | — | Finished module, not a BOM component. |

---

## Open Decisions (all resolved)

1. ~~MCU package~~ — resolved: CEU6, hot air assembly.
2. ~~Telemetry link~~ — resolved: ELRS native MAVLink on USART2, no separate radio.
3. ~~Assembly method~~ — resolved: hot air at home. Stencil + paste recommended for the QFN and the IMU's LGA pads.
4. ~~MAVLink implementation~~ — resolved: your own FreeRTOS firmware speaking MAVLink via `mavlink/c_library_v2`, not stock ArduPilot. Flash-size concern is moot — the library is header-only, no meaningful flash cost beyond the messages you actually pack.

**All open decisions closed. BOM is locked for schematic capture.**
