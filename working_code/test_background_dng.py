#!/usr/bin/env python3

# Works using our custom picamera2 with background DNG processing
import time
import sys
import os
from picamera2 import Picamera2

def test_background_dng():
    print(f"Python executable: {sys.executable}")
    print(f"Picamera2 location: {Picamera2.__module__}")
    print("Testing background DNG processing...")
    
    picam2 = Picamera2()
    
    try:
        # Configure for DNG capture
        config = picam2.create_still_configuration(
            raw={"size": (4608 , 2592 )}, 
            #raw={"size": (3760, 2120)}, 
            #raw={"size": (2304, 1296)},
            buffer_count=3
        )
        picam2.configure(config)
        picam2.start()
        
        print("Camera started, waiting 2s for settle...")
        time.sleep(2)
        
        # Test rapid DNG captures
        for i in range(3):
            print(f"\n=== Capture {i+1} ===")
            start_time = time.time()
            
            filename = f"test{i:03d}.dng"
            picam2.capture_file(filename, name="raw")
            
            capture_time = time.time() - start_time
            print(f"capture_file() returned in {capture_time:.3f}s")
            
            # Check if file exists immediately (it shouldn't be fully written yet)
            if os.path.exists(filename):
                size = os.path.getsize(filename)
                print(f"File {filename} exists with size {size} bytes")
            else:
                print(f"File {filename} not yet created")
            
            time.sleep(3)  # Wait before next capture
        
        print("\nWaiting 10s for background processing to complete...")
        time.sleep(10)
        
        # Check final file status
        for i in range(3):
            filename = f"test{i:03d}.dng"
            if os.path.exists(filename):
                size = os.path.getsize(filename)
                print(f"Final: {filename} = {size/1024/1024:.1f}MB")
            else:
                print(f"MISSING: {filename}")
    
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        picam2.close()
        print("Test completed!")

if __name__ == "__main__":
    test_background_dng()