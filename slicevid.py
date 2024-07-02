import sys, os
import cv2
import numpy as np
import argparse
import math
from pathlib import Path
import logging
from time import perf_counter

DEFAULT_PIXEL_WIDTH = 6
VIDEO_EXTENSIONS = ['.mov', '.mp4']
VIDEO_RESOLUTIONS = {
    "HD": {"x": 1920, "y": 1080},
    "4K": {"x": 3840, "y": 2160}
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=argparse.FileType('r'), help="input video file")
    ap.add_argument("--name", type=str, help="optional base name for output image")
    ap.add_argument("--path", type=Path)
    ap.add_argument("-p", "--pixels", type=int, help="number of pixels to sample")
    ap.add_argument("-o", "--offset", type=int, default=0, help="number of off-axis offset pixels")
    ap.add_argument("-c", "--slicecount", type=int, help="override with number of slices")
    ap.add_argument("-l", "--customline", type=int, help="override which line to scan")
    ap.add_argument("-v", "--vertical", action='store_true', help="vertical scan")
    ap.add_argument("-t", "--traverse", action='store_true', help="traverse scanline across frame")
    ap.add_argument("-r", "--reverse", action='store_true', help="reverse scan direction")
    ap.add_argument("-i", "--info", default=True, action='store_true', help="print extra info")
    args = vars(ap.parse_args())
    ms = MetaSlicer(args["input"].name, args["path"], [args], cli=True)

class MetaSlicer:
    def __init__(self, input_path, out_dir, args_list, cli=False):
        file_handler = logging.FileHandler(filename='tmp.log')
        stdout_handler = logging.StreamHandler(stream=sys.stdout)
        handlers = [file_handler, stdout_handler]

        logging.basicConfig(
            level=logging.INFO, 
            format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
            handlers=handlers
        )

        self.input_path = Path(input_path)
        self.out_dir = Path(out_dir)
        self.info = args_list[0].get("info", True)

        self.args_list = args_list

        if Path.exists(self.input_path):
            if Path.is_file(self.input_path):
                t1 = perf_counter()
                self.process_video_file(self.input_path)
                t2 = perf_counter()
                logging.info(f"Processing time: {t2 - t1} seconds")
            if Path.is_dir(self.input_path):
                t1 = perf_counter()
                self.process_video_dir(self.input_path)
                t2 = perf_counter()
                logging.info(f"Processing time: {t2 - t1} seconds")
            return
        logging.error(f"Invalid input path: {self.input_path}")

    def process_video_dir(self, video_dir):
        path_list = video_dir.glob('**/*')
        for video_path in sorted(path_list):
            if video_path.suffix in VIDEO_EXTENSIONS:
                self.process_video_file(video_path)

    def process_video_file(self, video_path):
        vb = VideoBoy(video_path, self.info)
        capture = vb.open_video()
        img_boys = self.init_img_boys(video_path, vb.frame_count, vb.video_width, vb.video_height)
        self.process_video_frames(capture, img_boys)
        vb.close_video(capture)
        self.write_images(img_boys)

    def write_images(self, img_boys):
        for img_boy in img_boys:
            img_boy.write_image()

    def init_img_boys(self, video_path, frame_count, video_width, video_height):
        img_boys = []
        for args in self.args_list:
            args["input_path"] = video_path
            args["out_dir"] = self.out_dir
            args["custom_filename"] = None
            args["info"] = self.info
            args["frame_count"] = frame_count
            args["video_width"] = video_width
            args["video_height"] = video_height
            img_boy = ImageBoy(args)
            img_boy.init_all_params()
            img_boys.append(img_boy)
        return img_boys

    def process_video_frames(self, capture, img_boys):
        logging.info(f"Processing frames for {len(img_boys)} image(s)")
        frame_nr = 0
        try:
            while (True):
                success, frame = capture.read()
                if success:
                    frame_nr += 1
                    for img_boy in img_boys:
                        if img_boy.processing_complete is True:
                            return
                        img_boy.process_frame(frame, frame_nr)
                else:
                    return
        finally:
            logging.info(f"Processing complete. Processed {frame_nr} frames, created {len(img_boys)} images.")
    
class VideoBoy:
    def __init__(self, video_path, info):
        self.video_path = video_path
        self.info = info

    def open_video(self):
        str_video_path = str(self.video_path)
        capture = cv2.VideoCapture(str_video_path)
        logging.info(f"Opened video {str_video_path}")
        self.frame_count  = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.video_width  = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.video_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logging.info(f"video input res: {self.video_width} x {self.video_height}")
        return capture

    def close_video(self, capture):
        capture.release()

