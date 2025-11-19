#!/usr/bin/env python3
"""
DNG LUT Tester - Processes DNG files and saves visual results
Usage: python3 dng_lut_tester.py your_photo.dng [--lut-dir ./luts]
"""

import cv2
import numpy as np
import time
import os
import argparse
from pathlib import Path
import subprocess
import tempfile

try:
    from PIL import Image
    from pillow_lut import load_cube_file
    PILLOW_LUT_AVAILABLE = True
    print("pillow-lut found - will test optimized 3D LUT performance")
except ImportError:
    PILLOW_LUT_AVAILABLE = False
    print("pillow-lut not found - install with: pip3 install pillow-lut")

class DNGLUTTester:
    def __init__(self):
        self.test_results = []
        
    def find_dcraw_executable(self):
        """Find dcraw executable"""
        import shutil
        
        possible_names = ["dcraw", "dcraw.exe"]
        
        for name in possible_names:
            found = shutil.which(name)
            if found:
                print(f"✅ Found dcraw at: {found}")
                return found
        
        # Try common locations
        common_paths = [
            "/usr/bin/dcraw",
            "/usr/local/bin/dcraw",
            "./dcraw",
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                print(f"✅ Found dcraw at: {path}")
                return path
        
        return None
    
    def process_dng_to_image(self, dng_path):
        """Convert DNG to processed image using dcraw"""
        print(f"📷 Processing DNG: {dng_path}")
        
        dcraw_exe = self.find_dcraw_executable()
        if not dcraw_exe:
            print("❌ dcraw not found!")
            print("Install with: sudo apt install dcraw")
            return None
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                temp_output = temp_path / "processed.tiff"
                
                # dcraw parameters optimized for Pi Camera
                cmd = [
                    dcraw_exe,
                    "-w",          # Use camera white balance
                    "-b", "1.0",   # Brightness
                    "-q", "3",     # Quality (good balance)
                    "-o", "1",     # sRGB output
                    "-T",          # TIFF output
                    "-6",          # 16-bit output
                    "-c",          # Write to stdout
                    str(dng_path)
                ]
                
                print(f"Running: {' '.join(cmd[:6])} ...")
                
                with open(temp_output, 'wb') as f:
                    result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, 
                                          check=True, timeout=30)
                
                if not temp_output.exists() or temp_output.stat().st_size == 0:
                    print("❌ dcraw produced no output")
                    return None
                
                # Load processed image
                image = cv2.imread(str(temp_output), cv2.IMREAD_COLOR)
                if image is None:
                    print(f"❌ Could not load processed TIFF")
                    return None
                
                print(f"✅ DNG processed: {image.shape}")
                return image
                
        except subprocess.TimeoutExpired:
            print("❌ dcraw timeout (30s)")
            return None
        except subprocess.CalledProcessError as e:
            print(f"❌ dcraw error: {e.stderr.decode() if e.stderr else 'Unknown error'}")
            return None
        except Exception as e:
            print(f"❌ DNG processing error: {e}")
            return None
    
    def load_1d_lut(self, filepath):
        """Load 1D LUT from numpy file (.npz)"""
        try:
            data = np.load(filepath)
            return {
                'red': data['red'],
                'green': data['green'], 
                'blue': data['blue'],
                'name': str(data.get('name', Path(filepath).stem))
            }
        except Exception as e:
            print(f"Error loading 1D LUT {filepath}: {e}")
            return None
    
    def load_3d_lut_cube(self, filepath):
        """Load 3D LUT from .cube file"""
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
            
            size = None
            lut_data = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('LUT_3D_SIZE'):
                    size = int(line.split()[-1])
                elif not line.startswith('#') and not line.startswith('TITLE') and line:
                    try:
                        values = line.split()
                        if len(values) >= 3:
                            r, g, b = float(values[0]), float(values[1]), float(values[2])
                            lut_data.append([r, g, b])
                    except ValueError:
                        continue
            
            if size is None or not lut_data:
                return None
            
            expected_size = size ** 3
            lut_array = np.array(lut_data[:expected_size]).reshape(size, size, size, 3)
            
            return {
                'data': lut_array,
                'size': size,
                'name': Path(filepath).stem,
                'filepath': filepath
            }
            
        except Exception as e:
            print(f"Error loading 3D LUT {filepath}: {e}")
            return None
    
    def apply_1d_lut_opencv(self, image, lut_dict):
        """Apply 1D LUT using OpenCV (fastest method)"""
        start_time = time.perf_counter()
        
        if image.dtype != np.uint8:
            image = (np.clip(image, 0, 1) * 255).astype(np.uint8)
        
        b, g, r = cv2.split(image)
        
        r_lut = (lut_dict['red'] * 255).astype(np.uint8)
        g_lut = (lut_dict['green'] * 255).astype(np.uint8)  
        b_lut = (lut_dict['blue'] * 255).astype(np.uint8)
        
        r_new = cv2.LUT(r, r_lut)
        g_new = cv2.LUT(g, g_lut)
        b_new = cv2.LUT(b, b_lut)
        
        result = cv2.merge([b_new, g_new, r_new])
        
        end_time = time.perf_counter()
        return result, end_time - start_time
    
    def apply_3d_lut_pillow(self, image, lut_dict):
        """Apply 3D LUT using pillow-lut (fastest 3D method)"""
        if not PILLOW_LUT_AVAILABLE:
            return None, float('inf')
        
        start_time = time.perf_counter()
        
        try:
            lut_filter = load_cube_file(str(lut_dict['filepath']))
            
            # Convert OpenCV (BGR) to PIL (RGB)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)
            
            # Apply LUT
            result_pil = pil_image.filter(lut_filter)
            
            # Convert back to OpenCV (RGB to BGR)
            result_cv = cv2.cvtColor(np.array(result_pil), cv2.COLOR_RGB2BGR)
            
            end_time = time.perf_counter()
            return result_cv, end_time - start_time
            
        except Exception as e:
            print(f"Pillow-LUT error: {e}")
            end_time = time.perf_counter()
            return None, end_time - start_time
    
    def process_image_with_luts(self, image, lut_files, output_dir):
        """Process image with all available LUTs and save results"""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # Save original
        original_path = output_dir / "00_original.jpg"
        cv2.imwrite(str(original_path), image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        print(f"💾 Saved original: {original_path}")
        
        results = []
        
        for i, lut_file in enumerate(sorted(lut_files)):
            if lut_file.suffix.lower() == '.npz':
                # 1D LUT
                lut_dict = self.load_1d_lut(lut_file)
                if lut_dict is None:
                    continue
                
                print(f"\n🎨 Applying 1D LUT: {lut_dict['name']}")
                
                # Apply using OpenCV (fastest method)
                result_image, process_time = self.apply_1d_lut_opencv(image.copy(), lut_dict)
                
                # Save result
                output_path = output_dir / f"{i+1:02d}_1D_{lut_dict['name']}.jpg"
                cv2.imwrite(str(output_path), result_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
                
                results.append({
                    'name': lut_dict['name'],
                    'type': '1D',
                    'method': 'OpenCV',
                    'time_ms': process_time * 1000,
                    'fps': 1.0 / process_time,
                    'output_path': output_path
                })
                
                print(f"  ⚡ Processed in {process_time*1000:.1f}ms ({1.0/process_time:.1f} FPS)")
                print(f"  💾 Saved: {output_path}")
                
            elif lut_file.suffix.lower() == '.cube':
                # 3D LUT
                lut_dict = self.load_3d_lut_cube(lut_file)
                if lut_dict is None or not PILLOW_LUT_AVAILABLE:
                    continue
                
                print(f"\n🎨 Applying 3D LUT: {lut_dict['name']} ({lut_dict['size']}³)")
                
                # Apply using pillow-lut (fastest 3D method)
                result_image, process_time = self.apply_3d_lut_pillow(image.copy(), lut_dict)
                
                if result_image is not None:
                    # Save result
                    output_path = output_dir / f"{i+1:02d}_3D_{lut_dict['name']}.jpg"
                    cv2.imwrite(str(output_path), result_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    
                    results.append({
                        'name': lut_dict['name'],
                        'type': '3D',
                        'method': 'Pillow-LUT',
                        'time_ms': process_time * 1000,
                        'fps': 1.0 / process_time,
                        'output_path': output_path
                    })
                    
                    print(f"  ⚡ Processed in {process_time*1000:.0f}ms ({1.0/process_time:.1f} FPS)")
                    print(f"  💾 Saved: {output_path}")
                else:
                    print(f"  ❌ Failed to process")
        
        return results
    
    def print_summary(self, results):
        """Print processing summary"""
        print("\n" + "="*80)
        print("PROCESSING RESULTS SUMMARY")
        print("="*80)
        
        print(f"{'LUT Name':<25} {'Type':<4} {'Method':<12} {'Time':<10} {'FPS':<6} {'Output'}")
        print("-" * 80)
        
        for result in results:
            print(f"{result['name'][:24]:<25} {result['type']:<4} {result['method']:<12} "
                  f"{result['time_ms']:.1f}ms{'':<5} {result['fps']:.1f}{'':<4} "
                  f"{result['output_path'].name}")
        
        print("\nPERFORMANCE CATEGORIES:")
        
        realtime_luts = [r for r in results if r['fps'] > 15]
        background_luts = [r for r in results if 1 <= r['fps'] <= 15]
        slow_luts = [r for r in results if r['fps'] < 1]
        
        if realtime_luts:
            print("✅ Real-time capable (>15 FPS):")
            for r in realtime_luts:
                print(f"   {r['name']} ({r['type']}) - {r['fps']:.1f} FPS")
        
        if background_luts:
            print("🔄 Background processing (1-15 FPS):")
            for r in background_luts:
                print(f"   {r['name']} ({r['type']}) - {r['fps']:.1f} FPS")
        
        if slow_luts:
            print("⏳ Slow processing (<1 FPS):")
            for r in slow_luts:
                print(f"   {r['name']} ({r['type']}) - {r['fps']:.1f} FPS")

def get_system_info():
    """Get system information"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpu_info = f.read()
        
        with open('/proc/meminfo', 'r') as f:
            mem_info = f.read()
        
        print("SYSTEM INFORMATION:")
        print("-" * 40)
        
        for line in cpu_info.split('\n'):
            if 'Model' in line:
                print(f"CPU: {line.split(':')[1].strip()}")
                break
        
        for line in mem_info.split('\n'):
            if 'MemTotal' in line:
                mem_kb = int(line.split(':')[1].strip().split()[0])
                print(f"RAM: {mem_kb/1024:.0f} MB")
                break
        
        print(f"Pillow-LUT: {PILLOW_LUT_AVAILABLE}")
        print()
        
    except Exception as e:
        print(f"Could not get system info: {e}")

def main():
    parser = argparse.ArgumentParser(description="DNG LUT Tester - Process DNG files with LUTs")
    parser.add_argument('dng_file', help='DNG file to process')
    parser.add_argument('--lut-dir', default='./luts',
                       help='Directory containing LUT files (default: ./luts)')
    parser.add_argument('--output-dir', default='./lut_results',
                       help='Output directory for results (default: ./lut_results)')
    
    args = parser.parse_args()
    
    get_system_info()
    
    tester = DNGLUTTester()
    
    # Check DNG file
    dng_path = Path(args.dng_file)
    if not dng_path.exists():
        print(f"❌ DNG file not found: {dng_path}")
        return
    
    # Process DNG to image
    print(f"📁 Processing DNG file: {dng_path}")
    image = tester.process_dng_to_image(dng_path)
    if image is None:
        print("❌ Failed to process DNG file")
        return
    
    # Find LUT files
    lut_dir = Path(args.lut_dir)
    if not lut_dir.exists():
        print(f"❌ LUT directory not found: {lut_dir}")
        print("Create the directory and add .npz (1D) and .cube (3D) files")
        return
    
    lut_files = list(lut_dir.glob("*.npz")) + list(lut_dir.glob("*.cube"))
    
    if not lut_files:
        print(f"❌ No LUT files found in {lut_dir}")
        print("Add .npz (1D) or .cube (3D) LUT files")
        return
    
    print(f"📂 Found {len(lut_files)} LUT files")
    
    # Process image with all LUTs
    results = tester.process_image_with_luts(image, lut_files, args.output_dir)
    
    # Print summary
    tester.print_summary(results)
    
    print(f"\n🎯 All results saved to: {Path(args.output_dir).absolute()}")
    print("📸 Ready to integrate fast methods into your instant camera!")

if __name__ == "__main__":
    main()