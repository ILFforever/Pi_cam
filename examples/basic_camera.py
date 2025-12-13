#!/usr/bin/env python3
"""
Capture raw images directly works but with some delays
is this working?
"""

from flask import Flask, render_template_string, jsonify
from picamera2 import Picamera2
from libcamera import Transform
import time
import os
import threading
import queue
import numpy as np
import psutil
from datetime import datetime

app = Flask(__name__)

os.makedirs("photos/jpg", exist_ok=True)
os.makedirs("photos/raw", exist_ok=True)
os.makedirs("photos/dng", exist_ok=True)
os.makedirs("photos/processed", exist_ok=True)

# Global variables
picam2 = None
camera_lock = threading.Lock()

# Background processing queue
raw_queue = queue.Queue(maxsize=10)  # Limit queue size for Pi Zero 2
processing_active = True

def get_next_photo_number():
    """Get next photo number by checking existing files"""
    dng_files = [f for f in os.listdir("photos/dng") if f.startswith("photo") and f.endswith(".dng")]
    if not dng_files:
        return 1
    
    numbers = []
    for f in dng_files:
        try:
            num = int(f[5:8])  # Extract number from "photoXXX.jpg"
            numbers.append(num)
        except:
            continue
    
    return max(numbers) + 1 if numbers else 1

def get_photo_count():
    """Get current photo count"""
    dng_files = [f for f in os.listdir("photos/dng") if f.endswith(".dng")]
    return len(dng_files)

def ultra_fast_dng_capture():
    print("⚡ Ultra-fast DNG capture using raw stream")

    photo_num = get_next_photo_number()
    dng_file = f"photos/dng/photo{photo_num:03d}.dng"
    os.makedirs(os.path.dirname(dng_file), exist_ok=True)

    print(f"[DEBUG] Next photo number: {photo_num}")
    print(f"[DEBUG] Target DNG file: {dng_file}")

    start_time = time.time()
    
    try:
        r = picam2.capture_request()
        if r is None:
            print("[ERROR] capture_request() returned None")
            return {'success': False, 'error': "No capture request"}
        
        print("[DEBUG] Capture request acquired")

        # Save to fast tmpfs first
        tmp = f"/dev/shm/photo{photo_num:03d}.dng"
        r.save_dng(tmp)
        r.release()
        print(f"[DEBUG] Temp DNG saved to {tmp}")

        # Write out in a background thread
        with open(tmp, "rb") as f:
            data = f.read()

        def writer_thread_func(data, dest):
            with open(dest, "wb") as out:
                out.write(data)
            print(f"[DEBUG] File flushed to {dest}")

        th = threading.Thread(target=writer_thread_func, args=(data, dng_file))
        th.daemon = True
        th.start()

    except Exception as e:
        print(f"[ERROR] Exception during capture: {e}")
        return {'success': False, 'error': str(e)}
    
    capture_time = time.time() - start_time
    
    return {
        'success': True,
        'photo_number': photo_num,
        'filename': f"photo{photo_num:03d}",
        'filepath': dng_file,
        'capture_time': f"{capture_time:.3f}s"
    }
    
def init_camera():
    """Initialize the Pi Camera for fast raw capture"""
    global picam2, raw_config
    try:
        picam2 = Picamera2()
        
        # Check sensor resolution
        sensor_res = picam2.sensor_resolution
        print(f"Sensor resolution: {sensor_res}")
        
        # CONFIG HERE
        capture_config = picam2.create_still_configuration( raw={"size": (3760, 2120)}, display=None)
        
        picam2.configure(capture_config)
        picam2.start()
        
        return True
    except Exception as e:
        print(f"Raw camera init failed: {e}")
        return False

@app.route('/')
def index():
    photo_count = get_photo_count()
    return render_template_string(HTML_TEMPLATE, photo_count=photo_count)

@app.route('/fast_capture', methods=['POST'])
def fast_capture():
    result = ultra_fast_dng_capture()
    return jsonify(result)

@app.route('/queue_status')
def queue_status():
    return jsonify({
        'queue_size': raw_queue.qsize(),
        'photo_count': get_photo_count()
    })

@app.route('/processing_status')
def processing_status():
    """Check how many background DNG processes are running"""
    # Fix thread counting - safely check for thread name and target
    active_threads = 0
    for t in threading.enumerate():
        thread_name = t.name.lower() if t.name else ""
        if 'background_dng_processor' in thread_name:
            active_threads += 1
        elif hasattr(t, 'target') and t.target and 'background_dng_processor' in str(t.target):
            active_threads += 1
    
    return jsonify({
        'active_background_processes': active_threads,
        'total_threads': len(threading.enumerate()),
        'photo_count': get_photo_count(),
        'queue_size': raw_queue.qsize()
    })
    
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

        h1 {
            color: #fff;
            margin-bottom: 30px;
        }

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

        .capture-btn:hover {
            background: #cc0010;
        }

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

        .success {
            background: #2d5f2f;
            color: #4caf50;
        }

        .error {
            background: #5f2d2d;
            color: #f44336;
        }

        .capturing {
            background: #2d4f5f;
            color: #2196f3;
        }

        .hidden {
            display: none;
        }

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
        setInterval(() => {
            fetch('/processing_status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('queue-size').textContent = data.active_background_processes;
                })
                .catch(() => { });
        }, 2000);

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
                .catch(() => { });
        }, 2000);

        // Keyboard shortcut - spacebar
        document.addEventListener('keydown', function (event) {
            if (event.code === 'Space') {
                event.preventDefault();
                fastCapture();
            }
        });
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    print("Starting Fast Pi Camera Raw Capture Server...")
    
    if init_camera():
        
        print(f"Web interface: http://0.0.0.0:8000")

        try:
            app.run(host='0.0.0.0', port=8000, debug=False)
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            processing_active = False
            raw_queue.put(None)
            if picam2:
                picam2.stop()
                print("Camera stopped. Goodbye!")
    else:
        print("Failed to initialize camera. Exiting.")