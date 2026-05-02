#!/usr/bin/env python3
"""
Live MJPEG video stream server.

Serves the webcam feed over HTTP — open in any browser, no plugins needed.

Usage:
  python scripts/video_stream.py [--port 8080] [--device 0] [--width 640] [--height 480] [--fps 20]

Then visit:
  http://<pi-ip>:8080/
"""
import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import cv2

_frame: bytes = b""
_frame_lock = threading.Lock()
_running = True

PAGE = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Pi Camera</title>
  <style>
    body { background: #111; margin: 0; display: flex; flex-direction: column;
           align-items: center; justify-content: center; min-height: 100vh; }
    img  { max-width: 100%; border: 2px solid #333; }
    p    { color: #888; font-family: monospace; margin-top: 8px; font-size: 13px; }
  </style>
</head>
<body>
  <img src="/stream" alt="live feed">
  <p>Pi Camera &mdash; MJPEG stream</p>
</body>
</html>
"""


class StreamHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress per-request noise

    def do_GET(self):
        if self.path == "/":
            self._send_page()
        elif self.path == "/stream":
            self._send_stream()
        else:
            self.send_error(404)

    def _send_page(self):
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        try:
            while _running:
                with _frame_lock:
                    jpg = _frame
                if not jpg:
                    time.sleep(0.01)
                    continue
                self.wfile.write(
                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
                )
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


def capture_loop(device: int, width: int, height: int, fps: int) -> None:
    global _frame, _running
    cap = cv2.VideoCapture(device)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)

    if not cap.isOpened():
        print(f"ERROR: cannot open camera device {device}")
        _running = False
        return

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Camera opened: device={device}  {actual_w}x{actual_h}  target={fps}fps")

    delay = 1.0 / fps
    while _running:
        t0 = time.monotonic()
        ok, frame = cap.read()
        if not ok:
            print("WARNING: missed frame")
            time.sleep(0.05)
            continue
        _, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        with _frame_lock:
            _frame = jpg.tobytes()
        elapsed = time.monotonic() - t0
        sleep_for = delay - elapsed
        if sleep_for > 0:
            time.sleep(sleep_for)

    cap.release()


def main() -> None:
    global _running
    parser = argparse.ArgumentParser(description="MJPEG stream server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=20)
    args = parser.parse_args()

    cap_thread = threading.Thread(
        target=capture_loop,
        args=(args.device, args.width, args.height, args.fps),
        daemon=True,
    )
    cap_thread.start()

    # wait for first frame before accepting connections
    print("Waiting for first frame...")
    while not _frame and _running:
        time.sleep(0.05)

    if not _running:
        return

    server = HTTPServer(("0.0.0.0", args.port), StreamHandler)
    print(f"Streaming at  http://0.0.0.0:{args.port}/")
    print(f"  local:     http://172.20.10.6:{args.port}/")
    print(f"  tailscale: http://100.125.43.120:{args.port}/")
    print("Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        _running = False
        server.server_close()


if __name__ == "__main__":
    main()
