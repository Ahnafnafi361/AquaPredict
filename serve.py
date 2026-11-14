import http.server
import socketserver
import os
import sys
import webbrowser
import json
import urllib.parse

PORT = 8000
DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

_CACHED_SCENARIOS_DATA = None

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
        
    def end_headers(self):
        # CORS Handling: Wildcard '*' is permitted only for local development iteration.
        # SECURITY MANDATE: In public/production deployment, Access-Control-Allow-Origin MUST NOT
        # remain a wildcard '*'; it must be restricted to the explicit frontend origin(s)
        # via the AQUAPREDICT_CORS_ORIGIN environment variable.
        cors_origin = os.environ.get('AQUAPREDICT_CORS_ORIGIN', '*')
        self.send_header('Access-Control-Allow-Origin', cors_origin)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def _send_json(self, status_code, data):
        payload = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        # Health check endpoint
        if parsed.path == '/api/health':
            return self._send_json(200, {
                "status": "healthy",
                "service": "AquaPredict",
                "version": "0.10.0",
                "pilot_area": "Downtown Houston / Buffalo Bayou",
                "bounding_box_wgs84": [-95.3750, 29.7560, -95.3650, 29.7650],
                "provenance_label": "AquaPredict Screening Model & ML Surrogate",
                "validation_status": "UNVALIDATED against real-world flood observations"
            })

        # Route: /api/terrain/heightmap
        if parsed.path == '/api/terrain/heightmap':
            params = urllib.parse.parse_qs(parsed.query)
            res_param = params.get('res', params.get('resolution', ['256']))[0]
            try:
                res_val = int(res_param)
                if res_val < 16 or res_val > 1024:
                    return self._send_json(400, {
                        "status": "error",
                        "error_code": "INVALID_RESOLUTION",
                        "message": "Resolution must be an integer between 16 and 1024."
                    })
            except ValueError:
                res_val = 256

            cached_file = os.path.join(DIRECTORY, 'data', 'terrain_heightmap_256.json')
            if res_val == 256 and os.path.exists(cached_file):
                with open(cached_file, 'rb') as f:
                    payload = f.read()
            else:
                from scripts.generate_heightmap import extract_heightmap
                hm = extract_heightmap(resolution=res_val)
                payload = json.dumps(hm).encode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/simulations':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 10 * 1024 * 1024:  # 10 MB limit
                return self._send_json(413, {
                    "status": "error",
                    "error_code": "PAYLOAD_TOO_LARGE",
                    "message": "Request payload exceeds 10MB limit."
                })
            if content_length > 0:
                try:
                    raw_body = self.rfile.read(content_length)
                    body = json.loads(raw_body.decode('utf-8'))
                except Exception as e:
                    return self._send_json(400, {
                        "status": "error",
                        "error_code": "MALFORMED_JSON",
                        "message": f"Could not parse JSON body: {str(e)}",
                        "provenance_label": "SYNTHETIC SURROGATE",
                        "validation_status": "UNVALIDATED against real-world flood observations"
                    })
            else:
                body = {}

            mode = body.get('mode', 'surrogate')
            if mode not in ('surrogate', 'original'):
                return self._send_json(400, {
                    "status": "error",
                    "error_code": "UNSUPPORTED_MODE",
                    "message": f"Unsupported simulation mode '{mode}'. Supported modes: 'surrogate', 'original'.",
                    "provenance_label": "SYNTHETIC SURROGATE",
                    "validation_status": "UNVALIDATED against real-world flood observations"
                })

            if mode == 'surrogate':
                try:
                    from ml.surrogate.predict import predict_surrogate_frame, is_model_available
                except Exception as e:
                    return self._send_json(503, {
                        "status": "error",
                        "error_code": "SURROGATE_DEPENDENCY_ERROR",
                        "message": f"Surrogate dependencies failed to load: {str(e)}",
                        "provenance_label": "SYNTHETIC SURROGATE",
                        "validation_status": "UNVALIDATED against real-world flood observations"
                    })

                if not is_model_available():
                    return self._send_json(503, {
                        "status": "error",
                        "error_code": "SURROGATE_MODEL_NOT_FOUND",
                        "message": "ML surrogate model artifact not found. Please train the model first.",
                        "provenance_label": "SYNTHETIC SURROGATE",
                        "validation_status": "UNVALIDATED against real-world flood observations"
                    })

                rainfall_mm = body.get('rainfall_mm', body.get('rainfall_total_mm', body.get('target_rainfall_mm', 50.0)))
                duration_min = body.get('duration_minutes', body.get('duration_min', 180))
                time_min = body.get('time_minutes', body.get('time_min'))
                if time_min is None:
                    step_idx = body.get('step_idx')
                    if step_idx is not None:
                        try:
                            time_min = int(step_idx) * 5
                        except (ValueError, TypeError):
                            time_min = 90
                    else:
                        time_min = int(duration_min) // 2

                temporal_shape = body.get('temporal_shape', 0.33)
                drain_rate = body.get('drain_rate', 0.05)

                try:
                    resp = predict_surrogate_frame(
                        rainfall_total_mm=rainfall_mm,
                        duration_min=duration_min,
                        time_min=time_min,
                        temporal_shape=temporal_shape,
                        drain_rate=drain_rate
                    )
                    return self._send_json(200, resp)
                except ValueError as ve:
                    return self._send_json(400, {
                        "status": "error",
                        "error_code": "INVALID_INPUT",
                        "message": str(ve),
                        "provenance_label": "SYNTHETIC SURROGATE",
                        "validation_status": "UNVALIDATED against real-world flood observations"
                    })
                except Exception as e:
                    return self._send_json(500, {
                        "status": "error",
                        "error_code": "INTERNAL_SURROGATE_ERROR",
                        "message": str(e),
                        "provenance_label": "SYNTHETIC SURROGATE",
                        "validation_status": "UNVALIDATED against real-world flood observations"
                    })

            elif mode == 'original':
                scenarios_file = os.path.join(DIRECTORY, 'data', 'simulation_scenarios.json')
                if not os.path.isfile(scenarios_file):
                    return self._send_json(503, {
                        "status": "error",
                        "error_code": "SIMULATION_DATA_NOT_FOUND",
                        "message": "Original simulation scenarios dataset not found."
                    })
                try:
                    global _CACHED_SCENARIOS_DATA
                    if _CACHED_SCENARIOS_DATA is None:
                        with open(scenarios_file, 'r', encoding='utf-8') as f:
                            _CACHED_SCENARIOS_DATA = json.load(f)

                    data = _CACHED_SCENARIOS_DATA
                    presets = data.get('presets', {})

                    preset_id = body.get('preset_id')
                    if not preset_id:
                        rainfall = float(body.get('rainfall_mm', body.get('target_rainfall_mm', 50)))
                        closest_key = min(presets.keys(), key=lambda k: abs(presets[k].get('target_rainfall_mm', 0) - rainfall))
                        preset_id = closest_key

                    if preset_id not in presets:
                        return self._send_json(400, {
                            "status": "error",
                            "error_code": "INVALID_PRESET",
                            "message": f"Unknown preset_id: '{preset_id}'. Available: {list(presets.keys())}"
                        })

                    preset = presets[preset_id]
                    timesteps = preset.get('timesteps', [])
                    time_min = body.get('time_minutes', body.get('time_min'))
                    step_idx = body.get('step_idx')

                    selected_step = None
                    if step_idx is not None:
                        idx = int(step_idx)
                        if 0 <= idx < len(timesteps):
                            selected_step = timesteps[idx]
                        else:
                            return self._send_json(400, {
                                "status": "error",
                                "error_code": "INVALID_STEP_INDEX",
                                "message": f"Step index {idx} out of range (0-{len(timesteps)-1})."
                            })
                    elif time_min is not None:
                        t_req = float(time_min)
                        selected_step = min(timesteps, key=lambda s: abs(s.get('time_minutes', 0) - t_req))
                    else:
                        selected_step = timesteps[len(timesteps) // 2]

                    return self._send_json(200, {
                        "status": "success",
                        "mode": "original",
                        "model_type": "SCREENING SIMULATION",
                        "provenance_label": "AquaPredict M5 Hydrological Screening Model",
                        "validation_status": "EXPLORATORY MODELLED OUTPUTS — NOT A CERTIFIED REAL-TIME FLOOD WARNING SYSTEM",
                        "timestep": selected_step,
                        "metadata": {
                            "preset_id": preset_id,
                            "target_rainfall_mm": preset.get('target_rainfall_mm'),
                            "duration_minutes": preset.get('duration_minutes'),
                            "framework": "Deterministic Physical Screening Model"
                        }
                    })
                except Exception as e:
                    return self._send_json(500, {
                        "status": "error",
                        "error_code": "ORIGINAL_SIMULATION_ERROR",
                        "message": str(e)
                    })

        self.send_error(404, "Endpoint not found")

    def guess_type(self, path):
        # Ensure geojson and json are served with correct mime type
        if path.endswith('.geojson'):
            return 'application/geo+json'
        if path.endswith('.json'):
            return 'application/json'
        return super().guess_type(path)

class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = False
    daemon_threads = True

def run():
    port = PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass

    server_address = ("", port)
    with ThreadingServer(server_address, CustomHandler) as httpd:
        url = f"http://localhost:{port}"
        print("=" * 65)
        print(" AquaPredict - Urban Waterlogging Risk Visualization Prototype")
        print(f" Houston Pilot M0 Server running at: {url}")
        print("=" * 65)
        print(" Press Ctrl+C to stop the server.")
        print("-" * 65)
        
        # Optionally auto-open browser if flag provided
        if "--open" in sys.argv:
            webbrowser.open(url)
            
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server gracefully...")

if __name__ == "__main__":
    run()
