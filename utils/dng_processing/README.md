# DNG Processing Utilities

Tools for processing RAW DNG files captured from the Raspberry Pi camera.

## Files

### fujifilm_lut.py
Apply Fujifilm film simulations to DNG/RAW images. Includes:
- Acros (Black & White)
- Classic Chrome
- Velvia (Vibrant colors)

### lut_creator.py
Create custom Look-Up Tables (LUTs) for color grading and film simulation.

### lut_tester.py
Test LUTs on sample images to preview effects before applying to full batches.

### ui_lut.py
User interface for applying LUTs to images.

## LUTs Directory

Contains pre-made Fujifilm film simulation LUTs:
- `fujifilm_acros.npz` - Black and white film look
- `fujifilm_classic_chrome.npz` - Muted, low-contrast colors
- `fujifilm_velvia.npz` - Saturated, vibrant colors

## Usage

```python
# Example: Apply Fujifilm Velvia to a DNG file
python3 fujifilm_lut.py input.dng --lut velvia --output output.jpg
```

## Notes

- These tools work with DNG files captured by the camera scripts
- Processing can be done on the Pi or transferred to a more powerful computer
- LUTs are stored in NumPy .npz format for fast loading
