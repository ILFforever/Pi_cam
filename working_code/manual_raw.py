#!/usr/bin/env python3
# WORKS (not work with custom picamera2)
import time
from picamera2 import Picamera2
import os

def test_raw_capture():
    print("Testing raw capture without DNG conversion...")
    
    picam2 = Picamera2()
    config = picam2.create_still_configuration(
        raw={"size": (3760, 2120)}, 
        buffer_count=2
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(2)
    
    # Try capturing raw data instead of DNG
    print("Capturing raw request...")
    start_time = time.time()
    
    request = picam2.capture_request()
    capture_time = time.time() - start_time
    print(f"capture_request() took {capture_time:.3f}s")
    
    # Check if we can access raw data
    try:
        raw_array = request.make_array("raw")
        print(f"Raw array shape: {raw_array.shape}, dtype: {raw_array.dtype}")
        
        # Try manual DNG save
        try:
            request.save_dng("manual_test.dng")
            print("Manual DNG save succeeded")
        except Exception as e:
            print(f"Manual DNG save failed: {e}")
            
    except Exception as e:
        print(f"Raw array access failed: {e}")
    
    finally:
        request.release()
        picam2.close()

if __name__ == "__main__":
    test_raw_capture()