# Joystick Controls for PiCam

## GPIO Pin Mapping

| Direction | GPIO Pin | Normal Mode | Gallery Mode | Focus Zone Mode |
|-----------|----------|-------------|--------------|-----------------|
| LEFT      | GPIO 19  | **Open Gallery** | Previous Photo | Move zone LEFT |
| RIGHT     | GPIO 21  | No action | Next Photo | Move zone RIGHT |
| UP        | GPIO 16  | No action | **Exit Gallery** | Move zone UP |
| DOWN      | GPIO 26  | **Activate Focus Zones** | No action | Move zone DOWN |
| SWITCH    | GPIO 20  | No action | **Exit Gallery** | Confirm & Exit Focus Mode |

## Modes Overview

The camera has three modes:
1. **Normal Mode** - Live camera viewfinder (default)
2. **Gallery Mode** - View captured photos on the display
3. **Focus Zone Mode** - Select specific area for camera to focus on

## Usage Guide

### 📸 Viewing Photos (Gallery Mode)

**To Open Gallery:**
1. Press **LEFT** (GPIO 19) in normal mode
2. Most recent photo is displayed on the screen
3. Photo counter shows current position (e.g., "1/10")
4. Single beep confirms

**Navigate Photos:**
- **LEFT** (GPIO 19): Previous photo (wraps around)
- **RIGHT** (GPIO 21): Next photo (wraps around)
- Each navigation beeps once

**Exit Gallery:**
- **UP** (GPIO 16): Exit and return to camera viewfinder
- **SWITCH** (GPIO 20): Exit and return to camera viewfinder

**If No Photos:**
- Triple beep indicates no photos available
- Returns to normal mode

---

### 🎯 Focus Zone Selection

**To Activate Focus Zones:**
1. Press **DOWN** (GPIO 26) in normal mode
2. Grid lines turn **bright green**
3. Yellow box highlights current zone (starts at center)
4. Double beep confirms activation

**Move the Focus Zone:**
- **LEFT** (GPIO 19): Move zone left (0-2)
- **RIGHT** (GPIO 21): Move zone right (0-2)
- **UP** (GPIO 16): Move zone up (0-2)
- **DOWN** (GPIO 26): Move zone down (0-2)
- Single beep for each movement
- Camera adjusts focus to selected zone in real-time

**Confirm and Exit:**
- **SWITCH** (GPIO 20): Confirm selection and exit focus zone mode
- Selected zone remains active for autofocus
- Grid returns to subtle gray
- Single beep confirms

---

### Visual Feedback

#### Normal Mode (Live Viewfinder)
- Subtle gray grid lines (rule of thirds)
- Camera info on left (ISO, shutter speed, focus distance)
- Photo counter on right (remaining photos)
- White border around preview area

#### Gallery Mode
- Photo displayed full-screen, scaled to fit
- Photo counter overlay (e.g., "3/15")
- Black bars if aspect ratio doesn't match

#### Focus Zone Mode
- Grid lines turn **bright green**
- Selected zone has **thick yellow border** (2px)
- **Yellow corner markers** at each corner of selected zone
- 3x3 grid of selectable zones

---

### Audio Feedback Summary

| Beep Pattern | Meaning |
|--------------|---------|
| Single beep | Button press, navigation, action confirmed |
| Double beep | Focus zone mode activated |
| Triple beep | No photos found in gallery |

---

## Additional Camera Controls

### Focus Lock Button (GPIO 2)
- **Press and Hold**: Lock autofocus and auto-exposure
- **Release**: Unlock and resume auto modes
- Green "LOCK" indicator appears on screen when active
- Short beep when locked

### Shutter Button (GPIO 3)
- **Press**: Capture high-resolution photo (4608x2592)
- Saves to `/home/pi/photos/` as `PICAM_XXX.jpg`
- Double beep during capture
- Brief pause while switching camera modes
- Photo counter updates automatically

---

## Hardware Setup

All joystick pins use **internal pull-up resistors** and are **active-low**:
- Button press connects the pin to **ground (GND)**
- When not pressed, pin is pulled **HIGH** by internal resistor
- No external resistors needed

### Wiring Diagram
```
Joystick        Raspberry Pi
--------        ------------
LEFT    ------>  GPIO 19
RIGHT   ------>  GPIO 21
UP      ------>  GPIO 16
DOWN    ------>  GPIO 26
SWITCH  ------>  GPIO 20
GND     ------>  GND
VCC     ------>  (Not connected - using pull-ups)
```

---

## Technical Notes

- **Gallery Display**: Photos are automatically resized to fit the 284x76 display while maintaining aspect ratio
- **Focus Zone Control**: Uses libcamera's `AfWindows` control for precise autofocus area selection
- **Performance**: Gallery mode pauses camera preview to save CPU resources
- **Web Access**: Photos also available at `http://picam.local:5000` from any device on the network

---

## Quick Reference Card

```
┌─────────────────────────────────────────────┐
│         PiCam Joystick Controls             │
├─────────────────────────────────────────────┤
│  Normal Mode:                               │
│    LEFT  → Open photo gallery on display    │
│    DOWN  → Activate focus zone selection    │
│                                             │
│  Gallery Mode:                              │
│    LEFT  → Previous photo                   │
│    RIGHT → Next photo                       │
│    UP    → Exit gallery                     │
│    SW    → Exit gallery                     │
│                                             │
│  Focus Zone Mode:                           │
│    LEFT  → Move zone left                   │
│    RIGHT → Move zone right                  │
│    UP    → Move zone up                     │
│    DOWN  → Move zone down                   │
│    SW    → Confirm and exit                 │
└─────────────────────────────────────────────┘
```
