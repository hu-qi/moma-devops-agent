import os
from http.server import BaseHTTPRequestHandler, HTTPServer

UPLOAD_DIR = "/var/data/uploads"


class FileHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        filename = self.path.lstrip("/")
        filepath = os.path.join(UPLOAD_DIR, filename)

        if not os.path.isfile(filepath):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"File not found")
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        with open(filepath, "rb") as f:
            self.wfile.write(f.read())


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), FileHandler)
    server.serve_forever()
