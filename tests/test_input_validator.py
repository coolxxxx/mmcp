from src.core.security.input_validator import (
    ValidationLevel,
    validate_file_path,
    validate_url,
)


def test_strict_url_validation_accepts_generic_public_domains():
    result = validate_url("https://example.com/gallery/page.html", ValidationLevel.STRICT)

    assert result["valid"] is True


def test_strict_url_validation_rejects_localhost():
    result = validate_url("http://localhost/admin", ValidationLevel.STRICT)

    assert result["valid"] is False


def test_strict_url_validation_rejects_private_ip_addresses():
    result = validate_url("http://192.168.1.20/image.jpg", ValidationLevel.STRICT)

    assert result["valid"] is False


def test_file_path_validation_accepts_windows_drive_paths():
    result = validate_file_path("C:\\Users\\tester\\image.jpg", ValidationLevel.STRICT)

    assert result["valid"] is True


def test_file_path_validation_rejects_colon_outside_drive_prefix():
    result = validate_file_path("downloads\\bad:name.jpg", ValidationLevel.STRICT)

    assert result["valid"] is False
    assert any("无效字符" in error for error in result["errors"])