class ImageBoy:
    def __init__(self, args):
        self.input_path = args.get("input_path")
        self.out_dir = args.get("out_dir")
        self.custom_filename = args.get("name")
        self.frame_count = args.get("frame_count")
        self.video_width = args.get("video_width")
        self.video_height = args.get("video_height")

        # int
        self.pixels = args.get("pixels")
        self.offset = args.get("offset", 0)
        self.slice_count = args.get("slicecount")
        self.custom_line = args.get("customline")

        # bool
        self.vertical = args.get("vertical")
        self.traverse = args.get("traverse") 
        self.reverse = args.get("reverse")
        self.info = args.get("info")

        # internal
        self.processing_complete = False

    def init_all_params(self):
        self.init_slicer_params()
        self.create_blank_image()
        self.init_printer_heads()
        self.init_scanner_heads()

        if self.info:
            logging.info(f"image output res:  {self.image_width} x {self.image_height}")
            logging.info(f"frame_count:       {self.frame_count}")
            logging.info(f"frames_to_process: {self.frames_to_process}")
            logging.info(f"slice_count:       {self.slice_count}")
            logging.info(f"frames_per_slice:  {self.frames_per_slice}")
            logging.info(f"scanner_in:        {self.scanner_in}")
            logging.info(f"scan_res:          {self.scan_res}")
            logging.info(f"offset:            {self.offset}")

    def generate_output_abs_path(self):
        if self.custom_filename is not None:
            namebase = self.custom_filename
        else:
            namebase = self.input_path.stem

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
        if self.custom_line is not None: namebase += ("-line" + str(self.custom_line))

        output_filename = f"{namebase}-{nameoffsets}.png"

        if self.out_dir is None:
            self.out_dir = Path.cwd() / "output"

        try:
            self.out_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            logging.info(f"Directory '{self.out_dir}' already exists. Continuing...")
        else:
            logging.info(f"Directory '{self.out_dir}' created. Continuing...")

        output_abs_path = str(self.out_dir) + "/" + output_filename
        return output_abs_path

    def write_image(self):
        output_abs_path = self.generate_output_abs_path()
        logging.info(f"Writing image to {output_abs_path}")
        try:
            cv2.imwrite(output_abs_path, self.img)
            logging.info(f"Image {output_abs_path} created.")
        except:
            logging.info(f"Image {output_abs_path} failed to write.")

    def init_slicer_params(self):
        self.frames_per_slice = 1
        if self.pixels is not None:
            self.scan_res = self.pixels
        elif self.slice_count is not None:
            self.frames_per_slice = math.ceil(self.frame_count / self.slice_count)
            if self.vertical:
                self.scan_res = math.ceil(self.video_height / self.slice_count)
            else:
                self.scan_res = math.ceil(self.video_width / self.slice_count)
        elif self.traverse:
            if self.vertical:
                self.scan_res = math.ceil(self.video_height / self.frame_count)
            else:
                self.scan_res = math.ceil(self.video_width / self.frame_count)
        else:
            self.scan_res = DEFAULT_PIXEL_WIDTH

        self.frames_to_process = self.frame_count
        if self.slice_count is not None:
            self.frames_to_process = self.slice_count
        elif self.traverse is True:
            if self.vertical is True and self.scan_res * self.frame_count > self.video_height:
                self.frames_to_process = math.floor(self.video_height / self.scan_res)
            elif self.vertical is False and self.scan_res * self.frame_count > self.video_width:
                self.frames_to_process = math.floor(self.video_width / self.scan_res)

        if self.vertical:
            self.image_width  = self.video_width + ((self.frames_to_process - 1) * abs(self.offset))
            self.image_height = self.frames_to_process * self.scan_res
        else:
            self.image_width  = self.frames_to_process * self.scan_res
            self.image_height = self.video_height + ((self.frames_to_process - 1) * abs(self.offset))

        self.max_width_index  = self.video_width - 1
        self.max_height_index = self.video_height - 1
  
    def create_blank_image(self):
        self.img = np.zeros((self.image_height, self.image_width, 4), np.uint8)
        logging.debug("Blank image created")

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
        if self.custom_line is not None:
            self.scanner_in = self.custom_line
        elif self.traverse:
            self.scanner_in = 0
        elif self.vertical: 
            self.scanner_in = int((self.video_height - self.scan_res) / 2)
        else:
            self.scanner_in = int((self.video_width - self.scan_res) / 2) 
        self.scanner_out = self.scanner_in + self.scan_res

    def process_frame(self, current_frame, current_frame_nr):
        if not self.should_process_next_frame():
            self.processing_complete = True
            return
        if current_frame_nr % self.frames_per_slice != 0:
            return

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

        print(f"Processed {current_frame_nr} frames", end="\r", flush=True)
    
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