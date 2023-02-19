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

    if args["batch"]:
        args_copy = args.copy()
        batch_list = [[False, False], [False, True], [True, False], [True, True]]
        for vertical, traverse in batch_list:
            args_copy["vertical"] = vertical
            args_copy["traverse"] = traverse
            flatten_video(args_copy)
    else:
        flatten_video(args)

def flatten_video(args):
    input_abs_path = args["input"].name
    print("Opening video", end=": ", flush=False)
    capture = cv2.VideoCapture(input_abs_path)
    print(f"Opened video {input_abs_path}")

    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    video_width  = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video input resolution:  {video_width} x {video_height}")

    offset = args["offset"]
    slice_count = args["slicecount"]
    frames_per_slice = 1

    if args["pixels"] is not None:
        scan_res = args["pixels"]
    elif slice_count is not None:
        frames_per_slice = int(frame_count / slice_count)
        print(f"frames per slice: {frames_per_slice}")
        if args["vertical"] is True:
            scan_res = math.floor(video_height / slice_count)
        else:
            scan_res = math.floor(video_width / slice_count)
    elif args["traverse"] is True:
        if args["vertical"] is True:
            scan_res = math.floor(video_height / frame_count)
        else:
            scan_res = math.floor(video_width / frame_count)
    else:
        scan_res = DEFAULT_PIXEL_WIDTH

    img = process_video(args, capture, frame_count, video_width, video_height, scan_res, slice_count, frames_per_slice)

    output_abs_path = generate_output_abs_path(args, input_abs_path, offset, scan_res)

    print(f"Writing image to {output_abs_path}", end=": ", flush=False)
    cv2.imwrite(output_abs_path, img)
    print(f"Image {output_abs_path} created.")

    capture.release()

def generate_output_abs_path(args, input_abs_path, offset, scan_res):
    if args["name"] is not None:
        namebase = args["name"]
    else:
        namebase = Path(input_abs_path).stem

    nameoffsets = ""
    if args["vertical"]:
        namebase += "-vertical"
        nameoffsets = f"({offset},{scan_res})px"
    else:
        namebase += "-horizontal"
        nameoffsets = f"({scan_res},{offset})px"

    if args["traverse"]: namebase += "-traverse"
    if args["reverse"]: namebase += "-reverse"
    if args["slicecount"] is not None: namebase += "-sliced"

    output_filename = f"{namebase}-{nameoffsets}.png"

    if args["path"] is not None:
        output_dir_path = args["path"]
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

def create_blank_image(image_width, image_height):
    print(f"Image output resolution: {image_width} x {image_height}")
    print("Creating blank image", end=": ", flush=False)
    img = np.zeros((image_height, image_width, 4), np.uint8)
    print("Blank image created.")
    return img

def process_video(args, capture, frame_count, video_width, video_height, scan_res, slice_count, frames_per_slice):
    frames = frame_count
    if slice_count is not None:
        frames = slice_count
    elif args["traverse"] is True and args["pixels"] is not None:
        if args["vertical"] is True and scan_res * frame_count > video_height:
            frames = math.floor(video_height / scan_res)
        elif args["vertical"] is False and scan_res * frame_count > video_width:
            frames = math.floor(video_width / scan_res)

    if args["vertical"]:
        image_width  = video_width + (frames * abs(args["offset"]))
        image_height = frames * scan_res
    else:
        image_width  = frames * scan_res
        image_height = video_height + (frames * abs(args["offset"]))

    img = create_blank_image(image_width, image_height)

    print(f"frames: {frames}, frame_count: {frame_count}, slice_count: {slice_count}, scan_res: {scan_res}")

    frame_nr = 1
    max_height = video_height - 1
    max_width = video_width - 1

    if args["reverse"] is True:
        if args["vertical"] is True:
            printer_in, printer_out = image_height, image_height
        else:
            printer_in, printer_out = image_width, image_width
    else:
        printer_in, printer_out = 0, 0
    
    if args["offset"] < 0:
        if args["vertical"]:
            printer_offaxis_in  = image_width - max_width
            printer_offaxis_out = image_width
        else:
            printer_offaxis_in  = image_height - max_height
            printer_offaxis_out = image_height
    else:
        printer_offaxis_in = 0
        if args["vertical"]:
            printer_offaxis_out = max_width
        else:
            printer_offaxis_out = max_height

    if args["traverse"] is True:
        scanner_in = 0
    elif args["vertical"] is True: 
        scanner_in = int((video_height - scan_res) / 2)
    else:
        scanner_in = int((video_width - scan_res) / 2) 
    scanner_out = scanner_in + scan_res

    print("Processing frames...")

    def process_frame(current_frame):
        nonlocal args, img, max_height, max_width, scan_res, frame_nr
        nonlocal scanner_in, scanner_out, printer_in, printer_out
        nonlocal printer_offaxis_in, printer_offaxis_out

        if args["offset"] != 0:
            input_image_alpha = np.full((current_frame.shape[0],current_frame.shape[1]), 255, dtype=np.uint8)
            current_frame = np.dstack((current_frame, input_image_alpha))

        if args["reverse"] is True:
            printer_in = printer_out - scan_res
        else:  
            printer_out = printer_in + scan_res

        if args["vertical"] is True:
            img[printer_in:printer_out, printer_offaxis_in:printer_offaxis_out] = (
                current_frame[scanner_in:scanner_out, 0:max_width])
        else:
            img[printer_offaxis_in:printer_offaxis_out, printer_in:printer_out] = (
                current_frame[0:max_height, scanner_in:scanner_out])
       
        if args["reverse"] is True:
            printer_out = printer_in
        else:  
            printer_in = printer_out

        if args["offset"] != 0:
            printer_offaxis_in  += args["offset"]
            printer_offaxis_out += args["offset"]

        if args["traverse"]:
            scanner_in, scanner_out = scanner_in + scan_res, scanner_out + scan_res

        print(f"Processed {frame_nr} frames", end="\r", flush=True)

    def should_process_next_frame():
        nonlocal args, video_height, video_width, image_height, image_width
        nonlocal scanner_out, printer_in, printer_out

        if args["reverse"] is True:
            if printer_in >= 0:
                return True
        else:
            if (
                (args["vertical"] is True)
                and (printer_out < image_height)
                and (scanner_out <= video_height)
            ):
                return True
            elif (
                (args["vertical"] is False)
                and (printer_out < image_width)
                and (scanner_out <= video_width)
            ):
                return True
        return False

    while (True):
        # process frames
        success, frame = capture.read()

        if success and should_process_next_frame():
            if frame_nr % frames_per_slice != 0:
                frame_nr += 1
                continue
            else:
                process_frame(frame)
                frame_nr += 1
        else:
            break

    print(f"Processing complete. Processed {frame_nr} frames.")

    return img

if __name__=="__main__":
    main()
