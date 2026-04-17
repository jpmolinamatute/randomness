from email.message import Message
from http import HTTPStatus
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from spotify.helpers import CustomHTTPServer, RequestHandler


class MockRequest:
    def __init__(self) -> None:
        pass

    def makefile(self, *args, **kwargs) -> BytesIO:
        return BytesIO(b"")


class MockRequestHandler(RequestHandler):
    response_code: int

    def __init__(self, path: str, server: MagicMock, wfile: BytesIO) -> None:
        self.path = path
        self.server = server
        self.wfile = wfile
        self.headers = Message()

    def send_response(self, code: int, message: str | None = None) -> None:
        self.response_code = code

    def end_headers(self) -> None:
        pass


def build_mock_handler(
    request_path: str, expected_state: str
) -> tuple[MockRequestHandler, BytesIO, MagicMock]:
    """Helper to construct a mock RequestHandler without socket binding."""
    # We mock the environment variable locally inside this test helper
    # because some paths read it during do_GET
    wfile = BytesIO()

    mock_server = MagicMock(spec=CustomHTTPServer)
    mock_server.callback = MagicMock()

    handler = MockRequestHandler(request_path, mock_server, wfile)
    return handler, wfile, mock_server.callback


def test_request_handler_404_not_found() -> None:
    """Test missing/invalid paths yield a 404 response."""
    handler, wfile, mock_callback = build_mock_handler("/invalid_path", "test_state")

    handler.do_GET()

    assert handler.response_code == HTTPStatus.NOT_FOUND
    assert wfile.getvalue() == b"Not Found"
    mock_callback.assert_not_called()


def test_request_handler_400_missing_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test missing code parameter yields a 400 response."""
    monkeypatch.setenv("SPOTIFY_STATE", "test_state")
    handler, wfile, mock_callback = build_mock_handler("/callback?state=test_state", "test_state")

    handler.do_GET()

    assert handler.response_code == HTTPStatus.BAD_REQUEST
    assert wfile.getvalue() == b"State mismatch or missing code"
    mock_callback.assert_not_called()


def test_request_handler_400_invalid_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test mismatched state yields a 400 response."""
    monkeypatch.setenv("SPOTIFY_STATE", "test_state")
    handler, wfile, mock_callback = build_mock_handler(
        "/callback?code=123&state=bad_state", "test_state"
    )

    handler.do_GET()

    assert handler.response_code == HTTPStatus.BAD_REQUEST
    assert wfile.getvalue() == b"State mismatch or missing code"
    mock_callback.assert_not_called()


def test_request_handler_200_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test valid parameters invoke callback and return a 200 response."""
    monkeypatch.setenv("SPOTIFY_STATE", "test_state")
    handler, wfile, mock_callback = build_mock_handler(
        "/callback?code=valid_code123&state=test_state", "test_state"
    )

    handler.do_GET()

    assert handler.response_code == HTTPStatus.OK
    assert wfile.getvalue() == b"Authorization successful. You may close this tab."
    mock_callback.assert_called_once_with("valid_code123")
