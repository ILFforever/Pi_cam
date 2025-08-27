#!/usr/bin/env python3
"""
Web-based camera interface
Access via browser: http://[pi-ip]:8000
original code takes jpg only (should work with new picamera2)
"""

from flask import Flask, render_template, jsonify, send_from_directory, request
from picamera2 import Picamera2
from libcamera import Transform
import time
import os
import threading
import queue
import psutil
from datetime import datetime

app = Flask(__name__)

# Global variables
picam2 = None
photos_folder = "photos"
normal_photos_folder = os.path.join(photos_folder, "normal")
highrez_photos_folder = os.path.join(photos_folder, "highrez")
camera_lock = threading.Lock()
dng_queue = queue.Queue(maxsize=10)
processing_active = True

dng_photos_folder = os.path.join(photos_folder, "dng")
processed_photos_folder = os.path.join(photos_folder, "processed")

for folder in [photos_folder, normal_photos_folder, highrez_photos_folder, dng_photos_folder, processed_photos_folder]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def get_photo_counts():
    """Get photo counts by checking folder contents"""
    try:
        normal_files = [f for f in os.listdir(normal_photos_folder) if f.endswith('.jpg')]
        highrez_files = [f for f in os.listdir(highrez_photos_folder) if f.endswith('.jpg')]
        dng_files = [f for f in os.listdir(dng_photos_folder) if f.endswith('.dng')]
        return len(normal_files), len(highrez_files), len(dng_files)
    except Exception as e:
        print(f"Error counting photos: {e}")
        return 0, 0, 0

def get_next_photo_number(folder_path, prefix):
    """Get the next photo number for a given folder and prefix"""
    try:
        files = [f for f in os.listdir(folder_path) if f.startswith(prefix) and f.endswith('.jpg')]
        if not files:
            return 1
        
        # Extract numbers from filenames and find the highest
        numbers = []
        for f in files:
            try:
                # Remove prefix and .jpg, convert to int
                num_str = f[len(prefix):-4]  # Remove prefix and .jpg extension
                numbers.append(int(num_str))
            except ValueError:
                continue
        
        return max(numbers) + 1 if numbers else 1
    except Exception as e:
        print(f"Error getting next photo number: {e}")
        return 1

def init_camera():
    global picam2
    try:
        picam2 = Picamera2()
        
        # Start with normal resolution
        config = picam2.create_still_configuration(
            main={"size": (2304, 1296), "format": "RGB888"},
            lores=None,
            display=None,
            buffer_count=2,
            queue=False,
            transform=Transform(vflip=True, hflip=True)
        )
        
        picam2.configure(config)
        
        # Enable autofocus and check if it's working
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
            center_window = (864, 486, 576, 324)
            picam2.set_controls({"AfWindows": [center_window]})
            
            print("✓ Autofocus enabled (continuous mode)")
            print(f"✓ AF window set to center 25%: {center_window}")
        else:
            print("⚠ Autofocus not available on this camera")
        
        picam2.start()
        time.sleep(1.0)  # Camera warm-up
        
        # Check AF status after startup
        metadata = picam2.capture_metadata()
        if 'LensPosition' in metadata:
            print(f"✓ Lens position: {metadata['LensPosition']:.2f}")
        if 'AfState' in metadata:
            af_states = {0: "Inactive", 1: "Passive Scan", 2: "Passive Focused", 3: "Active Scan", 4: "Focused", 5: "Failed"}
            af_state = metadata.get('AfState', 0)
            print(f"✓ AF State: {af_states.get(af_state, 'Unknown')} ({af_state})")
        
        # Print initial photo counts
        normal_count, highrez_count, dng_count = get_photo_counts()
        print(f"✓ Existing photos - Normal: {normal_count}, High-res: {highrez_count}, DNG: {dng_count}")
        
        print("Camera initialized successfully")
        return True
    except Exception as e:
        print(f"Camera initialization failed: {e}")
        return False

@app.route('/')
def index():
    normal_count, highrez_count, dng_count = get_photo_counts()
    return render_template('index.html', 
                          photo_count=normal_count, 
                          highrez_count=highrez_count,
                          dng_count=dng_count)

