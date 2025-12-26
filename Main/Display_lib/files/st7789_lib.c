/***************************************************
 * ST7789 Display Library - Shared Library Version
 * For Python ctypes bindings
 * * Compiles to: libst7789.so
 ***************************************************/

#include <bcm2835.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "st7789.h"

// KEY FIX: Access the global buffer defined in st7789.c
extern char buffer[TFT_WIDTH * TFT_HEIGHT * 2];

// Export these functions for Python to call
#ifdef __cplusplus
extern "C" {
#endif

// Initialize display - call once at startup
int display_init(void) {
    if (!bcm2835_init()) {
        fprintf(stderr, "bcm2835_init failed. Are you running as root?\n");
        return -1;
    }
    
    st7789_begin();
    st7789_clear_screen(0xFFFF);  // Clear to WHITE on init (0xFFFF is white)
    st7789_display();
    
    return 0;
}

// Display a raw RGB565 buffer
// buffer: RGB565 data (2 bytes per pixel)
// width: image width (must be 284)
// height: image height (must be 76)
void display_buffer_rgb565(uint8_t *input_buffer, int width, int height) {
    if (width != TFT_WIDTH || height != TFT_HEIGHT) {
        fprintf(stderr, "Error: Image must be %dx%d, got %dx%d\n", 
                TFT_WIDTH, TFT_HEIGHT, width, height);
        return;
    }
    
    // KEY FIX: Copy from Python input to the GLOBAL display buffer
    memcpy(buffer, input_buffer, TFT_WIDTH * TFT_HEIGHT * 2);
    
    // Send to display
    st7789_display();
}

// Display a raw RGB888 buffer (converts to RGB565)
// buffer: RGB888 data (3 bytes per pixel - R, G, B)
// width: image width (must be 284)
// height: image height (must be 76)
void display_buffer_rgb888(uint8_t *rgb_buffer, int width, int height) {
    if (width != TFT_WIDTH || height != TFT_HEIGHT) {
        fprintf(stderr, "Error: Image must be %dx%d, got %dx%d\n", 
                TFT_WIDTH, TFT_HEIGHT, width, height);
        return;
    }
    
    // Convert RGB888 to RGB565 directly into the global buffer
    // This is faster than calling st7789_draw_point for every pixel
    for (int i = 0; i < width * height; i++) {
        int idx = i * 3;
        uint8_t r = rgb_buffer[idx];
        uint8_t g = rgb_buffer[idx + 1];
        uint8_t b = rgb_buffer[idx + 2];
        
        // Convert to RGB565
        uint16_t color = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);
        
        // Direct write to global buffer (Big Endian for SPI)
        // buffer is char*, so we write high byte then low byte
        buffer[i * 2] = color >> 8;
        buffer[i * 2 + 1] = color & 0xFF;
    }
    
    // Send to display
    st7789_display();
}

// Clear display to solid color (RGB565)
void display_clear(uint16_t color) {
    st7789_clear_screen(color);
    st7789_display();
}

// Draw a single pixel
void display_pixel(int x, int y, uint16_t color) {
    st7789_draw_point(x, y, color);
}

// Refresh display (call after drawing pixels)
void display_refresh(void) {
    st7789_display();
}

// Draw text string
void display_text(int x, int y, const char *text, uint8_t size, uint16_t color) {
    st7789_string(x, y, text, size, 1, color);
}

// Cleanup - call before exit
void display_cleanup(void) {
    bcm2835_spi_end();
    bcm2835_close();
}

#ifdef __cplusplus
}
#endif