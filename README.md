# Pi_cam

A collection of Raspberry Pi camera interfaces and utilities for capturing high-quality photos including RAW/DNG format support.

## Features

- Multiple camera interface examples with Flask web UI
- RAW/DNG capture support
- Autofocus control for compatible cameras
- LED status indicators
- Background DNG processing for fast captures
- Fujifilm film simulation LUTs
- Web-based camera controls

## Requirements

- Raspberry Pi (tested on Pi Zero 2)
- Raspberry Pi Camera Module (v3 recommended for autofocus)
- Python 3.7+
- picamera2 library

## Installation

```bash
# Install system dependencies
sudo apt update
sudo apt install -y python3-picamera2 python3-flask

# Install Python dependencies
pip3 install -r requirements.txt
```

## Project Structure

```
Pi_cam/
├── examples/              # Camera implementation examples
│   ├── basic_camera.py           # Basic web camera interface
│   ├── camera_with_autofocus.py  # Advanced interface with autofocus
│   └── dng_camera_led.py         # DNG capture with LED indicator
├── web_interfaces/        # HTML web interfaces
│   ├── camera_json.html          # JSON-based camera control
│   └── dng_trigger.html          # DNG capture trigger interface
├── tests/                 # Test scripts
│   └── test_background_dng.py    # Test background DNG processing
└── utils/                 # Utility scripts
    └── dng_processing/           # DNG/RAW processing tools
        ├── fujifilm_lut.py       # Fujifilm film simulation
        ├── lut_creator.py        # LUT creation tool
        ├── lut_tester.py         # LUT testing
        ├── ui_lut.py             # LUT UI interface
        └── luts/                 # Pre-made LUT files
```

## Usage

### Basic Camera Interface

```bash
python3 examples/basic_camera.py
```

Access the web interface at `http://[pi-ip]:8000`

Features:
- Normal resolution (2304x1296) and high-res (4608x2592) capture
- Gallery view
- Photo management
- Camera settings control

### Camera with Autofocus

```bash
python3 examples/camera_with_autofocus.py
```

Access at `http://[pi-ip]:8000`

Additional features:
- Autofocus control (continuous, manual)
- AF window selection
- Lens position control
- Full camera metadata

### DNG Camera with LED

```bash
python3 examples/dng_camera_led.py
```

Access at `http://[pi-ip]:8080`

Features:
- RAW DNG capture
- LED pulse indicator during operation
- Background DNG processing
- Memory usage monitoring
- Fast capture mode

## DNG Processing

The `utils/dng_processing/` directory contains tools for processing RAW DNG files:

- **fujifilm_lut.py**: Apply Fujifilm film simulations (Acros, Classic Chrome, Velvia)
- **lut_creator.py**: Create custom LUTs
- **lut_tester.py**: Test LUTs on images
- **ui_lut.py**: UI interface for LUT application

## Configuration

### Camera Settings

Each camera script supports different resolutions and configurations. Edit the `create_still_configuration()` calls in the scripts to adjust:

- Resolution
- Image format
- Buffer count
- Transform (flip/rotation)

### GPIO Pin (DNG Camera)

The DNG camera uses GPIO pin 29 for LED control. Change `led_pin` in `examples/dng_camera_led.py` to use a different pin.

## Service Management

The camera viewfinder runs as a systemd service on the Raspberry Pi.

### Restart the Camera Service

```bash
# Restart the service (applies code changes)
sudo systemctl restart camera-viewfinder.service

# Check service status
sudo systemctl status camera-viewfinder.service

# View real-time logs
sudo journalctl -u camera-viewfinder.service -f
```

### Other Service Commands

```bash
# Stop the service
sudo systemctl stop camera-viewfinder.service

# Start the service
sudo systemctl start camera-viewfinder.service

# View recent logs (last 100 lines)
sudo journalctl -u camera-viewfinder.service -n 100

# Check if service is enabled on boot
sudo systemctl is-enabled camera-viewfinder.service
```

## Troubleshooting

### Camera Not Detected

```bash
# Check if camera is detected
libcamera-hello --list-cameras

# Ensure camera is enabled in raspi-config
sudo raspi-config
# Interface Options -> Camera -> Enable
```

### Memory Issues

The DNG camera includes emergency cleanup functionality:
- Access `/emergency_cleanup` endpoint
- Automatically triggered on capture timeout

### Autofocus Not Working

- Ensure you have a camera module with autofocus (e.g., Camera Module 3)
- Check camera capabilities in script output

## License

See LICENSE file for details.

## Contributing

This is a work in progress. Contributions and improvements are welcome!