@app.route('/capture/<photo_type>', methods=['POST'])
def capture_photo(photo_type):
    global picam2
    
    with camera_lock:
        try:
            start_time = time.time()
            
            if photo_type == 'normal':
                # Ensure normal resolution
                picam2.stop()
                config = picam2.create_still_configuration(
                    main={"size": (2304, 1296), "format": "RGB888"},
                    lores=None,
                    display=None,
                    buffer_count=2,
                    queue=False,
                    transform=Transform(vflip=True , hflip=True)
                )
                picam2.configure(config)
                picam2.start()
                time.sleep(0.2)
                
                # Get next photo number and create filename
                photo_num = get_next_photo_number(normal_photos_folder, "photo")
                filename = f"photo{photo_num}.jpg"
                filepath = os.path.join(normal_photos_folder, filename)
                picam2.capture_file(filepath)
                
            elif photo_type == 'highrez':
                # Switch to high resolution
                picam2.stop()
                config = picam2.create_still_configuration(
                    main={"size": (4608, 2592), "format": "RGB888"},
                    lores=None,
                    display=None,
                    buffer_count=2,
                    queue=False,
                    transform=Transform(vflip=True , hflip=True)
                )
                picam2.configure(config)
                picam2.start()
                time.sleep(0.3)
                
                # Get next photo number and create filename
                photo_num = get_next_photo_number(highrez_photos_folder, "highrez")
                filename = f"highrez{photo_num}.jpg"
                filepath = os.path.join(highrez_photos_folder, filename)
                picam2.capture_file(filepath)
                
                # Switch back to normal
                picam2.stop()
                config = picam2.create_still_configuration(
                    main={"size": (2304, 1296), "format": "RGB888"},
                    lores=None,
                    display=None,
                    buffer_count=2,
                    queue=False,
                    transform=Transform(vflip=True , hflip=True)
                )
                picam2.configure(config)
                picam2.start()
                time.sleep(0.2)
            
            end_time = time.time()
            capture_time = round(end_time - start_time, 3)
            
            # Get updated counts
            normal_count, highrez_count, dng_count = get_photo_counts()
            
            return jsonify({
                'success': True,
                'filename': filename,
                'time': capture_time,
                'photo_count': normal_count,
                'highrez_count': highrez_count,
                'dng_count': dng_count
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            })
            
@app.route('/capture_dng', methods=['POST'])
def capture_dng():
    global picam2
    
    with camera_lock:
        try:
            start_time = time.time()
            
            # Switch to full resolution for DNG
            picam2.stop()
            config = picam2.create_still_configuration(
                raw={"size": (4608, 2592)},
                buffer_count=3,
                queue=False
            )
            picam2.configure(config)
            picam2.start()
            time.sleep(0.3)
            
            # Get next photo number and create filename
            photo_num = get_next_photo_number(dng_photos_folder, "dng")
            filename = f"dng{photo_num:03d}.dng"
            filepath = os.path.join(dng_photos_folder, filename)
            
            # Capture DNG with background processing
            picam2.capture_file(filepath, name="raw")
            
            # Switch back to normal resolution
            picam2.stop()
            config = picam2.create_still_configuration(
                main={"size": (2304, 1296), "format": "RGB888"},
                buffer_count=2,
                queue=False,
                transform=Transform(vflip=True, hflip=True)
            )
            picam2.configure(config)
            picam2.start()
            time.sleep(0.2)
            
            end_time = time.time()
            capture_time = round(end_time - start_time, 3)
            
            return jsonify({
                'success': True,
                'filename': filename,
                'time': capture_time,
                'photo_number': photo_num
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            })
            
@app.route('/gallery')
def gallery():
    try:
        # Get photos from both folders
        normal_photos = []
        highrez_photos = []
        
        # Get normal photos
        if os.path.exists(normal_photos_folder):
            normal_files = [f for f in os.listdir(normal_photos_folder) if f.endswith('.jpg')]
            for f in normal_files:
                normal_photos.append({
                    'filename': f,
                    'path': f'normal/{f}',
                    'type': 'normal',
                    'timestamp': os.path.getctime(os.path.join(normal_photos_folder, f))
                })
        
        # Get highrez photos
        if os.path.exists(highrez_photos_folder):
            highrez_files = [f for f in os.listdir(highrez_photos_folder) if f.endswith('.jpg')]
            for f in highrez_files:
                highrez_photos.append({
                    'filename': f,
                    'path': f'highrez/{f}',
                    'type': 'highrez',
                    'timestamp': os.path.getctime(os.path.join(highrez_photos_folder, f))
                })
        
        # Combine and sort by timestamp (newest first)
        all_photos = normal_photos + highrez_photos
        all_photos.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Return just the paths for backward compatibility, but include type info
        photos_list = [{'path': photo['path'], 'type': photo['type'], 'filename': photo['filename']} for photo in all_photos]
        
        return jsonify({'photos': photos_list})
    except Exception as e:
        return jsonify({'photos': [], 'error': str(e)})

