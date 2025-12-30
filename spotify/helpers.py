from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from os import environ
from typing import Any
from urllib.parse import parse_qs, urlparse

_AfInetAddress = tuple[str, int]


class CustomHTTPServer(HTTPServer):
    """HTTP server that stores a callback to deliver the authorization code.

    The callback receives the authorization code string extracted from the
    redirect request. Error handling is done in the caller (Auth.authenticate).
    """

    def __init__(
        self,
        server_address: _AfInetAddress,
        request_class: type[BaseHTTPRequestHandler],
        callback: Callable[[str], Any],
    ) -> None:
        super().__init__(server_address, request_class)
        self.callback = callback


class RequestHandler(BaseHTTPRequestHandler):
    """Handle the single OAuth redirect GET request.

    Expected path: /callback?code=...&state=...
    On success: invokes server.callback(code) and returns 200.
    On failure: returns 400 with a short error message.
    Any other path: 404.
    """

    # pylint: disable=invalid-name
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return

        # Extract query params
        params = parse_qs(parsed.query)
        code: str | None = params.get("code", [None])[0]
        state: str | None = params.get("state", [None])[0]
        # Fail fast if not present; standardize strict env access
        expected_state = environ["SPOTIFY_STATE"]

        if code and state == expected_state:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorization successful. You may close this tab.")
            # Invoke callback AFTER responding so browser doesn't hang.
            self.server.callback(code)  # type: ignore[attr-defined]
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"State mismatch or missing code")
