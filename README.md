# Flatscape

Flatscape takes a video file as input, then combines a portion of each video frame into a single output image file.

## Usage

The easiest way to get started is to edit and run the example file `example.py`. `input_path` should point to a video file, and `output_path` specifies where generated images should go.

### CLI Options

Same names are used when calling in Python instead of CLI, unless otherwise noted.

  * `--input`: input video file path. `input_path` in Python.
  * `--name`: optional base name for output image. Default is to use input filename as base for output.
  * `--path`: output path. `output_path` in Python.
  * `-p --pixels`: width, in pixels, of scan/print section for each sampled line. Default is 6. Integer.
  * `-o --offset`: number of off-axis offset pixels when printing. Value can be positive or negative. Will result in a diagonal image. Integer.
  * `-c --slicecount`: override the number of slices, skipping frames if necessary. Integer.
  * `-l --customline`: override which line to scan. Default is the center line. Integer.
  * `-v --vertical`: vertical scan, traversing horizontal slices up or down. Boolean.
  * `-t --traverse`: traverse scanline across frame instead of holding the scanline in place. Boolean.
  * `-r --reverse`: reverse scan direction. Boolean.
  * `-i --info`: print extra info and logs. Boolean.
