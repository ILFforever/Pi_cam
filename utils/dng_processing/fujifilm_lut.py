#!/usr/bin/env python3
"""
Simple LUT Applier
Apply pre-made LUTs to images quickly
Based on fujifilm_lut.py
"""

import numpy as np
import cv2
import argparse
from pathlib import Path
import subprocess
import os
import tempfile
import shutil

# Get script directory for local dcraw
SCRIPT_DIR = Path(__file__).parent.absolute()

class SimpleLUTApplier:
    def __init__(self):
        self.available_luts = {
            'classic_chrome': self.create_classic_chrome_lut,
            'velvia': self.create_velvia_lut,
            'acros': self.create_acros_lut,
            'portra': self.create_portra_lut,
            'neutral': self.create_neutral_lut
        }
    
    def create_classic_chrome_lut(self):
        """Classic Chrome film simulation"""
        curve_size = 256
        
        # Warm, muted look with lifted shadows
        red_curve = np.linspace(0, 1, curve_size)
        red_curve = np.power(red_curve, 0.92) * 1.05  # Slight warm boost
        
        green_curve = np.linspace(0, 1, curve_size)
        green_curve = np.power(green_curve, 0.95) * 0.98  # Slight reduction
        
        blue_curve = np.linspace(0, 1, curve_size)
        blue_curve = (blue_curve + 0.08) * 0.96  # Shadow lift + cool reduction
        
        return {
            'red': np.clip(red_curve, 0, 1),
            'green': np.clip(green_curve, 0, 1),
            'blue': np.clip(blue_curve, 0, 1),
            'name': 'classic_chrome'
        }
    
    def create_velvia_lut(self):
        """Velvia - vibrant, saturated look"""
        curve_size = 256
        base_curve = np.linspace(0, 1, curve_size)
        
        # High contrast S-curves
        red_curve = self._s_curve(base_curve, 1.3) * 1.08
        green_curve = self._s_curve(base_curve, 1.25) * 0.95
        blue_curve = self._s_curve(base_curve, 1.3) * 1.1
        
        return {
            'red': np.clip(red_curve, 0, 1),
            'green': np.clip(green_curve, 0, 1),
            'blue': np.clip(blue_curve, 0, 1),
            'name': 'velvia'
        }
    
    def create_acros_lut(self):
        """ACROS - B&W film simulation"""
        curve_size = 256
        base_curve = np.linspace(0, 1, curve_size)
        
        # Film-like B&W curve with warm tint
        base_curve = self._s_curve(base_curve, 1.1)
        
        red_curve = base_curve * 1.02    # Warm B&W
        green_curve = base_curve
        blue_curve = base_curve * 0.98
        
        return {
            'red': np.clip(red_curve, 0, 1),
            'green': np.clip(green_curve, 0, 1),
            'blue': np.clip(blue_curve, 0, 1),
            'name': 'acros'
        }
    
    def create_portra_lut(self):
        """Kodak Portra-inspired - creamy skin tones"""
        curve_size = 256
        base_curve = np.linspace(0, 1, curve_size)
        
        # Lifted shadows, warm mids, protected highlights
        red_curve = base_curve + 0.05  # Warm lift
        red_curve = np.power(red_curve, 0.9) * 1.02
        
        green_curve = base_curve + 0.03  # Slight green lift
        green_curve = np.power(green_curve, 0.95)
        
        blue_curve = base_curve * 0.96  # Reduce blue for warmth
        blue_curve = np.power(blue_curve, 1.05)
        
        return {
            'red': np.clip(red_curve, 0, 1),
            'green': np.clip(green_curve, 0, 1),
            'blue': np.clip(blue_curve, 0, 1),
            'name': 'portra'
        }
    
    def create_neutral_lut(self):
        """Neutral - no changes"""
        curve_size = 256
        neutral_curve = np.linspace(0, 1, curve_size)
        
        return {
            'red': neutral_curve,
            'green': neutral_curve,
            'blue': neutral_curve,
            'name': 'neutral'
        }
    
    def _s_curve(self, values, strength=1.2):
        """Apply S-curve for contrast"""
        return np.where(values < 0.5,
                       np.power(values * 2, strength) / 2,
                       1 - np.power((1 - values) * 2, strength) / 2)
    
    def load_custom_lut(self, lut_file):
        """Load LUT from .npz file"""
        try:
            data = np.load(lut_file)
            return {
                'red': data['red'],
                'green': data['green'],
                'blue': data['blue'],
                'name': str(data.get('name', Path(lut_file).stem))
            }
        except Exception as e:
            print(f"❌ Error loading LUT {lut_file}: {e}")
            return None
    
    def apply_lut(self, image, lut_dict):
        """Apply LUT to image"""
        print(f"🎨 Applying {lut_dict['name']} LUT...")
        
        # Ensure image is uint8
        if image.dtype != np.uint8:
            image = (np.clip(image, 0, 1) * 255).astype(np.uint8)
        
        # Split channels (OpenCV uses BGR)
        b, g, r = cv2.split(image)
        
        # Apply LUT curves
        r_lut = (lut_dict['red'] * 255).astype(np.uint8)
        g_lut = (lut_dict['green'] * 255).astype(np.uint8)
        b_lut = (lut_dict['blue'] * 255).astype(np.uint8)
        
        r_new = r_lut[r]
        g_new = g_lut[g]
        b_new = b_lut[b]
        
        return cv2.merge([b_new, g_new, r_new])
    
    def process_dng_with_dcraw(self, dng_path):
        """Process DNG with local dcraw"""
        print(f"📷 Processing DNG: {dng_path}")
        
        dcraw_exe = SCRIPT_DIR / "dcraw.exe"
        if not dcraw_exe.exists():
            print("❌ dcraw.exe not found!")
            print("Place dcraw.exe in the same folder as this script")
            return None
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_output = Path(temp_dir) / "processed.tiff"
                
                cmd = [
                    str(dcraw_exe),
                    "-w", "-b", "1.0", "-q", "3", "-o", "1", "-T", "-6", "-c",
                    str(dng_path)
                ]
                
                print(f"Running: dcraw {Path(dng_path).name}")
                
                with open(temp_output, 'wb') as f:
                    result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, 
                                          check=True, timeout=30)
                
                image = cv2.imread(str(temp_output), cv2.IMREAD_COLOR)
                if image is None:
                    print("❌ Could not load processed TIFF")
                    return None
                
                print(f"✅ DNG processed: {image.shape}")
                return image
                
        except Exception as e:
            print(f"❌ dcraw error: {e}")
            return None
    
    def load_image(self, image_path):
        """Load image (DNG or regular format)"""
        path = Path(image_path)
        
        if not path.exists():
            print(f"❌ File not found: {image_path}")
            return None
        
        print(f"📸 Loading: {path.name}")
        
        if path.suffix.lower() in ['.dng', '.DNG']:
            return self.process_dng_with_dcraw(path)
        else:
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                print(f"❌ Could not load: {path}")
                return None
            print(f"✅ Image loaded: {image.shape}")
            return image
    
    def add_film_grain(self, image, intensity=0.015):
        """Add subtle film grain"""
        if intensity <= 0:
            return image
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        noise = np.random.normal(0, intensity * 255, gray.shape).astype(np.float32)
        
        # Apply grain more to midtones
        mask = np.where((gray > 50) & (gray < 200), 1.0, 0.3)
        noise *= mask
        
        result = image.astype(np.float32)
        for i in range(3):
            result[:, :, i] += noise
        
        return np.clip(result, 0, 255).astype(np.uint8)
    
    def process_image(self, input_path, output_path, lut_name, add_grain=False, custom_lut=None):
        """Process single image with LUT"""
        # Load image
        image = self.load_image(input_path)
        if image is None:
            return False
        
        # Get LUT
        if custom_lut:
            lut_dict = self.load_custom_lut(custom_lut)
            if lut_dict is None:
                return False
        else:
            if lut_name not in self.available_luts:
                print(f"❌ Unknown LUT: {lut_name}")
                print(f"Available LUTs: {', '.join(self.available_luts.keys())}")
                return False
            lut_dict = self.available_luts[lut_name]()
        
        # Apply LUT
        processed = self.apply_lut(image, lut_dict)
        
        # Add grain if requested
        if add_grain and lut_dict['name'] != 'acros':
            processed = self.add_film_grain(processed, 0.012)
            print("✨ Film grain added")
        
        # Save result
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        cv2.imwrite(str(output_path), processed, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"✅ Saved: {output_path}")
        
        return True

