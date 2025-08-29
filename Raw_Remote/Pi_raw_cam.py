#!/usr/bin/env python3
"""
Simple DNG Camera Interface - Flask Backend
Single photo capture using background DNG processing
"""

from flask import Flask, render_template_string, jsonify, request,send_file
import os
import time
import threading
import psutil
import glob
from pathlib import Path
import socket
from libcamera import controls
import RPi.GPIO as GPIO

# Import your picamera2 library
from picamera2 import Picamera2
from libcamera import Transform
dng_folder = "dng"

app = Flask(__name__)

# Global camera instance
camera_state = {
    'picam2': None,
    'initialized': False,
    'capturing': False,
    'photo_counter': 0
}

# --- LED Pulse Control ---
led_pin = 29  # Change this to your GPIO pin number
pwm_thread_stop = threading.Event()
pwm_running = False

# --- Utility Functions ---
def pwm_pulse_led():
    """Pulses the LED using PWM in a separate thread."""
    global pwm_running
    
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(led_pin, GPIO.OUT)
        pwm = GPIO.PWM(led_pin, 100) # 100 Hz frequency
        pwm.start(0)
        
        pwm_running = True
        
        while not pwm_thread_stop.is_set():
            # Slowly increase brightness
            for dc in range(0, 101, 5):
                pwm.ChangeDutyCycle(dc)
                time.sleep(0.05)
            # Slowly decrease brightness
            for dc in range(100, -1, -5):
                pwm.ChangeDutyCycle(dc)
                time.sleep(0.05)
                
    except Exception as e:
        print(f"LED PWM thread error: {e}")
        
    finally:
        # Cleanup GPIO when thread stops
        pwm.stop()
        GPIO.cleanup()
        pwm_running = False
        print("LED PWM thread stopped and GPIO cleaned up.")


def get_ip_address():
    """Attempts to get the local IP address of the Raspberry Pi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception:
        return "localhost"

def get_memory_info():
    """Get current memory usage in MB"""
    try:
        mem = psutil.virtual_memory()
        return {
            'available_mb': mem.available / 1024 / 1024,
            'total_mb': mem.total / 1024 / 1024,
            'used_mb': mem.used / 1024 / 1024,
            'percent': mem.percent
        }
    except Exception as e:
        return {'available_mb': 0, 'total_mb': 4096, 'used_mb': 0, 'percent': 0}

def get_dng_files():
    """Get list of DNG files with sizes"""
    files = []
    dng_folder = "dng"
    
    # Update the glob pattern to look inside the 'dng' folder
    try:
        for dng_file_path in glob.glob(os.path.join(dng_folder, "photo*.dng")):
            stat = os.stat(dng_file_path)
            # Use os.path.basename() to get just the filename
            dng_file_name = os.path.basename(dng_file_path)
            files.append({
                'name': dng_file_name,
                'size_mb': stat.st_size / 1024 / 1024,
                'modified': stat.st_mtime
            })
        files.sort(key=lambda x: x['modified'], reverse=True)
    except Exception as e:
        print(f"Error getting DNG files: {e}")
        return []
    return files

def create_dng_folder():
    """Create DNG folder if it doesn't exist"""
    if not os.path.exists(dng_folder):
        os.makedirs(dng_folder)
        
