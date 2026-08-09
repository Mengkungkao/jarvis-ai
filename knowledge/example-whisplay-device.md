# Example knowledge: my Whisplay chatbot device

This is an example training document. Replace it with files about the task
you want JARVIS to master, then run: ./jarvis-cli train

## Hardware

My JARVIS device is a Raspberry Pi Zero 2W with a PiSugar Whisplay HAT.
The Whisplay HAT has a color LCD screen, one physical button, an RGB status
LED, an on-board speaker, and a microphone. Power comes from a PiSugar 3
1200mAh battery board.

## Whisplay button gestures

With the whisplay daemon running, a single click switches between apps, a
long press launches or foregrounds the selected app, and four rapid clicks
ask the foreground app to exit.

## Useful commands

The Whisplay driver is installed with: sudo bash install_driver.sh from the
Whisplay repository, followed by a reboot. Daemon logs can be inspected
with: journalctl -u whisplay-daemon.service -f. The daemon settings live in
~/.whisplay-daemon/settings.json.
