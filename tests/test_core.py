"""Tests for core functionality."""

import pytest
from writing_assistant.core.definitions import Metadata


def test_metadata_creation():
    """Test that Metadata can be created with default values."""
    metadata = Metadata()
    assert metadata.writing_style == "formal"
    assert metadata.target_audience == "general public"
    assert metadata.tone == "neutral"
    assert metadata.word_limit == 250


def test_metadata_customization():
    """Test that Metadata can be customized."""
    metadata = Metadata()
    metadata.writing_style = "casual"
    metadata.target_audience = "students"
    metadata.tone = "friendly"
    metadata.word_limit = 500

    assert metadata.writing_style == "casual"
    assert metadata.target_audience == "students"
    assert metadata.tone == "friendly"
    assert metadata.word_limit == 500