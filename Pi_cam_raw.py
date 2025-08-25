#!/usr/bin/env python3
"""
Fast raw capture for Pi Zero 2: Capture raw arrays instantly, process DNGs in background
Can capture 1 photo every 1-2 seconds while processing happens separately
"""

from flask import Flask, render_template_string, jsonify
from picamera2 import Picamera2
from libcamera import Transform
import time
import os
import threading
import queue
import numpy as np
from datetime import datetime

app = Flask(__name__)

# Setup folders
os.makedirs("photos/jpg", exist_ok=True)
os.makedirs("photos/raw", exist_ok=True)
os.makedirs("photos/dng", exist_ok=True)
os.makedirs("photos/processed", exist_ok=True)

# Global variables
picam2 = None
camera_lock = threading.Lock()

# Background processing queue
raw_queue = queue.Queue()
processing_active = True

def get_next_photo_number():
    """Get next photo number by checking existing files"""
    jpg_files = [f for f in os.listdir("photos/jpg") if f.startswith("photo") and f.endswith(".jpg")]
    if not jpg_files:
        return 1
    
    numbers = []
    for f in jpg_files:
        try:
            num = int(f[5:8])  # Extract number from "photoXXX.jpg"
            numbers.append(num)
        except:
            continue
    
    return max(numbers) + 1 if numbers else 1

def get_photo_count():
    """Get current photo count"""
    jpg_files = [f for f in os.listdir("photos/jpg") if f.endswith(".jpg")]
    return len(jpg_files)

def background_dng_processor():
    """Background thread that converts raw arrays to DNG files"""
    print("🔄 Background DNG processor started")
    
    while processing_active or not raw_queue.empty():
        try:
            # Get item from queue with timeout
            item = raw_queue.get(timeout=1.0)
            
            if item is None:  # Shutdown signal
                break
                
            photo_num, raw_array, metadata, capture_time = item
            
            print(f"🔄 Processing DNG for photo {photo_num:03d}...")
            
            # Start timing the processing
            process_start = time.time()
            
            # Save raw array as numpy file (fast backup)
            npy_start = time.time()
            npy_file = f"photos/raw/photo{photo_num:03d}.npy"
            np.save(npy_file, raw_array)
            npy_time = time.time() - npy_start
            
            # Convert to actual DNG file using picamera2's built-in method
            dng_start = time.time()
            dng_file = f"photos/dng/photo{photo_num:03d}.dng"
            
            try:
                # Method 1: Try using pidng if available
                try:
                    from pidng.core import PICAM2DNG
                    from pidng.camdefs import Picamera2Camera
                    
                    # Get camera configuration for pidng
                    raw_config = {
                        'format': 'SRGGB12',  # Default Bayer format
                        'size': raw_array.shape[::-1],  # Width, height
                        'stride': raw_array.shape[1] * 2,  # Bytes per row
                        'framesize': raw_array.size * 2   # Total bytes
                    }
                    
                    # Create camera definition
                    camera = Picamera2Camera(raw_config, metadata)
                    
                    # Create DNG
                    dng_converter = PICAM2DNG(camera)
                    dng_converter.convert(raw_array, dng_file)
                    dng_method = "pidng"
                    
                except (ImportError, AttributeError) as pidng_error:
                    print(f"📝 pidng error: {pidng_error}")
                    raise pidng_error
                    
            except Exception as dng_error:
                # Method 2: Fallback to compressed numpy with metadata
                print(f"⚠️ DNG creation failed: {dng_error}")
                print("📝 Using compressed numpy fallback")
                
                fallback_file = dng_file.replace('.dng', '.npz')
                np.savez_compressed(fallback_file, 
                                  raw=raw_array, 
                                  metadata=metadata,
                                  shape=raw_array.shape,
                                  dtype=str(raw_array.dtype))
                dng_method = "npz_fallback"
                dng_file = fallback_file
                
            dng_time = time.time() - dng_start
            
            # Calculate file sizes
            npy_size = os.path.getsize(npy_file) / 1024 / 1024  # MB
            
            if os.path.exists(dng_file):
                dng_size = os.path.getsize(dng_file) / 1024 / 1024  # MB
            elif os.path.exists(dng_file.replace('.dng', '.npz')):
                dng_size = os.path.getsize(dng_file.replace('.dng', '.npz')) / 1024 / 1024
                dng_file = dng_file.replace('.dng', '.npz')
            else:
                dng_size = 0
            
            total_process_time = time.time() - process_start
            
            # Detailed timing report
            print(f"✅ Photo {photo_num:03d} processing complete:")
            print(f"   📁 NPY save: {npy_time:.3f}s ({npy_size:.1f}MB)")
            print(f"   🎞️ DNG save: {dng_time:.3f}s ({dng_size:.1f}MB) [{dng_method}]")
            print(f"   ⏱️ Total time: {total_process_time:.3f}s")
            print(f"   📊 Queue remaining: {raw_queue.qsize()}")
            print()
            
            # Optional: Add your custom Fuji-style processing here
            if True:  # Change to enable custom processing
                custom_start = time.time()
                
                # This is where you'd add your film simulation pipeline:
                # 1. Debayer the raw array
                # 2. Apply color grading (Velvia, Classic Chrome, etc.)
                # 3. Apply tone curves
                # 4. Save as PNG
                
                # Example placeholder:
                processed_file = f"photos/processed/photo{photo_num:03d}_fuji.png"
                os.makedirs("photos/processed", exist_ok=True)
                
                # Your processing pipeline would go here
                # For now, just create a placeholder
                with open(processed_file, 'w') as f:
                    f.write(f"Processed photo {photo_num:03d}")
                
                custom_time = time.time() - custom_start
                print(f"   🎨 Custom processing: {custom_time:.3f}s")
            
            raw_queue.task_done()
            
        except queue.Empty:
            continue
        except Exception as e:
            print(f"❌ DNG processing error: {e}")
            raw_queue.task_done()  # Don't forget to mark as done even on error