@app.route('/photo/<path:filename>')
def serve_photo(filename):
    # Handle both old format (direct filename) and new format (folder/filename)
    if '/' in filename:
        # New format: folder/filename
        return send_from_directory(photos_folder, filename)
    else:
        # Old format: try to find in either folder for backward compatibility
        if os.path.exists(os.path.join(normal_photos_folder, filename)):
            return send_from_directory(normal_photos_folder, filename)
        elif os.path.exists(os.path.join(highrez_photos_folder, filename)):
            return send_from_directory(highrez_photos_folder, filename)
        else:
            # Fallback to old photos folder
            return send_from_directory(photos_folder, filename)

@app.route('/photo_counts')
def photo_counts():
    """API endpoint to get current photo counts"""
    normal_count, highrez_count, dng_count = get_photo_counts()
    return jsonify({
        'normal_count': normal_count,
        'highrez_count': highrez_count,
        'dng_count': dng_count
    })

@app.route('/af_status')
def af_status():
    global picam2
    try:
        with camera_lock:
            metadata = picam2.capture_metadata()
            
            # Get current AF info
            af_mode = metadata.get('AfMode', 0)
            af_state = metadata.get('AfState', 0)
            lens_position = metadata.get('LensPosition', 0.0)
            
            return jsonify({
                'af_mode': af_mode,
                'af_state': af_state,
                'lens_position': lens_position
            })
    except Exception as e:
        return jsonify({
            'af_mode': 0,
            'af_state': 0,
            'lens_position': 0.0,
            'error': str(e)
        })

@app.route('/set_af_mode', methods=['POST'])
def set_af_mode():
    global picam2
    try:
        data = request.get_json()
        af_mode = data.get('mode', 2)
        
        with camera_lock:
            if af_mode == 0:  # Manual
                picam2.set_controls({
                    "AfMode": af_mode,
                    "LensPosition": 3.0  # Default manual position
                })
            else:  # Auto or Continuous
                picam2.set_controls({"AfMode": af_mode})
            
            time.sleep(0.1)  # Brief delay for setting to take effect
        
        return jsonify({'success': True, 'mode': af_mode})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/camera_settings')
def camera_settings():
    global picam2
    try:
        with camera_lock:
            metadata = picam2.capture_metadata()
            
            return jsonify({
                'exposure_time': metadata.get('ExposureTime', 0),
                'analogue_gain': metadata.get('AnalogueGain', 1.0),
                'digital_gain': metadata.get('DigitalGain', 1.0),
                'colour_gains': metadata.get('ColourGains', [1.0, 1.0]),
                'lens_position': metadata.get('LensPosition', 0.0),
                'frame_duration': metadata.get('FrameDuration', 0),
                'brightness': metadata.get('Brightness', 0.0),
                'contrast': metadata.get('Contrast', 1.0),
                'saturation': metadata.get('Saturation', 1.0),
                'sharpness': metadata.get('Sharpness', 1.0),
                'awb_mode': metadata.get('AwbMode', 0),
                'ae_enable': metadata.get('AeEnable', True)
            })
    except Exception as e:
        return jsonify({
            'exposure_time': 0,
            'analogue_gain': 1.0,
            'digital_gain': 1.0,
            'colour_gains': [1.0, 1.0],
            'lens_position': 0.0,
            'frame_duration': 0,
            'brightness': 0.0,
            'contrast': 1.0,
            'saturation': 1.0,
            'sharpness': 1.0,
            'awb_mode': 0,
            'ae_enable': True,
            'error': str(e)
        })

