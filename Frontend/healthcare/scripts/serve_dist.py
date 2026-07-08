from __future__ import annotations

import argparse
import http.server
import os
import socketserver
from pathlib import Path


class SpaHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        target = self.translate_path(self.path)
        if self.path == "/" or os.path.exists(target):
            return super().do_GET()

        self.path = "/index.html"
        return super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a Vite dist folder with SPA fallback.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument(
        "--dist",
        default=str(Path(__file__).resolve().parents[1] / "dist"),
    )
    args = parser.parse_args()

    dist_path = Path(args.dist).resolve()
    os.chdir(dist_path)
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer((args.host, args.port), SpaHandler) as httpd:
        print(f"Serving {dist_path} at http://{args.host}:{args.port}", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