def simple_dng_capture():
    """Ultra-simple DNG capture - exactly what the forums recommend"""
    photo_num = get_next_photo_number()
    
    # Direct DNG capture (from therealdavidp's recommendation)
    jpg_file = f"photos/jpg/photo{photo_num:03d}.jpg"
    dng_file = f"photos/dng/photo{photo_num:03d}.dng"
    
    request = picam2.capture_request()
    try:
        request.save("main", jpg_file)      # Processed preview
        request.save_dng(dng_file)          # Raw for your processing
    finally:
        request.release()
    
    return {'filename': f"photo{photo_num:03d}"}

def fast_capture_photo():
    """Ultra-fast raw capture - just grab the data and queue processing"""
    global picam2
    
    with camera_lock:
        try:
            photo_num = get_next_photo_number()
            timestamp = time.strftime("%H:%M:%S")
            
            print(f"📸 [{timestamp}] Fast capturing photo {photo_num:03d}...")
            
            start_time = time.time()
            
            # FAST CAPTURE: Get raw array directly (fastest method)
            request = picam2.capture_request()
            
            try:
                # Save JPG immediately (fast)
                jpg_file = f"photos/jpg/photo{photo_num:03d}.jpg"
                request.save("main", jpg_file)
                
                # Get raw array (very fast - just memory copy)
                raw_array = request.make_array("raw")
                metadata = request.get_metadata()
                
                # Queue raw data for background DNG processing
                raw_queue.put((photo_num, raw_array.copy(), metadata, time.time()))
                
            finally:
                request.release()
            
            capture_time = time.time() - start_time
            
            # Get JPG file size
            jpg_size = os.path.getsize(jpg_file) / 1024 / 1024  # MB
            
            print(f"⚡ Captured photo{photo_num:03d} in {capture_time:.3f}s (DNG queued for processing)")
            
            return {
                'success': True,
                'photo_number': photo_num,
                'jpg_size': f"{jpg_size:.1f}MB",
                'capture_time': f"{capture_time:.3f}s",
                'filename': f"photo{photo_num:03d}",
                'queue_size': raw_queue.qsize()
            }
            
        except Exception as e:
            print(f"❌ Capture error: {e}")
            return {'success': False, 'error': str(e)}

def init_camera():
    """Initialize the Pi Camera for fast raw capture"""
    global picam2
    try:
        print("🎥 Initializing Pi Camera for fast capture...")
        picam2 = Picamera2()
        
        # Optimized configuration for speed
        # Use smaller resolution for Pi Zero 2 speed
        config = picam2.create_still_configuration(
            main={"size": (2304, 1296), "format": "RGB888"},  # Smaller for speed
            raw={"size": picam2.sensor_resolution},            # Full raw resolution
            transform=Transform(vflip=True),
            buffer_count=3  # More buffers for speed
        )
        
        picam2.configure(config)
        
        # Optimized camera settings for speed
        picam2.set_controls({
            "AfMode": 2,        # Continuous autofocus (fastest)
            "AeEnable": True,   # Auto exposure
            "AwbEnable": True,  # Auto white balance
            "FrameRate": 30,    # High frame rate for responsive capture
        })
        
        picam2.start()
        time.sleep(1)  # Quick warm-up
        
        print(f"✅ Camera ready for fast capture!")
        print(f"   Main: {config['main']['size']}, Raw: {config['raw']['size']}")
        print(f"   Target: 1 photo every 1-2 seconds")
        
        return True
        
    except Exception as e:
        print(f"❌ Camera initialization failed: {e}")
        return False

