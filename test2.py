import cv2
import threading
import time
from ultralytics import YOLO
import os
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

# =====================================================
# LOAD MODELS
# =====================================================

# Person Detection Model
person_model = YOLO("yolo11n.pt")   # Change if required

# PPE Detection Model
ppe_model = YOLO(
    r"C:\Users\ipras\OneDrive\Desktop\L&TMAIN\runs\detect\runs\ppe_detection\weights\best.pt"
)

# Print class names once
print("PPE Classes:", ppe_model.names)

# =====================================================
# CLASS IDS
# =====================================================

PERSON_CLASS = 0

# CHANGE THESE IF YOUR MODEL USES DIFFERENT IDS
HELMET_CLASS = 2
VEST_CLASS = 4

# =====================================================
# CAMERA FUNCTION
# =====================================================

def run_camera(camera_name, rtsp_url):
    

    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print(f"{camera_name}: Unable to connect.")
        return

    print(f"{camera_name}: Connected")

    while True:

        ret, frame = cap.read()

        if not ret:
            print(f"{camera_name}: Reconnecting...")
            cap.release()
            time.sleep(2)
            cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            continue

        # -------------------------
        # PERSON DETECTION
        # -------------------------
        person_results = person_model.predict(
            frame,
            classes=[PERSON_CLASS],
            conf=0.45,
            verbose=False
        )

        person_id = 1

        for result in person_results:

            for person in result.boxes:

                px1, py1, px2, py2 = map(int, person.xyxy[0])

                px1 = max(0, px1)
                py1 = max(0, py1)

                px2 = min(frame.shape[1], px2)
                py2 = min(frame.shape[0], py2)

                crop = frame[py1:py2, px1:px2]

                if crop.size == 0:
                    continue

                # -------------------------
                # PPE DETECTION
                # -------------------------
                ppe_results = ppe_model.predict(
                    crop,
                    conf=0.35,
                    verbose=False
                )

                helmet = False
                vest = False

                for ppe in ppe_results:

                    for box in ppe.boxes:

                        cls = int(box.cls[0])

                        x1, y1, x2, y2 = map(int, box.xyxy[0])

                        x1 += px1
                        x2 += px1
                        y1 += py1
                        y2 += py1

                        if cls == HELMET_CLASS:

                            helmet = True

                            cv2.rectangle(
                                frame,
                                (x1, y1),
                                (x2, y2),
                                (0, 255, 0),
                                2
                            )

                            cv2.putText(
                                frame,
                                "Helmet",
                                (x1, y1 - 8),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (0, 255, 0),
                                2
                            )

                        elif cls == VEST_CLASS:

                            vest = True

                            cv2.rectangle(
                                frame,
                                (x1, y1),
                                (x2, y2),
                                (0, 255, 255),
                                2
                            )

                            cv2.putText(
                                frame,
                                "Vest",
                                (x1, y1 - 8),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (0, 255, 255),
                                2
                            )

                # -------------------------
                # PERSON STATUS
                # -------------------------
                color = (0, 255, 0)

                if not helmet or not vest:
                    color = (0, 0, 255)

                cv2.rectangle(
                    frame,
                    (px1, py1),
                    (px2, py2),
                    color,
                    3
                )

                status = f"P{person_id}"

                status += " H✔" if helmet else " H✘"
                status += " V✔" if vest else " V✘"

                cv2.putText(
                    frame,
                    status,
                    (px1, py1 - 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    color,
                    2
                )

                person_id += 1

        cv2.imshow(camera_name, frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyWindow(camera_name)

# =====================================================
# CAMERA URLS
# =====================================================

camera1 = "rtsp://admin:Secur!ty%402026@43.225.25.146:555/Streaming/channels/101"
camera2 = "rtsp://admin:Secur!ty%402026@43.225.25.146:556/Streaming/channels/101"
camera3 = "rtsp://admin:Secur!ty%402026@43.225.25.146:557/Streaming/channels/101"
# camera4 = "rtsp://admin:Secur!ty%2026%43.225.25.146:558:/Streaming/channels/101"
# camera5 = 
# camera6 =
# camera7 = 
# camera8 =
# camera9 =
# camera10 =
# camera11 =
# camera12 =
# camera13 =
# camera14 =
# camera15 =
# camera16 =
# camera17 =
# camera18 =
# camera19 =
# camera20 =
# camera21 =
# camera22 =
# camera23 =
# camera24 = 

# =====================================================
# THREADS
# =====================================================

thread1 = threading.Thread(
    target=run_camera,
    args=("Camera 1", camera1)
)

thread2 = threading.Thread(
    target=run_camera,
    args=("Camera 2", camera2)
)
thread3 = threading.Thread(
    target=run_camera,
    args=("Camera 3", camera3)
)
# thread4 = threading.Thread(
#     target=run_camera,
#     args=("Camera 4", camera4)
# )
# thread5 = threading.Thread(
#     target=run_camera,
#     args=("Camera 5", camera5)
# )
# thread6 = threading.Thread(
#     target=run_camera,
#     args=("Camera 6", camera6)
# )
# thread7 = threading.Thread(
#     target=run_camera,
#     args=("Camera 7", camera7)
# )
# thread8 = threading.Thread(
#     target=run_camera,
#     args=("Camera 8", camera8)
# )
# thread9 = threading.Thread(
#     target=run_camera,
#     args=("Camera 9", camera9)
# )
# thread10 = threading.Thread(
#     target=run_camera,
#     args=("Camera 10", camera10)
# )
# thread11 = threading.Thread(
#     target=run_camera,
#     args=("Camera 11", camera11)
# )
# thread12 = threading.Thread(
#     target=run_camera,
#     args=("Camera 12", camera12)
# )
# thread13 = threading.Thread(
#     target=run_camera,
#     args=("Camera 13", camera13)
# )
# thread14 = threading.Thread(
#     target=run_camera,
#     args=("Camera 14", camera14)
# )
# thread15 = threading.Thread(
#     target=run_camera,
#     args=("Camera 15", camera15)
# )
# thread16 = threading.Thread(
#     target=run_camera,
#     args=("Camera 16", camera16)
# )
# thread17 = threading.Thread(
#     target=run_camera,
#     args=("Camera 17", camera17)
# )
# thread18 = threading.Thread(
#     target=run_camera,
#     args=("Camera 18", camera18)
# )
# thread19 = threading.Thread(
#     target=run_camera,
#     args=("Camera 19", camera19)
# )
# thread20 = threading.Thread(
#     target=run_camera,
#     args=("Camera 20", camera20)
# )
# thread21 = threading.Thread(
#     target=run_camera,
#     args=("Camera 21", camera21)
# )
# thread22 = threading.Thread(
#     target=run_camera,
#     args=("Camera 22", camera22)
# )
# thread23 = threading.Thread(
#     target=run_camera,
#     args=("Camera 23", camera23)
# )
# thread24 = threading.Thread(
#     target=run_camera,
#     args=("Camera 24", camera24)
# )

thread1.start()
thread2.start()
thread3.start()
# thread4.start()
# thread5.start()
# thread6.start()
# thread7.start()
# thread8.start()
# thread9.start()
# thread10.start()
# thread11.start()
# thread12.start()
# thread13.start()
# thread14.start()
# thread15.start()
# thread16.start()
# thread17.start()
# thread18.start()
# thread19.start()
# thread20.start()
# thread21.start()
# thread22.start()
# thread23.start()
# thread24.start()


thread1.join()
thread2.join()
thread3.join()
# thread4.join()
# thread5.join()
# thread6.join()
# thread7.join()
# thread8.join()
# thread9.join()
# thread10.join()
# thread11.join()
# thread12.join()
# thread13.join()
# thread14.join()
# thread15.join()
# thread16.join()
# thread17.join()
# thread18.join()
# thread19.join()
# thread20.join()
# thread21.join()
# thread22.join()
# thread23.join()
# thread24.join()

cv2.destroyAllWindows()