import numpy as np
import matplotlib.pyplot as plt

# Load the raw array
raw_data = np.load("C:/Users/paeki/OneDrive/Desktop/Pi_cam/photo001.npy")

# Check the data properties
print(f"Shape: {raw_data.shape}")           # e.g., (1944, 2592) - height x width
print(f"Data type: {raw_data.dtype}")       # e.g., uint16
print(f"Min value: {raw_data.min()}")       # e.g., 64 (black level)
print(f"Max value: {raw_data.max()}")       # e.g., 4095 (12-bit sensor)
print(f"Mean value: {raw_data.mean()}")     # Average brightness

# Look at a small section
print(f"Top-left 4x4 pixels:\n{raw_data[:4, :4]}")