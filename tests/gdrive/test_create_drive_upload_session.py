"""
Unit tests for create_drive_upload_session (resumable upload URL for client-side uploads).
"""

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httplib2
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from gdrive.drive_tools import create_drive_upload_session  # noqa: E402

SESSION_URL = (
    "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable"
    "&supportsAllDrives=true&upload_id=TEST_UPLOAD_ID"
)


def _unwrap(tool):
    fn = tool.fn if hasattr(tool, "fn") else tool
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _service(status="200", location=SESSION_URL, body=b""):
    headers = {"status": status}
    if location:
        headers["location"] = location
    service = MagicMock()
    service._http.request = MagicMock(return_value=(httplib2.Response(headers), body))
    return service


@pytest.mark.asyncio
async def test_starts_resumable_session_with_metadata_and_headers():
    service = _service()
    with patch("gdrive.drive_tools.resolve_folder_id", new_callable=AsyncMock, return_value="FOLDER"):
        result = await _unwrap(create_drive_upload_session)(
            service,
            user_google_email="u@example.com",
            file_name="手引き.pdf",
            folder_id="FOLDER",
            mime_type="application/pdf",
            file_size=662560,
        )

    url = service._http.request.call_args.args[0]
    kwargs = service._http.request.call_args.kwargs
    parsed = urlparse(url)
    assert parsed.netloc == "www.googleapis.com"
    assert parsed.path == "/upload/drive/v3/files"
    query = parse_qs(parsed.query)
    assert query["uploadType"] == ["resumable"]
    assert query["supportsAllDrives"] == ["true"]
    assert "md5Checksum" in query["fields"][0]
    assert kwargs["method"] == "POST"
    assert json.loads(kwargs["body"]) == {
        "name": "手引き.pdf",
        "parents": ["FOLDER"],
        "mimeType": "application/pdf",
    }
    assert kwargs["headers"]["X-Upload-Content-Type"] == "application/pdf"
    assert kwargs["headers"]["X-Upload-Content-Length"] == "662560"
    assert SESSION_URL in result
    assert "curl -sS -X PUT" in result
    assert "exactly 662560 bytes" in result


@pytest.mark.asyncio
async def test_size_header_omitted_when_unknown_and_description_sent():
    service = _service()
    with patch("gdrive.drive_tools.resolve_folder_id", new_callable=AsyncMock, return_value="root"):
        await _unwrap(create_drive_upload_session)(
            service, user_google_email="u@example.com", file_name="a.bin", description="memo"
        )
    kwargs = service._http.request.call_args.kwargs
    assert "X-Upload-Content-Length" not in kwargs["headers"]
    assert kwargs["headers"]["X-Upload-Content-Type"] == "application/octet-stream"
    assert json.loads(kwargs["body"])["description"] == "memo"


@pytest.mark.asyncio
async def test_error_status_is_reported():
    service = _service(status="403", location=None, body=b'{"error": "insufficientPermissions"}')
    with patch("gdrive.drive_tools.resolve_folder_id", new_callable=AsyncMock, return_value="root"):
        with pytest.raises(Exception, match="HTTP 403"):
            await _unwrap(create_drive_upload_session)(
                service, user_google_email="u@example.com", file_name="a.bin"
            )


@pytest.mark.asyncio
async def test_missing_location_is_reported():
    service = _service(location=None)
    with patch("gdrive.drive_tools.resolve_folder_id", new_callable=AsyncMock, return_value="root"):
        with pytest.raises(Exception, match="no upload URL"):
            await _unwrap(create_drive_upload_session)(
                service, user_google_email="u@example.com", file_name="a.bin"
            )


@pytest.mark.asyncio
async def test_negative_size_rejected_before_any_request():
    service = _service()
    with pytest.raises(Exception, match="non-negative"):
        await _unwrap(create_drive_upload_session)(
            service, user_google_email="u@example.com", file_name="a.bin", file_size=-1
        )
    service._http.request.assert_not_called()
