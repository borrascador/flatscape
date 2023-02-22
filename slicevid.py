import sys, os
import cv2
import numpy as np
import argparse
import math
from pathlib import Path

DEFAULT_PIXEL_WIDTH = 6

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=argparse.FileType('r'), help="input video file")
    ap.add_argument("--name", type=str, help="optional base name for output image")
    ap.add_argument("--path", type=Path)
    ap.add_argument("-p", "--pixels", type=int, help="number of pixels to sample")
    ap.add_argument("-o", "--offset", type=int, default=0, help="number of off-axis offset pixels")
    ap.add_argument("-c", "--slicecount", type=int, help="override with number of slices")
    ap.add_argument("-v", "--vertical", action='store_true', help="vertical scan")
    ap.add_argument("-t", "--traverse", action='store_true', help="traverse scanline across frame")
    ap.add_argument("-r", "--reverse", action='store_true', help="reverse scan direction")
    ap.add_argument("-i", "--info", action='store_true', help="print extra info")
    ap.add_argument("-b", "--batch", action='store_true', help="make four common images variants")
    args = vars(ap.parse_args())
    vs = VideoSlicer(args)
    vs.main()

class VideoSlicer:
    def __init__(self, args, as_cli=True):
        if as_cli:
            self.input_abs_path = args["input"].name
            self.path = args["path"]
        else:
            self.input_abs_path = args["input"]
            self.path = Path.abspath(args["path"])
        
        # str
        self.custom_filename = args.get("name")

        # int
        self.pixels = args.get("pixels")
        self.offset = args.get("offset", 0)
        self.slice_count = args.get("slicecount")

        # bool
        self.vertical = args.get("vertical")
        self.traverse = args.get("traverse") 
        self.reverse = args.get("reverse")
        self.info = args.get("info")
        self.batch = args.get("batch")

    def main(self):
        capture = self.open_video()
        self.init_slicer_params()
        self.create_blank_image()
        self.init_printer_heads()
        self.init_scanner_heads()
        self.process_video(capture)
        self.write_image()
        self.close_video(capture)

    def open_video(self):
        print("Opening video", end=": ", flush=False)
        capture = cv2.VideoCapture(self.input_abs_path)
        print(f"Opened video {self.input_abs_path}")
        self.frame_count  = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.video_width  = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if self.info: print(f"  video input res:   {self.video_width} x {self.video_height}")
        return capture

    def close_video(self, capture):
        capture.release()

    def generate_output_abs_path(self):
        if self.custom_filename is not None:
            namebase = self.custom_filename
        else:
            namebase = Path(self.input_abs_path).stem

        nameoffsets = ""
        if self.vertical:
            namebase += "-vertical"
            nameoffsets = f"({self.offset},{self.scan_res})px"
        else:
            namebase += "-horizontal"
            nameoffsets = f"({self.scan_res},{self.offset})px"

        if self.traverse: namebase += "-traverse"
        if self.reverse: namebase += "-reverse"
        if self.slice_count is not None: namebase += "-sliced"

        output_filename = f"{namebase}-{nameoffsets}.png"

        if self.path is not None:
            output_dir_path = self.path
        else:
            output_dir_path = Path.cwd() / "output"

        try:
            output_dir_path.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            print(f"Directory '{output_dir_path}' already exists. Continuing...")
        else:
            print(f"Directory '{output_dir_path}' created. Continuing...")

        output_abs_path = str(output_dir_path) + "/" + output_filename
        return output_abs_path

    def write_image(self):
        output_abs_path = self.generate_output_abs_path()
        print(f"Writing image to {output_abs_path}", end=": ", flush=False)
        cv2.imwrite(output_abs_path, self.img)
        print(f"Image {output_abs_path} created.")

    def init_slicer_params(self):
        self.frames_per_slice = 1
        if self.pixels is not None:
            self.scan_res = self.pixels
        elif self.slice_count is not None:
            self.frames_per_slice = math.floor(self.frame_count / self.slice_count)
            if self.vertical:
                self.scan_res = math.floor(self.video_height / self.slice_count)
            else:
                self.scan_res = math.floor(self.video_width / self.slice_count)
        elif self.traverse:
            if self.vertical:
                self.scan_res = math.floor(self.video_height / self.frame_count)
            else:
                self.scan_res = math.floor(self.video_width / self.frame_count)
        else:
            self.scan_res = DEFAULT_PIXEL_WIDTH

        frames_to_process = self.frame_count
        if self.slice_count is not None:
            frames_to_process = self.slice_count
        elif self.traverse is True and self.pixels is not None:
            if self.vertical is True and self.scan_res * self.frame_count > self.video_height:
                frames_to_process = math.floor(self.video_height / self.scan_res)
            elif self.vertical is False and self.scan_res * self.frame_count > self.video_width:
                frames_to_process = math.floor(self.video_width / self.scan_res)

        if self.vertical:
            self.image_width  = self.video_width + ((frames_to_process - 1) * abs(self.offset))
            self.image_height = frames_to_process * self.scan_res
        else:
            self.image_width  = frames_to_process * self.scan_res
            self.image_height = self.video_height + ((frames_to_process - 1) * abs(self.offset))

        self.max_width_index  = self.video_width - 1
        self.max_height_index = self.video_height - 1

        if self.info:
            print(f"  image output res:  {self.image_width} x {self.image_height}")
            print(f"  frame_count:       {self.frame_count}")
            print(f"  frames_to_process: {frames_to_process}")
            print(f"  slice_count:       {self.slice_count}")
            print(f"  scan_res:          {self.scan_res}")
            print(f"  offset:            {self.offset}")
        
    def create_blank_image(self):
        print("Creating blank image", end=": ", flush=False)
        self.img = np.zeros((self.image_height, self.image_width, 4), np.uint8)
        print("Blank image created.")

    def init_printer_heads(self):
        if self.reverse:
            if self.vertical:
                self.printer_in  = self.image_height - self.scan_res
                self.printer_out = self.image_height
            else:
                self.printer_in  = self.image_width
                self.printer_out = self.image_width + self.scan_res
        else:
            self.printer_in, self.printer_out = 0, self.scan_res
        
        if self.offset < 0:
            if self.vertical:
                self.printer_offaxis_in  = self.image_width - self.max_width_index
                self.printer_offaxis_out = self.image_width
            else:
                self.printer_offaxis_in  = self.image_height - self.max_height_index
                self.printer_offaxis_out = self.image_height
        else:
            self.printer_offaxis_in = 0
            if self.vertical:
                self.printer_offaxis_out = self.max_width_index
            else:
                self.printer_offaxis_out = self.max_height_index

    def init_scanner_heads(self):
        if self.traverse:
            self.scanner_in = 0
        elif self.vertical: 
            self.scanner_in = int((self.video_height - self.scan_res) / 2)
        else:
            self.scanner_in = int((self.video_width - self.scan_res) / 2) 
        self.scanner_out = self.scanner_in + self.scan_res

    def process_frame(self, current_frame):
        input_image_alpha = np.full((current_frame.shape[0],current_frame.shape[1]), 255, dtype=np.uint8)
        current_frame = np.dstack((current_frame, input_image_alpha))

        if self.vertical:
            self.img[
                self.printer_in:self.printer_out,
                self.printer_offaxis_in:self.printer_offaxis_out
            ] = current_frame[
                self.scanner_in:self.scanner_out,
                0:self.max_width_index
            ]
        else:
            self.img[
                self.printer_offaxis_in:self.printer_offaxis_out,
                self.printer_in:self.printer_out
            ] = current_frame[
                0:self.max_height_index,
                self.scanner_in:self.scanner_out
            ]
    
        if self.reverse:
            self.printer_out = self.printer_in
            self.printer_in  = self.printer_out - self.scan_res
        else:
            self.printer_in  = self.printer_out
            self.printer_out = self.printer_in + self.scan_res

        if self.offset != 0:
            self.printer_offaxis_in  += self.offset
            self.printer_offaxis_out += self.offset

        if self.traverse:
            self.scanner_in  += self.scan_res
            self.scanner_out += self.scan_res

        print(f"Processed {self.frame_nr} frames", end="\r", flush=True)

    def process_video(self, capture):
        print("Processing frames...")
        self.frame_nr = 0
        while (True):
            # process frames
            success, frame = capture.read()
            if success and self.should_process_next_frame():
                if self.frame_nr % self.frames_per_slice != 0:
                    self.frame_nr += 1
                    continue
                else:
                    self.frame_nr += 1
                    self.process_frame(frame)
            else:
                break
        print(f"Processing complete. Processed {self.frame_nr} frames.")

    def should_process_next_frame(self):
        if self.reverse:
            if self.printer_in >= 0:
                return True
        else:
            if (
                (self.vertical is True)
                and (self.printer_out <= self.image_height)
                and (self.scanner_out <= self.video_height)
            ):
                return True
            elif (
                (self.vertical is False)
                and (self.printer_out <= self.image_width)
                and (self.scanner_out <= self.video_width)
            ):
                return True
        return False

if __name__=="__main__":
    main()