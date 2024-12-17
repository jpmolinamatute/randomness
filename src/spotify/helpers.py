from http.server import BaseHTTPRequestHandler, HTTPServer
from os import environ
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse


_AfInetAddress = tuple[str, int]


class CustomHTTPServer(HTTPServer):
    def __init__(
        self,
        server_address: _AfInetAddress,
        request_class: type[BaseHTTPRequestHandler],
        callback: Callable[[str], Any],
    ) -> None:
        super().__init__(server_address, request_class)
        self.callback = callback


class RequestHandler(BaseHTTPRequestHandler):
    server: CustomHTTPServer

    def do_GET(self) -> None:
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/callback":
            query_params = parse_qs(parsed_path.query)
            code = query_params.get("code", [None])[0]
            state = query_params.get("state", [None])[0]
            if code and state == environ["SPOTIFY_STATE"]:
                self.send_response(200)
                self.end_headers()
                self.server.callback(code)
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch error")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
