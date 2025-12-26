# Building the ST7789 Display Library - Step by Step Guide

## Prerequisites

Install the ST7789 Lib from BuyDisplay using
```bash
sudo bash install_display.sh
```
Display C code must be present (st7789.c, st7789.h)

# Step-by-Step Build Process
## Step 1: Navigate to Directory
```bash
bashcd ~/ST7789_Display/ER-TFTM2.25-1_Rapberry\ Pi_Tutorial/ER-TFTM2.25-1/
```
## Step 2: Clean Previous Builds
```bash
bashrm -f *.o libst7789.so tft
```
## Step 3: Copy New Files
Copy these 4 files to the current directory:
```bash
st7789_lib.c
Makefile.lib
st7789_display.py
camera_viewfinder.py
```
## Step 4: Build Shared Library
```bash
bashmake -f Makefile.lib
```

**Expected output:**
```
gcc -Wall -O2 -fPIC -c st7789.c -o st7789.o
gcc -Wall -O2 -fPIC -c st7789_lib.c -o st7789_lib.o
gcc -shared -o libst7789.so st7789_lib.o st7789.o -lbcm2835 -lm

==========================================
Shared library built: libst7789.so
==========================================
```
## Step 5: Verify Library Exists
```bash
bashls -lh libst7789.so

Should show: -rwxr-xr-x 1 pi pi 199K ... libst7789.so
```
## Step 6: Test Display Library
```bash
bashsudo python3 st7789_display.py

Should show color tests and text.
```
## Step 7: Run Camera Viewfinder
```bash
bashsudo python3 camera_viewfinder.py
```