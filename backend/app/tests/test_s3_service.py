"""Unit tests for S3 service utility functions."""

import pytest

from app.services.s3_service import parse_s3_uri


class TestParseS3Uri:
    def test_valid_uri(self):
        bucket, key = parse_s3_uri("s3://my-bucket/path/to/backup.tar.gz")
        assert bucket == "my-bucket"
        assert key == "path/to/backup.tar.gz"

    def test_single_level_key(self):
        bucket, key = parse_s3_uri("s3://bucket/file.tar.gz")
        assert bucket == "bucket"
        assert key == "file.tar.gz"

    def test_deeply_nested_key(self):
        bucket, key = parse_s3_uri("s3://prod-backups/cloudtab/us-east/2024/01/backup.tar.gz")
        assert bucket == "prod-backups"
        assert key == "cloudtab/us-east/2024/01/backup.tar.gz"

    def test_invalid_scheme(self):
        with pytest.raises(ValueError, match="Not a valid S3 URI"):
            parse_s3_uri("https://bucket/key")

    def test_empty_string(self):
        with pytest.raises(ValueError, match="Not a valid S3 URI"):
            parse_s3_uri("")

    def test_missing_key(self):
        with pytest.raises(ValueError, match="missing bucket or key"):
            parse_s3_uri("s3://bucket/")

    def test_missing_bucket(self):
        with pytest.raises(ValueError, match="missing bucket or key"):
            parse_s3_uri("s3:///key")

    def test_only_protocol(self):
        with pytest.raises(ValueError, match="missing bucket or key"):
            parse_s3_uri("s3://")

    def test_key_with_spaces(self):
        bucket, key = parse_s3_uri("s3://bucket/path with spaces/file.tar.gz")
        assert bucket == "bucket"
        assert key == "path with spaces/file.tar.gz"
