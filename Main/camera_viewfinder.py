#!/usr/bin/env python3
"""
Camera Viewfinder - Using C Display Library
ST7789P3 Display (284x76 horizontal)
Raspberry Pi Zero 2W + Camera Module
With integrated Photo Gallery Web Server
"""

import time
import numpy as np
import os
import shutil
from pathlib import Path
from datetime import datetime
from gpiozero import Button, PWMOutputDevice
import RPi.GPIO as GPIO
import threading
from picamera2 import Picamera2
from libcamera import Transform
from PIL import Image, ImageDraw
from st7789_display import ST7789Display
from flask import Flask, render_template, send_from_directory, jsonify

# Display dimensions (HORIZONTAL orientation)
DISPLAY_WIDTH = 284
DISPLAY_HEIGHT = 76

# Camera preview settings (3:2 ratio)
PREVIEW_WIDTH = 114
PREVIEW_HEIGHT = 76

# Position preview centered horizontally
PREVIEW_OFFSET_X = (DISPLAY_WIDTH - PREVIEW_WIDTH) // 2

# Frame rate
PREVIEW_FPS = 20

# Photo storage
PHOTO_DIR = Path("/home/pi/photos")

# GPIO pins
GPIO_FOCUS = 2      # Focus lock button
GPIO_SHUTTER = 3    # Capture photo button
GPIO_BUZZER = 17    # Active buzzer

# Joystick GPIO pins (with pull-up resistors)
GPIO_JOY_LEFT = 19
GPIO_JOY_UP = 16
GPIO_JOY_SWITCH = 20
GPIO_JOY_DOWN = 26
GPIO_JOY_RIGHT = 21

# Flask web server for photo gallery
# Get the project root directory (parent of utils/)
PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATE_DIR = PROJECT_ROOT / 'web_interfaces'
STATIC_DIR = PROJECT_ROOT / 'web_interfaces' / 'static'

app = Flask(__name__,
            template_folder=str(TEMPLATE_DIR),
            static_folder=str(STATIC_DIR))

# Reference to the camera viewfinder instance (set during initialization)
viewfinder_instance = None

@app.route('/')
def index():
    """Serve the photo gallery page"""
    return render_template('photo_gallery.html')

