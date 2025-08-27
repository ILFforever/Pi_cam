#!/usr/bin/env python3
"""
Fujifilm-style LUT Generator with dcraw integration
Uses dcraw for DNG processing + Python for fast LUT application
Perfect for Pi Zero 2 - minimal memory usage
"""

import numpy as np
import cv2
import subprocess
import argparse
import os
import tempfile
from pathlib import Path
DCRAW_PATH = "W:\\dcraw\\dcraw.exe"

class FujifilmLUT:
    def __init__(self):
        self.lut_size = 64  # Smaller LUT for Pi efficiency
        
    def create_classic_chrome_lut(self):
        """Create Classic Chrome film simulation LUT"""
        print("🎞️  Generating Classic Chrome LUT...")
        
        # Create simple 1D curves for each channel (much faster than 3D LUT)
        curve_size = 256
        
        # Red channel - slight boost, warm
        red_curve = np.linspace(0, 1, curve_size)
        red_curve = np.power(red_curve, 0.92) * 1.05  # Lift + warm
        red_curve = np.clip(red_curve, 0, 1)
        
        # Green channel - slightly reduced for warmth  
        green_curve = np.linspace(0, 1, curve_size)
        green_curve = np.power(green_curve, 0.95) * 0.98  # Slight reduction
        green_curve = np.clip(green_curve, 0, 1)
        
        # Blue channel - reduced for warmth, lifted shadows
        blue_curve = np.linspace(0, 1, curve_size)
        blue_curve = (blue_curve + 0.08) * 0.96  # Shadow lift + cool reduction
        blue_curve = np.clip(blue_curve, 0, 1)
        
        return {
            'red': red_curve,
            'green': green_curve, 
            'blue': blue_curve,
            'name': 'classic_chrome'
        }
    
    def create_velvia_lut(self):
        """Create Velvia film simulation LUT"""
        print("🌈 Generating Velvia LUT...")
        
        curve_size = 256
        
        # High contrast S-curves
        red_curve = np.linspace(0, 1, curve_size)
        red_curve = self._s_curve(red_curve, 1.3) * 1.08  # Boost reds
        
        green_curve = np.linspace(0, 1, curve_size)
        green_curve = self._s_curve(green_curve, 1.25) * 0.95  # Mute greens slightly
        
        blue_curve = np.linspace(0, 1, curve_size)
        blue_curve = self._s_curve(blue_curve, 1.3) * 1.1  # Boost blues
        
        return {
            'red': np.clip(red_curve, 0, 1),
            'green': np.clip(green_curve, 0, 1),
            'blue': np.clip(blue_curve, 0, 1),
            'name': 'velvia'
        }
    
    def create_acros_lut(self):
        """Create ACROS B&W film simulation LUT"""
        print("⚫ Generating ACROS B&W LUT...")
        
        curve_size = 256
        
        # Film-like B&W curve with slight warm cast
        base_curve = np.linspace(0, 1, curve_size)
        base_curve = self._s_curve(base_curve, 1.1)  # Gentle S-curve
        
        # Warm B&W tint
        red_curve = base_curve * 1.02
        green_curve = base_curve  
        blue_curve = base_curve * 0.98
        
        return {
            'red': np.clip(red_curve, 0, 1),
            'green': np.clip(green_curve, 0, 1),
            'blue': np.clip(blue_curve, 0, 1),
            'name': 'acros'
        }
    
    def _s_curve(self, values, strength=1.2):
        """Apply S-curve for contrast"""
        return np.where(values < 0.5,
                       np.power(values * 2, strength) / 2,
                       1 - np.power((1 - values) * 2, strength) / 2)
    
    def save_lut_as_numpy(self, lut_dict, filename):
        """Save LUT as compact numpy file for fast loading"""
        np.savez_compressed(filename, 
                           red=lut_dict['red'],
                           green=lut_dict['green'], 
                           blue=lut_dict['blue'],
                           name=lut_dict['name'])
        print(f"💾 LUT saved as {filename}")
    
    def load_lut_from_numpy(self, filename):
        """Load LUT from numpy file"""
        data = np.load(filename)
        return {
            'red': data['red'],
            'green': data['green'],
            'blue': data['blue'], 
            'name': str(data['name'])
        }
    
    def apply_lut_fast(self, image, lut_dict):
        """Apply 1D LUT curves very fast - perfect for Pi"""
        print(f"🎨 Applying {lut_dict['name']} LUT...")
        
        # Ensure image is uint8
        if image.dtype != np.uint8:
            image = (np.clip(image, 0, 1) * 255).astype(np.uint8)
        
        # Split channels
        b, g, r = cv2.split(image)  # OpenCV uses BGR
        
        # Apply curves using numpy's advanced indexing (super fast!)
        r_indices = (lut_dict['red'] * 255).astype(np.uint8)
        g_indices = (lut_dict['green'] * 255).astype(np.uint8)
        b_indices = (lut_dict['blue'] * 255).astype(np.uint8)
        
        r_new = r_indices[r]
        g_new = g_indices[g]  
        b_new = b_indices[b]
        
        # Merge back
        result = cv2.merge([b_new, g_new, r_new])
        
        return result

