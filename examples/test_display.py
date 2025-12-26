import time
import board
import busio
import digitalio
from PIL import Image
import adafruit_rgb_display.st7789 as st7789

# Display configuration
DISPLAY_WIDTH = 76
DISPLAY_HEIGHT = 284

# Pin definitions
CS_PIN = board.CE0
DC_PIN = board.D6
RESET_PIN = board.D5
BACKLIGHT_PIN = board.D25

def send_command(display, command, data=None):
    """Send raw command to ST7789P3"""
    # This is a workaround - the library should handle it
    pass

def initialize_display():
    """Initialize ST7789P3 with specific settings"""
    
    spi = busio.SPI(clock=board.SCK, MOSI=board.MOSI)
    
    cs = digitalio.DigitalInOut(CS_PIN)
    dc = digitalio.DigitalInOut(DC_PIN)
    reset = digitalio.DigitalInOut(RESET_PIN)
    
    # Backlight ON
    backlight = digitalio.DigitalInOut(BACKLIGHT_PIN)
    backlight.switch_to_output()
    backlight.value = False
    
    # Hardware reset
    reset.switch_to_output()
    reset.value = False
    time.sleep(0.01)
    reset.value = True
    time.sleep(0.12)
    
    # ST7789P3 specific initialization
    # Try these offset combinations specific to P3 variant
    configs_to_try = [
        # (width, height, x_offset, y_offset, rotation)
        (76, 284, 0, 0, 0),
        (76, 284, 34, 0, 0),
        (76, 284, 0, 20, 0),
        (80, 160, 26, 1, 90),  # Some P3 variants need these
        (80, 160, 0, 0, 90),
    ]
    
    for w, h, x_off, y_off, rot in configs_to_try:
        print(f"Testing: {w}x{h}, offsets=({x_off},{y_off}), rotation={rot}")
        
        try:
            display = st7789.ST7789(
                spi,
                cs=cs,
                dc=dc,
                rst=reset,
                width=w,
                height=h,
                rotation=rot,
                baudrate=4000000,
                x_offset=x_off,
                y_offset=y_off,
            )
            
            # Create test pattern
            img_width = display.width
            img_height = display.height
            
            # Red screen test
            print(f"  Creating {img_width}x{img_height} red image...")
            image = Image.new("RGB", (img_width, img_height), color=(255, 0, 0))
            display.image(image)
            time.sleep(1.5)
            
            # Green screen test
            print(f"  Creating {img_width}x{img_height} green image...")
            image = Image.new("RGB", (img_width, img_height), color=(0, 255, 0))
            display.image(image)
            time.sleep(1.5)
            
            # Blue screen test
            print(f"  Creating {img_width}x{img_height} blue image...")
            image = Image.new("RGB", (img_width, img_height), color=(0, 0, 255))
            display.image(image)
            
            print(f"✓ SUCCESS! Use: width={w}, height={h}, x_offset={x_off}, y_offset={y_off}, rotation={rot}")
            return display
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            continue
    
    print("\n⚠ None of the standard configs worked.")
    print("Your display may need a different library or custom driver.")
    return None

def main():
    print("=" * 50)
    print("ST7789P3 Display Initialization Test")
    print("=" * 50)
    
    display = initialize_display()
    
    if display:
        print("\n✓ Display is working!")
        print("Update your code with the successful parameters shown above.")
    else:
        print("\n✗ Could not initialize display.")
        print("\nNext steps:")
        print("1. Search for 'ST7789P3 76x284' specific drivers")
        print("2. Check if seller provided sample code")
        print("3. Try different Python libraries (luma.lcd, fbcp)")
    
    return 0 if display else 1

if __name__ == "__main__":
    exit(main())