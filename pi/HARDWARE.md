# HARDWARE.md — Pi capture device pinout and wiring

Owner: **Engineer A**.

All GPIO numbers are BCM (Broadcom). The Pi 5 uses the same BCM numbering as Pi 4.

## GPIO pinout

| Component | BCM pin | Physical pin | Direction | Notes |
|-----------|---------|--------------|-----------|-------|
| LED Red channel | 12 | 32 | OUT | Active high; 330Ω series resistor to GND |
| LED Green channel | 13 | 33 | OUT | Active high; 330Ω series resistor to GND |
| LED Blue channel | 16 | 36 | OUT | Active high; 330Ω series resistor to GND |
| Haptic motor | 18 | 12 | OUT (PWM) | Drives N-MOSFET gate; motor on drain side |
| Button | 22 | 15 | IN | Active low; internal pull-up enabled |
| GND (LED common) | — | 34 | — | Common cathode return |
| GND (haptic) | — | 6 | — | Source of N-MOSFET |
| 3.3V (LED supply) | — | 17 | — | Via 330Ω resistors to each channel |
| 5V (motor) | — | 4 | — | Motor supply via MOSFET; use a flyback diode |

## Schematic notes

### RGB LED
- LED is common-cathode (4-pin). Red/Green/Blue anodes connect via 330Ω resistors to GPIO12/13/16 respectively. Common cathode to GND (pin 34).
- `gpiozero.RGBLED` drives each channel independently; `active_high=True`.
- At 3.3V and 330Ω: ~10mA per channel — bright enough, within GPIO current limits.

### Haptic motor
- Small DC motor (≤100mA at 5V). Do not drive directly from GPIO.
- Circuit: GPIO18 → N-MOSFET gate (e.g. 2N7000) → motor drain, 5V to motor VCC.
- Flyback diode (1N4001) across motor terminals, cathode to +5V.
- PWM frequency: 1 kHz (audible buzz serves as secondary feedback).

### Button
- Momentary tactile switch between GPIO22 and GND.
- `gpiozero.Button(22, pull_up=True, bounce_time=0.05)` enables internal pull-up and 50ms debounce.
- Physical pin 15; GND to physical pin 14.

## LED state table

| State | Colour | R | G | B | Meaning |
|-------|--------|---|---|---|---------|
| `off` | None | 0 | 0 | 0 | Device not initialised or session ended |
| `armed` | Blue | 0 | 0 | 1 | Connected to backend, waiting for session / partner consent |
| `recording` | **Green** | 0 | 1 | 0 | **Actively streaming audio — recording indicator (consent-required)** |
| `degraded` | Yellow | 1 | 1 | 0 | WS disconnected, buffering locally |
| `offline` | Red | 1 | 0 | 0 | No network, not recording |

> **Recording indicator (non-negotiable):** The green LED MUST be clearly visible at all times when audio is streaming to the backend. This is a consent requirement. Never suppress or dim it during active streaming.

## Wiring checklist (before first power-on)

- [ ] 330Ω resistors on all three LED channels
- [ ] Flyback diode across haptic motor, polarity correct (cathode to +5V)
- [ ] N-MOSFET source to GND, gate to GPIO18 via 10kΩ pull-down
- [ ] Button between GPIO22 and GND (internal pull-up enabled in software)
- [ ] No GPIO pin exceeding 16mA current draw

## USB camera / mic

The Logitech USB camera appears as `/dev/video0` (camera) and a USB audio device in `arecord -l`. OpenCV and sounddevice auto-detect these. If the device index changes, set `LARPCHEKR_CAMERA_INDEX` (default 0) and `LARPCHEKR_AUDIO_DEVICE` (default `None` = system default).

## Enclosure

3D-printed chest mount (PLA, 2-part shell). Key constraints:
- Open grille directly over the mic element (no occlusion — coordinate with designer before printing).
- LED window: 5mm diameter hole on upper-right face, aligned with LED position.
- Button: panel-mount hole on left face, 12mm diameter tactile cap.
- Camera: centred rectangular cutout matching lens barrel OD.
- USB cable runs inside the shell, strain-relieved at exit point.
