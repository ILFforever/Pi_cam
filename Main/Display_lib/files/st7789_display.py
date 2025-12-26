#!/usr/bin/env python3
"""
ST7789 Display Library - Python Wrapper
Uses ctypes to call C shared library
"""

import ctypes
import numpy as np
from pathlib import Path

class ST7789Display:
    """Python wrapper for ST7789 C library"""
    
    def __init__(self, lib_path=None):
        """
        Initialize display library
        
        Args:
            lib_path: Path to libst7789.so (optional)
                     If None, searches current directory and /usr/local/lib
        """
        # Find library
        if lib_path is None:
            lib_path = self._find_library()
        
        # Load shared library
        try:
            self.lib = ctypes.CDLL(lib_path)
        except OSError as e:
            raise RuntimeError(f"Failed to load library: {e}\n"
                             f"Make sure libst7789.so is compiled and accessible")
        
        # Define function signatures
        self._setup_functions()
        
        # Initialize display
        result = self.lib.display_init()
        if result != 0:
            raise RuntimeError("Display initialization failed. Are you running as root?")
        
        print("ST7789 Display initialized (284x76 horizontal)")
    
    def _find_library(self):
        """Find libst7789.so in common locations"""
        search_paths = [
            Path.cwd() / "libst7789.so",  # Current directory
            Path("/usr/local/lib/libst7789.so"),  # System install
            Path.home() / "ST7789_Display/ER-TFTM2.25-1_Rapberry Pi_Tutorial/ER-TFTM2.25-1/libst7789.so"
        ]
        
        for path in search_paths:
            if path.exists():
                return str(path)
        
        raise FileNotFoundError(
            "libst7789.so not found. Please compile it first:\n"
            "  make -f Makefile.lib"
        )
    
    def _setup_functions(self):
        """Define C function signatures for ctypes"""
        
        # int display_init(void)
        self.lib.display_init.argtypes = []
        self.lib.display_init.restype = ctypes.c_int
        
        # void display_buffer_rgb888(uint8_t *buffer, int width, int height)
        self.lib.display_buffer_rgb888.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int,
            ctypes.c_int
        ]
        self.lib.display_buffer_rgb888.restype = None
        
        # void display_buffer_rgb565(uint8_t *buffer, int width, int height)
        self.lib.display_buffer_rgb565.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int,
            ctypes.c_int
        ]
        self.lib.display_buffer_rgb565.restype = None
        
        # void display_clear(uint16_t color)
        self.lib.display_clear.argtypes = [ctypes.c_uint16]
        self.lib.display_clear.restype = None
        
        # void display_pixel(int x, int y, uint16_t color)
        self.lib.display_pixel.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint16
        ]
        self.lib.display_pixel.restype = None
        
        # void display_refresh(void)
        self.lib.display_refresh.argtypes = []
        self.lib.display_refresh.restype = None
        
        # void display_text(int x, int y, const char *text, uint8_t size, uint16_t color)
        self.lib.display_text.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint8,
            ctypes.c_uint16
        ]
        self.lib.display_text.restype = None
        
        # void display_cleanup(void)
        self.lib.display_cleanup.argtypes = []
        self.lib.display_cleanup.restype = None
    
    def show_image(self, image_array):
        """
        Display numpy array (from camera or PIL Image)
        
        Args:
            image_array: numpy array, expected shape (76, 284, 3) for horizontal
        """
        # We expect (Height, Width, Channels) = (76, 284, 3)
        # If the array is correct, DO NOT TRANSPOSE IT.
        
        # Validation: Check for the NumPy shape (76, 284, 3)
        if image_array.shape != (76, 284, 3):
             # Just in case we receive the transposed version, flip it back
            if image_array.shape == (284, 76, 3):
                 image_array = np.transpose(image_array, (1, 0, 2))
            else:
                raise ValueError(f"Image must be (76, 284, 3), got {image_array.shape}")
        
        if image_array.dtype != np.uint8:
            image_array = image_array.astype(np.uint8)
        
        # Ensure contiguous memory (crucial for C interop)
        if not image_array.flags['C_CONTIGUOUS']:
            image_array = np.ascontiguousarray(image_array)

        # Flatten and convert to ctypes
        flat = image_array.flatten()
        c_buffer = flat.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
        
        # Pass Width=284, Height=76 to C
        self.lib.display_buffer_rgb888(c_buffer, 284, 76)
    
    def clear(self, color=(0, 0, 0)):
        """
        Clear display to solid color
        
        Args:
            color: (R, G, B) tuple, each 0-255
        """
        r, g, b = color
        # Convert to RGB565
        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        self.lib.display_clear(rgb565)
    
    def draw_pixel(self, x, y, color):
        """
        Draw single pixel
        
        Args:
            x, y: pixel coordinates
            color: (R, G, B) tuple
        """
        r, g, b = color
        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        self.lib.display_pixel(x, y, rgb565)
    
    def refresh(self):
        """Update display (call after drawing pixels)"""
        self.lib.display_refresh()
    
    def draw_text(self, x, y, text, size=12, color=(255, 255, 255)):
        """
        Draw text string
        
        Args:
            x, y: position
            text: string to display
            size: font size (12 or 16)
            color: (R, G, B) tuple
        """
        r, g, b = color
        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        text_bytes = text.encode('utf-8')
        self.lib.display_text(x, y, text_bytes, size, rgb565)
    
    def cleanup(self):
        """Clean up resources"""
        self.lib.display_cleanup()
    
    def __del__(self):
        """Destructor - cleanup on object deletion"""
        try:
            self.cleanup()
        except:
            pass


# Color constants (RGB565 format)
class Colors:
    BLACK   = 0x0000
    WHITE   = 0xFFFF
    RED     = 0xF800
    GREEN   = 0x07E0
    BLUE    = 0x001F
    YELLOW  = 0xFFE0
    CYAN    = 0x07FF
    MAGENTA = 0xF81F


if __name__ == "__main__":
    """Test the display library"""
    import time
    
    print("Testing ST7789 Display Library")
    print("=" * 40)
    
    try:
        # Initialize display
        display = ST7789Display()
        
        # Test 1: Clear to colors
        print("Test 1: Color test...")
        colors = [
            (255, 0, 0, "RED"),
            (0, 255, 0, "GREEN"),
            (0, 0, 255, "BLUE"),
            (255, 255, 0, "YELLOW"),
            (0, 0, 0, "BLACK")
        ]
        
        for r, g, b, name in colors:
            print(f"  {name}")
            display.clear((r, g, b))
            time.sleep(0.5)
        
        # Test 2: Text
        print("Test 2: Text rendering...")
        display.clear((0, 0, 0))
        display.draw_text(10, 10, "ST7789", 16, (255, 255, 255))
        display.draw_text(10, 40, "Python", 16, (0, 255, 0))
        display.draw_text(10, 70, "Library", 16, (255, 0, 0))
        display.refresh()
        time.sleep(2)
        
        # Test 3: Numpy array
        print("Test 3: Numpy array...")
        test_image = np.zeros((284, 76, 3), dtype=np.uint8)
        # Create gradient
        for y in range(284):
            intensity = int((y / 284) * 255)
            test_image[y, :, :] = [intensity, 0, 255 - intensity]
        
        display.show_image(test_image)
        time.sleep(2)
        
        print("\n" + "=" * 40)
        print("All tests passed!")
        print("=" * 40)
        
        # Cleanup
        display.cleanup()
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
