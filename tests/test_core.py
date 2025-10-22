"""Tests for core functionality."""

from unittest.mock import MagicMock, patch

import pytest

from writing_assistant.core.callbacks import get_system_prompt, new_paragraph
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


def test_get_system_prompt_ideas():
    """Test get_system_prompt for ideas mode."""
    prompt = get_system_prompt("ideas")
    assert "bulleted list" in prompt
    assert "actionable improvement suggestions" in prompt


def test_get_system_prompt_rewrite():
    """Test get_system_prompt for rewrite mode."""
    prompt = get_system_prompt("rewrite")
    assert "Completely rewrite" in prompt
    assert "clarity, engagement, and impact" in prompt


def test_get_system_prompt_improve():
    """Test get_system_prompt for improve mode."""
    prompt = get_system_prompt("improve")
    assert "Enhance the provided" in prompt
    assert "Strengthening word choices" in prompt


def test_get_system_prompt_proofread():
    """Test get_system_prompt for proofread mode."""
    prompt = get_system_prompt("proofread")
    assert "Proofread the current paragraph" in prompt
    assert "Grammar errors" in prompt


def test_get_system_prompt_default():
    """Test get_system_prompt for unknown mode (falls back to default)."""
    prompt = get_system_prompt("unknown_mode")
    assert "Rewrite or improve" in prompt
    assert "provided paragraph" in prompt


@patch('writing_assistant.core.callbacks.fillTemplate')
@patch('writing_assistant.core.callbacks.Print')
@patch('writing_assistant.core.callbacks.LLMPrompt')
def test_new_paragraph_string_result(mock_llm, mock_print, mock_fill):
    """Test new_paragraph when LLM returns a string result."""
    # Setup mocks for the pipeline chain
    mock_function = MagicMock(return_value="  Generated text with whitespace  ")
    mock_pipeline = MagicMock()
    mock_pipeline.as_function.return_value = mock_function

    # Mock the pipeline chaining: fillTemplate | Print | LLMPrompt
    mock_fill.return_value.__or__.return_value.__or__.return_value = mock_pipeline

    metadata = Metadata()
    result = new_paragraph("Test text", metadata)

    assert result == "Generated text with whitespace"


@patch('writing_assistant.core.callbacks.fillTemplate')
@patch('writing_assistant.core.callbacks.Print')
@patch('writing_assistant.core.callbacks.LLMPrompt')
def test_new_paragraph_non_string_result(mock_llm, mock_print, mock_fill):
    """Test new_paragraph when LLM returns a non-string result."""
    # Setup mocks to return a non-string result
    non_string_result = {"generated": "text"}
    mock_function = MagicMock(return_value=non_string_result)
    mock_pipeline = MagicMock()
    mock_pipeline.as_function.return_value = mock_function

    # Mock the pipeline chaining: fillTemplate | Print | LLMPrompt
    mock_fill.return_value.__or__.return_value.__or__.return_value = mock_pipeline

    metadata = Metadata()
    result = new_paragraph("Test text", metadata)

    assert result == non_string_result