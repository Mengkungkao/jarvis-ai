# Digital electronics and communication protocols

Digital logic uses two states: high (1) and low (0). Common logic
families run at 5 V (classic TTL/CMOS) or 3.3 V (modern CMOS); many
sensors now use 1.8 V. The Raspberry Pi GPIO uses 3.3 V logic and its
pins are NOT 5 V tolerant — connecting a 5 V signal directly to a Pi
GPIO pin can permanently damage the Pi. Use a voltage divider (for
example 1 kΩ and 2 kΩ) or a level shifter to read 5 V signals on a Pi.

The basic logic gates are AND, OR, NOT, NAND, NOR, XOR. NAND and NOR
are universal gates: any logic function can be built from either alone.
A flip-flop stores one bit; a D flip-flop captures its input on a clock
edge. A shift register (like the 74HC595) converts serial data to
parallel outputs and is a cheap way to add output pins.

Binary counting: 8 bits make one byte, holding values 0–255.
Hexadecimal digits represent 4 bits each: 0xFF equals 255. A 10-bit ADC
gives values 0–1023; a 12-bit ADC gives 0–4095. ADC resolution in volts
equals the reference voltage divided by the number of steps. The
Raspberry Pi has no built-in analog input; use an external ADC such as
the MCP3008 (10-bit, SPI) or ADS1115 (16-bit, I2C). Arduino boards have
built-in ADCs.

UART serial uses two data lines: TX (transmit) and RX (receive),
crossed between devices (TX to RX). Both sides must agree on the baud
rate; common rates are 9600 and 115200 bits per second. UART has no
clock line, so accurate timing matters. The classic frame is 8 data
bits, no parity, 1 stop bit (8N1).

I2C uses two lines: SDA (data) and SCL (clock), both open-drain and
requiring pull-up resistors (typically 4.7 kΩ) to the supply. I2C
supports many devices on one bus, each with a 7-bit address (0x03 to
0x77). Standard speed is 100 kHz, fast mode 400 kHz. On a Raspberry Pi,
scan the I2C bus with the command: i2cdetect -y 1. The Whisplay HAT
uses I2C for its audio codec and touch functions.

SPI is a fast full-duplex bus with four lines: MOSI (controller out),
MISO (controller in), SCLK (clock), and CS/SS (chip select, one per
device). SPI easily runs at tens of MHz — displays like the Whisplay
HAT LCD use SPI for fast pixel data. SPI has no addressing; each device
needs its own chip-select line.

I2S is a dedicated digital audio bus with bit clock, word/LR clock, and
data lines; the Whisplay HAT sound card uses I2S for audio samples.

A microcontroller (like an Arduino, AVR, STM32, or ESP32) runs one
program on bare metal with precise timing; a single-board computer
(like a Raspberry Pi) runs a full Linux OS. Use a microcontroller for
hard real-time control and lowest power; use a Pi when you need Linux,
networking, and heavier software. The ESP32 adds built-in WiFi and
Bluetooth and is popular for IoT projects.

Debouncing: mechanical switches bounce for a few milliseconds when
pressed, producing multiple edges; fix it in software by ignoring
changes for 10–50 ms, or in hardware with an RC filter and Schmitt
trigger.
