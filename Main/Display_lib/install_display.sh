#!/bin/bash
# Installation script for ER-TFTM2.25-1 ST7789P3 Display
# For Raspberry Pi Zero 2W

set -e  # Exit on error

echo "========================================="
echo "ST7789P3 Display Installation Script"
echo "========================================="

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo: sudo bash install_display.sh"
    exit 1
fi

# Get the actual user (not root)
ACTUAL_USER=${SUDO_USER:-$USER}
USER_HOME=$(eval echo ~$ACTUAL_USER)

echo ""
echo "Step 1: Installing BCM2835 Library..."
echo "========================================="

cd /tmp
wget --no-check-certificate https://www.airspayce.com/mikem/bcm2835/bcm2835-1.75.tar.gz
tar xzf bcm2835-1.75.tar.gz
cd bcm2835-1.75
./configure
make -j4
make install
ldconfig

echo ""
echo "✓ BCM2835 library installed successfully"
echo ""
echo "Step 2: Downloading Display Tutorial..."
echo "========================================="

cd "$USER_HOME"
mkdir -p ST7789_Display
cd ST7789_Display

wget --no-check-certificate https://www.buydisplay.com/Raspberry_Pi/ER-TFTM2.25-1_Raspberry_Pi_Tutorial.zip
unzip -o ER-TFTM2.25-1_Raspberry_Pi_Tutorial.zip

cd "ER-TFTM2.25-1_Rapberry Pi_Tutorial/ER-TFTM2.25-1"

echo ""
echo "✓ Tutorial files downloaded"
echo ""
echo "Step 3: Modifying Pin Configuration..."
echo "========================================="

# Backup original file
cp st7789.h st7789.h.original

# Modify pin definitions to match your wiring:
# Your connections: DC=GPIO6, RST=GPIO5, BL=GPIO25
# Tutorial default: DC=GPIO24, RST=GPIO25

# Update the pin definitions
sed -i 's/#define RST 25/#define RST 5/' st7789.h
sed -i 's/#define DC  24/#define DC  6/' st7789.h

echo "Modified pin configuration:"
echo "  RST = GPIO 5  (was GPIO 25)"
echo "  DC  = GPIO 6  (was GPIO 24)"
echo ""
echo "✓ Pin configuration updated"
echo ""
echo "Step 4: Compiling Display Code..."
echo "========================================="

# Clean previous build
make clean 2>/dev/null || true

# Compile
make

echo ""
echo "✓ Compilation successful"
echo ""
echo "========================================="
echo "Installation Complete!"
echo "========================================="
echo ""
echo "Your wiring:"
echo "  Display -> Raspberry Pi"
echo "  GND     -> GND"
echo "  VCC     -> 3.3V"
echo "  SCL     -> GPIO 11 (SCLK, Pin 23)"
echo "  SDA     -> GPIO 10 (MOSI, Pin 19)"
echo "  RES     -> GPIO 5  (Pin 29)"
echo "  DC      -> GPIO 6  (Pin 31)"
echo "  CS      -> GPIO 8  (CE0, Pin 24)"
echo "  BLK     -> GPIO 25 (Pin 22) - or 3.3V direct"
echo ""
echo "To run the demo:"
echo "  cd $USER_HOME/ST7789_Display/ER-TFTM2.25-1_Rapberry\ Pi_Tutorial/ER-TFTM2.25-1"
echo "  sudo ./tft"
echo ""
echo "Note: Backlight control (GPIO 25) is handled in software."
echo "      Set to LOW to turn backlight ON (inverted logic)."
echo "========================================="

# Fix permissions
chown -R $ACTUAL_USER:$ACTUAL_USER "$USER_HOME/ST7789_Display"

echo ""
echo "Files are ready in: $USER_HOME/ST7789_Display/"
