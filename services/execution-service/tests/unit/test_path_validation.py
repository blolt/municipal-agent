"""Unit tests for path validation."""

import pytest
from pathlib import Path

from src.utils.path_validation import (
    PathValidationError,
    extract_path_from_arguments,
    get_sandbox_directory,
    validate_path,
    validate_paths,
)


def test_get_sandbox_directory_creates_if_not_exists(tmp_path, monkeypatch):
    """Test that sandbox directory is created if it doesn't exist."""
    sandbox = tmp_path / "sandbox"
    monkeypatch.setattr("src.utils.path_validation.settings.sandbox_directory", str(sandbox))

    result = get_sandbox_directory()

    assert result.exists()
    assert result.is_dir()
    assert result == sandbox.resolve()


def test_validate_path_accepts_relative_path_within_sandbox(tmp_path, monkeypatch):
    """Test that relative paths within sandbox are accepted."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setattr("src.utils.path_validation.settings.sandbox_directory", str(sandbox))

    result = validate_path("test.txt")

    assert result == (sandbox / "test.txt").resolve()


def test_validate_path_accepts_absolute_path_within_sandbox(tmp_path, monkeypatch):
    """Test that absolute paths within sandbox are accepted."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    test_file = sandbox / "test.txt"
    monkeypatch.setattr("src.utils.path_validation.settings.sandbox_directory", str(sandbox))

    result = validate_path(str(test_file))

    assert result == test_file.resolve()


def test_validate_path_rejects_path_outside_sandbox(tmp_path, monkeypatch):
    """Test that paths outside sandbox are rejected."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside_path = tmp_path / "outside.txt"
    monkeypatch.setattr("src.utils.path_validation.settings.sandbox_directory", str(sandbox))

    with pytest.raises(PathValidationError, match="outside sandbox directory"):
        validate_path(str(outside_path))


def test_validate_path_rejects_parent_directory_traversal(tmp_path, monkeypatch):
    """Test that parent directory traversal is blocked."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setattr("src.utils.path_validation.settings.sandbox_directory", str(sandbox))

    with pytest.raises(PathValidationError, match="outside sandbox directory"):
        validate_path("../outside.txt")


def test_validate_path_rejects_symlink_escape(tmp_path, monkeypatch):
    """Test that symlinks pointing outside sandbox are blocked."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("secret")
    symlink = sandbox / "link.txt"
    symlink.symlink_to(outside_file)
    monkeypatch.setattr("src.utils.path_validation.settings.sandbox_directory", str(sandbox))

    # Symlink resolution should detect it points outside sandbox
    with pytest.raises(PathValidationError, match="outside sandbox directory"):
        validate_path(str(symlink))


def test_validate_paths_validates_multiple_paths(tmp_path, monkeypatch):
    """Test that multiple paths can be validated at once."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setattr("src.utils.path_validation.settings.sandbox_directory", str(sandbox))

    paths = ["file1.txt", "dir/file2.txt", "file3.txt"]
    results = validate_paths(paths)

    assert len(results) == 3
    assert all(isinstance(p, Path) for p in results)
    assert all(str(p).startswith(str(sandbox)) for p in results)


def test_validate_paths_raises_on_any_invalid_path(tmp_path, monkeypatch):
    """Test that validation fails if any path is invalid."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setattr("src.utils.path_validation.settings.sandbox_directory", str(sandbox))

    paths = ["valid.txt", "../invalid.txt", "also_valid.txt"]

    with pytest.raises(PathValidationError):
        validate_paths(paths)


def test_extract_path_from_arguments_finds_common_keys():
    """Test that path extraction finds common argument keys."""
    arguments = {
        "path": "/tmp/test.txt",
        "other_arg": "value",
        "count": 5,
    }

    paths = extract_path_from_arguments(arguments)

    assert paths == ["/tmp/test.txt"]


def test_extract_path_from_arguments_finds_multiple_keys():
    """Test that path extraction finds multiple path keys."""
    arguments = {
        "source": "/tmp/source.txt",
        "destination": "/tmp/dest.txt",
        "other": "value",
    }

    paths = extract_path_from_arguments(arguments)

    assert set(paths) == {"/tmp/source.txt", "/tmp/dest.txt"}


def test_extract_path_from_arguments_handles_list_of_paths():
    """Test that path extraction handles lists of paths."""
    arguments = {
        "paths": ["/tmp/file1.txt", "/tmp/file2.txt"],
        "other": "value",
    }

    paths = extract_path_from_arguments(arguments)

    assert paths == ["/tmp/file1.txt", "/tmp/file2.txt"]


def test_extract_path_from_arguments_returns_empty_if_no_paths():
    """Test that path extraction returns empty list if no paths found."""
    arguments = {
        "count": 5,
        "name": "test",
    }

    paths = extract_path_from_arguments(arguments)

    assert paths == []
