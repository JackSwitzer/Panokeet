#!/usr/bin/env python3
"""Simple server that serves editor and receives JSON from iPad."""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from pathlib import Path
from datetime import datetime

class EditorHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/save':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            try:
                data = json.loads(post_data.decode('utf-8'))
                canvas_type = data.get('type', 'unknown')  # 'idle' or 'active'
                pixels = data.get('pixels', [])

                # Save JSON
                output_dir = Path('received')
                output_dir.mkdir(exist_ok=True)

                timestamp = datetime.now().strftime('%H%M%S')
                filename = f"{canvas_type}_{timestamp}.json"
                filepath = output_dir / filename

                with open(filepath, 'w') as f:
                    json.dump(pixels, f)

                # Also save as latest
                latest_path = output_dir / f"{canvas_type}_latest.json"
                with open(latest_path, 'w') as f:
                    json.dump(pixels, f)

                print(f"✓ Received {canvas_type} → {filepath}")

                # Send success response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'file': filename}).encode())

            except Exception as e:
                print(f"✗ Error: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def run(port=8899):
    server = HTTPServer(('0.0.0.0', port), EditorHandler)
    print(f"🦜 Panokeet Editor Server")
    print(f"   Local:     http://localhost:{port}/editor.html")
    print(f"   Tailscale: http://100.80.140.98:{port}/editor.html")
    print(f"   Received files → ./received/")
    print(f"\nWaiting for submissions from iPad...\n")
    server.serve_forever()

if __name__ == '__main__':
    run()
