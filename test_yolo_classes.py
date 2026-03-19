from ultralytics import YOLO

model = YOLO('yolov8n.pt')
for k, v in model.names.items():
    if v in ['knife', 'scissors', 'cell phone', 'bottle', 'cup']:
        print(f"{k}: {v}")
