"""
Universal LUT Tuner with DearPyGui - FIXED VERSION
Create any film look with comprehensive tone and color controls
Run on laptop to create luts
"""

import numpy as np
import cv2
import dearpygui.dearpygui as dpg
from pathlib import Path
import os
import tempfile
import subprocess
import shutil
import traceback
import uuid
SCRIPT_DIR = Path(__file__).parent.absolute()

class UniversalLUTTuner:
    def __init__(self):
        self.original_image = None
        self.processed_image = None
        self.image_width = 1800       
        self.image_height = 1050
        self.texture_created = False
        self.current_texture_tag = "preview_texture"
        self.last_update_time = 0
        self.update_delay = 0.5  # 50ms minimum between updates

        
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
    
    def process_dng_with_dcraw(self, dng_path):
        """Process DNG with dcraw - with better error handling"""
        print(f"Processing DNG: {dng_path}")
        
        dcraw_exe = SCRIPT_DIR / "dcraw.exe"
        if not dcraw_exe.exists():
            print(f"❌ dcraw.exe not found at: {dcraw_exe}")
            print("Place dcraw.exe in the same folder as this script")
            return None
        print(f"✅ Using local dcraw: {dcraw_exe}")
                
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                temp_output = temp_path / "processed.tiff"
                
                # More conservative dcraw parameters
                cmd = [
                    str(dcraw_exe),
                    "-w",          # Use camera white balance
                    "-b", "1.0",   # Brightness
                    "-q", "2",     # Quality (2 = bilinear)
                    "-o", "1",     # sRGB output
                    "-T",          # TIFF output
                    "-6",          # 16-bit
                    "-c",          # Write to stdout
                    str(dng_path)
                ]
                
                print(f"Running dcraw command: {' '.join(cmd)}")
                
                with open(temp_output, 'wb') as f:
                    result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, 
                                          check=True, timeout=30)
                
                if not temp_output.exists() or temp_output.stat().st_size == 0:
                    print("❌ dcraw produced no output")
                    return None
                
                # Load the processed image
                image = cv2.imread(str(temp_output), cv2.IMREAD_COLOR)
                if image is None:
                    print(f"❌ Could not load processed TIFF: {temp_output}")
                    return None
                
                print(f"✅ Successfully processed DNG: {image.shape}")
                return image
                
        except subprocess.TimeoutExpired:
            print("❌ dcraw timeout (30s)")
            return None
        except subprocess.CalledProcessError as e:
            print(f"❌ dcraw error: {e.stderr.decode() if e.stderr else 'Unknown error'}")
            return None
        except Exception as e:
            print(f"❌ dcraw processing error: {e}")
            traceback.print_exc()
            return None
    
    def load_image(self, file_path):
        """Load and prepare image for processing - with comprehensive error handling"""
        try:
            print(f"Loading image: {file_path}")
            path = Path(file_path)
            
            if not path.exists():
                print(f"❌ File does not exist: {file_path}")
                return False
            
            # Check file size (warn if > 50MB)
            file_size = path.stat().st_size / (1024 * 1024)  # MB
            print(f"File size: {file_size:.1f} MB")
            if file_size > 50:
                print("⚠️ Large file - may take time to process")
            
            image = None
            
            if path.suffix.lower() in ['.dng', '.DNG']:
                # Process DNG with dcraw
                image = self.process_dng_with_dcraw(path)
                if image is None:
                    print("❌ Failed to process DNG file")
                    return False
            else:
                # Load regular image file
                print("Loading regular image file...")
                image = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if image is None:
                    print(f"❌ Could not load image: {path}")
                    print("Supported formats: JPG, PNG, TIFF, DNG")
                    return False
            
            print(f"Original image shape: {image.shape}")
            
            # Resize image for preview while maintaining aspect ratio
            height, width = image.shape[:2]
            aspect = width / height
            
            print(f"Original aspect ratio: {aspect:.2f}")
            
            # Calculate new dimensions to fit within preview area
            if aspect > self.image_width / self.image_height:
                # Image is wider - fit to width
                new_width = self.image_width
                new_height = int(self.image_width / aspect)
            else:
                # Image is taller - fit to height
                new_height = self.image_height
                new_width = int(self.image_height * aspect)
            
            # Ensure dimensions are reasonable
            new_width = max(100, min(new_width, self.image_width))
            new_height = max(100, min(new_height, self.image_height))
            
            print(f"Resizing to: {new_width}x{new_height}")
            
            # Resize with high-quality interpolation
            self.original_image = cv2.resize(image, (new_width, new_height), 
                                           interpolation=cv2.INTER_LANCZOS4)
            
            print(f"Resized image shape: {self.original_image.shape}")
            
            # Update the preview
            success = self.update_preview()
            if not success:
                print("❌ Failed to update preview")
                return False
            
            print("✅ Image loaded successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error loading image: {e}")
            traceback.print_exc()
            return False
    
    def create_or_update_texture(self, rgba_array, width, height):
        """Create or update texture with proper error handling"""
        try:
            flat_image = rgba_array.flatten().astype(np.float32) / 255.0
            
            # Always delete and recreate - simpler and more reliable
            if hasattr(self, 'current_texture_tag') and dpg.does_item_exist(self.current_texture_tag):
                dpg.delete_item(self.current_texture_tag)
            
            # Generate unique texture tag
            new_texture_tag = f"texture_{uuid.uuid4().hex[:8]}"
            
            # Create new texture
            dpg.add_raw_texture(width, height, flat_image, 
                            tag=new_texture_tag, format=dpg.mvFormat_Float_rgba,
                            parent="texture_registry")
            
            # Delete old image widget and create new one
            if dpg.does_item_exist("preview_image"):
                dpg.delete_item("preview_image")
            
            # Create new image widget in the correct parent
            dpg.add_image(new_texture_tag, tag="preview_image", parent="preview_group")
            
            # Store current texture tag
            self.current_texture_tag = new_texture_tag
            self.texture_created = True
            
            print(f"✅ Texture created successfully: {new_texture_tag}")
            return True
            
        except Exception as e:
            print(f"❌ Texture creation error: {e}")
            traceback.print_exc()
            return False
        
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
        
        try:
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
        except Exception as e:
            print(f"Error in color temperature adjustment: {e}")
            return image
    
    def apply_saturation_vibrance(self, image, saturation, vibrance):
        """Apply saturation and vibrance adjustments"""
        if saturation == 0 and vibrance == 0:
            return image
        
        try:
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
        except Exception as e:
            print(f"Error in saturation/vibrance adjustment: {e}")
            return image
    
    def create_lut_with_params(self):
        """Create comprehensive LUT with current parameters"""
        try:
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
        except Exception as e:
            print(f"Error creating LUT: {e}")
            # Return neutral LUT
            neutral_curve = np.linspace(0, 1, 256)
            return {'red': neutral_curve, 'green': neutral_curve, 'blue': neutral_curve}
    
    def apply_lut(self, image, lut_dict):
        """Apply LUT to image"""
        try:
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
        except Exception as e:
            print(f"Error applying LUT: {e}")
            return image
    
    def update_preview(self):
        """Update the preview image with current parameters"""
        if self.original_image is None:
            print("No original image to process")
            return False
        
        try:
            print("Updating preview...")
            
            # Start with original image
            processed = self.original_image.copy()
            
            # Apply color temperature and tint
            processed = self.apply_color_temperature(processed, 
                                                   self.params['temperature'], 
                                                   self.params['tint'])
            
            # Create and apply LUT
            lut_dict = self.create_lut_with_params()
            processed = self.apply_lut(processed, lut_dict)
            
            # Apply saturation and vibrance
            processed = self.apply_saturation_vibrance(processed, 
                                                     self.params['saturation'], 
                                                     self.params['vibrance'])
            
            self.processed_image = processed
            
            # Convert for DPG display (BGR to RGB, then add alpha channel)
            rgb_image = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            
            # Add alpha channel
            height, width = rgb_image.shape[:2]
            rgba_image = np.zeros((height, width, 4), dtype=np.uint8)
            rgba_image[:, :, :3] = rgb_image  # RGB channels
            rgba_image[:, :, 3] = 255  # Alpha channel (fully opaque)
            
            # Update or create texture
            success = self.create_or_update_texture(rgba_image, width, height)
            if not success:
                print("Failed to update texture")
                return False
            
            print("Preview updated successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error updating preview: {e}")
            traceback.print_exc()
            return False
    
    def parameter_callback(self, sender, app_data, user_data):
        """Callback when any parameter changes - with throttling"""
        try:
            import time
            current_time = time.time()
            
            param_name = user_data
            self.params[param_name] = app_data
            print(f"Parameter changed: {param_name} = {app_data}")
            
            # Throttle updates during dragging
            if current_time - self.last_update_time > self.update_delay:
                self.update_preview()
                self.last_update_time = current_time
            else:
                # Schedule a delayed update
                if not hasattr(self, 'pending_update'):
                    self.pending_update = True
                    def delayed_update():
                        time.sleep(0.1)  # Wait a bit
                        if hasattr(self, 'pending_update') and self.pending_update:
                            self.update_preview()
                            self.pending_update = False
                    
                    import threading
                    threading.Thread(target=delayed_update, daemon=True).start()
            
        except Exception as e:
            print(f"Error in parameter callback: {e}")
    
    def load_file_callback(self, sender, app_data, user_data):
        """Callback for file dialog"""
        try:
            file_path = app_data['file_path_name']
            print(f"File dialog selected: {file_path}")
            
            dpg.set_value("status_text", f"Loading: {Path(file_path).name}...")
            
            if self.load_image(file_path):
                dpg.set_value("status_text", f"✅ Loaded: {Path(file_path).name}")
            else:
                dpg.set_value("status_text", f"❌ Failed to load: {Path(file_path).name}")
                
        except Exception as e:
            print(f"Error in load file callback: {e}")
            dpg.set_value("status_text", f"❌ Error loading file: {e}")
    
    def save_lut_callback(self, sender, app_data, user_data):
        """Save current LUT parameters"""
        try:
            lut_dict = self.create_lut_with_params()
            
            # Save as numpy file with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"custom_lut_{timestamp}.npz"
            
            np.savez_compressed(output_path,
                               red=lut_dict['red'],
                               green=lut_dict['green'],
                               blue=lut_dict['blue'],
                               params=self.params,
                               name='custom_lut')
            
            print(f"LUT saved: {output_path}")
            dpg.set_value("status_text", f"✅ LUT saved as: {output_path}")
            
        except Exception as e:
            print(f"Error saving LUT: {e}")
            dpg.set_value("status_text", f"❌ Error saving LUT: {e}")
    
    def reset_parameters_callback(self, sender, app_data, user_data):
        """Reset to neutral parameters"""
        try:
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
            dpg.set_value("status_text", "✅ Parameters reset to defaults")
            
        except Exception as e:
            print(f"Error resetting parameters: {e}")
            dpg.set_value("status_text", f"❌ Error resetting: {e}")
    
    def export_image_callback(self, sender, app_data, user_data):
        """Export current processed image"""
        try:
            if self.processed_image is None:
                dpg.set_value("status_text", "❌ No image to export")
                return
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"exported_image_{timestamp}.jpg"
            
            cv2.imwrite(output_path, self.processed_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"Image exported: {output_path}")
            dpg.set_value("status_text", f"✅ Image exported: {output_path}")
            
        except Exception as e:
            print(f"Error exporting image: {e}")
            dpg.set_value("status_text", f"❌ Error exporting: {e}")