def find_dcraw_executable():
    """Find dcraw executable on different platforms"""
    import shutil
    
    # First try standard names
    possible_names = ["dcraw", "dcraw.exe"]
    
    for name in possible_names:
        # Use shutil.which for better PATH detection
        found = shutil.which(name)
        if found:
            print(f"✅ Found dcraw at: {found}")
            return found
    
    # If not in PATH, try common Windows locations
    common_paths = [
        "W:\\dcraw\\dcraw.exe",  # Your specific path
        "C:\\dcraw\\dcraw.exe",
        "C:\\tools\\dcraw.exe",
        ".\\dcraw.exe",  # Current directory
        "dcraw\\dcraw.exe"  # Subfolder
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            print(f"✅ Found dcraw at: {path}")
            return path
    
    # Last resort: try to run each name to see if it works
    for name in possible_names:
        try:
            result = subprocess.run([name, "-h"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0 or "dcraw" in result.stderr.lower():
                print(f"✅ Found working dcraw: {name}")
                return name
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    
    return None

def process_dng_with_dcraw(dng_path, temp_dir, dcraw_params=None):
    """Use dcraw to convert DNG to temp image file"""
    print(f"📷 Processing {dng_path} with dcraw...")
    
    # Find dcraw executable
    dcraw_exe = find_dcraw_executable()
    if not dcraw_exe:
        print("❌ dcraw not found!")
        print("Windows: Download dcraw.exe from https://www.dcraw.org/")
        print("Linux: sudo apt install dcraw")  
        print("macOS: brew install dcraw")
        return None
    
    if dcraw_params is None:
        # Optimized dcraw params for Pi Camera DNG files
        dcraw_params = [
            "-w",          # Use camera white balance
            "-t", "2",
            "-b", "1.0",   # Brightness (neutral)
            "-q", "4",     # Quality (3 = good, fast)
            "-o", "1",     # Output colorspace (sRGB)
            "-T",          # Output TIFF
            "-6"           # 16-bit output
        ]
    
    # Create temp output path
    temp_output = temp_dir / f"{Path(dng_path).stem}_dcraw.tiff"
    
    # Run dcraw with found executable
    cmd = [dcraw_exe] + dcraw_params + ["-c", str(dng_path)]
    
    try:
        with open(temp_output, 'wb') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=True)
        
        print(f"✅ dcraw processed: {temp_output}")
        return temp_output
        
    except subprocess.CalledProcessError as e:
        print(f"❌ dcraw error: {e.stderr.decode()}")
        return None
    except Exception as e:
        print(f"❌ dcraw execution error: {e}")
        return None

def add_subtle_grain(image, intensity=0.015):
    """Add very subtle film grain - optimized for Pi"""
    if intensity <= 0:
        return image
        
    # Generate grain only for luminance channel (faster)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    noise = np.random.normal(0, intensity * 255, gray.shape).astype(np.float32)
    
    # Apply grain more to midtones
    mask = np.where((gray > 50) & (gray < 200), 1.0, 0.3)
    noise *= mask
    
    # Add back to image
    result = image.astype(np.float32)
    for i in range(3):
        result[:, :, i] += noise
    
    return np.clip(result, 0, 255).astype(np.uint8)

def process_single_dng(dng_path, output_path, lut_dict, add_grain=True):
    """Complete pipeline: dcraw -> LUT -> grain -> save"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Step 1: Process DNG with dcraw  
        tiff_path = process_dng_with_dcraw(dng_path, temp_path)
        if not tiff_path:
            return False
            
        # Step 2: Load processed image
        image = cv2.imread(str(tiff_path), cv2.IMREAD_COLOR)
        if image is None:
            print(f"❌ Could not load {tiff_path}")
            return False
        
        # Step 3: Apply LUT
        lut_processor = FujifilmLUT()
        image = lut_processor.apply_lut_fast(image, lut_dict)
        
        # Step 4: Add film grain (optional)
        if add_grain and lut_dict['name'] != 'acros':
            image = add_subtle_grain(image, 0.012)
        
        # Step 5: Save final result
        cv2.imwrite(str(output_path), image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"✅ Final output: {output_path}")
        
        return True

def main():
    parser = argparse.ArgumentParser(description="Fujifilm LUT + dcraw Pipeline")
    parser.add_argument("--style", choices=["classic_chrome", "velvia", "acros"], 
                       default="classic_chrome", help="Film simulation style")
    parser.add_argument("--input", type=str, help="Input DNG file or directory")
    parser.add_argument("--output", type=str, help="Output directory")
    parser.add_argument("--no-grain", action="store_true", help="Skip film grain")
    parser.add_argument("--generate-lut", action="store_true", 
                       help="Generate and save LUT file only")
    
    args = parser.parse_args()
    
    # Create LUT processor
    lut_gen = FujifilmLUT()
    
    # Generate the appropriate LUT
    if args.style == "classic_chrome":
        lut_dict = lut_gen.create_classic_chrome_lut()
    elif args.style == "velvia":
        lut_dict = lut_gen.create_velvia_lut()
    elif args.style == "acros":
        lut_dict = lut_gen.create_acros_lut()
    
    # Save LUT file
    lut_filename = f"fujifilm_{args.style}.npz"
    lut_gen.save_lut_as_numpy(lut_dict, lut_filename)
    
    if args.generate_lut:
        print(f"🎭 LUT generated: {lut_filename}")
        return
    
    # Process images if input provided
    if args.input and args.output:
        input_path = Path(args.input)
        output_path = Path(args.output)
        output_path.mkdir(parents=True, exist_ok=True)
        
        add_grain = not args.no_grain
        
        if input_path.is_file() and input_path.suffix.lower() in ['.dng', '.DNG']:
            # Single DNG file
            output_file = output_path / f"{input_path.stem}_{args.style}.jpg"
            success = process_single_dng(input_path, output_file, lut_dict, add_grain)
            
        elif input_path.is_dir():
            # Directory of DNG files
            dng_files = list(input_path.glob("*.dng")) + list(input_path.glob("*.DNG"))
            print(f"📁 Found {len(dng_files)} DNG files")
            
            for i, dng_file in enumerate(dng_files, 1):
                print(f"[{i}/{len(dng_files)}] Processing {dng_file.name}")
                output_file = output_path / f"{dng_file.stem}_{args.style}.jpg"
                process_single_dng(dng_file, output_file, lut_dict, add_grain)
        
        else:
            print("❌ Input must be a DNG file or directory containing DNG files")
    
    print(f"🎉 Done! LUT saved: {lut_filename}")

if __name__ == "__main__":
    main()