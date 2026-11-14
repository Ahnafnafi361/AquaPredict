# AquaPredict Deployment Guide (Milestone M10)

This guide documents the procedures for running AquaPredict locally, deploying it as a precomputed static site, and running it inside a containerized host.

---

## A. Local Deployment (Windows PowerShell)

### 1. Prerequisites
* **Operating System:** Windows 10 / 11, macOS, or Linux.
* **Python Runtime:** Python 3.12+ (64-bit).
* **Node.js (Optional):** Node.js 18+ for running CDP automated test suites (optional for regular application usage).

### 2. Environment Setup (PowerShell)
Open Windows PowerShell in the project directory:

```powershell
cd c:\Users\ASUS\Desktop\AquaPredict

# (Optional) Create and activate a clean virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install core scientific dependencies
pip install -r requirements.txt
```

### 3. Starting the Application Server
Run the zero-dependency Python server:

```powershell
python serve.py
```

Expected output:
```text
=================================================================
 AquaPredict - Urban Waterlogging Risk Visualization Prototype
 Houston Pilot M0 Server running at: http://localhost:8000
=================================================================
```

### 4. Accessing the Application
Open any modern web browser (Chrome, Edge, Firefox, Safari) and navigate to:
`http://localhost:8000/`

To verify backend health:
`http://localhost:8000/api/health`

### 5. Local Troubleshooting
* **`WinError 10048` / Port Already in Use:**
  If port 8000 is occupied by a lingering process:
  ```powershell
  # Find PID using port 8000
  netstat -ano | findstr :8000
  # Terminate PID (replace <PID>)
  Stop-Process -Id <PID> -Force
  ```
  Or pass an alternative port:
  ```powershell
  python serve.py 8080
  ```
* **Browser 3D View WebGL Disabled:**
  If 3D Terrain view displays the WebGL fallback card, verify hardware acceleration is enabled in `chrome://settings/system`.

---

## B. Static Web Hosting (Precomputed Offline Mode)

### 1. Objective & Capabilities
Static mode allows hosting AquaPredict on any standard static web server (such as Nginx, Apache, GitHub Pages, Netlify, Cloudflare Pages, or AWS S3) **without requiring a Python backend or machine learning runtime**.

### 2. Generating the Static Export
Run the automated export pipeline:

```powershell
python scripts/export_static.py
```

This compiles:
* `dist_static/index.html` (injected with static mode configuration).
* `dist_static/css/` & `dist_static/js/` (application styles, Leaflet, Three.js).
* `dist_static/i18n/` (English `en.json` and Bangla `bn.json` language dictionaries).
* `dist_static/data/` (all GeoJSON layers, 1m DEM rasters, heightmaps, precomputed simulation scenarios, and static export manifest).

### 3. Serving the Static Export Locally
Test the static bundle using Python's built-in HTTP server:

```powershell
cd dist_static
python -m http.server 8080
```
Open `http://localhost:8080/`.

### 4. Supported vs. Unsupported Features in Static Mode

| Feature | Static Mode Status | Notes |
| :--- | :--- | :--- |
| **2D GIS & DEM Topography** | Fully Supported | Pre-rendered GeoJSONs and 1m Bare Earth rasters load client-side |
| **M1 Waterlogging Susceptibility** | Fully Supported | 100x100 matrix queries run client-side |
| **M5 Simulation Scenarios** | Fully Supported | 10mm, 25mm, 50mm, 75mm, 100mm presets scrubbable client-side |
| **M8 3D Terrain & Flood View** | Fully Supported | Pre-extracted continuous 256×256 elevation heightmap |
| **M7 Route Alternatives** | Fully Supported | Client-side Dijkstra engine executes over `m7_routing_graph.json` |
| **English / Bangla Internationalisation** | Fully Supported | Instant client-side switching via JSON dictionaries |
| **M9 Live ML Surrogate Inference** | Disabled | Requires active scikit-learn Python server; physical screening model is active |
| **Arbitrary Live Ingestion** | Disabled | Requires Python file watcher / pipeline |

---

## C. Container Host Deployment (Docker)

### 1. Building the Docker Image
A multi-stage, hardened production `Dockerfile` is provided in the repository root.

```bash
docker build -t aquapredict:0.10.0 .
```

### 2. Running the Container
Run the container mapping host port 8000:

```bash
docker run -d \
  --name aquapredict-app \
  -p 8000:8000 \
  --restart unless-stopped \
  aquapredict:0.10.0
```

### 3. Container Configuration & Health Check
* **Environment Variables:**
  - `PORT`: Server listening port (default: `8000`).
  - `PYTHONUNBUFFERED`: Set to `1` for immediate stdout/stderr flushing.
  - `AQUAPREDICT_CORS_ORIGIN`: Permitted CORS origin header.
    > [!WARNING]
    > **CORS Deployment Security:** The default development setting permits wildcard origins (`*`) for frictionless local prototyping. Wildcard CORS is **NOT production-hardened**. Any public or multi-tenant deployment must restrict `AQUAPREDICT_CORS_ORIGIN` to the specific authorized frontend domain(s) (e.g. `-e AQUAPREDICT_CORS_ORIGIN="https://aquapredict.yourorg.org"`).
* **Health Check Endpoint:**
  The container executes an automated health check every 30 seconds:
  ```bash
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)" || exit 1
  ```
* **Security Hardening:**
  - Container executes under an unprivileged user (`appuser`, UID 1001).
  - No root privileges required during runtime.
  - Read-only container root filesystems are supported (`--read-only`).

---

## D. Scientific Scope & Operational Safeguards

1. **Active Pilot Area:** Strictly bounded to Downtown Houston / Buffalo Bayou (`[-95.3750, 29.7560, -95.3650, 29.7650]`, $0.97\,\text{km}^2$).
2. **Exploratory Prototype Indicator:** The system generates physical screening indicators; it is **NOT a certified real-time flood forecasting or emergency flood warning system**.
3. **No Validation Data:** Outputs have not been calibrated or verified against observed water levels or flood gauges.
