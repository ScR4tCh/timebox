# Divoom Timebox CLI
Control the divoom timebox using your terminal.
Thanks to derHeinz and his [divoom-aurabox code](https://github.com/derHeinz/divoom-adapter) for giving some hints on how to interpret the protocol.

## Project status
This project is WIP, so not every feature might work as expected yet. Also this tools is communicating with the timebox unidirectional.
This means, that no answers from the box will be processed at the moment.

## What works
* Switching "screens" :  "clock","temp","anim","graph","image","stopwatch","scoreboard
* display images, most formats should be supported thanks to [pillow](https://github.com/python-pillow/Pillow). The images will be scaled to fit the 11x11 matrix
* display animations, either load a series of images from a directory OR a GIF animation. The loaded frames will also be scaled
* display clock and set 12h/24h format as well as color. There are a dozen of possebilities to describe a color, take a look at [colour](https://github.com/vaab/colour)
* display temperature set °C/°F as well as the color
* switch radio on/off

## What does not work (or needs improvements)
* Setting the radios frequency does not yet work
* animations with a shorter framelength "as usual" (I am about to investigate this) might be "glued together" resulting in two or more animations shown after each other
* Error handling is bad at the moment, so be careful what you type. The CLI might not inform you about what went wrong yet.
* ... Documentation ;) ...
* ... No Tests, only tested on my Linux boxes ...

## Future plans
* split CLI and library
* support text "rendering" and marquees
* support everything that could be done using the "original" android app
