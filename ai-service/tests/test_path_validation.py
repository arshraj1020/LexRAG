"""
Path traversal / file path validation tests.

Verifies the ingest endpoint's _validate_file_path helper:
1. Paths within upload_dir are accepted.
2. Paths outside upload_dir (absolute or relative traversal) are rejected.
3. Non-existent files are rejected.
4. Non-regular-files (directories, symlinks to outside) are rejected.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException


# ── Import the validator from routes ─────────────────────────
# We import directly so we can unit-test the path check without HTTP overhead.
from app.api.routes import _validate_file_path


@pytest.fixture()
def upload_dir(tmp_path):
    """Temporary upload directory, patched into _UPLOAD_DIR."""
    upload = tmp_path / "uploads"
    upload.mkdir()
    with patch("app.api.routes._UPLOAD_DIR", upload.resolve()):
        yield upload


class TestValidateFilePath:
    def test_valid_file_within_upload_dir(self, upload_dir):
        """A PDF file inside the upload dir must be accepted."""
        owner = upload_dir / "user-1"
        owner.mkdir()
        pdf = owner / "document.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake content")
        result = _validate_file_path(str(pdf))
        assert result == pdf.resolve()

    def test_path_traversal_dot_dot_rejected(self, upload_dir):
        """../etc/passwd style traversal must be rejected with 400."""
        malicious = str(upload_dir) + "/../../etc/passwd"
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_path(malicious)
        assert exc_info.value.status_code == 400

    def test_absolute_path_outside_upload_dir_rejected(self, upload_dir):
        """Absolute path to /etc/passwd must be rejected."""
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_path("/etc/passwd")
        assert exc_info.value.status_code == 400

    def test_nonexistent_file_rejected(self, upload_dir):
        """A path that doesn't exist must be rejected."""
        missing = str(upload_dir / "ghost.pdf")
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_path(missing)
        assert exc_info.value.status_code == 400

    def test_directory_rejected(self, upload_dir):
        """A directory path (not a file) must be rejected."""
        subdir = upload_dir / "subdir"
        subdir.mkdir()
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_path(str(subdir))
        assert exc_info.value.status_code == 400

    def test_nested_file_inside_upload_dir_accepted(self, upload_dir):
        """Files in subdirectories of upload_dir must be accepted."""
        nested = upload_dir / "tenant-a" / "2024" / "case.pdf"
        nested.parent.mkdir(parents=True)
        nested.write_bytes(b"PDF content")
        result = _validate_file_path(str(nested))
        assert result == nested.resolve()

    def test_empty_path_rejected(self, upload_dir):
        """An empty string path must be rejected."""
        with pytest.raises((HTTPException, Exception)):
            _validate_file_path("")
