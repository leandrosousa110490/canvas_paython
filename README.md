# Python Qt Canvas Application

A Figma-like canvas application built with Python and the Qt framework (PySide6).

## Features

*   Drawing tools: Rectangle, Ellipse, Line, Pen, Triangle
*   Selection and transformation of shapes (move, resize)
    *   Rotation for all item types (shapes, lines, images, pen strokes)
*   Image import and manipulation:
    *   Add images from local files
    *   Move, resize (proportionally with mouse, independently via properties panel), rotate, delete images
    *   Remove image background (using `rembg`)
    *   Brightness adjustment
    *   Image cropping
    *   Save image with all transformations and effects applied
*   Z-Ordering:
    *   Bring to Front
    *   Send to Back
    *   Bring Forward
    *   Send Backward
*   Theming: Light and Dark modes
*   Canvas:
    *   Zoom (mouse wheel, buttons)
    *   Pan (Hand tool)
    *   Changeable background color
*   Eraser tool (pixel-based, rasterizes vector shapes on touch)
*   Properties panel for selected items (color, width, image effects)
*   Basic menu and toolbar structure.

## Prerequisites

*   Python 3.x
*   PySide6
*   Pillow (PIL)
*   rembg

Install dependencies using:
`pip install -r requirements.txt`

## Running the Application

`python app.py` 