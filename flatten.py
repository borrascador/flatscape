import cv2 
import numpy as np
import argparse
import itertools
from pathlib import Path

DEFAULT_PIXEL_WIDTH = 6

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=argparse.FileType('r'), help="input video file")
    ap.add_argument("--output", type=str, help="optional base name for output image")
    ap.add_argument("--path", type=Path)
    ap.add_argument("-p", "--pixels", type=int, help="number of pixels to sample")
    ap.add_argument("-o", "--offset", type=int, default=0, help="number of off-axis offset pixels")
    ap.add_argument("-c", "--slicecount", type=int, help="override with number of slices")
    ap.add_argument("-v", "--vertical", action='store_true', help="vertical scan")
    ap.add_argument("-t", "--traverse", action='store_true', help="traverse scanline across frame")
    ap.add_argument("-r", "--reverse", action='store_true', help="reverse scan direction")
    ap.add_argument("-i", "--info", action='store_true', help="print extra info")
    ap.add_argument("-b", "--batch", action='store_true', help="make four common images variants")
    ap.add_argument("-f", "--flip", action='store_true', help="flip diagonal orientation")
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
    input_filepath = args["input"].name
    print("Opening video", end=": ", flush=False)
    capture = cv2.VideoCapture(input_filepath)
    print(f"Opened video {input_filepath}")

    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    video_width  = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

    print(video_width, video_height)
    offset = args["offset"]
    slice_count = args["slicecount"]
    frames_per_slice = 1
    
    print(slice_count)

    if args["pixels"] is not None:
        scan_res = args["pixels"]
    elif slice_count is not None:
        frames_per_slice = int(frame_count / slice_count)
        print(f"frames per slice: {frames_per_slice}")
        if args["vertical"] is True:
            scan_res = int(video_height / slice_count)
        else:
            scan_res = int(video_width / slice_count)
        print("scan_res: ", scan_res)
    elif args["traverse"] is True:
        if args["vertical"] is True:
            scan_res = int(video_height / frame_count)
        else:
            scan_res = int(video_width / frame_count)
    else:
        scan_res = DEFAULT_PIXEL_WIDTH

    img = process_video(args, capture, frame_count, video_width, video_height, scan_res, slice_count, frames_per_slice)
 
    if args["output"] is not None:
        namebase = args["output"]
    else:
        namebase = Path(input_filepath).stem

    nameoffsets = ""
    if args["vertical"]:
        namebase += "-vertical"
        nameoffsets = f"({offset},{scan_res})px"
    else:
        namebase += "-horizontal"
        nameoffsets = f"({scan_res},{offset})px"

    if args["traverse"]:
        namebase += "-traverse"

    if args["reverse"]:
        namebase += "-reverse"
        
    if args["flip"]:
        namebase += "-flip"

    if args["slicecount"] is not None:
        namebase += "-sliced"

    imgname = f"{namebase}-{nameoffsets}.png"

    if args["path"] is not None:
        output_directory_path = args["path"]
    else:
        output_directory_path = Path.cwd() / "output"

    try:
        output_directory_path.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        print(f"Directory '{output_directory_path}' already exists. Continuing...")
    else:
        print(f"Directory '{output_directory_path}' created. Continuing...")
   
    output_absolute_path = str(output_directory_path) + "/" + imgname

    print(f"Writing image to {output_absolute_path}", end=": ", flush=False)

    cv2.imwrite(output_absolute_path, img)
    print(f"Image {output_absolute_path} created.")

    capture.release()

def create_blank_image(height, width):
    print("Creating blank image", end=": ", flush=False)
    img = np.zeros((height, width, 4), np.uint8)
    print("Blank image created.")
    return img

def process_video(args, capture, frame_count, video_width, video_height, scan_res, slice_count, frames_per_slice):
    if slice_count is not None:
        frames = slice_count
    else:
        frames = frame_count
    print(f"frames: {frames}, frame_count: {frame_count}, slice_count: {slice_count}, scan_res: {scan_res}")
    if args["vertical"]:
        image_height, image_width = frames * scan_res, video_width + (frames * args["offset"])
        if args["traverse"] is True and args["pixels"] is not None:
            image_height = video_height
    else:
        image_height, image_width = video_height + (frames * args["offset"]), frames * scan_res
        if args["traverse"] is True and args["pixels"] is not None:
            image_width = video_width
    print(f"image height: {image_height}, image width: {image_width}")
    img = create_blank_image(image_height, image_width)

    frame_nr = 1
    printer_in, printer_out = 0, scan_res
    max_height = video_height - 1
    max_width = video_width - 1
    if (args["offset"] is not None) and (args["flip"] is True):
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

    if args["offset"] < 0:
        printer_offaxis_in, printer_offaxis_out = printer_offaxis_out, printer_offaxis_in

    print("Processing frames...")

    if args["reverse"] is True:
        frame_list = []

    def process_frame(current_frame):
        nonlocal args, img, max_height, max_width, scan_res, frame_nr
        nonlocal scanner_in, scanner_out, printer_in, printer_out
        nonlocal printer_offaxis_in, printer_offaxis_out

        input_image_alpha = np.full((current_frame.shape[0],current_frame.shape[1]), 255, dtype=np.uint8)
        current_frame = np.dstack((current_frame, input_image_alpha))

        printer_out = printer_in + scan_res

        if args["vertical"] is True:
            img[printer_in:printer_out, printer_offaxis_in:printer_offaxis_out] = (
                current_frame[scanner_in:scanner_out, 0:max_width])
        else:
            img[printer_offaxis_in:printer_offaxis_out, printer_in:printer_out] = (
                current_frame[0:max_height, scanner_in:scanner_out])
       
        print(f"Processed {frame_nr} frames", end="\r", flush=True)
        printer_in = printer_out

        if (args["offset"] is not None) and (args["flip"] is True):
            printer_offaxis_in -=  args["offset"]
            printer_offaxis_out -= args["offset"]
        else:
            printer_offaxis_in +=  args["offset"]
            printer_offaxis_out += args["offset"]

        if args["traverse"]:
            scanner_in, scanner_out = scanner_in + scan_res, scanner_out + scan_res

    while (True):
        # process frames
        success, frame = capture.read()

        if success and (
            (
                (args["vertical"] is True)
                and (printer_out < image_height)
                and ((scanner_out <= video_height))
            ) or
            (
                (args["vertical"] is False)
                and (printer_out < image_width)
                and ((scanner_out <= video_width))
            )   
        ):
            if args["reverse"] is True:
                frame_list.append(frame)
            else:
                if (slice_count is not None) and (frame_nr % frames_per_slice != 0):
                    frame_nr += 1
                    continue
                else:
                    process_frame(frame)
                    frame_nr += 1
        else:
            break

    ## TODO - eliminate this memory usage, causes crash with big files

    if args["reverse"] is True:
        while len(frame_list) > 0:
            frame = frame_list.pop()
            if (slice_count is not None) and (frame_nr % frames_per_slice != 0):
                frame_nr += 1
                continue
            else:
                process_frame(frame)
                frame_nr += 1

    print(f"Processing complete. Processed {frame_nr} frames.")

    return img

if __name__=="__main__":
    main()
