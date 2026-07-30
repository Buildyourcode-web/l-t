# Construction Site AI Monitoring System

A comprehensive AI-powered safety monitoring system for construction sites. It uses computer vision to detect Personal Protective Equipment (PPE) compliance (helmets, vests) and fire hazards in real-time through multiple RTSP camera streams.

## Architecture

```text
+-------------------+      +-------------------+      +-------------------+
|                   |      |                   |      |                   |
|   IP Cameras /    +----->|  Camera Manager   +----->|   Frame Queue     |
|   RTSP Streams    |      |  (Multi-threaded) |      |   (Non-blocking)  |
|                   |      |                   |      |                   |
+-------------------+      +-------------------+      +---------+---------+
                                                                |
                                                                v
+-------------------+      +-------------------+      +---------+---------+
|                   |      |                   |      |                   |
|   Database        |<-----+  Detection Engine |<-----+  Detection        |
|   (PostgreSQL)    |      |  (YOLOv8 + CUDA)  |      |  Pipeline (Async) |
|                   |      |                   |      |                   |
+---------+---------+      +-------------------+      +---------+---------+
          |                                                     |
          v                                                     v
+---------+---------+      +-------------------+      +---------+---------+
|                   |      |                   |      |                   |
|   FastAPI         +----->|  WebSocket Server +----->|  React Frontend   |
|   REST API        |      |  (Real-time)      |      |  (Dashboard)      |
|                   |      |                   |      |                   |
+-------------------+      +-------------------+      +-------------------+
```

## Prerequisites
- Python 3.10+
- PostgreSQL 15+
- Node.js 20+ (for frontend development)
- NVIDIA GPU with CUDA (optional but highly recommended for multi-camera real-time inference)

## Quick Start (Local Development)

1. **Clone/download the repository**

2. **Prepare Models**
   Copy your trained YOLO models into the `models/` directory:
   - Copy your PPE detection model weights to `models/ppe.pt` (e.g., from `runs/ppe_detection/weights/best.pt`)
   - Copy your fire detection model weights to `models/fire.pt` (can use `yolov8n.pt` or custom)

3. **Configure Cameras**
   Edit `config/cameras.json` to add your real RTSP URLs or video file paths.

4. **Environment Variables**
   Copy `.env.example` to `.env` (or create one) and adjust the parameters, specifically database credentials.

5. **Install Backend Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

6. **Initialize Database**
   ```bash
   alembic upgrade head
   ```

7. **Run Backend**
   ```bash
   uvicorn app.main:app --reload
   ```

8. **Run Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Docker Deployment

1. Make sure you have Docker and Docker Compose installed.
2. Place your models in the `models/` directory.
3. Configure `config/cameras.json` and `.env`.
4. Run with Docker Compose:
   ```bash
   docker-compose up -d --build
   ```

To enable GPU support in Docker, uncomment the `deploy` section under the `backend` service in `docker-compose.yml` and ensure you have the NVIDIA Container Toolkit installed.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_HOST` | Database host | `localhost` |
| `DB_PORT` | Database port | `5432` |
| `DB_NAME` | Database name | `construction_monitor` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `postgres` |
| `MODEL_PPE_PATH` | Path to PPE model | `models/ppe.pt` |
| `MODEL_FIRE_PATH` | Path to Fire model | `models/fire.pt` |
| `MODEL_DEVICE` | Compute device (`0` for GPU, `cpu` for CPU) | `0` |
| `DETECTION_FPS` | Target FPS for detection processing | `2` |
| `ALERT_COOLDOWN_SECONDS`| Cooldown between alerts per camera/type | `30` |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard/stats` | GET | Retrieve high-level statistics |
| `/api/violations` | GET | List violations with filters |
| `/api/cameras` | GET | List all configured cameras |
| `/api/health` | GET | System and GPU health metrics |
| `/api/reports/daily` | GET | Trigger or fetch daily reports |
| `/ws/alerts` | WS | Real-time WebSocket connection for alerts |

## Camera Configuration

Edit `config/cameras.json` to define your cameras:
```json
[
  {
    "id": 1,
    "name": "Gate 1",
    "url": "rtsp://user:pass@192.168.1.10:554/stream1",
    "active": true
  }
]
```

## Performance Tuning
- **Frame Skipping:** Adjust `DETECTION_FPS` to limit the number of frames processed per second. Real-time safety monitoring often only needs 1-5 FPS.
- **Batching:** YOLOv8 batches requests internally. Use a capable GPU if monitoring >4 cameras.
- **Resolution:** Reduce RTSP sub-stream resolution to 720p or 480p to speed up decoding and inference.

## Troubleshooting
- **No AI Detections:** Ensure `MODEL_PPE_PATH` and `MODEL_FIRE_PATH` point to valid `.pt` files.
- **RTSP Connection Drops:** Check the camera network connection and ensure `ffmpeg` and `opencv` can read the stream reliably. Increase timeout settings if necessary.
- **High CPU/Memory:** If running on CPU, scale down `DETECTION_FPS` to 1.