def initialize_camera():
    """Initialize the camera for single shot DNG capture"""
    global camera_state
    global pwm_running

    if camera_state['initialized']:
        return True
    
    try:
        print("🎯 Initializing camera for DNG capture...")
        
        picam2 = Picamera2()
        
        # Configure for DNG capture - single shot optimized
        config = picam2.create_still_configuration(
            raw={"size": (4608, 2592)},
            lores=None,
            display=None,
            buffer_count=3,
            queue=False,
            transform=Transform(vflip=True , hflip=True)
        )
        
        picam2.configure(config)
        
        # --- Autofocus Logic Added Here ---
        print("Checking autofocus capabilities...")
        controls = picam2.camera_controls
        if 'AfMode' in controls:
            print("✓ Autofocus is available")
            picam2.set_controls({
                "AfMode": 2,  # Continuous AF
                "AfSpeed": 1  # Fast AF speed
            })
            
            # Set AF window to center 25% of frame
            # For 2304x1296: center is 1152,648
            # 25% window = 576x324 pixels
            # Window coords: (864, 486, 576, 324)
            center_window = (979, 551, 345, 194)
            picam2.set_controls({"AfWindows": [center_window]})
            
            print("✓ Autofocus enabled (continuous mode)")
            print(f"✓ AF window set to center 25%: {center_window}")
        else:
            print("⚠ Autofocus not available on this camera")
        
        picam2.start()
        
        # Let camera settle
        time.sleep(2)
        
        camera_state['picam2'] = picam2
        camera_state['initialized'] = True
        camera_state['photo_counter'] = len(get_dng_files()) + 1
        
        print("✅ Camera initialized successfully")
        # Start the LED pulsing thread
        if not pwm_running:
            pwm_thread = threading.Thread(target=pwm_pulse_led)
            pwm_thread.daemon = True # Set as a daemon to exit with main program
            pwm_thread.start()
            
        return True
        
    except Exception as e:
        print(f"❌ Camera initialization failed: {e}")
        return False
    
def _capture_thread(picam2_instance, filename, result_container):
    """Internal thread function to perform the capture with result tracking."""
    try:
        result_container['started'] = True
        result_container['start_time'] = time.time()
        picam2_instance.capture_file(filename, name="raw")
        result_container['completed'] = True
        result_container['end_time'] = time.time()
    except Exception as e:
        result_container['error'] = e
        result_container['completed'] = False

def capture_single_dng():
    """Capture a single DNG photo with improved timeout handling."""
    global camera_state
    
    if not camera_state['initialized']:
        return {'success': False, 'error': 'Camera is not initialized'}
    
    if camera_state['capturing']:
        return {'success': False, 'error': 'Already capturing'}
    
    camera_state['capturing'] = True
    
    try:
        picam2 = camera_state['picam2']
        photo_num = camera_state['photo_counter']
        
        filename = os.path.join(dng_folder, f"photo{photo_num:03d}.dng")
        
        print(f"📸 Attempting to capture {filename}...")
        
        mem_before = get_memory_info()
        start_time = time.time()
        
        # Create result container for thread communication
        result_container = {
            'started': False,
            'completed': False,
            'error': None,
            'start_time': None,
            'end_time': None
        }
        
        # Start the capture in a separate thread
        capture_thread = threading.Thread(
            target=_capture_thread, 
            args=(picam2, filename, result_container)
        )
        capture_thread.daemon = True  # Dies with main thread
        capture_thread.start()
        
        # Wait for capture to actually start (up to 2 seconds)
        start_timeout = 2.0
        start_check_time = time.time()
        while not result_container['started'] and (time.time() - start_check_time) < start_timeout:
            time.sleep(0.1)
        
        if not result_container['started']:
            print("❌ Capture failed to start within timeout")
            return {'success': False, 'error': 'Capture failed to start - camera may be frozen'}
        
        # Wait for capture to complete (up to 10 seconds total)
        capture_timeout = 10.0
        capture_thread.join(timeout=capture_timeout)
        
        if capture_thread.is_alive() or not result_container['completed']:
            print("❌ Capture timed out or failed to complete")
            # Force camera restart
            try:
                camera_state['picam2'].stop()
                camera_state['picam2'].close()
                camera_state['picam2'] = None
                camera_state['initialized'] = False
                print("🔄 Camera forcibly closed due to timeout")
            except Exception as cleanup_error:
                print(f"Cleanup error: {cleanup_error}")
            
            return {
                'success': False, 
                'error': 'Capture timed out. Camera has been reset.',
                'restart_required': True
            }
        
        # Check for capture errors
        if result_container['error']:
            raise result_container['error']
            
        capture_time = time.time() - start_time
        mem_after = get_memory_info()
        
        file_size_mb = 0
        if os.path.exists(filename):
            file_size_mb = os.path.getsize(filename) / 1024 / 1024
        else:
            return {'success': False, 'error': 'Capture completed but file not found'}
        
        camera_state['photo_counter'] += 1
        
        result = {
            'success': True,
            'filename': os.path.basename(filename),  # Just filename, not full path
            'photo_number': photo_num,
            'capture_time': f"{capture_time:.3f}s",
            'size_mb': file_size_mb,
            'memory_info': mem_after,
            'memory_freed': mem_after['available_mb'] - mem_before['available_mb']
        }
        
        print(f"✅ Captured {filename} in {capture_time:.3f}s ({file_size_mb:.1f}MB)")
        return result
        
    except Exception as e:
        print(f"❌ Capture failed: {e}")
        return {'success': False, 'error': str(e)}
        
    finally:
        camera_state['capturing'] = False   
           
