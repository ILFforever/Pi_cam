#!/usr/bin/env python3
"""
1D LUT Creator - Interactive GUI Tool
Create custom 1D LUTs with real-time preview and reference images
Requires: pip install dearpygui opencv-python numpy pillow
"""

import dearpygui.dearpygui as dpg
import cv2
import numpy as np
from pathlib import Path
import time

class LUTCreator:
    def __init__(self):
        self.current_image = None
        self.reference_image = None
        self.preview_size = (800, 600)
        
        # LUT parameters - all start at neutral/linear
        self.params = {
            # SECTION 1: Global Tonal Controls
            'contrast': 0.0,         # -0.5 to 0.5 (S-curve strength)
            'brightness': 0.0,       # -0.3 to 0.3 (overall exposure)
            'exposure': 0.0,         # -2.0 to 2.0 (stops, multiplicative)
            'blacks_lift': 0.0,      # 0.0 to 0.2 (raise shadow floor - faded look)
            'whites_clip': 1.0,      # 0.8 to 1.0 (lower ceiling for soft highlights)
            'toe': 0.0,              # 0.0 to 0.5 (film-style shadow rolloff)
            'shoulder': 0.0,         # 0.0 to 0.5 (film-style highlight rolloff)
            
            # SECTION 2: Gamma/Power Controls
            'gamma': 1.0,            # 0.5 to 2.0 (global gamma)
            'red_gamma': 1.0,        # 0.5 to 2.0 (per-channel gamma)
            'green_gamma': 1.0,
            'blue_gamma': 1.0,
            
            # SECTION 3: Lift/Gamma/Gain (Professional Color Grading)
            'lift_master': 0.0,      # -0.15 to 0.15 (shadows)
            'gamma_master': 1.0,     # 0.5 to 1.5 (midtones)
            'gain_master': 1.0,      # 0.7 to 1.3 (highlights)
            
            # SECTION 4: Per-Channel Shadows/Mids/Highlights
            'red_shadows': 0.0,      # -0.2 to 0.2 (lift blacks)
            'red_midtones': 1.0,     # 0.5 to 1.5 (contrast)
            'red_highlights': 1.0,   # 0.7 to 1.3 (boost/reduce)
            
            'green_shadows': 0.0,
            'green_midtones': 1.0,
            'green_highlights': 1.0,
            
            'blue_shadows': 0.0,
            'blue_midtones': 1.0,
            'blue_highlights': 1.0,
            
            # SECTION 5: White Balance / Color Temperature
            'temperature': 0.0,      # -1.0 to 1.0 (cool to warm)
            'tint': 0.0,             # -1.0 to 1.0 (green to magenta)
            
            # SECTION 6: Vibrance/Saturation (approximated in 1D)
            'vibrance': 0.0,         # -0.3 to 0.3 (smart saturation boost)
            'saturation': 0.0,       # -0.5 to 0.5 (overall saturation)
            
            # SECTION 7: Color Tint Controls
            'red_tint': 0.0,         # -0.2 to 0.2 (overall red cast)
            'green_tint': 0.0,       # -0.2 to 0.2 (overall green cast)
            'blue_tint': 0.0,        # -0.2 to 0.2 (overall blue cast)
            
            # SECTION 8: Curve Shape Controls
            'curve_type': 0,         # 0=Linear, 1=Log, 2=Exp, 3=S-curve
            'curve_strength': 0.0,   # 0.0 to 1.0 (how much of curve to apply)
            
            # SECTION 9: Channel Mixing (subtle)
            'red_from_green': 0.0,   # -0.1 to 0.1 (add green to red channel)
            'red_from_blue': 0.0,    # -0.1 to 0.1 (add blue to red channel)
            'green_from_red': 0.0,
            'green_from_blue': 0.0,
            'blue_from_red': 0.0,
            'blue_from_green': 0.0,
            
            # SECTION 10: Hue Approximation (limited in 1D)
            'hue_shift': 0.0,        # -0.3 to 0.3 (approximate hue rotation)
        }
        
        self.lut_name = "custom_lut"
        self.processing_time = 0.0
        
    def generate_lut_from_params(self):
        """Generate 1D LUT curves from current parameters - COMPREHENSIVE VERSION"""
        x = np.linspace(0, 1, 256)
        
        # ===== HELPER FUNCTIONS =====
        
        def apply_s_curve(vals, strength):
            """S-curve for contrast"""
            if abs(strength) < 0.001:
                return vals
            midpoint = 0.5
            steepness = strength * 4.0
            curved = 1.0 / (1.0 + np.exp(-steepness * (vals - midpoint)))
            curve_min = 1.0 / (1.0 + np.exp(steepness * midpoint))
            curve_max = 1.0 / (1.0 + np.exp(-steepness * (1.0 - midpoint)))
            return (curved - curve_min) / (curve_max - curve_min)
        
        def apply_log_curve(vals, strength):
            """Logarithmic curve (compresses highlights, expands shadows)"""
            if strength < 0.001:
                return vals
            return np.log1p(vals * strength) / np.log1p(strength)
        
        def apply_exp_curve(vals, strength):
            """Exponential curve (expands highlights, compresses shadows)"""
            if strength < 0.001:
                return vals
            return (np.exp(vals * strength) - 1) / (np.exp(strength) - 1)
        
        def apply_toe(vals, amount):
            """Film-style toe (gentle shadow rolloff)"""
            if amount < 0.001:
                return vals
            # Toe affects lower range
            return np.where(vals < 0.18,
                          vals * (1.0 - amount * (0.18 - vals) / 0.18),
                          vals)
        
        def apply_shoulder(vals, amount):
            """Film-style shoulder (gentle highlight rolloff)"""
            if amount < 0.001:
                return vals
            # Shoulder affects upper range
            return np.where(vals > 0.75,
                          0.75 + (vals - 0.75) * (1.0 - amount * (vals - 0.75) / 0.25),
                          vals)
        
        # ===== START WITH LINEAR =====
        red = x.copy()
        green = x.copy()
        blue = x.copy()
        
        # ===== STEP 1: EXPOSURE (multiplicative, first) =====
        if abs(self.params['exposure']) > 0.001:
            exp_mult = 2.0 ** self.params['exposure']  # Stops to multiplier
            red = red * exp_mult
            green = green * exp_mult
            blue = blue * exp_mult
        
        # ===== STEP 2: WHITE BALANCE / TEMPERATURE / TINT =====
        if abs(self.params['temperature']) > 0.001:
            # Temperature: positive = warm (more red/yellow), negative = cool (more blue)
            temp = self.params['temperature']
            red = red * (1.0 + temp * 0.3)
            blue = blue * (1.0 - temp * 0.3)
        
        if abs(self.params['tint']) > 0.001:
            # Tint: positive = magenta (more red/blue), negative = green
            tint = self.params['tint']
            if tint > 0:
                red = red * (1.0 + tint * 0.2)
                blue = blue * (1.0 + tint * 0.2)
                green = green * (1.0 - tint * 0.15)
            else:
                green = green * (1.0 - tint * 0.2)
        
        # ===== STEP 3: GLOBAL GAMMA =====
        if abs(self.params['gamma'] - 1.0) > 0.001:
            red = np.power(np.clip(red, 0, 1), 1.0 / self.params['gamma'])
            green = np.power(np.clip(green, 0, 1), 1.0 / self.params['gamma'])
            blue = np.power(np.clip(blue, 0, 1), 1.0 / self.params['gamma'])
        
        # ===== STEP 4: BRIGHTNESS (additive) =====
        if abs(self.params['brightness']) > 0.001:
            red = red + self.params['brightness']
            green = green + self.params['brightness']
            blue = blue + self.params['brightness']
        
        # ===== STEP 5: CONTRAST (S-curve) =====
        if abs(self.params['contrast']) > 0.001:
            red = apply_s_curve(red, self.params['contrast'])
            green = apply_s_curve(green, self.params['contrast'])
            blue = apply_s_curve(blue, self.params['contrast'])
        
        # ===== STEP 6: CURVE TYPE (Log/Exp/S-curve alternative) =====
        if self.params['curve_type'] == 1 and self.params['curve_strength'] > 0.001:
            # Log curve
            strength = self.params['curve_strength'] * 2.0
            red = apply_log_curve(np.clip(red, 0, 1), strength)
            green = apply_log_curve(np.clip(green, 0, 1), strength)
            blue = apply_log_curve(np.clip(blue, 0, 1), strength)
        elif self.params['curve_type'] == 2 and self.params['curve_strength'] > 0.001:
            # Exp curve
            strength = self.params['curve_strength'] * 2.0
            red = apply_exp_curve(np.clip(red, 0, 1), strength)
            green = apply_exp_curve(np.clip(green, 0, 1), strength)
            blue = apply_exp_curve(np.clip(blue, 0, 1), strength)
        elif self.params['curve_type'] == 3 and self.params['curve_strength'] > 0.001:
            # Alternative S-curve
            red = apply_s_curve(red, self.params['curve_strength'])
            green = apply_s_curve(green, self.params['curve_strength'])
            blue = apply_s_curve(blue, self.params['curve_strength'])
        
        # ===== STEP 7: TOE AND SHOULDER (Film response) =====
        if self.params['toe'] > 0.001:
            red = apply_toe(red, self.params['toe'])
            green = apply_toe(green, self.params['toe'])
            blue = apply_toe(blue, self.params['toe'])
        
        if self.params['shoulder'] > 0.001:
            red = apply_shoulder(red, self.params['shoulder'])
            green = apply_shoulder(green, self.params['shoulder'])
            blue = apply_shoulder(blue, self.params['shoulder'])
        
        # ===== STEP 8: BLACKS LIFT / WHITES CLIP =====
        if self.params['blacks_lift'] > 0.001:
            lift = self.params['blacks_lift']
            red = red * (1.0 - lift) + lift
            green = green * (1.0 - lift) + lift
            blue = blue * (1.0 - lift) + lift
        
        if abs(self.params['whites_clip'] - 1.0) > 0.001:
            clip_point = self.params['whites_clip']
            red = np.minimum(red, clip_point)
            green = np.minimum(green, clip_point)
            blue = np.minimum(blue, clip_point)
        
        # ===== STEP 9: LIFT/GAMMA/GAIN (Professional grading) =====
        if abs(self.params['lift_master']) > 0.001:
            # Lift affects shadows
            shadow_mask = np.where(x < 0.3, (0.3 - x) / 0.3, 0.0)
            red = red + self.params['lift_master'] * shadow_mask
            green = green + self.params['lift_master'] * shadow_mask
            blue = blue + self.params['lift_master'] * shadow_mask
        
        if abs(self.params['gamma_master'] - 1.0) > 0.001:
            # Gamma affects midtones
            midtone_mask = np.where((x >= 0.2) & (x <= 0.8),
                                   1.0 - np.abs(x - 0.5) / 0.3, 0.0)
            red = red * (1.0 + (self.params['gamma_master'] - 1.0) * midtone_mask)
            green = green * (1.0 + (self.params['gamma_master'] - 1.0) * midtone_mask)
            blue = blue * (1.0 + (self.params['gamma_master'] - 1.0) * midtone_mask)
        
        if abs(self.params['gain_master'] - 1.0) > 0.001:
            # Gain affects highlights
            highlight_mask = np.where(x > 0.7, (x - 0.7) / 0.3, 0.0)
            red = red * (1.0 + (self.params['gain_master'] - 1.0) * highlight_mask)
            green = green * (1.0 + (self.params['gain_master'] - 1.0) * highlight_mask)
            blue = blue * (1.0 + (self.params['gain_master'] - 1.0) * highlight_mask)
        
        # ===== STEP 10: PER-CHANNEL GAMMA =====
        if abs(self.params['red_gamma'] - 1.0) > 0.001:
            red = np.power(np.clip(red, 0, 1), 1.0 / self.params['red_gamma'])
        if abs(self.params['green_gamma'] - 1.0) > 0.001:
            green = np.power(np.clip(green, 0, 1), 1.0 / self.params['green_gamma'])
        if abs(self.params['blue_gamma'] - 1.0) > 0.001:
            blue = np.power(np.clip(blue, 0, 1), 1.0 / self.params['blue_gamma'])
        
        # ===== STEP 11: PER-CHANNEL SHADOWS/MIDS/HIGHLIGHTS =====
        # Shadows
        shadow_mask = np.where(x < 0.3, (0.3 - x) / 0.3, 0.0)
        red = red + self.params['red_shadows'] * shadow_mask
        green = green + self.params['green_shadows'] * shadow_mask
        blue = blue + self.params['blue_shadows'] * shadow_mask
        
        # Midtones
        midtone_mask = np.where((x >= 0.3) & (x <= 0.7),
                               1.0 - np.abs(x - 0.5) / 0.2, 0.0)
        red = red * (1.0 + (self.params['red_midtones'] - 1.0) * midtone_mask)
        green = green * (1.0 + (self.params['green_midtones'] - 1.0) * midtone_mask)
        blue = blue * (1.0 + (self.params['blue_midtones'] - 1.0) * midtone_mask)
        
        # Highlights
        highlight_mask = np.where(x > 0.7, (x - 0.7) / 0.3, 0.0)
        red = red * (1.0 + (self.params['red_highlights'] - 1.0) * highlight_mask)
        green = green * (1.0 + (self.params['green_highlights'] - 1.0) * highlight_mask)
        blue = blue * (1.0 + (self.params['blue_highlights'] - 1.0) * highlight_mask)
        
        # ===== STEP 12: COLOR TINTS =====
        if abs(self.params['red_tint']) > 0.001:
            red = red + self.params['red_tint']
        if abs(self.params['green_tint']) > 0.001:
            green = green + self.params['green_tint']
        if abs(self.params['blue_tint']) > 0.001:
            blue = blue + self.params['blue_tint']
        
        # ===== STEP 13: SATURATION / VIBRANCE (approximated) =====
        if abs(self.params['saturation']) > 0.001 or abs(self.params['vibrance']) > 0.001:
            # Calculate luminance (approximate)
            luma = 0.299 * red + 0.587 * green + 0.114 * blue
            
            # Saturation: push away from or toward gray
            if abs(self.params['saturation']) > 0.001:
                sat = self.params['saturation']
                red = luma + (red - luma) * (1.0 + sat)
                green = luma + (green - luma) * (1.0 + sat)
                blue = luma + (blue - luma) * (1.0 + sat)
            
            # Vibrance: smart saturation (affects muted colors more)
            if abs(self.params['vibrance']) > 0.001:
                vib = self.params['vibrance']
                # Calculate current saturation level
                max_rgb = np.maximum(np.maximum(red, green), blue)
                min_rgb = np.minimum(np.minimum(red, green), blue)
                current_sat = np.where(max_rgb > 0.001, (max_rgb - min_rgb) / max_rgb, 0.0)
                # Apply vibrance more to less saturated areas
                vib_strength = vib * (1.0 - current_sat)
                red = luma + (red - luma) * (1.0 + vib_strength)
                green = luma + (green - luma) * (1.0 + vib_strength)
                blue = luma + (blue - luma) * (1.0 + vib_strength)
        
        # ===== STEP 14: CHANNEL MIXING =====
        if (abs(self.params['red_from_green']) > 0.001 or abs(self.params['red_from_blue']) > 0.001 or
            abs(self.params['green_from_red']) > 0.001 or abs(self.params['green_from_blue']) > 0.001 or
            abs(self.params['blue_from_red']) > 0.001 or abs(self.params['blue_from_green']) > 0.001):
            
            # Save originals
            r_orig = red.copy()
            g_orig = green.copy()
            b_orig = blue.copy()
            
            # Mix channels
            red = r_orig + g_orig * self.params['red_from_green'] + b_orig * self.params['red_from_blue']
            green = g_orig + r_orig * self.params['green_from_red'] + b_orig * self.params['green_from_blue']
            blue = b_orig + r_orig * self.params['blue_from_red'] + g_orig * self.params['blue_from_green']
        
        # ===== STEP 15: HUE SHIFT (approximated in 1D) =====
        if abs(self.params['hue_shift']) > 0.001:
            # Simplified hue shift by rotating RGB
            # This is a crude approximation - true hue shift needs 3D LUT
            shift = self.params['hue_shift']
            r_orig = red.copy()
            g_orig = green.copy()
            b_orig = blue.copy()
            
            # Rotate color channels (limited hue shift)
            if shift > 0:
                red = r_orig * (1 - shift * 0.3) + g_orig * (shift * 0.3)
                green = g_orig * (1 - shift * 0.3) + b_orig * (shift * 0.3)
                blue = b_orig * (1 - shift * 0.3) + r_orig * (shift * 0.3)
            else:
                shift = -shift
                red = r_orig * (1 - shift * 0.3) + b_orig * (shift * 0.3)
                green = g_orig * (1 - shift * 0.3) + r_orig * (shift * 0.3)
                blue = b_orig * (1 - shift * 0.3) + g_orig * (shift * 0.3)
        
        # ===== FINAL CLAMP =====
        red = np.clip(red, 0.0, 1.0)
        green = np.clip(green, 0.0, 1.0)
        blue = np.clip(blue, 0.0, 1.0)
        
        return red, green, blue
    
    def apply_lut_to_image(self, image, red_lut, green_lut, blue_lut):
        """Apply LUT to image using OpenCV (fast)"""
        start = time.perf_counter()
        
        # Split channels
        b, g, r = cv2.split(image)
        
        # Convert LUT to uint8 lookup tables
        r_table = (red_lut * 255).astype(np.uint8)
        g_table = (green_lut * 255).astype(np.uint8)
        b_table = (blue_lut * 255).astype(np.uint8)
        
        # Apply LUTs
        r_new = cv2.LUT(r, r_table)
        g_new = cv2.LUT(g, g_table)
        b_new = cv2.LUT(b, b_table)
        
        # Merge back
        result = cv2.merge([b_new, g_new, r_new])
        
        self.processing_time = (time.perf_counter() - start) * 1000
        return result
    
    def update_preview(self):
        """Update the preview image with current LUT"""
        if self.current_image is None:
            return
        
        # Generate LUT from current parameters
        red_lut, green_lut, blue_lut = self.generate_lut_from_params()
        
        # Apply to image
        result = self.apply_lut_to_image(self.current_image.copy(), red_lut, green_lut, blue_lut)
        
        # Resize for display
        display_img = cv2.resize(result, self.preview_size)
        
        # Convert to RGBA for DearPyGui
        display_img = cv2.cvtColor(display_img, cv2.COLOR_BGR2RGBA)
        display_img = display_img.astype(np.float32) / 255.0
        
        # Update texture
        dpg.set_value("preview_texture", display_img.flatten())
        
        # Update processing time display
        dpg.set_value("processing_time", f"Processing: {self.processing_time:.1f}ms")
    
    def load_image(self, sender, app_data):
        """Load image from file"""
        selections = app_data['selections']
        if not selections:
            return
        
        filepath = list(selections.values())[0]
        
        # Load image
        img = cv2.imread(filepath)
        if img is None:
            print(f"Failed to load: {filepath}")
            return
        
        self.current_image = img
        self.reference_image = img.copy()  # Save original as reference
        print(f"Loaded: {filepath} ({img.shape[1]}x{img.shape[0]})")
        
        # Update reference texture with original
        display_ref = cv2.resize(self.reference_image, self.preview_size)
        display_ref = cv2.cvtColor(display_ref, cv2.COLOR_BGR2RGBA)
        display_ref = display_ref.astype(np.float32) / 255.0
        dpg.set_value("reference_texture", display_ref.flatten())
        
        # Update preview with LUT applied
        self.update_preview()
    
    def load_reference_image(self, sender, app_data):
        """Load reference image for comparison - REMOVED, now uses original"""
        pass
    
    def save_lut(self):
        """Save current LUT as .npz file"""
        red_lut, green_lut, blue_lut = self.generate_lut_from_params()
        
        output_dir = Path("./custom_luts")
        output_dir.mkdir(exist_ok=True)
        
        filename = f"{self.lut_name}.npz"
        filepath = output_dir / filename
        
        np.savez(filepath,
                red=red_lut,
                green=green_lut,
                blue=blue_lut,
                name=self.lut_name)
        
        print(f"Saved LUT: {filepath}")
        dpg.set_value("save_status", f"Saved: {filename}")
    
    def reset_all(self):
        """Reset all parameters to neutral"""
        # Reset parameters dict
        neutral_values = {
            # Values that should be 0.0
            'contrast': 0.0, 'brightness': 0.0, 'exposure': 0.0, 'blacks_lift': 0.0,
            'toe': 0.0, 'shoulder': 0.0, 'lift_master': 0.0, 'temperature': 0.0,
            'tint': 0.0, 'vibrance': 0.0, 'saturation': 0.0, 'red_tint': 0.0,
            'green_tint': 0.0, 'blue_tint': 0.0, 'curve_strength': 0.0,
            'red_from_green': 0.0, 'red_from_blue': 0.0, 'green_from_red': 0.0,
            'green_from_blue': 0.0, 'blue_from_red': 0.0, 'blue_from_green': 0.0,
            'hue_shift': 0.0, 'red_shadows': 0.0, 'green_shadows': 0.0, 'blue_shadows': 0.0,
            # Values that should be 1.0
            'gamma': 1.0, 'red_gamma': 1.0, 'green_gamma': 1.0, 'blue_gamma': 1.0,
            'gamma_master': 1.0, 'gain_master': 1.0, 'red_midtones': 1.0,
            'green_midtones': 1.0, 'blue_midtones': 1.0, 'red_highlights': 1.0,
            'green_highlights': 1.0, 'blue_highlights': 1.0, 'whites_clip': 1.0,
            # Curve type should be 0
            'curve_type': 0,
        }
        
        # Update all slider values
        for param_name, value in neutral_values.items():
            if dpg.does_item_exist(param_name):
                dpg.set_value(param_name, value)
            self.params[param_name] = value
        
        # Update preview
        self.update_preview()
        print("Reset all parameters to neutral")
    
    def parameter_changed(self, sender, value):
        """Called when any parameter slider changes"""
        param_name = sender
        self.params[param_name] = value
        self.update_preview()
    
    def curve_type_changed(self, sender, value):
        """Called when curve type combo changes"""
        curve_map = {"Linear": 0, "Log": 1, "Exp": 2, "S-Curve": 3}
        self.params['curve_type'] = curve_map.get(value, 0)
        self.update_preview()
    
    def name_changed(self, sender, value):
        """Called when LUT name changes"""
        self.lut_name = value
    
    def create_gui(self):
        """Create the DearPyGui interface"""
        dpg.create_context()
        
        # Create texture for preview (RGBA)
        preview_data = np.zeros((self.preview_size[1], self.preview_size[0], 4), dtype=np.float32)
        
        with dpg.texture_registry():
            dpg.add_raw_texture(width=self.preview_size[0], 
                              height=self.preview_size[1],
                              default_value=preview_data.flatten(),
                              format=dpg.mvFormat_Float_rgba,
                              tag="preview_texture")
            
            dpg.add_raw_texture(width=self.preview_size[0],
                              height=self.preview_size[1],
                              default_value=preview_data.flatten(),
                              format=dpg.mvFormat_Float_rgba,
                              tag="reference_texture")
        
        # File dialogs
        with dpg.file_dialog(directory_selector=False, show=False, 
                           callback=self.load_image, tag="file_dialog",
                           width=700, height=400):
            dpg.add_file_extension(".*")
            dpg.add_file_extension(".jpg", color=(255, 255, 0, 255))
            dpg.add_file_extension(".png", color=(255, 0, 255, 255))
            dpg.add_file_extension(".jpeg", color=(255, 255, 0, 255))
        
        with dpg.file_dialog(directory_selector=False, show=False,
                           callback=self.load_reference_image, tag="ref_file_dialog",
                           width=700, height=400):
            dpg.add_file_extension(".*")
            dpg.add_file_extension(".jpg", color=(255, 255, 0, 255))
            dpg.add_file_extension(".png", color=(255, 0, 255, 255))
        
        # Main window
        with dpg.window(label="1D LUT Creator", tag="main_window", no_close=True):
            
            # Top controls
            with dpg.group(horizontal=True):
                dpg.add_button(label="Load Image", callback=lambda: dpg.show_item("file_dialog"))
                dpg.add_button(label="Save LUT", callback=lambda: self.save_lut())
                dpg.add_button(label="Reset All", callback=lambda: self.reset_all())
            
            dpg.add_separator()
            
            # LUT name input
            with dpg.group(horizontal=True):
                dpg.add_text("LUT Name:")
                dpg.add_input_text(default_value="custom_lut", 
                                 callback=self.name_changed,
                                 width=200)
                dpg.add_text("", tag="save_status")
            
            dpg.add_separator()
            
            # Main layout: Controls on left, images on right
            with dpg.group(horizontal=True):
                
                # Left side: Controls (scrollable)
                with dpg.child_window(width=450, height=700):
                    
                    # SECTION 1: Global Tonal Controls
                    with dpg.collapsing_header(label="GLOBAL TONAL CONTROLS", default_open=True):
                        dpg.add_text("Exposure (stops)")
                        dpg.add_slider_float(tag="exposure", default_value=0.0, min_value=-2.0, max_value=2.0,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Brightness")
                        dpg.add_slider_float(tag="brightness", default_value=0.0, min_value=-0.3, max_value=0.3,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Contrast")
                        dpg.add_slider_float(tag="contrast", default_value=0.0, min_value=-0.5, max_value=0.5,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Global Gamma")
                        dpg.add_slider_float(tag="gamma", default_value=1.0, min_value=0.5, max_value=2.0,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Blacks Lift (Faded Look)")
                        dpg.add_slider_float(tag="blacks_lift", default_value=0.0, min_value=0.0, max_value=0.2,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Whites Clip (Soft Highlights)")
                        dpg.add_slider_float(tag="whites_clip", default_value=1.0, min_value=0.8, max_value=1.0,
                                           callback=self.parameter_changed, width=400)
                    
                    # SECTION 2: Film Response Curves
                    with dpg.collapsing_header(label="FILM RESPONSE CURVES", default_open=False):
                        dpg.add_text("Toe (Shadow Rolloff)")
                        dpg.add_slider_float(tag="toe", default_value=0.0, min_value=0.0, max_value=0.5,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Shoulder (Highlight Rolloff)")
                        dpg.add_slider_float(tag="shoulder", default_value=0.0, min_value=0.0, max_value=0.5,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Curve Type")
                        dpg.add_combo(tag="curve_type", items=["Linear", "Log", "Exp", "S-Curve"],
                                    default_value="Linear", callback=self.curve_type_changed, width=400)
                        
                        dpg.add_text("Curve Strength")
                        dpg.add_slider_float(tag="curve_strength", default_value=0.0, min_value=0.0, max_value=1.0,
                                           callback=self.parameter_changed, width=400)
                    
                    # SECTION 3: Lift/Gamma/Gain (Professional)
                    with dpg.collapsing_header(label="LIFT / GAMMA / GAIN", default_open=False):
                        dpg.add_text("Lift (Shadows)")
                        dpg.add_slider_float(tag="lift_master", default_value=0.0, min_value=-0.15, max_value=0.15,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Gamma (Midtones)")
                        dpg.add_slider_float(tag="gamma_master", default_value=1.0, min_value=0.5, max_value=1.5,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Gain (Highlights)")
                        dpg.add_slider_float(tag="gain_master", default_value=1.0, min_value=0.7, max_value=1.3,
                                           callback=self.parameter_changed, width=400)
                    
                    # SECTION 4: White Balance
                    with dpg.collapsing_header(label="WHITE BALANCE", default_open=False):
                        dpg.add_text("Temperature (Cool <-> Warm)")
                        dpg.add_slider_float(tag="temperature", default_value=0.0, min_value=-1.0, max_value=1.0,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Tint (Green <-> Magenta)")
                        dpg.add_slider_float(tag="tint", default_value=0.0, min_value=-1.0, max_value=1.0,
                                           callback=self.parameter_changed, width=400)
                    
                    # SECTION 5: Saturation/Vibrance
                    with dpg.collapsing_header(label="SATURATION / VIBRANCE", default_open=False):
                        dpg.add_text("Saturation")
                        dpg.add_slider_float(tag="saturation", default_value=0.0, min_value=-0.5, max_value=0.5,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Vibrance (Smart Saturation)")
                        dpg.add_slider_float(tag="vibrance", default_value=0.0, min_value=-0.3, max_value=0.3,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Hue Shift (Approximate)")
                        dpg.add_slider_float(tag="hue_shift", default_value=0.0, min_value=-0.3, max_value=0.3,
                                           callback=self.parameter_changed, width=400)
                    
                    # SECTION 6: Per-Channel Gamma
                    with dpg.collapsing_header(label="PER-CHANNEL GAMMA", default_open=False):
                        dpg.add_text("Red Gamma", color=(255, 100, 100))
                        dpg.add_slider_float(tag="red_gamma", default_value=1.0, min_value=0.5, max_value=2.0,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Green Gamma", color=(100, 255, 100))
                        dpg.add_slider_float(tag="green_gamma", default_value=1.0, min_value=0.5, max_value=2.0,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Blue Gamma", color=(100, 150, 255))
                        dpg.add_slider_float(tag="blue_gamma", default_value=1.0, min_value=0.5, max_value=2.0,
                                           callback=self.parameter_changed, width=400)
                    
                    # SECTION 7: Red Channel
                    with dpg.collapsing_header(label="RED CHANNEL", default_open=False):
                        dpg.add_text("Shadows", color=(255, 100, 100))
                        dpg.add_slider_float(tag="red_shadows", default_value=0.0, min_value=-0.2, max_value=0.2,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Midtones", color=(255, 100, 100))
                        dpg.add_slider_float(tag="red_midtones", default_value=1.0, min_value=0.5, max_value=1.5,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Highlights", color=(255, 100, 100))
                        dpg.add_slider_float(tag="red_highlights", default_value=1.0, min_value=0.7, max_value=1.3,
                                           callback=self.parameter_changed, width=400)
                    
                    # SECTION 8: Green Channel
                    with dpg.collapsing_header(label="GREEN CHANNEL", default_open=False):
                        dpg.add_text("Shadows", color=(100, 255, 100))
                        dpg.add_slider_float(tag="green_shadows", default_value=0.0, min_value=-0.2, max_value=0.2,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Midtones", color=(100, 255, 100))
                        dpg.add_slider_float(tag="green_midtones", default_value=1.0, min_value=0.5, max_value=1.5,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Highlights", color=(100, 255, 100))
                        dpg.add_slider_float(tag="green_highlights", default_value=1.0, min_value=0.7, max_value=1.3,
                                           callback=self.parameter_changed, width=400)
                    
                    # SECTION 9: Blue Channel
                    with dpg.collapsing_header(label="BLUE CHANNEL", default_open=False):
                        dpg.add_text("Shadows", color=(100, 150, 255))
                        dpg.add_slider_float(tag="blue_shadows", default_value=0.0, min_value=-0.2, max_value=0.2,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Midtones", color=(100, 150, 255))
                        dpg.add_slider_float(tag="blue_midtones", default_value=1.0, min_value=0.5, max_value=1.5,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Highlights", color=(100, 150, 255))
                        dpg.add_slider_float(tag="blue_highlights", default_value=1.0, min_value=0.7, max_value=1.3,
                                           callback=self.parameter_changed, width=400)
                    
                    # SECTION 10: Color Tints
                    with dpg.collapsing_header(label="COLOR TINTS", default_open=False):
                        dpg.add_text("Red Tint", color=(255, 100, 100))
                        dpg.add_slider_float(tag="red_tint", default_value=0.0, min_value=-0.2, max_value=0.2,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Green Tint", color=(100, 255, 100))
                        dpg.add_slider_float(tag="green_tint", default_value=0.0, min_value=-0.2, max_value=0.2,
                                           callback=self.parameter_changed, width=400)
                        
                        dpg.add_text("Blue Tint", color=(100, 150, 255))
                        dpg.add_slider_float(tag="blue_tint", default_value=0.0, min_value=-0.2, max_value=0.2,
                                           callback=self.parameter_changed, width=400)
                    
                    # SECTION 11: Channel Mixing
                    with dpg.collapsing_header(label="CHANNEL MIXING (Advanced)", default_open=False):
                        dpg.add_text("Add to Red from:")
                        dpg.add_slider_float(tag="red_from_green", default_value=0.0, min_value=-0.1, max_value=0.1,
                                           callback=self.parameter_changed, width=400, label="Green")
                        dpg.add_slider_float(tag="red_from_blue", default_value=0.0, min_value=-0.1, max_value=0.1,
                                           callback=self.parameter_changed, width=400, label="Blue")
                        
                        dpg.add_text("Add to Green from:")
                        dpg.add_slider_float(tag="green_from_red", default_value=0.0, min_value=-0.1, max_value=0.1,
                                           callback=self.parameter_changed, width=400, label="Red")
                        dpg.add_slider_float(tag="green_from_blue", default_value=0.0, min_value=-0.1, max_value=0.1,
                                           callback=self.parameter_changed, width=400, label="Blue")
                        
                        dpg.add_text("Add to Blue from:")
                        dpg.add_slider_float(tag="blue_from_red", default_value=0.0, min_value=-0.1, max_value=0.1,
                                           callback=self.parameter_changed, width=400, label="Red")
                        dpg.add_slider_float(tag="blue_from_green", default_value=0.0, min_value=-0.1, max_value=0.1,
                                           callback=self.parameter_changed, width=400, label="Green")
                
                # Right side: Image previews
                with dpg.child_window(width=850):
                    dpg.add_text("Preview with LUT", color=(100, 255, 100))
                    dpg.add_image("preview_texture")
                    dpg.add_text("", tag="processing_time")
                    
                    dpg.add_separator()
                    
                    dpg.add_text("Original Image (No LUT)", color=(255, 200, 100))
                    dpg.add_image("reference_texture")
        
        dpg.create_viewport(title="1D LUT Creator - Interactive Tool", 
                          width=1280, height=800)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.set_primary_window("main_window", True)
        dpg.start_dearpygui()
        dpg.destroy_context()

def main():
    print("1D LUT Creator - Interactive Tool")
    print("="*50)
    print("Controls:")
    print("  - Load Image: Your photo to grade")
    print("  - Top image: Preview with LUT applied")
    print("  - Bottom image: Original without LUT")
    print("  - Adjust sliders to create your look")
    print("  - Save LUT: Export as .npz file")
    print("  - Reset All: Start over")
    print("="*50)
    
    creator = LUTCreator()
    creator.create_gui()

if __name__ == "__main__":
    main()