@app.route('/api/photos')
def list_photos():
    """API endpoint to list all photos"""
    try:
        # Get all JPEG photos
        photo_files = sorted(PHOTO_DIR.glob("PICAM_*.jpg"), reverse=True)

        # Create list of photo info
        photos = []
        for photo in photo_files:
            stat = photo.stat()
            photos.append({
                'filename': photo.name,
                'size': stat.st_size,
                'timestamp': stat.st_mtime,
                'url': f'/photos/{photo.name}'
            })

        return jsonify({
            'success': True,
            'count': len(photos),
            'photos': photos
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/photos/<path:filename>')
def serve_photo(filename):
    """Serve individual photo files"""
    try:
        return send_from_directory(PHOTO_DIR, filename)
    except Exception as e:
        return f"Error: {str(e)}", 404

@app.route('/api/stats')
def stats():
    """Get storage statistics"""
    try:
        # Count photos
        photo_files = list(PHOTO_DIR.glob("PICAM_*.jpg"))
        photo_count = len(photo_files)

        # Calculate total size
        total_size = sum(f.stat().st_size for f in photo_files)

        # Get disk usage
        disk_usage = shutil.disk_usage(PHOTO_DIR)

        return jsonify({
            'success': True,
            'photo_count': photo_count,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'disk_free_mb': round(disk_usage.free / (1024 * 1024), 2),
            'disk_total_mb': round(disk_usage.total / (1024 * 1024), 2),
            'disk_used_percent': round((disk_usage.used / disk_usage.total) * 100, 1)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def run_flask_server():
    """Run Flask server in a separate thread"""
    print("[WEB] Starting photo gallery server on http://0.0.0.0:5000")
    print(f"[WEB] Template directory: {TEMPLATE_DIR}")
    print(f"[WEB] Template exists: {(TEMPLATE_DIR / 'photo_gallery.html').exists()}")
    print(f"[WEB] Static directory: {STATIC_DIR}")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


class CameraViewfinder:
    """Camera viewfinder with UI overlay"""

    def _pwm_pulse_led(self):
        """Pulses the LED using PWM in a separate thread."""
        try:
            while not self.pwm_thread_stop.is_set():
                # Slowly increase brightness
                for dc in range(0, 101, 5):
                    if self.pwm_thread_stop.is_set():
                        break
                    self.led_pwm.ChangeDutyCycle(dc)
                    time.sleep(0.05)
                # Slowly decrease brightness
                for dc in range(100, -1, -5):
                    if self.pwm_thread_stop.is_set():
                        break
                    self.led_pwm.ChangeDutyCycle(dc)
                    time.sleep(0.05)
        except Exception as e:
            print(f"LED PWM thread error: {e}")

    def __init__(self):
        global viewfinder_instance
        viewfinder_instance = self

        print("Initializing camera viewfinder...")
        print(f"Display: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT} (horizontal)")
        print(f"Preview: {PREVIEW_WIDTH}x{PREVIEW_HEIGHT} (centered)")

        # Create photo storage directory
        PHOTO_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Photo directory: {PHOTO_DIR}")

        # Start Flask web server in background thread
        print("Starting photo gallery web server...")
        flask_thread = threading.Thread(target=run_flask_server, daemon=True)
        flask_thread.start()
        
        # Initialize GPIO
        print("Initializing GPIO...")
        self.focus_button = Button(GPIO_FOCUS, pull_up=None, active_state=False, bounce_time=0.05)  # GPIO2 hardware pull-up, active low
        self.shutter_button = Button(GPIO_SHUTTER, pull_up=None, active_state=False, bounce_time=0.05)  # GPIO3 hardware pull-up, active low
        self.buzzer = PWMOutputDevice(GPIO_BUZZER, frequency=2000)  # Passive buzzer at 2kHz

        # Initialize joystick buttons (with pull-up resistors, active low)
        print("Initializing joystick GPIO...")
        self.joy_left = Button(GPIO_JOY_LEFT, pull_up=True, bounce_time=0.05)
        self.joy_up = Button(GPIO_JOY_UP, pull_up=True, bounce_time=0.05)
        self.joy_switch = Button(GPIO_JOY_SWITCH, pull_up=True, bounce_time=0.05)
        self.joy_down = Button(GPIO_JOY_DOWN, pull_up=True, bounce_time=0.05)
        self.joy_right = Button(GPIO_JOY_RIGHT, pull_up=True, bounce_time=0.05)

        # Initialize built-in LED on GPIO 29 (Pi Zero 2 W activity LED)
        # Using RPi.GPIO instead of gpiozero because GPIO 29 requires direct access
        self.led_pin = 29
        self.led_pwm = None
        self.pwm_thread_stop = threading.Event()
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.led_pin, GPIO.OUT)
            self.led_pwm = GPIO.PWM(self.led_pin, 100)  # 100 Hz frequency
            self.led_pwm.start(0)
            print("LED initialized on GPIO 29 with PWM")
        except Exception as e:
            print(f"Could not initialize LED: {e}")
            self.led_pwm = None
        
        # Set up button handlers
        self.focus_button.when_pressed = self.on_focus_pressed
        self.focus_button.when_released = self.on_focus_released
        self.shutter_button.when_pressed = self.on_shutter_pressed

        # Set up joystick handlers
        self.joy_left.when_pressed = self.on_joy_left_pressed
        self.joy_up.when_pressed = self.on_joy_up_pressed
        self.joy_switch.when_pressed = self.on_joy_switch_pressed
        self.joy_down.when_pressed = self.on_joy_down_pressed
        self.joy_right.when_pressed = self.on_joy_right_pressed
        
        # Focus state
        self.focus_locked = False

        # Focus zone selection state (3x3 grid)
        self.focus_zone_enabled = False  # Toggle with joystick switch
        self.focus_zone_x = 1  # Center position (0, 1, 2)
        self.focus_zone_y = 1  # Center position (0, 1, 2)
        self.focus_zones_grid = 3  # 3x3 grid

        # Gallery viewer state
        self.gallery_mode = False  # Toggle with LEFT button
        self.gallery_index = 0  # Current photo index
        self.gallery_photos = []  # List of photo paths
        
        # Initialize display
        print("Initializing display...")
        self.display = ST7789Display()
        
        # Show startup screen
        self.display.clear((0, 0, 0))
        self.display.draw_text(10, DISPLAY_HEIGHT // 2 - 20, "CAMERA", 16, (255, 255, 255))
        self.display.draw_text(5, DISPLAY_HEIGHT // 2, "STARTING", 12, (0, 255, 0))
        self.display.refresh()
        
        # Initialize camera
        print("Initializing camera...")
        self.camera = Picamera2()
        
        # Configure camera for square preview
        config = self.camera.create_preview_configuration(
            main={"size": (PREVIEW_WIDTH, PREVIEW_HEIGHT), "format": "RGB888"}
        )
        self.camera.configure(config)
        
        # Camera settings
        self.camera.set_controls({
            "Contrast": 1.2,
            "Saturation": 1.1,
            "Sharpness": 1.0
        })

        self.camera.start()
        time.sleep(1)  # Camera warm-up

        # Disable auto-exposure and use manual control with fixed shutter speed
        # We'll manually adjust ISO based on brightness
        self.camera.set_controls({
            "AeEnable": False,  # Disable auto-exposure
            "ExposureTime": 20000,  # Fixed 1/50s shutter speed
            "AnalogueGain": 1.0  # Start with low gain
        })

        # Store manual exposure state
        self.manual_exposure = True
        self.target_brightness = 0.45  # Target mean brightness (0-1 scale)
        self.current_gain = 1.0
        self.min_gain = 1.0
        self.max_gain = 16.0  # Allow up to ISO 1600 equivalent

        print("Camera ready!")

        # Start LED pulsing to indicate running
        if self.led_pwm:
            print("Starting LED pulse...")
            pwm_thread = threading.Thread(target=self._pwm_pulse_led)
            pwm_thread.daemon = True
            pwm_thread.start()
        else:
            print("LED not available, skipping pulse")

        # Test buzzer on boot
        print("Testing buzzer...")
        self.buzzer.value = 0.5  # 50% duty cycle for passive buzzer
        time.sleep(0.2)
        self.buzzer.value = 0

        # Count existing photos
        self.photos_taken = self.count_existing_photos()
        self.photos_remaining = self.calculate_photos_remaining()
        print(f"Existing photos: {self.photos_taken}")
        print(f"Photos remaining: {self.photos_remaining}")

        # UI state
        self.frame_count = 0
        self.current_iso = 0
        self.current_shutter_speed = 0
        self.current_focus_distance = 0
        self.capturing = False  # Flag to pause main loop during photo capture
    
    def count_existing_photos(self):
        """Count existing photos in storage directory"""
        try:
            photo_files = list(PHOTO_DIR.glob("PICAM_*.jpg"))
            return len(photo_files)
        except Exception as e:
            print(f"Error counting photos: {e}")
            return 0

    def calculate_photos_remaining(self):
        """Calculate how many photos can fit based on available disk space"""
        try:
            # Get disk usage for the photo directory
            stat = shutil.disk_usage(PHOTO_DIR)
            available_bytes = stat.free

            # Estimate average photo size (adjust based on your camera settings)
            # Typical JPEG from Raspberry Pi camera: ~2-5 MB
            avg_photo_size_mb = 3.5  # Conservative estimate in MB
            avg_photo_size_bytes = avg_photo_size_mb * 1024 * 1024

            # Calculate remaining photos
            photos_remaining = int(available_bytes / avg_photo_size_bytes)

            return max(0, photos_remaining)  # Don't return negative
        except Exception as e:
            print(f"Error calculating remaining photos: {e}")
            return 999  # Default fallback value
    
    def create_viewfinder_frame(self, camera_array):
        """
        Add UI overlay to camera preview

        Args:
            camera_array: numpy array (114, 76, 3) from camera

        Returns:
            numpy array (76, 284, 3) with UI elements - HORIZONTAL
        """
        # Flip camera view both horizontally and vertically
        camera_array = np.flip(camera_array, axis=(0, 1))

        # Fix inverted colors by swapping RGB channels to BGR
        camera_array = camera_array[:, :, ::-1]

        # Create full-width canvas (horizontal display)
        canvas = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 3), dtype=np.uint8)

        # Place camera preview in center horizontally
        canvas[:, PREVIEW_OFFSET_X:PREVIEW_OFFSET_X + PREVIEW_WIDTH, :] = camera_array
        
        # Convert to PIL for drawing UI elements
        img = Image.fromarray(canvas)
        draw = ImageDraw.Draw(img)

        # Left side UI - ISO value (converted to int)
        iso_text = f"ISO{int(self.current_iso)}"
        draw.text((5, 5), iso_text, fill=(255, 255, 255))

        # Below ISO - Shutter speed
        if self.current_shutter_speed > 0:
            shutter_ms = self.current_shutter_speed / 1000.0  # Convert to ms
            if shutter_ms >= 1000:
                shutter_text = f"{shutter_ms/1000:.1f}s"
            else:
                shutter_text = f"1/{int(1000000/self.current_shutter_speed)}"
        else:
            shutter_text = "---"
        draw.text((5, 18), shutter_text, fill=(255, 255, 255))

        # Below shutter - Focus distance (rounded to int)
        if self.current_focus_distance > 0:
            if self.current_focus_distance < 1:
                focus_text = f"{int(self.current_focus_distance*100)}cm"
            else:
                focus_text = f"{int(self.current_focus_distance)}m"
        else:
            focus_text = "---"
        draw.text((5, 31), focus_text, fill=(255, 255, 255))
        
        # Right side UI - Photo counter (showing remaining images)
        counter_text = f"{self.photos_remaining}"
        draw.text((DISPLAY_WIDTH - 40, 5), counter_text, fill=(255, 255, 255))

        # Focus lock indicator (bottom right)
        if self.focus_locked:
            draw.text((DISPLAY_WIDTH - 50, DISPLAY_HEIGHT - 15), "LOCK", fill=(0, 255, 0))
        
        # Draw white border around preview area
        border_x1 = PREVIEW_OFFSET_X - 1
        border_x2 = PREVIEW_OFFSET_X + PREVIEW_WIDTH
        draw.rectangle([border_x1, 0, border_x2, DISPLAY_HEIGHT - 1], 
                    outline=(255, 255, 255), width=1)
        
        # Rule of thirds grid lines (subtle gray) OR Focus zone grid (bright when enabled)
        if self.focus_zone_enabled:
            grid_color = (0, 255, 0)  # Green when focus zone is active
        else:
            grid_color = (80, 80, 80)  # Subtle gray for rule of thirds

        # Vertical lines (at 1/3 and 2/3 of preview width)
        third_width = PREVIEW_WIDTH // 3
        line1_x = PREVIEW_OFFSET_X + third_width
        line2_x = PREVIEW_OFFSET_X + (2 * third_width)

        draw.line([line1_x, 0, line1_x, DISPLAY_HEIGHT], fill=grid_color, width=1)
        draw.line([line2_x, 0, line2_x, DISPLAY_HEIGHT], fill=grid_color, width=1)

        # Horizontal lines (at 1/3 and 2/3 of preview height)
        third_height = DISPLAY_HEIGHT // 3
        line1_y = third_height
        line2_y = 2 * third_height

        draw.line([PREVIEW_OFFSET_X, line1_y, PREVIEW_OFFSET_X + PREVIEW_WIDTH, line1_y],
                fill=grid_color, width=1)
        draw.line([PREVIEW_OFFSET_X, line2_y, PREVIEW_OFFSET_X + PREVIEW_WIDTH, line2_y],
                fill=grid_color, width=1)

        # Draw focus zone indicator if enabled
        if self.focus_zone_enabled:
            # Calculate zone rectangle bounds
            zone_width = PREVIEW_WIDTH // self.focus_zones_grid
            zone_height = DISPLAY_HEIGHT // self.focus_zones_grid

            zone_x1 = PREVIEW_OFFSET_X + (self.focus_zone_x * zone_width)
            zone_y1 = self.focus_zone_y * zone_height
            zone_x2 = zone_x1 + zone_width
            zone_y2 = zone_y1 + zone_height

            # Draw highlighted zone with thick yellow border
            draw.rectangle([zone_x1, zone_y1, zone_x2, zone_y2],
                         outline=(255, 255, 0), width=2)

            # Draw corner markers for better visibility
            marker_len = 8
            marker_color = (255, 255, 0)
            # Top-left corner
            draw.line([zone_x1, zone_y1, zone_x1 + marker_len, zone_y1], fill=marker_color, width=2)
            draw.line([zone_x1, zone_y1, zone_x1, zone_y1 + marker_len], fill=marker_color, width=2)
            # Top-right corner
            draw.line([zone_x2, zone_y1, zone_x2 - marker_len, zone_y1], fill=marker_color, width=2)
            draw.line([zone_x2, zone_y1, zone_x2, zone_y1 + marker_len], fill=marker_color, width=2)
            # Bottom-left corner
            draw.line([zone_x1, zone_y2, zone_x1 + marker_len, zone_y2], fill=marker_color, width=2)
            draw.line([zone_x1, zone_y2, zone_x1, zone_y2 - marker_len], fill=marker_color, width=2)
            # Bottom-right corner
            draw.line([zone_x2, zone_y2, zone_x2 - marker_len, zone_y2], fill=marker_color, width=2)
            draw.line([zone_x2, zone_y2, zone_x2, zone_y2 - marker_len], fill=marker_color, width=2)
        
        # Convert back to numpy
        return np.array(img)
    
    def on_focus_pressed(self):
        """Focus button pressed - lock AF and AE"""
        print("\n[FOCUS DEBUG] Button pressed!")
        print("[FOCUS] Locking focus and exposure...")
        self.focus_locked = True

        # Get current camera metadata
        metadata = self.camera.capture_metadata()

        # Lock current AF and AE values
        self.camera.set_controls({
            "AfMode": 0,  # Manual focus mode
            "AeEnable": False  # Disable auto-exposure
        })

        # Short beep for focus lock
        print("[FOCUS] Beeping...")
        self.buzzer.value = 0.5
        time.sleep(0.05)
        self.buzzer.value = 0

    def on_focus_released(self):
        """Focus button released - unlock AF and AE"""
        print("[FOCUS DEBUG] Button released!")
        print("[FOCUS] Unlocking focus and exposure...")
        self.focus_locked = False

        # Re-enable auto modes
        self.camera.set_controls({
            "AfMode": 2,  # Continuous auto-focus
            "AeEnable": True
        })

    def on_joy_left_pressed(self):
        """Joystick LEFT pressed - GPIO 19 - Open gallery OR previous photo OR move focus zone"""
        if self.gallery_mode:
            # In gallery mode, go to previous photo
            self.gallery_index = (self.gallery_index - 1) % len(self.gallery_photos)
            print(f"\n[GALLERY] Previous photo ({self.gallery_index + 1}/{len(self.gallery_photos)})")
            self._display_gallery_photo()
        elif self.focus_zone_enabled:
            # In focus zone mode, move left
            self.focus_zone_x = max(0, self.focus_zone_x - 1)
            print(f"\n[FOCUS ZONE] Moved LEFT to position ({self.focus_zone_x}, {self.focus_zone_y})")
            self._apply_focus_zone()
        else:
            # Open image gallery on display
            print("\n[GALLERY] Opening photo gallery...")
            self._open_gallery()
        # Short beep
        self.buzzer.value = 0.3
        time.sleep(0.05)
        self.buzzer.value = 0

    def on_joy_up_pressed(self):
        """Joystick UP pressed - GPIO 16 - Exit gallery OR move focus zone up"""
        if self.gallery_mode:
            # Exit gallery mode
            print("\n[GALLERY] Exiting gallery mode")
            self._exit_gallery()
        elif self.focus_zone_enabled:
            self.focus_zone_y = max(0, self.focus_zone_y - 1)
            print(f"\n[FOCUS ZONE] Moved UP to position ({self.focus_zone_x}, {self.focus_zone_y})")
            self._apply_focus_zone()
        else:
            print("\n[JOYSTICK DEBUG] UP pressed (GPIO 16) - No action")
        # Short beep
        self.buzzer.value = 0.3
        time.sleep(0.05)
        self.buzzer.value = 0

    def on_joy_switch_pressed(self):
        """Joystick SWITCH pressed - GPIO 20 - Exit gallery OR confirm focus zone"""
        if self.gallery_mode:
            # Exit gallery mode
            print("\n[GALLERY] Exiting gallery mode")
            self._exit_gallery()
        elif self.focus_zone_enabled:
            # In focus zone mode, pressing switch confirms and exits
            print(f"\n[FOCUS ZONE] Confirmed zone ({self.focus_zone_x}, {self.focus_zone_y})")
            self.focus_zone_enabled = False
        else:
            print("\n[JOYSTICK DEBUG] SWITCH pressed (GPIO 20) - No action")
        # Short beep
        self.buzzer.value = 0.3
        time.sleep(0.05)
        self.buzzer.value = 0

    def on_joy_down_pressed(self):
        """Joystick DOWN pressed - GPIO 26 - Activate focus zones OR move down in gallery"""
        if self.gallery_mode:
            # In gallery mode, do nothing (or could delete photo, etc.)
            print("\n[JOYSTICK DEBUG] DOWN pressed in gallery mode - No action")
        elif self.focus_zone_enabled:
            # In focus zone mode, move down
            self.focus_zone_y = min(self.focus_zones_grid - 1, self.focus_zone_y + 1)
            print(f"\n[FOCUS ZONE] Moved DOWN to position ({self.focus_zone_x}, {self.focus_zone_y})")
            self._apply_focus_zone()
        else:
            # Activate focus zone mode
            self.focus_zone_enabled = True
            print(f"\n[FOCUS ZONE] ENABLED at position ({self.focus_zone_x}, {self.focus_zone_y})")
            self._apply_focus_zone()
            # Double beep for enable
            self.buzzer.value = 0.3
            time.sleep(0.05)
            self.buzzer.value = 0
            time.sleep(0.05)
            self.buzzer.value = 0.3
            time.sleep(0.05)
            self.buzzer.value = 0
            return
        # Short beep
        self.buzzer.value = 0.3
        time.sleep(0.05)
        self.buzzer.value = 0

    def on_joy_right_pressed(self):
        """Joystick RIGHT pressed - GPIO 21 - Next photo OR move focus zone right"""
        if self.gallery_mode:
            # In gallery mode, go to next photo
            self.gallery_index = (self.gallery_index + 1) % len(self.gallery_photos)
            print(f"\n[GALLERY] Next photo ({self.gallery_index + 1}/{len(self.gallery_photos)})")
            self._display_gallery_photo()
        elif self.focus_zone_enabled:
            self.focus_zone_x = min(self.focus_zones_grid - 1, self.focus_zone_x + 1)
            print(f"\n[FOCUS ZONE] Moved RIGHT to position ({self.focus_zone_x}, {self.focus_zone_y})")
            self._apply_focus_zone()
        else:
            print("\n[JOYSTICK DEBUG] RIGHT pressed (GPIO 21) - No action")
        # Short beep
        self.buzzer.value = 0.3
        time.sleep(0.05)
        self.buzzer.value = 0

    def _open_gallery(self):
        """Enter gallery mode to view photos on the display"""
        try:
            # Get list of photos
            self.gallery_photos = sorted(PHOTO_DIR.glob("PICAM_*.jpg"), reverse=True)

            if len(self.gallery_photos) == 0:
                print("[GALLERY] No photos found")
                # Triple beep to indicate no photos
                for _ in range(3):
                    self.buzzer.value = 0.3
                    time.sleep(0.1)
                    self.buzzer.value = 0
                    time.sleep(0.05)
                return

            # Enter gallery mode
            self.gallery_mode = True
            self.gallery_index = 0
            print(f"[GALLERY] Entered gallery mode - {len(self.gallery_photos)} photos")
            self._display_gallery_photo()

        except Exception as e:
            print(f"[GALLERY] Error opening gallery: {e}")

    def _display_gallery_photo(self):
        """Display the current gallery photo on the screen"""
        try:
            if not self.gallery_photos or self.gallery_index >= len(self.gallery_photos):
                return

            photo_path = self.gallery_photos[self.gallery_index]
            print(f"[GALLERY] Displaying {photo_path.name} ({self.gallery_index + 1}/{len(self.gallery_photos)})")

            # Load and resize image to fit display
            img = Image.open(photo_path)

            # Calculate aspect ratios
            img_aspect = img.width / img.height
            display_aspect = DISPLAY_WIDTH / DISPLAY_HEIGHT

            # Resize to fit display while maintaining aspect ratio
            if img_aspect > display_aspect:
                # Image is wider - fit to width
                new_width = DISPLAY_WIDTH
                new_height = int(DISPLAY_WIDTH / img_aspect)
            else:
                # Image is taller - fit to height
                new_height = DISPLAY_HEIGHT
                new_width = int(DISPLAY_HEIGHT * img_aspect)

            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Create canvas and center image
            canvas = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 3), dtype=np.uint8)
            offset_x = (DISPLAY_WIDTH - new_width) // 2
            offset_y = (DISPLAY_HEIGHT - new_height) // 2

            img_array = np.array(img)
            canvas[offset_y:offset_y + new_height, offset_x:offset_x + new_width] = img_array

            # Convert to PIL for adding info overlay
            canvas_img = Image.fromarray(canvas)
            draw = ImageDraw.Draw(canvas_img)

            # Draw photo info overlay
            info_text = f"{self.gallery_index + 1}/{len(self.gallery_photos)}"
            draw.text((5, 5), info_text, fill=(255, 255, 255))

            # Display on screen
            self.display.show_image(np.array(canvas_img))

        except Exception as e:
            print(f"[GALLERY] Error displaying photo: {e}")

    def _exit_gallery(self):
        """Exit gallery mode and return to camera viewfinder"""
        self.gallery_mode = False
        self.gallery_photos = []
        self.gallery_index = 0
        print("[GALLERY] Exited gallery mode")

    def _apply_focus_zone(self):
        """Apply the selected focus zone to camera AF"""
        # Calculate focus window based on zone position
        # Focus window is in normalized coordinates (0.0 - 1.0)
        zone_width = 1.0 / self.focus_zones_grid
        zone_height = 1.0 / self.focus_zones_grid

        # Calculate window bounds
        x_start = self.focus_zone_x * zone_width
        y_start = self.focus_zone_y * zone_height
        x_end = x_start + zone_width
        y_end = y_start + zone_height

        # Set AF window (libcamera uses (x, y, width, height) format)
        # AfMetering window controls where the camera focuses
        try:
            self.camera.set_controls({
                "AfMode": 2,  # Continuous AF
                "AfMetering": 0,  # Windows mode (uses AfWindows)
                "AfWindows": [(int(x_start * 65535), int(y_start * 65535),
                              int((x_end - x_start) * 65535), int((y_end - y_start) * 65535))]
            })
            print(f"[FOCUS ZONE] AF window set to zone ({self.focus_zone_x}, {self.focus_zone_y})")
        except Exception as e:
            print(f"[FOCUS ZONE] Warning: Could not set AF window: {e}")
            # Fallback to manual control if AF windowing not supported
            pass

    def on_shutter_pressed(self):
        """Shutter button pressed - capture photo in high resolution"""
        # Set flag to pause main loop
        self.capturing = True

        print("\n[SHUTTER DEBUG] Button pressed!")
        print("[SHUTTER] Capturing photo in high resolution...")

        # Double beep for capture
        print("[SHUTTER] Beeping...")
        self.buzzer.value = 0.5
        time.sleep(0.1)
        self.buzzer.value = 0
        time.sleep(0.05)
        self.buzzer.value = 0.5
        time.sleep(0.1)
        self.buzzer.value = 0

        try:
            # Generate filename
            photo_num = self.photos_taken + 1
            filename = PHOTO_DIR / f"PICAM_{photo_num:03d}.jpg"

            # Switch to high resolution mode
            print("[SHUTTER] Switching to high-res mode (4608x2592)...")
            self.camera.stop()
            time.sleep(0.1)

            highrez_config = self.camera.create_still_configuration(
                main={"size": (4608, 2592), "format": "RGB888"},
                lores=None,
                display=None,
                buffer_count=2,
                queue=False,
                transform=Transform(vflip=True, hflip=True)
            )
            self.camera.configure(highrez_config)
            self.camera.start()
            time.sleep(0.3)  # Allow camera to stabilize

            # Capture high resolution image
            self.camera.capture_file(str(filename))
            print(f"[SHUTTER] High-res photo saved: {filename}")

            # Switch back to preview mode
            print("[SHUTTER] Switching back to preview mode...")
            self.camera.stop()
            time.sleep(0.1)

            preview_config = self.camera.create_preview_configuration(
                main={"size": (PREVIEW_WIDTH, PREVIEW_HEIGHT), "format": "RGB888"}
            )
            self.camera.configure(preview_config)

            # Restore camera settings with fixed shutter speed
            self.camera.set_controls({
                "Contrast": 1.2,
                "Saturation": 1.1,
                "Sharpness": 1.0,
                "AeEnable": False,  # Keep manual exposure
                "ExposureTime": 20000,  # Fixed 1/50s
                "AnalogueGain": self.current_gain  # Restore current gain
            })

            # Restore focus lock state if it was locked
            if self.focus_locked:
                self.camera.set_controls({
                    "AfMode": 0
                })
            else:
                self.camera.set_controls({
                    "AfMode": 2
                })

            self.camera.start()
            time.sleep(0.3)  # Extra time to ensure preview is ready

            # Update counter
            self.photos_taken += 1
            self.photos_remaining = self.calculate_photos_remaining()
            print(f"[SHUTTER] Total photos: {self.photos_taken}, Remaining: {self.photos_remaining}")
            print("[SHUTTER] Ready to resume preview")

        except Exception as e:
            print(f"[SHUTTER] Error capturing photo: {e}")
            import traceback
            traceback.print_exc()

            # Error beep (long beep)
            self.buzzer.value = 0.5
            time.sleep(0.3)
            self.buzzer.value = 0

            # Try to restart preview mode on error
            try:
                self.camera.stop()
                time.sleep(0.1)
                preview_config = self.camera.create_preview_configuration(
                    main={"size": (PREVIEW_WIDTH, PREVIEW_HEIGHT), "format": "RGB888"}
                )
                self.camera.configure(preview_config)
                self.camera.start()
                time.sleep(0.3)
            except:
                pass

        finally:
            # Resume main loop
            self.capturing = False
        
    def run(self):
        """Main viewfinder loop"""
        print("\n" + "=" * 60)
        print("CAMERA VIEWFINDER RUNNING")
        print("=" * 60)
        print(f"Preview: {PREVIEW_WIDTH}x{PREVIEW_HEIGHT} centered")
        print(f"Target FPS: ~{PREVIEW_FPS}")
        print(f"\n📸 Photo Gallery: http://[pi-ip]:5000")
        print("   View your photos from any device on the network!")
        print("\nPress Ctrl+C to exit\n")
        
        try:
            frame_time = 1.0 / PREVIEW_FPS
            last_fps_print = time.time()
            last_storage_update = time.time()
            fps_counter = 0

            while True:
                start = time.time()

                # Skip frame capture if in gallery mode or taking a photo
                if self.gallery_mode:
                    # In gallery mode, just sleep and wait for joystick input
                    time.sleep(0.1)
                    continue

                # Skip frame capture if we're currently taking a photo
                if not self.capturing:
                    try:
                        # Capture camera frame (metadata included with the frame)
                        camera_array = self.camera.capture_array()

                        # Get metadata only every 5 frames to reduce overhead
                        if self.frame_count % 5 == 0:
                            metadata = self.camera.capture_metadata()
                            # Update camera info from metadata
                            self.current_iso = metadata.get("AnalogueGain", 0) * metadata.get("DigitalGain", 1.0) * 100
                            self.current_shutter_speed = metadata.get("ExposureTime", 0)
                            self.current_focus_distance = metadata.get("FocusFoM", 0)

                            # Manual exposure control - adjust gain to maintain brightness
                            if self.manual_exposure and not self.focus_locked:
                                # Calculate mean brightness of the image (0-1 scale)
                                mean_brightness = np.mean(camera_array) / 255.0

                                # Adjust gain based on brightness difference
                                brightness_error = self.target_brightness - mean_brightness

                                # Proportional control with smoothing
                                if abs(brightness_error) > 0.05:  # Only adjust if significant difference
                                    gain_adjustment = 1.0 + (brightness_error * 0.3)  # 30% adjustment rate
                                    self.current_gain = np.clip(
                                        self.current_gain * gain_adjustment,
                                        self.min_gain,
                                        self.max_gain
                                    )

                                    # Apply new gain
                                    self.camera.set_controls({
                                        "AnalogueGain": float(self.current_gain)
                                    })

                        # Add UI overlay (creates 284x76 image)
                        display_frame = self.create_viewfinder_frame(camera_array)

                        # Send to display via C library
                        self.display.show_image(display_frame)

                        # Frame counting
                        self.frame_count += 1
                        fps_counter += 1
                    except Exception as e:
                        # Silently skip frame errors during mode switching
                        pass
                else:
                    # If capturing, just sleep a bit
                    time.sleep(0.05)

                # Update storage info every 5 seconds
                if time.time() - last_storage_update >= 5.0:
                    self.photos_remaining = self.calculate_photos_remaining()
                    last_storage_update = time.time()

                # Print FPS every 2 seconds
                if time.time() - last_fps_print >= 2.0:
                    actual_fps = fps_counter / 2.0
                    print(f"\rFrames: {self.frame_count} | FPS: {actual_fps:.1f}  ",
                          end='', flush=True)
                    fps_counter = 0
                    last_fps_print = time.time()
                
                # Frame rate control
                elapsed = time.time() - start
                if elapsed < frame_time:
                    time.sleep(frame_time - elapsed)
        
        except KeyboardInterrupt:
            print("\n\nShutting down...")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        print("Cleaning up...")

        # Stop LED PWM thread
        if self.led_pwm:
            try:
                self.pwm_thread_stop.set()
                time.sleep(0.2)  # Give thread time to exit
                self.led_pwm.stop()
                GPIO.cleanup(self.led_pin)
                print("LED PWM stopped and cleaned up")
            except Exception as e:
                print(f"LED cleanup error: {e}")

        # Turn off buzzer
        try:
            self.buzzer.value = 0
        except:
            pass

        # Close GPIO
        try:
            self.focus_button.close()
            self.shutter_button.close()
            self.buzzer.close()
            # Close joystick buttons
            self.joy_left.close()
            self.joy_up.close()
            self.joy_switch.close()
            self.joy_down.close()
            self.joy_right.close()
        except:
            pass
        
        # Stop camera
        try:
            self.camera.stop()
            self.camera.close()
        except:
            pass

        # Clear screen and turn off backlight
        try:
            self.display.clear((0, 0, 0))
            self.display.refresh()
            self.display.cleanup()
        except:
            pass

        print("Done!")


if __name__ == "__main__":
    try:
        viewfinder = CameraViewfinder()
        viewfinder.run()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
