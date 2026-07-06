# Banner Processor

A tool for preparing graphics files for large-format printing. I wrote it during my internship at Studio Delta (a large-format print shop) and it's used there in production now.

Before every print run someone had to add registration marks and a border by hand, which took a few minutes and was easy to get slightly crooked. This program does it automatically and saves the finished file.

## What it does

- Adds crosshair registration marks that show where the hanging holes (eyelets) get punched, and picks their number and spacing automatically based on the banner size (default around every 50 cm). All gaps come out equal.
- Adds a white weld border for folding/hanging (default 3.6 cm)
- Draws two edge lines with independent thickness and opacity: an inner line centered on the image edge and an outer line on the edge of the white border
- Keeps the ICC profile and DPI, so a CMYK file comes out as CMYK with its profile
- Reads and writes PDF, and processes several same-size files at once (batch)

![Main window](screens/1_main.jpg)

## Running it

Requirements: Python 3.8+, Pillow, pypdfium2 (for PDF support). Optional: tkinterdnd2 for drag-and-drop.

```bash
pip install Pillow pypdfium2
pip install tkinterdnd2   # optional, enables dragging files onto the window
python main.py
```

Without arguments it launches the GUI. With arguments it runs as a CLI:

```bash
python main.py baner.tif
python main.py baner.tif -o wynik.pdf --width 300 --height 150
python main.py baner.tif --no-border --spacing 40
python main.py baner1.tif baner2.tif --format jpg   # batch, must be the same size
python main.py --help
```

## GUI

The window is laid out like an editor: settings on the left, a large preview on the right. The preview updates live as you change any setting (no button to click). You can zoom with the mouse wheel and pan by dragging, or click "Dopasuj" to fit.

Pick a file (or several at once, or drag them onto the window) and the print dimensions fill in automatically. Buttons +/- next to the horizontal and vertical readouts let you add or remove eyelets by hand; the spacing recalculates to stay even. Warnings show up for low resolution or a margin so large the marks would overlap. Shortcuts: Ctrl+O open, Ctrl+S save, Ctrl+0 fit, Ctrl +/- zoom. Settings (mark spacing, border width and so on) are saved to `banner_processor_config.json` next to the exe/script.

![Preview with registration marks applied](screens/2_podglad.jpg)

## Supported formats

Input: TIFF, JPEG, PNG, PSD, PDF (PDF is rasterized at a chosen DPI)
Output: JPEG (quality 100%), TIFF (LZW), PNG or PDF
Color spaces: RGB and CMYK

## Parameters

All have defaults matched to the print shop workflow:

| Parameter | Default | What it does |
|----------|-----------|---------|
| `marker_size` | 1.0 cm | mark size (10x10 mm) |
| `margin` | 2.0 cm | distance from the edge to the mark axis (center) |
| `target_spacing` | 50.0 cm | target spacing between marks |
| `border` | 3.6 cm | white weld border |
| `inner_line_width` | 0.05 cm | inner line thickness |
| `inner_line_opacity` | 100% | inner line opacity |
| `outer_line_width` | 0.03 cm | outer line thickness |
| `outer_line_opacity` | 70% | outer line opacity |

## How the marks are placed

There are always 4 in the corners. Along each side the program picks the number of intermediate marks so the spacing comes out as close to the target as possible, and every gap on that side is equal. Distances are measured axis to axis (center of one eyelet to the center of the next), and `margin` is the distance from the image edge to the mark axis. Short sides get only the 2 corner marks. In the GUI you can override the count per side with the +/- buttons.

## Building the exe (Windows)

```bash
pip install pyinstaller
pyinstaller BannerProcessor_v2.spec
```

The spec bundles pypdfium2, so PDF support works in the built exe. The finished file lands in `dist/`.

## Known limitations

- The CMYK preview in the GUI is converted to RGB without the ICC profile, so the colors in the preview can differ from the print
- PDF input is rasterized to RGB, and PDF output is a raster PDF without an embedded ICC profile. For CMYK with a profile use TIFF
- If a file has no DPI metadata, the program assumes 150 DPI and shows a warning, in which case you have to enter the dimensions manually

## More

Portfolio: [wojtas.it](https://wojtas.it)
