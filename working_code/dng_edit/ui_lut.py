# #!/usr/bin/env python3
"""
Universal LUT Tuner with DearPyGui
Create any film look with comprehensive tone and color controls
"""

import numpy as np
import cv2
import dearpygui.dearpygui as dpg
from pathlib import Path
import os
import tempfile
import subprocess
import shutil

class UniversalLUTTuner:
    def __init__(self):
        self.original_image = None
        self.processed_image = None
        self.image_width = 800
        self.image_height = 600
        
        # Comprehensive parameters for any film look
        self.params = {
            # Tone Controls
            'exposure': 0.0,           # -2.0 to +2.0
            'contrast': 0.0,           # -1.0 to +1.0
            'highlights': 0.0,         # -1.0 to +1.0
            'shadows': 0.0,            # -1.0 to +1.0
            'whites': 0.0,             # -1.0 to +1.0
            'blacks': 0.0,             # -1.0 to +1.0
            'midtones': 0.0,           # -1.0 to +1.0
            
            # Advanced Shadow/Highlight
            'shadow_lift': 0.0,        # 0.0 to 0.3
            'highlight_rolloff': 0.0,  # 0.0 to 0.5
            'shadow_contrast': 1.0,    # 0.5 to 2.0
            'highlight_contrast': 1.0, # 0.5 to 2.0
            'midtone_contrast': 1.0,   # 0.5 to 2.0
            
            # Color Controls
            'saturation': 0.0,         # -1.0 to +1.0
            'vibrance': 0.0,           # -1.0 to +1.0
            'temperature': 0.0,        # -1.0 to +1.0 (warm/cool)
            'tint': 0.0,              # -1.0 to +1.0 (magenta/green)
            
            # Individual Channel Controls
            'red_lift': 0.0,           # 0.0 to 0.3
            'red_gain': 1.0,           # 0.5 to 1.5
            'red_gamma': 1.0,          # 0.5 to 2.0
            
            'green_lift': 0.0,
            'green_gain': 1.0,
            'green_gamma': 1.0,
            
            'blue_lift': 0.0,
            'blue_gain': 1.0,
            'blue_gamma': 1.0,
            
            # Film-specific effects
            'film_grain': 0.0,         # 0.0 to 1.0
            'vintage_fade': 0.0,       # 0.0 to 1.0
            'color_grading': 0.0,      # 0.0 to 1.0
        }
    
    def find_dcraw_executable(self):
        """Find dcraw executable"""
        found = shutil.which("dcraw") or shutil.which("dcraw.exe")
        if found:
            return found
        
        common_paths = [
            "W:\\dcraw\\dcraw.exe",
            "C:\\dcraw\\dcraw.exe", 
            "C:\\tools\\dcraw.exe",
            ".\\dcraw.exe"
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None
    
    def process_dng_with_dcraw(self, dng_path):
        """Process DNG with dcraw"""
        dcraw_exe = self.find_dcraw_executable()
        if not dcraw_exe:
            return None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            temp_output = temp_path / "processed.tiff"
            
            cmd = [dcraw_exe, "-w", "-b", "1.0", "-q", "3", "-o", "1", "-T", "-6", "-c", str(dng_path)]
            
            try:
                with open(temp_output, 'wb') as f:
                    subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, check=True)
                
                image = cv2.imread(str(temp_output), cv2.IMREAD_COLOR)
                return image
            except Exception as e:
                print(f"dcraw error: {e}")
                return None
    
    def load_image(self, file_path):
        """Load and prepare image for processing"""
        path = Path(file_path)
        
        if path.suffix.lower() in ['.dng', '.DNG']:
            # Process DNG with dcraw
            image = self.process_dng_with_dcraw(path)
        else:
            # Load regular image file
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        
        if image is None:
            return False
        
        # Resize image for preview
        height, width = image.shape[:2]
        aspect = width / height
        
        if aspect > self.image_width / self.image_height:
            new_width = self.image_width
            new_height = int(self.image_width / aspect)
        else:
            new_height = self.image_height
            new_width = int(self.image_height * aspect)
        
        self.original_image = cv2.resize(image, (new_width, new_height))
        self.update_preview()
        return True
    
    def apply_tone_curve(self, values, shadows, highlights, midtones, contrast):
        """Apply comprehensive tone curve"""
        values = np.clip(values, 0, 1)
        
        # Apply exposure-like adjustment to midtones
        if midtones != 0:
            values = values * (1 + midtones)
        
        # Shadow and highlight adjustments
        shadow_mask = values < 0.5
        highlight_mask = values >= 0.5
        
        # Shadow adjustment
        if shadows != 0:
            shadow_factor = 1 + shadows
            values[shadow_mask] = values[shadow_mask] * shadow_factor
        
        # Highlight adjustment  
        if highlights != 0:
            highlight_factor = 1 + highlights
            values[highlight_mask] = values[highlight_mask] * highlight_factor
        
        # Apply contrast
        if contrast != 0:
            # S-curve for contrast
            strength = 1 + contrast
            values = np.where(values < 0.5,
                             np.power(values * 2, 1.0/strength) / 2,
                             1 - np.power((1 - values) * 2, 1.0/strength) / 2)
        
        return np.clip(values, 0, 1)
    
    def apply_lift_gamma_gain(self, values, lift, gamma, gain):
        """Apply lift-gamma-gain color correction"""
        values = np.clip(values, 0, 1)
        
        # Lift (shadows)
        if lift != 0:
            values = values + lift * (1 - values)
        
        # Gamma (midtones)
        if gamma != 1.0:
            values = np.power(np.maximum(values, 1e-10), 1.0/gamma)
        
        # Gain (overall multiplier)
        if gain != 1.0:
            values = values * gain
        
        return np.clip(values, 0, 1)
    
    def apply_color_temperature(self, image, temperature, tint):
        """Apply color temperature and tint adjustments"""
        if temperature == 0 and tint == 0:
            return image
        
        # Convert to float
        img_float = image.astype(np.float32) / 255.0
        b, g, r = cv2.split(img_float)
        
        # Temperature adjustment (warm/cool)
        if temperature != 0:
            if temperature > 0:  # Warmer
                r = r * (1 + temperature * 0.3)
                b = b * (1 - temperature * 0.3)
            else:  # Cooler
                r = r * (1 + temperature * 0.3)
                b = b * (1 - temperature * 0.3)
        
        # Tint adjustment (magenta/green)
        if tint != 0:
            if tint > 0:  # More magenta
                r = r * (1 + tint * 0.2)
                b = b * (1 + tint * 0.2)
                g = g * (1 - tint * 0.2)
            else:  # More green
                g = g * (1 - tint * 0.2)
                r = r * (1 + tint * 0.1)
                b = b * (1 + tint * 0.1)
        
        # Merge and convert back
        result = cv2.merge([b, g, r])
        result = np.clip(result * 255, 0, 255).astype(np.uint8)
        return result
    
    def apply_saturation_vibrance(self, image, saturation, vibrance):
        """Apply saturation and vibrance adjustments"""
        if saturation == 0 and vibrance == 0:
            return image
        
        # Convert to HSV for saturation adjustment
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
        h, s, v = cv2.split(hsv)
        
        # Saturation adjustment (affects all colors equally)
        if saturation != 0:
            s = s * (1 + saturation)
        
        # Vibrance adjustment (protects skin tones, affects low-saturation areas more)
        if vibrance != 0:
            # Vibrance affects less saturated colors more
            vibrance_mask = 1 - (s / 255.0)  # Inverse of current saturation
            s = s + vibrance * 50 * vibrance_mask
        
        s = np.clip(s, 0, 255)
        
        # Merge and convert back
        hsv_merged = cv2.merge([h, s, v])
        result = cv2.cvtColor(hsv_merged.astype(np.uint8), cv2.COLOR_HSV2BGR)
        return result
    
    def create_lut_with_params(self):
        """Create comprehensive LUT with current parameters"""
        curve_size = 256
        base_curve = np.linspace(0, 1, curve_size)
        
        # Apply tone adjustments
        red_curve = self.apply_tone_curve(
            base_curve.copy(), 
            self.params['shadows'], 
            self.params['highlights'],
            self.params['midtones'],
            self.params['contrast']
        )
        
        green_curve = self.apply_tone_curve(
            base_curve.copy(),
            self.params['shadows'],
            self.params['highlights'], 
            self.params['midtones'],
            self.params['contrast']
        )
        
        blue_curve = self.apply_tone_curve(
            base_curve.copy(),
            self.params['shadows'],
            self.params['highlights'],
            self.params['midtones'], 
            self.params['contrast']
        )
        
        # Apply individual channel lift-gamma-gain
        red_curve = self.apply_lift_gamma_gain(
            red_curve, 
            self.params['red_lift'],
            self.params['red_gamma'],
            self.params['red_gain']
        )
        
        green_curve = self.apply_lift_gamma_gain(
            green_curve,
            self.params['green_lift'],
            self.params['green_gamma'], 
            self.params['green_gain']
        )
        
        blue_curve = self.apply_lift_gamma_gain(
            blue_curve,
            self.params['blue_lift'],
            self.params['blue_gamma'],
            self.params['blue_gain']
        )
        
        # Apply exposure adjustment
        if self.params['exposure'] != 0:
            exposure_factor = 2 ** self.params['exposure']
            red_curve = red_curve * exposure_factor
            green_curve = green_curve * exposure_factor
            blue_curve = blue_curve * exposure_factor
        
        # Apply whites and blacks adjustment
        if self.params['whites'] != 0 or self.params['blacks'] != 0:
            # Whites affect highlights
            white_factor = 1 + self.params['whites']
            highlight_mask = base_curve > 0.7
            red_curve[highlight_mask] *= white_factor
            green_curve[highlight_mask] *= white_factor
            blue_curve[highlight_mask] *= white_factor
            
            # Blacks affect shadows
            black_factor = 1 + self.params['blacks']
            shadow_mask = base_curve < 0.3
            red_curve[shadow_mask] *= black_factor
            green_curve[shadow_mask] *= black_factor
            blue_curve[shadow_mask] *= black_factor
        
        # Clean up curves
        red_curve = np.nan_to_num(red_curve, nan=0.5, posinf=1.0, neginf=0.0)
        green_curve = np.nan_to_num(green_curve, nan=0.5, posinf=1.0, neginf=0.0)
        blue_curve = np.nan_to_num(blue_curve, nan=0.5, posinf=1.0, neginf=0.0)
        
        return {
            'red': np.clip(red_curve, 0, 1),
            'green': np.clip(green_curve, 0, 1),
            'blue': np.clip(blue_curve, 0, 1)
        }
    
    def apply_lut(self, image, lut_dict):
        """Apply LUT to image"""
        if image.dtype != np.uint8:
            image = (np.clip(image, 0, 1) * 255).astype(np.uint8)
        
        # Split channels
        b, g, r = cv2.split(image)
        
        # Apply curves
        r_indices = (lut_dict['red'] * 255).astype(np.uint8)
        g_indices = (lut_dict['green'] * 255).astype(np.uint8)
        b_indices = (lut_dict['blue'] * 255).astype(np.uint8)
        
        r_new = r_indices[r]
        g_new = g_indices[g]
        b_new = b_indices[b]
        
        return cv2.merge([b_new, g_new, r_new])
    
    def update_preview(self):
        """Update the preview image with current parameters"""
        if self.original_image is None:
            return
        
        # Start with original image
        processed = self.original_image.copy()
        
        # Apply color temperature and tint
        processed = self.apply_color_temperature(processed, self.params['temperature'], self.params['tint'])
        
        # Create and apply LUT
        lut_dict = self.create_lut_with_params()
        processed = self.apply_lut(processed, lut_dict)
        
        # Apply saturation and vibrance
        processed = self.apply_saturation_vibrance(processed, self.params['saturation'], self.params['vibrance'])
        
        self.processed_image = processed
        
        # Convert for DPG display (RGB to RGBA, normalize to 0-1)
        rgb_image = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
        rgba_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2RGBA)
        flat_image = rgba_image.flatten().astype(np.float32) / 255.0
        
        # Update texture
        if dpg.does_item_exist("preview_texture"):
            height, width = rgba_image.shape[:2]
            dpg.set_value("preview_texture", flat_image)
    
    def parameter_callback(self, sender, app_data, user_data):
        """Callback when any parameter changes"""
        param_name = user_data
        self.params[param_name] = app_data
        self.update_preview()
    
    def load_file_callback(self, sender, app_data, user_data):
        """Callback for file dialog"""
        file_path = app_data['file_path_name']
        if self.load_image(file_path):
            dpg.set_value("status_text", f"Loaded: {Path(file_path).name}")
        else:
            dpg.set_value("status_text", "Failed to load image")
    
    def save_lut_callback(self, sender, app_data, user_data):
        """Save current LUT parameters"""
        lut_dict = self.create_lut_with_params()
        
        # Save as numpy file
        output_path = "custom_lut.npz"
        np.savez_compressed(output_path,
                           red=lut_dict['red'],
                           green=lut_dict['green'],
                           blue=lut_dict['blue'],
                           params=self.params,
                           name='custom_lut')
        
        dpg.set_value("status_text", f"LUT saved as: {output_path}")
    
    def reset_parameters_callback(self, sender, app_data, user_data):
        """Reset to neutral parameters"""
        defaults = {
            'exposure': 0.0, 'contrast': 0.0, 'highlights': 0.0, 'shadows': 0.0,
            'whites': 0.0, 'blacks': 0.0, 'midtones': 0.0, 'shadow_lift': 0.0,
            'highlight_rolloff': 0.0, 'shadow_contrast': 1.0, 'highlight_contrast': 1.0,
            'midtone_contrast': 1.0, 'saturation': 0.0, 'vibrance': 0.0,
            'temperature': 0.0, 'tint': 0.0, 'red_lift': 0.0, 'red_gain': 1.0,
            'red_gamma': 1.0, 'green_lift': 0.0, 'green_gain': 1.0, 'green_gamma': 1.0,
            'blue_lift': 0.0, 'blue_gain': 1.0, 'blue_gamma': 1.0, 'film_grain': 0.0,
            'vintage_fade': 0.0, 'color_grading': 0.0
        }
        
        for param, value in defaults.items():
            self.params[param] = value
            if dpg.does_item_exist(f"{param}_slider"):
                dpg.set_value(f"{param}_slider", value)
        
        self.update_preview()
    
    def export_image_callback(self, sender, app_data, user_data):
        """Export current processed image"""
        if self.processed_image is None:
            dpg.set_value("status_text", "No image to export")
            return
        
        output_path = "exported_image.jpg"
        cv2.imwrite(output_path, self.processed_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        dpg.set_value("status_text", f"Image exported: {output_path}")

def main():
    tuner = UniversalLUTTuner()
    
    dpg.create_context()
    dpg.create_viewport(title="Universal LUT Tuner", width=1600, height=1000)
    
    # File dialog
    with dpg.file_dialog(directory_selector=False, show=False, callback=tuner.load_file_callback,
                        file_count=1, tag="file_dialog_tag", width=700, height=400):
        dpg.add_file_extension("Image Files (*.jpg *.jpeg *.png *.tiff *.dng){.jpg,.jpeg,.png,.tiff,.tiff,.dng}", color=(255, 255, 0, 255))
    
    with dpg.window(label="Universal LUT Tuner", tag="main_window"):
        
        # Top controls
        with dpg.group(horizontal=True):
            dpg.add_button(label="Load Image", callback=lambda: dpg.show_item("file_dialog_tag"))
            dpg.add_button(label="Reset All", callback=tuner.reset_parameters_callback)
            dpg.add_button(label="Save LUT", callback=tuner.save_lut_callback)
            dpg.add_button(label="Export Image", callback=tuner.export_image_callback)
        
        dpg.add_separator()
        
        with dpg.group(horizontal=True):
            # Left panel - Controls
            with dpg.group(width=400):
                
                # Basic Tone Controls
                with dpg.collapsing_header(label="Basic Tone Controls", default_open=True):
                    dpg.add_slider_float(label="Exposure", tag="exposure_slider",
                                       default_value=0.0, min_value=-2.0, max_value=2.0,
                                       callback=tuner.parameter_callback, user_data='exposure')
                    
                    dpg.add_slider_float(label="Contrast", tag="contrast_slider",
                                       default_value=0.0, min_value=-1.0, max_value=1.0,
                                       callback=tuner.parameter_callback, user_data='contrast')
                    
                    dpg.add_slider_float(label="Highlights", tag="highlights_slider",
                                       default_value=0.0, min_value=-1.0, max_value=1.0,
                                       callback=tuner.parameter_callback, user_data='highlights')
                    
                    dpg.add_slider_float(label="Shadows", tag="shadows_slider",
                                       default_value=0.0, min_value=-1.0, max_value=1.0,
                                       callback=tuner.parameter_callback, user_data='shadows')
                    
                    dpg.add_slider_float(label="Whites", tag="whites_slider",
                                       default_value=0.0, min_value=-1.0, max_value=1.0,
                                       callback=tuner.parameter_callback, user_data='whites')
                    
                    dpg.add_slider_float(label="Blacks", tag="blacks_slider",
                                       default_value=0.0, min_value=-1.0, max_value=1.0,
                                       callback=tuner.parameter_callback, user_data='blacks')
                    
                    dpg.add_slider_float(label="Midtones", tag="midtones_slider",
                                       default_value=0.0, min_value=-1.0, max_value=1.0,
                                       callback=tuner.parameter_callback, user_data='midtones')
                
                # Advanced Shadow/Highlight Controls
                with dpg.collapsing_header(label="Advanced Shadow/Highlight Controls"):
                    dpg.add_slider_float(label="Shadow Lift", tag="shadow_lift_slider",
                                       default_value=0.0, min_value=0.0, max_value=0.3,
                                       callback=tuner.parameter_callback, user_data='shadow_lift')
                    
                    dpg.add_slider_float(label="Highlight Rolloff", tag="highlight_rolloff_slider",
                                       default_value=0.0, min_value=0.0, max_value=0.5,
                                       callback=tuner.parameter_callback, user_data='highlight_rolloff')
                    
                    dpg.add_slider_float(label="Shadow Contrast", tag="shadow_contrast_slider",
                                       default_value=1.0, min_value=0.5, max_value=2.0,
                                       callback=tuner.parameter_callback, user_data='shadow_contrast')
                    
                    dpg.add_slider_float(label="Highlight Contrast", tag="highlight_contrast_slider",
                                       default_value=1.0, min_value=0.5, max_value=2.0,
                                       callback=tuner.parameter_callback, user_data='highlight_contrast')
                    
                    dpg.add_slider_float(label="Midtone Contrast", tag="midtone_contrast_slider",
                                       default_value=1.0, min_value=0.5, max_value=2.0,
                                       callback=tuner.parameter_callback, user_data='midtone_contrast')
                
                # Color Controls
                with dpg.collapsing_header(label="Color Controls", default_open=True):
                    dpg.add_slider_float(label="Saturation", tag="saturation_slider",
                                       default_value=0.0, min_value=-1.0, max_value=1.0,
                                       callback=tuner.parameter_callback, user_data='saturation')
                    
                    dpg.add_slider_float(label="Vibrance", tag="vibrance_slider",
                                       default_value=0.0, min_value=-1.0, max_value=1.0,
                                       callback=tuner.parameter_callback, user_data='vibrance')
                    
                    dpg.add_slider_float(label="Temperature", tag="temperature_slider",
                                       default_value=0.0, min_value=-1.0, max_value=1.0,
                                       callback=tuner.parameter_callback, user_data='temperature')
                    
                    dpg.add_slider_float(label="Tint", tag="tint_slider",
                                       default_value=0.0, min_value=-1.0, max_value=1.0,
                                       callback=tuner.parameter_callback, user_data='tint')
                
                # Red Channel Controls
                with dpg.collapsing_header(label="Red Channel (Lift-Gamma-Gain)"):
                    dpg.add_slider_float(label="Red Lift", tag="red_lift_slider",
                                       default_value=0.0, min_value=0.0, max_value=0.3,
                                       callback=tuner.parameter_callback, user_data='red_lift')
                    
                    dpg.add_slider_float(label="Red Gamma", tag="red_gamma_slider",
                                       default_value=1.0, min_value=0.5, max_value=2.0,
                                       callback=tuner.parameter_callback, user_data='red_gamma')
                    
                    dpg.add_slider_float(label="Red Gain", tag="red_gain_slider",
                                       default_value=1.0, min_value=0.5, max_value=1.5,
                                       callback=tuner.parameter_callback, user_data='red_gain')
                
                # Green Channel Controls
                with dpg.collapsing_header(label="Green Channel (Lift-Gamma-Gain)"):
                    dpg.add_slider_float(label="Green Lift", tag="green_lift_slider",
                                       default_value=0.0, min_value=0.0, max_value=0.3,
                                       callback=tuner.parameter_callback, user_data='green_lift')
                    
                    dpg.add_slider_float(label="Green Gamma", tag="green_gamma_slider",
                                       default_value=1.0, min_value=0.5, max_value=2.0,
                                       callback=tuner.parameter_callback, user_data='green_gamma')
                    
                    dpg.add_slider_float(label="Green Gain", tag="green_gain_slider",
                                       default_value=1.0, min_value=0.5, max_value=1.5,
                                       callback=tuner.parameter_callback, user_data='green_gain')
                
                # Blue Channel Controls
                with dpg.collapsing_header(label="Blue Channel (Lift-Gamma-Gain)"):
                    dpg.add_slider_float(label="Blue Lift", tag="blue_lift_slider",
                                       default_value=0.0, min_value=0.0, max_value=0.3,
                                       callback=tuner.parameter_callback, user_data='blue_lift')
                    
                    dpg.add_slider_float(label="Blue Gamma", tag="blue_gamma_slider",
                                       default_value=1.0, min_value=0.5, max_value=2.0,
                                       callback=tuner.parameter_callback, user_data='blue_gamma')
                    
                    dpg.add_slider_float(label="Blue Gain", tag="blue_gain_slider",
                                       default_value=1.0, min_value=0.5, max_value=1.5,
                                       callback=tuner.parameter_callback, user_data='blue_gain')
            
            dpg.add_separator()
            
            # Right panel - Preview
            with dpg.group():
                dpg.add_text("Preview (Load an image to start)")
                
                # Placeholder texture
                placeholder = np.zeros((tuner.image_height, tuner.image_width, 4), dtype=np.float32)
                placeholder[:, :, 3] = 1.0  # Alpha channel
                
                with dpg.texture_registry():
                    dpg.add_raw_texture(tuner.image_width, tuner.image_height, 
                                      placeholder.flatten(), tag="preview_texture", format=dpg.mvFormat_Float_rgba)
                
                dpg.add_image("preview_texture")
        
        dpg.add_separator()
        dpg.add_text("Ready - Load an image to start creating your LUT", tag="status_text")
    
    dpg.set_primary_window("main_window", True)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()

if __name__ == "__main__":
    main()