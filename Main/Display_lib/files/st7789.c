/***************************************************
//Web: http://www.buydisplay.com
EastRising Technology Co.,LTD
****************************************************/
// Modified for horizontal
#include <bcm2835.h>
#include <stdio.h>
#include "st7789.h"

char buffer[TFT_WIDTH * TFT_HEIGHT * 2];

void command(char cmd)
{
    bcm2835_gpio_write(DC, LOW);
    bcm2835_spi_transfer(cmd);
}

void data(char cmd)
{
    bcm2835_gpio_write(DC, HIGH);
    bcm2835_spi_transfer(cmd);
}

void st7789_begin()
{
    bcm2835_gpio_fsel(RST, BCM2835_GPIO_FSEL_OUTP);
    bcm2835_gpio_fsel(DC, BCM2835_GPIO_FSEL_OUTP);

    bcm2835_spi_begin();
    bcm2835_spi_setBitOrder(BCM2835_SPI_BIT_ORDER_MSBFIRST);   // The default
    bcm2835_spi_setDataMode(BCM2835_SPI_MODE0);                // The default
    bcm2835_spi_setClockDivider(BCM2835_SPI_CLOCK_DIVIDER_64); // The default
    bcm2835_spi_chipSelect(BCM2835_SPI_CS0);                   // The default
    bcm2835_spi_setChipSelectPolarity(BCM2835_SPI_CS0, LOW);   // the default

    bcm2835_gpio_write(RST, HIGH);
    bcm2835_delay(10);
    bcm2835_gpio_write(RST, LOW);
    bcm2835_delay(10);
    bcm2835_gpio_write(RST, HIGH);
    bcm2835_delay(50);

    command(0xB2);
    data(0x0C);
    data(0x0C);
    data(0x00);
    data(0x33);
    data(0x33);

    command(0xB0);
    data(0x00);
    data(0xE0);

    command(0x36);
    data(0x70); // Horizontal orientation (landscape)

    command(0x3A);
    data(0x05);

    command(0xB7);
    data(0x45);

    command(0xBB);
    data(0x1D);

    command(0xC0);
    data(0x2C);

    command(0xC2);
    data(0x01);

    command(0xC3);
    data(0x19);

    command(0xC4);
    data(0x20);

    command(0xC6);
    data(0x0F);

    command(0xD0);
    data(0xA4);
    data(0xA1);

    command(0xD6);
    data(0xA1);

    command(0xE0);
    data(0xD0);
    data(0x10);
    data(0x21);
    data(0x14);
    data(0x15);
    data(0x2D);
    data(0x41);
    data(0x44);
    data(0x4F);
    data(0x28);
    data(0x0E);
    data(0x0C);
    data(0x1D);
    data(0x1F);

    command(0xE1);
    data(0xD0);
    data(0x0F);
    data(0x1B);
    data(0x0D);
    data(0x0D);
    data(0x26);
    data(0x42);
    data(0x54);
    data(0x50);
    data(0x3E);
    data(0x1A);
    data(0x18);
    data(0x22);
    data(0x25);

    command(0x11);
    bcm2835_delay(120);
    command(0x29);

    st7789_clear();
}

void st7789_clear()
{
    int i;
    for (i = 0; i < sizeof(buffer); i++)
    {
        buffer[i] = 0;
    }
}

void st7789_draw_point(int x, int y, uint16_t hwColor)
{
    if (x >= TFT_WIDTH || y >= TFT_HEIGHT)
    {
        return;
    }
    buffer[x * 2 + y * TFT_WIDTH * 2] = hwColor >> 8;
    buffer[x * 2 + y * TFT_WIDTH * 2 + 1] = hwColor;
}

void st7789_char1616(uint16_t x, uint16_t y, uint8_t chChar, uint16_t hwColor)
{
    uint8_t i, j;
    uint8_t chTemp = 0, y0 = y;

    for (i = 0; i < 32; i++)
    {
        chTemp = Font1612[chChar - 0x30][i];
        for (j = 0; j < 8; j++)
        {
            if (chTemp & 0x80)
            {
                st7789_draw_point(x, y, hwColor);
            }
            else
            {
                st7789_draw_point(x, y, 0);
            }
            chTemp <<= 1;
            y++;
            if ((y - y0) == 16)
            {
                y = y0;
                x++;
                break;
            }
        }
    }
}