@app.route('/set_camera_setting', methods=['POST'])
def set_camera_setting():
    global picam2
    try:
        data = request.get_json()
        control = data.get('control')
        value = data.get('value')
        
        with camera_lock:
            picam2.set_controls({control: value})
            time.sleep(0.1)
        
        return jsonify({'success': True, 'control': control, 'value': value})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/reset_camera_settings', methods=['POST'])
def reset_camera_settings():
    global picam2
    try:
        with camera_lock:
            # Reset to default settings
            picam2.set_controls({
                "AeEnable": True,
                "AwbMode": 0,  # Auto white balance
                "Brightness": 0.0,
                "Contrast": 1.0,
                "Saturation": 1.0,
                "Sharpness": 1.0,
                "AnalogueGain": 1.0,
                "ExposureTime": 8000
            })
            time.sleep(0.2)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/set_lens_position', methods=['POST'])
def set_lens_position():
    global picam2
    try:
        data = request.get_json()
        position = data.get('position', 3.0)
        
        with camera_lock:
            picam2.set_controls({
                "AfMode": 0,  # Must be manual for lens position
                "LensPosition": position
            })
            time.sleep(0.1)
        
        return jsonify({'success': True, 'position': position})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/set_af_window', methods=['POST'])
def set_af_window():
    global picam2
    try:
        data = request.get_json()
        window_type = data.get('window', 'center')
        
        # Calculate window coordinates based on 2304x1296 resolution
        windows = {
            'full': None,  # No window = full frame
            'center': (864, 486, 576, 324),      # Center 25%
            'center-large': (576, 324, 1152, 648),  # Center 50%
            'top': (864, 162, 576, 324),         # Top 25%
            'bottom': (864, 810, 576, 324),      # Bottom 25%
        }
        
        window_coords = windows.get(window_type)
        
        with camera_lock:
            if window_coords is None:
                # Remove AF window (full frame)
                picam2.set_controls({"AfMode": 0})  # Temporarily disable
                time.sleep(0.1)
                picam2.set_controls({"AfMode": 2})  # Re-enable continuous
            else:
                picam2.set_controls({"AfWindows": [window_coords]})
            time.sleep(0.1)
        
        return jsonify({'success': True, 'window': window_type, 'coords': window_coords})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/trigger_af', methods=['POST'])
def trigger_af():
    global picam2
    try:
        with camera_lock:
            # Trigger autofocus cycle
            picam2.set_controls({"AfTrigger": 0})  # Start AF
            time.sleep(0.1)
            picam2.set_controls({"AfTrigger": 1})  # Cancel AF (completes cycle)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/save_all_settings', methods=['POST'])
def save_all_settings():
    global picam2
    try:
        data = request.get_json()
        
        with camera_lock:
            # Apply all settings at once
            picam2.set_controls(data)
            time.sleep(0.2)
        
        return jsonify({'success': True, 'settings_applied': len(data)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
@app.route('/clear_all_photos', methods=['POST'])
def clear_all_photos():
    """Delete all photos from all folders"""
    try:
        deleted_count = 0
        
        # Clear normal photos
        if os.path.exists(normal_photos_folder):
            for filename in os.listdir(normal_photos_folder):
                if filename.endswith('.jpg'):
                    file_path = os.path.join(normal_photos_folder, filename)
                    os.remove(file_path)
                    deleted_count += 1
        
        # Clear high-res photos
        if os.path.exists(highrez_photos_folder):
            for filename in os.listdir(highrez_photos_folder):
                if filename.endswith('.jpg'):
                    file_path = os.path.join(highrez_photos_folder, filename)
                    os.remove(file_path)
                    deleted_count += 1
        
        # Clear DNG photos
        if os.path.exists(dng_photos_folder):
            for filename in os.listdir(dng_photos_folder):
                if filename.endswith('.dng'):
                    file_path = os.path.join(dng_photos_folder, filename)
                    os.remove(file_path)
                    deleted_count += 1
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'normal_count': 0,
            'highrez_count': 0,
            'dng_count': 0
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })
        
if __name__ == '__main__':
    print("Initializing camera...")
    if init_camera():
        print("Starting web server...")
        print("Access camera at: http://[your-pi-ip]:8000")
        print("Press Ctrl+C to stop")
        
        try:
            app.run(host='0.0.0.0', port=8000, debug=False)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            if picam2:
                picam2.stop()
                print("Camera stopped")