# Simple HTML interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Fast Pi Camera Raw Capture</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            background: #111;
            color: white;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            padding: 30px;
            background: #222;
            border-radius: 10px;
        }
        h1 { color: #fff; margin-bottom: 30px; }
        .capture-btn {
            background: #e60012;
            color: white;
            border: none;
            padding: 20px 40px;
            font-size: 24px;
            font-weight: bold;
            border-radius: 10px;
            cursor: pointer;
            margin: 20px;
            min-width: 250px;
        }
        .capture-btn:hover { background: #cc0010; }
        .capture-btn:disabled {
            background: #666;
            cursor: not-allowed;
        }
        .stats {
            background: #333;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            text-align: left;
        }
        .status {
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            font-weight: bold;
        }
        .success { background: #2d5f2f; color: #4caf50; }
        .error { background: #5f2d2d; color: #f44336; }
        .capturing { background: #2d4f5f; color: #2196f3; }
        .hidden { display: none; }
        .queue-info {
            font-size: 14px;
            color: #ccc;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ Fast Pi Camera Raw Capture</h1>
        
        <div class="stats">
            <div>📊 <strong>Stats:</strong></div>
            <div>Photos captured: <span id="photo-count">{{ photo_count }}</span></div>
            <div>Processing queue: <span id="queue-size">0</span></div>
            <div>Last capture time: <span id="last-time">-</span></div>
        </div>
        
        <button id="capture-btn" class="capture-btn" onclick="fastCapture()">
            ⚡ FAST CAPTURE
        </button>
        
        <div id="status" class="status hidden"></div>
        
        <div class="stats">
            <strong>🚀 Speed Optimized:</strong><br>
            • Ultra-fast raw capture (~0.1-0.3s)<br>
            • Background DNG processing<br>
            • Can capture every 1-2 seconds<br>
            • Raw data queued for processing<br>
        </div>
    </div>

    <script>
        let lastCaptureTime = 0;
        
        function fastCapture() {
            const now = Date.now();
            const timeSinceLastCapture = now - lastCaptureTime;
            
            // Enforce minimum 1 second between captures
            if (timeSinceLastCapture < 1000) {
                const waitTime = Math.ceil((1000 - timeSinceLastCapture) / 1000);
                showStatus(`⏳ Wait ${waitTime}s before next capture`, 'error');
                return;
            }
            
            const btn = document.getElementById('capture-btn');
            const status = document.getElementById('status');
            
            btn.disabled = true;
            btn.textContent = '⚡ CAPTURING...';
            status.className = 'status capturing';
            status.textContent = '⚡ Fast capturing raw data...';
            status.classList.remove('hidden');
            
            const captureStart = Date.now();
            
            fetch('/fast_capture', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    const captureTime = Date.now() - captureStart;
                    lastCaptureTime = captureStart;
                    
                    if (data.success) {
                        status.className = 'status success';
                        status.innerHTML = `⚡ ${data.filename} captured in ${data.capture_time}! <br>
                                           <span class="queue-info">Queue: ${data.queue_size} items</span>`;
                        
                        // Update stats
                        document.getElementById('photo-count').textContent = data.photo_number;
                        document.getElementById('queue-size').textContent = data.queue_size;
                        document.getElementById('last-time').textContent = data.capture_time;
                        
                    } else {
                        status.className = 'status error';
                        status.textContent = `❌ Error: ${data.error}`;
                    }
                })
                .catch(error => {
                    status.className = 'status error';
                    status.textContent = `❌ Network error: ${error}`;
                })
                .finally(() => {
                    btn.disabled = false;
                    btn.textContent = '⚡ FAST CAPTURE';
                    
                    setTimeout(() => {
                        if (status.classList.contains('success')) {
                            status.classList.add('hidden');
                        }
                    }, 3000);
                });
        }
        
        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.className = `status ${type}`;
            status.textContent = message;
            status.classList.remove('hidden');
            
            setTimeout(() => status.classList.add('hidden'), 2000);
        }
        
        // Update queue size every 2 seconds
        setInterval(() => {
            fetch('/queue_status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('queue-size').textContent = data.queue_size;
                })
                .catch(() => {});
        }, 2000);
        
        // Keyboard shortcut - spacebar
        document.addEventListener('keydown', function(event) {
            if (event.code === 'Space') {
                event.preventDefault();
                fastCapture();
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    photo_count = get_photo_count()
    return render_template_string(HTML_TEMPLATE, photo_count=photo_count)

@app.route('/fast_capture', methods=['POST'])
def fast_capture():
    result = simple_dng_capture()
    return jsonify(result)

@app.route('/queue_status')
def queue_status():
    return jsonify({
        'queue_size': raw_queue.qsize(),
        'photo_count': get_photo_count()
    })

if __name__ == '__main__':
    print("🚀 Starting Fast Pi Camera Raw Capture Server...")
    
    if init_camera():
        # Start background processing thread
        processing_thread = threading.Thread(target=background_dng_processor, daemon=True)
        processing_thread.start()
        
        print(f"🌐 Web interface: http://0.0.0.0:8000")
        print("   ⚡ Optimized for Pi Zero 2 - 1 photo every 1-2 seconds")
        print("   Press Ctrl+C to stop\n")
        
        try:
            app.run(host='0.0.0.0', port=8000, debug=False)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
        finally:
            processing_active = False
            raw_queue.put(None)  # Signal background thread to stop
            if picam2:
                picam2.stop()
                print("👋 Camera stopped. Goodbye!")
    else:
        print("❌ Failed to initialize camera. Exiting.")