def emergency_memory_cleanup():
    """Emergency memory cleanup function"""
    global camera_state
    
    try:
        mem_before = get_memory_info()['available_mb']
        
        # Stop and close camera
        if camera_state['picam2']:
            try:
                camera_state['picam2'].stop()
                camera_state['picam2'].close()
                camera_state['picam2'] = None
                camera_state['initialized'] = False
                print("🔄 Camera closed for cleanup")
            except Exception as e:
                print(f"Camera cleanup error: {e}")
        
        # Force garbage collection
        import gc
        for _ in range(5):
            gc.collect()
        
        time.sleep(1.0)
        
        mem_after = get_memory_info()['available_mb']
        freed = mem_after - mem_before
        
        print(f"🧹 Emergency cleanup freed {freed:.1f}MB")
        return {'success': True, 'memory_freed': freed}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Flask Routes
@app.route('/')
def index():
    """Serve the HTML interface"""
    with open('simple_dng_trigger.html', 'r') as f:
        html_content = f.read()
    return html_content

@app.route('/test_status')
def test_status():
    """Get current camera status"""
    memory = get_memory_info()
    files = get_dng_files()
    
    return jsonify({
        'queue_size': 0,
        'dng_count': len(files),
        'memory_mb': memory['available_mb'],
        'camera_status': 'Capturing' if camera_state['capturing'] else 
                         ('Ready' if camera_state['initialized'] else 'Initializing'),
        'initialized': camera_state['initialized']
    })

@app.route('/test_files')
def test_files():
    """Get list of captured DNG photos"""
    files = get_dng_files()
    return jsonify({'files': files})

@app.route('/capture_single_dng', methods=['POST'])
def capture_single_dng_route():
    """Capture a single DNG photo with auto-restart on timeout"""
    if camera_state['capturing']:
        return jsonify({'success': False, 'error': 'Already capturing a photo'})
    
    result = capture_single_dng()
    
    # Auto-restart camera if needed
    if not result['success'] and result.get('restart_required'):
        print("🔄 Attempting to reinitialize camera...")
        time.sleep(2)
        if initialize_camera():
            print("✅ Camera reinitialized successfully")
            result['camera_restarted'] = True
        else:
            print("❌ Camera reinitialize failed")
            result['camera_restart_failed'] = True
    
    return jsonify(result)

@app.route('/download/<filename>')
def download_file(filename):
    """Download DNG file"""
    try:
        dng_path = os.path.join("dng", filename)
        if os.path.exists(dng_path) and filename.endswith('.dng'):
            return send_file(dng_path, as_attachment=True, download_name=filename)
        else:
            return "File not found", 404
    except Exception as e:
        return f"Error downloading file: {e}", 500

@app.route('/emergency_cleanup', methods=['POST'])
def emergency_cleanup_route():
    """Emergency memory cleanup and camera restart"""
    result = emergency_memory_cleanup()
    initialize_camera()
    return jsonify(result)

if __name__ == '__main__':
    print("📸 Simple DNG Camera Interface Starting...")
    print("🎯 Single photo capture with background DNG processing")
    print(f"🌐 Open http://{get_ip_address()}:8080 to access the camera")
    create_dng_folder()
    # Initialize camera on startup
    if not initialize_camera():
        print("Fatal Error: Could not initialize camera. Exiting.")
        exit(1)
    
    try:
        app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\nServer shutting down...")
    finally:
        # Stop the PWM thread and perform cleanup
        pwm_thread_stop.set()
        if camera_state['picam2']:
            camera_state['picam2'].stop()
            camera_state['picam2'].close()
        GPIO.cleanup()