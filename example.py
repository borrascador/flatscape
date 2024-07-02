from slicevid import MetaSlicer

script_path = __file__

input_path = "/Users/username/Movies/my-video-file.mov"
output_path =  "/Users/username/src/flatscape/output/first-test"

args_list = [{"pixels":40,"vertical":False,"info":True}]
ms = MetaSlicer(input_path, output_path, args_list)

args_list = [{"pixels":40,"vertical":False,"traverse":True,"info":True}]
ms = MetaSlicer(input_path, output_path, args_list)

args_list = [{"pixels":40,"vertical":True,"info":True}]
ms = MetaSlicer(input_path, output_path, args_list)

args_list = [{"pixels":40,"vertical":True,"traverse":True,"info":True}]
ms = MetaSlicer(input_path, output_path, args_list)
