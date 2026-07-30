import cv2

rtsp_url = "rtsp://admin:Veeru%40555@192.168.0.102:554/Streaming/Channels/101"

cap = cv2.VideoCapture(rtsp_url)

if not cap.isOpened():
    print("❌ RTSP camera connection failed")
    exit()

print("✅ RTSP camera connected successfully")

while True:
    ret, frame = cap.read()

    if not ret:
        print("❌ Failed to receive video stream")
        break

    cv2.imshow("RTSP Camera Test", frame)

    # Press q to quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()