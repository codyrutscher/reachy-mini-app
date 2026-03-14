"""Camera streaming server — serves Reachy's camera as MJPEG over HTTP.
Runs on a separate port so the dashboard can embed it as an img tag."""

import io
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

import cv2
import numpy as np

_latest_frame = None
_frame_lock = threading.Lock()
_running = False


class MJPEGHandler(BaseHTTPRequestHandler):
    """Serves MJPEG stream or single snapshot."""

    def do_GET(self):
        if self.path == "/snapshot":
            self._send_snapshot()
        elif self.path == "/stream":
            self._send_stream()
        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b'<html><body><img src="/stream" style="width:100%"></body></html>')
        else:
            self.send_error(404)

    def _send_snapshot(self):
        with _frame_lock:
            frame = _latest_frame
        if frame is None:
            self.send_error(503, "No frame available")
            return
        _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(jpg.tobytes())

    def _send_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            while _running:
                with _frame_lock:
                    frame = _latest_frame
                if frame is not None:
                    _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    data = jpg.tobytes()
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(data)}\r\n\r\n".encode())
                    self.wfile.write(data)
                    self.wfile.write(b"\r\n")
                time.sleep(0.1)  # ~10 fps
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        pass  # suppress logs


def update_frame(frame):
    """Called by the robot to push a new camera frame."""
    global _latest_frame
    with _frame_lock:
        _latest_frame = frame


def start_stream_server(port=5556):
    """Start the MJPEG server in a background thread."""
    global _running
    _running = True
    server = HTTPServer(("0.0.0.0", port), MJPEGHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[CAMERA] Stream server running on http://localhost:{port}/stream")
    return server


def stop_stream_server(server):
    global _running
    _running = False
    if server:
        server.shutdown()