def main():
    print("Starting Universal LUT Tuner...")
    tuner = UniversalLUTTuner()
    
    try:
        dpg.create_context()
        dpg.create_viewport(title="Universal LUT Tuner - FIXED", width=2300, height=1200)
        
        # File dialog
        with dpg.file_dialog(directory_selector=False, show=False, 
                            callback=tuner.load_file_callback,
                            file_count=1, tag="file_dialog_tag", width=700, height=400):
            dpg.add_file_extension("Image Files{.jpg,.jpeg,.png,.tiff,.tif,.dng,.DNG}", 
                                 color=(255, 255, 0, 255))
        
        # Create texture registry first
        with dpg.texture_registry(tag="texture_registry"):
            pass  
        
        with dpg.window(label="Universal LUT Tuner", tag="main_window"):
            
            # Top controls
            with dpg.group(horizontal=True):
                dpg.add_button(label="Load Image", 
                             callback=lambda: dpg.show_item("file_dialog_tag"))
                dpg.add_button(label="Reset All", callback=tuner.reset_parameters_callback)
                dpg.add_button(label="Save LUT", callback=tuner.save_lut_callback)
                dpg.add_button(label="Export Image", callback=tuner.export_image_callback)
            
            dpg.add_separator()
            
            with dpg.group(horizontal=True):
                # Left panel - Controls
                with dpg.child_window(width=450, height=900, horizontal_scrollbar=False):
                    
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
                
                with dpg.child_window(width=1800    , height=1060, tag="preview_group"):
                    dpg.add_text("Preview", color=(255, 255, 255))
                    dpg.add_separator()

            
            dpg.add_separator()
            dpg.add_text("Ready - Load an image to start creating your LUT", tag="status_text")
        
        dpg.set_primary_window("main_window", True)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        
        print("✅ GUI started successfully")
        print("📁 Load an image to begin tuning")
        print("💾 Supported formats: JPG, PNG, TIFF, DNG")
        
        dpg.start_dearpygui()
        
    except Exception as e:
        print(f"❌ GUI Error: {e}")
        traceback.print_exc()
    finally:
        try:
            dpg.destroy_context()
        except:
            pass
        print("GUI closed")

if __name__ == "__main__":
    # Check dependencies
    missing_deps = []
    
    try:
        import cv2
    except ImportError:
        missing_deps.append("opencv-python")
    
    try:
        import dearpygui.dearpygui as dpg
    except ImportError:
        missing_deps.append("dearpygui")
    
    try:
        import numpy as np
    except ImportError:
        missing_deps.append("numpy")
    
    if missing_deps:
        print("❌ Missing dependencies:")
        for dep in missing_deps:
            print(f"   pip install {dep}")
        print("\nInstall missing dependencies and try again.")
    else:
        print("✅ All dependencies found")
        main()