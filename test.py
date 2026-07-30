from ultralytics import YOLO

# Load your trained model
model = YOLO(r"C:\Users\chipp\Downloads\image\runs\detect\runs\fire_detection-3\weights\best.pt")

# Print class names
print(model.names)