void st7789_char3216(uint16_t x, uint16_t y, uint8_t chChar, uint16_t hwColor)
{
    uint8_t i, j;
    uint8_t chTemp = 0, y0 = y;

    for (i = 0; i < 64; i++)
    {
        chTemp = Font3216[chChar - 0x30][i];
        for (j = 0; j < 8; j++)
        {
            if (chTemp & 0x80)
            {
                st7789_draw_point(x, y, hwColor);
            }
            else
            {
                st7789_draw_point(x, y, 0);
            }

            chTemp <<= 1;
            y++;
            if ((y - y0) == 32)
            {
                y = y0;
                x++;
                break;
            }
        }
    }
}

void st7789_char(uint16_t x, uint16_t y, char acsii, char size, char mode, uint16_t hwColor)
{
    uint16_t i, j, y0 = y;
    char temp;
    uint8_t ch = acsii - ' ';
    for (i = 0; i < size; i++)
    {
        if (size == 12)
        {
            if (mode)
                temp = Font1206[ch][i];
            else
                temp = ~Font1206[ch][i];
        }
        else
        {
            if (mode)
                temp = Font1608[ch][i];
            else
                temp = ~Font1608[ch][i];
        }
        for (j = 0; j < 8; j++)
        {
            if (temp & 0x80)
                st7789_draw_point(x, y, hwColor);
            else
                st7789_draw_point(x, y, 0);
            temp <<= 1;
            y++;
            if ((y - y0) == size)
            {
                y = y0;
                x++;
                break;
            }
        }
    }
}

void st7789_string(uint16_t x, uint16_t y, const char *pString, uint8_t Size, uint8_t Mode, uint16_t hwColor)
{
    while (*pString != '\0')
    {
        if (x > (TFT_WIDTH - Size / 2))
        {
            x = 0;
            y += Size;
            if (y > (TFT_HEIGHT - Size))
            {
                y = x = 0;
            }
        }

        st7789_char(x, y, *pString, Size, Mode, hwColor);
        x += Size / 2;
        pString++;
    }
}

void st7789_mono_bitmap(uint16_t x, uint16_t y, const uint8_t *pBmp, uint16_t chWidth, uint16_t chHeight, uint16_t hwColor)
{
    uint16_t i, j, byteWidth = (chWidth + 7) / 8;
    for (j = 0; j < chHeight; j++)
    {
        for (i = 0; i < chWidth; i++)
        {
            if (*(pBmp + j * byteWidth + i / 8) & (128 >> (i & 7)))
            {
                st7789_draw_point(x + i, y + j, hwColor);
            }
        }
    }
}

void st7789_bitmap24(uint16_t x, uint16_t y, uint8_t *pBmp, uint16_t chWidth, uint16_t chHeight)
{
    uint16_t i, j;
    uint16_t hwColor;
    uint32_t temp;

    for (j = 0; j < chHeight; j++)
    {
        for (i = 0; i < chWidth; i++)
        {
            temp = *(unsigned int *)(pBmp + i * 3 + j * 3 * chWidth);
            hwColor = RGB(((temp >> 16) & 0xFF),
                          ((temp >> 8) & 0xFF),
                          (temp & 0xFF));
            st7789_draw_point(x + i, y + chHeight - 1 - j, hwColor);
        }
    }
}
void st7789_display()
{
    // COMMAND 2A: Column Address Set (Mapped to X-Axis / Long Axis in Landscape)
    // We must use the 320-pixel axis offset here (18)
    command(0x2a);
    data(0);
    data(0 + 0x12);        // Start at 18 (0x12)
    data((TFT_WIDTH + 0x11) >> 8);  // End at Width + 17
    data((TFT_WIDTH + 0x11) & 0xFF);

    // COMMAND 2B: Row Address Set (Mapped to Y-Axis / Short Axis in Landscape)
    // We must use the 240-pixel axis offset here (82)
    command(0x2b);
    data(0);
    data(0 + 0x52);        // Start at 82 (0x52)
    data((TFT_HEIGHT + 0x51) >> 8); // End at Height + 81
    data((TFT_HEIGHT + 0x51) & 0xFF);

    command(0x2C);
    bcm2835_gpio_write(DC, HIGH);
    bcm2835_spi_transfern(buffer, sizeof(buffer));
}

void st7789_clear_screen(uint16_t hwColor)
{
    uint16_t i, j;
    for (i = 0; i < TFT_HEIGHT; i++)
    {
        for (j = 0; j < TFT_WIDTH; j++)
        {
            st7789_draw_point(j, i, hwColor);
        }
    }
}