def main():
    parser = argparse.ArgumentParser(description="Simple LUT Applier")
    parser.add_argument("input", help="Input image file")
    parser.add_argument("-l", "--lut", default="classic_chrome",
                       help="LUT name (classic_chrome, velvia, acros, portra, neutral)")
    parser.add_argument("-o", "--output", help="Output file (default: input_LUTNAME.jpg)")
    parser.add_argument("-c", "--custom-lut", help="Custom LUT file (.npz)")
    parser.add_argument("-g", "--grain", action="store_true", help="Add film grain")
    parser.add_argument("--list-luts", action="store_true", help="List available LUTs")
    
    args = parser.parse_args()
    
    applier = SimpleLUTApplier()
    
    if args.list_luts:
        print("📋 Available LUTs:")
        for lut_name in applier.available_luts.keys():
            print(f"  • {lut_name}")
        return
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        input_path = Path(args.input)
        lut_suffix = Path(args.custom_lut).stem if args.custom_lut else args.lut
        output_path = input_path.parent / f"{input_path.stem}_{lut_suffix}.jpg"
    
    # Process image
    print(f"🚀 Processing: {args.input}")
    print(f"🎭 LUT: {args.custom_lut or args.lut}")
    print(f"💾 Output: {output_path}")
    
    success = applier.process_image(
        args.input, 
        output_path, 
        args.lut,
        add_grain=args.grain,
        custom_lut=args.custom_lut
    )
    
    if success:
        print("🎉 Done!")
    else:
        print("❌ Failed!")

if __name__ == "__main__":
    # Quick usage examples
    if len(os.sys.argv) == 1:
        print("📸 Simple LUT Applier")
        print("\nUsage:")
        print("  python simple_lut_applier.py image.jpg")
        print("  python simple_lut_applier.py image.dng -l velvia -g")
        print("  python simple_lut_applier.py image.jpg -c custom_lut.npz")
        print("  python simple_lut_applier.py --list-luts")
        print("\nAvailable LUTs: classic_chrome, velvia, acros, portra, neutral")
        print("Add -g for film grain, -o for custom output filename")
    else:
        main()