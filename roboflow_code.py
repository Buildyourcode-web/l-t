

from roboflow import Roboflow
rf = Roboflow(api_key="q3MIng2ft2TiDaaONPnM")
project = rf.workspace("vicky-vishnu").project("fire-and-smoke-detection-hiwia-1vzaj")
version = project.version(1)
dataset = version.download("yolov8")
                