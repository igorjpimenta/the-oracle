# flake8: noqa: F811
"""
Pytest test suite for WhisperTranscriptionTool

This module contains comprehensive tests for the Whisper transcription
functionality using pytest framework.

Usage:
    pytest test_whisper_transcription_pytest.py -v
    pytest test_whisper_transcription_pytest.py::test_basic_initialization -v
"""

import os
import tempfile
import uuid
from typing import Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

try:
    from ..whisper_transcription import (
        WhisperTranscriptionTool,
        transcribe_audio_tool,
        _create_whisper_tool,
        WhisperAvailableModels
    )
except ImportError as e:
    pytest.skip(
        f"Import error: {e}.",
        allow_module_level=True
    )

# Check for required dependencies
try:
    import whisper as _  # type: ignore  # noqa: F401
    import torch as _  # noqa: F401
except ImportError as e:
    pytest.skip(
        f"Missing required dependency: {e}. "
        f"Install with: pipenv install openai-whisper torch",
        allow_module_level=True
    )


@pytest.fixture
def test_session_id() -> str:
    """Fixture providing a test session ID"""
    return str(uuid.uuid4())


@pytest.fixture
def temp_files_cleanup() -> Generator[Callable[[str], None], None, None]:
    """Fixture for tracking and cleaning up temporary files"""
    temp_files = []

    def add_temp_file(file_path):
        temp_files.append(file_path)
        return file_path

    yield add_temp_file

    # Cleanup
    for file_path in temp_files:
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass  # Ignore cleanup errors


@pytest.fixture
def dummy_audio_file(
    temp_files_cleanup: Callable[[str], None]
) -> Callable[[str], tuple[str, bytes]]:
    """Fixture providing a dummy audio file for testing"""
    def create_audio_file(
        filename: str = "test_audio.mp3"
    ) -> tuple[str, bytes]:
        # Create a simple WAV file header (minimal valid WAV)
        wav_header = (
            b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00'
            b'\x44\xAC\x00\x00\x88\x58\x01\x00\x04\x00\x10\x00data\x00\x08'
            b'\x00\x00'
        )
        dummy_audio_data = wav_header + b'\x00' * 1000

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(filename)[1]
        )
        temp_file.write(dummy_audio_data)
        temp_file.close()

        temp_files_cleanup(temp_file.name)
        return temp_file.name, dummy_audio_data

    return create_audio_file


@pytest.fixture
def whisper_tool() -> WhisperTranscriptionTool:
    """Fixture providing a WhisperTranscriptionTool instance"""
    return WhisperTranscriptionTool()


class TestWhisperTranscriptionTool:
    """Group of tests for WhisperTranscriptionTool"""

    def test_basic_initialization(self) -> None:
        """Test basic tool initialization with different models"""
        # Test with default model
        tool = WhisperTranscriptionTool()
        assert tool.whisper_model == "base"
        assert tool.supported_languages == ["en", "es", "auto"]

        # Test with different models
        models: list[WhisperAvailableModels] = \
            ["base", "small", "medium", "large"]

        for model in models:
            tool = WhisperTranscriptionTool(whisper_model=model)
            assert tool.whisper_model == model

    def test_file_format_validation(
            self, whisper_tool: WhisperTranscriptionTool
    ) -> None:
        """Test file format validation"""
        # Test supported formats
        supported_files = [
            "test.mp3", "test.wav", "test.m4a", "test.mp4",
            "test.mov", "test.avi", "test.flv", "test.wmv"
        ]

        for filename in supported_files:
            assert whisper_tool._is_supported_format(filename)

        # Test unsupported formats
        unsupported_files = [
            "test.txt", "test.pdf", "test.doc", "test.xyz"
        ]

        for filename in unsupported_files:
            assert not whisper_tool._is_supported_format(filename)

    def test_language_validation(
            self, whisper_tool: WhisperTranscriptionTool
    ) -> None:
        """Test language validation and normalization"""
        test_cases = [
            (None, "auto"),
            ("en", "en"),
            ("es", "es"),
            ("auto", "auto"),
            ("English", "en"),
            ("Spanish", "es"),
            ("invalid", "auto")
        ]

        for input_lang, expected in test_cases:
            result = whisper_tool._validate_language(input_lang)
            assert result == expected

    @patch('app.core.tools.whisper_transcription.whisper.load_model')
    def test_whisper_model_loading(self, mock_load_model: MagicMock) \
            -> None:
        """Test Whisper model loading"""
        # Mock the whisper model
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model

        tool = WhisperTranscriptionTool(whisper_model="base")

        # Verify model was loaded
        mock_load_model.assert_called_with("base")
        assert tool._model == mock_model

    @patch('app.core.tools.whisper_transcription.whisper.load_model')
    def test_transcription_with_mock(
        self,
        mock_load_model: MagicMock,
        dummy_audio_file: Callable[[str], tuple[str, bytes]]
    ) -> None:
        """Test transcription with mocked Whisper model"""
        # Create mock model and transcription result
        mock_model = MagicMock()
        mock_transcription_result = {
            "text": "This is a test transcription",
            "language": "en",
            "segments": [
                {
                    "start": 0.0,
                    "end": 3.0,
                    "text": "This is a test transcription",
                    "avg_logprob": -0.5,
                    "tokens": [],
                    "temperature": 0.0,
                    "compression_ratio": 1.0,
                    "no_speech_prob": 0.1
                }
            ]
        }
        mock_model.transcribe.return_value = mock_transcription_result
        mock_load_model.return_value = mock_model

        # Create dummy audio file
        audio_file_path, _ = dummy_audio_file("test.wav")

        # Test transcription
        tool = WhisperTranscriptionTool()
        result = tool._transcribe_audio_file(
            audio_file_path, language="en"
        )

        # Verify results
        assert result["text"] == "This is a test transcription"
        assert result["language"] == "en"
        assert result["confidence_score"] is not None
        assert "processing_time_seconds" in result

    def test_factory_function(self) -> None:
        """Test the factory function for creating tool instances"""
        # Test factory function with different models
        models: list[WhisperAvailableModels] = \
            ["base", "small", "medium", "large"]
        for model in models:
            tool = _create_whisper_tool(model)
            assert isinstance(tool, WhisperTranscriptionTool)
            assert tool.whisper_model == model

    @pytest.mark.asyncio
    async def test_transcribe_audio_tool_with_mocks(
        self,
        test_session_id: str,
        dummy_audio_file: Callable[[str], tuple[str, bytes]]
    ) -> None:
        """Test the LangGraph tool function with mocked dependencies"""
        # Create dummy audio content
        _, audio_content = dummy_audio_file("test.mp3")

        # Mock all external dependencies
        mock_nyxen_path = (
            'app.core.tools.whisper_transcription.NyxenAPIClient'
        )
        mock_db_path = 'app.core.tools.whisper_transcription.get_db'
        mock_whisper_path = (
            'app.core.tools.whisper_transcription.whisper.load_model'
        )

        with patch(mock_nyxen_path) as mock_nyxen, \
                patch(mock_db_path) as mock_get_db, \
                patch(mock_whisper_path) as mock_load_model:

            # Setup mocks
            mock_client_instance = AsyncMock()
            mock_nyxen.return_value.__aenter__.return_value = (
                mock_client_instance
            )
            mock_client_instance.upload_audio_file.return_value = {
                "id": "test-file-id",
                "originalname": "test.mp3",
                "size": len(audio_content),
                "bucket": "test-bucket",
                "public": True,
                "mimetype": "audio/mpeg"
            }
            url = "https://example.com/test.mp3"
            mock_client_instance.get_media_file_url.return_value = url

            # Mock database
            mock_db = AsyncMock()

            async def async_db_generator():
                yield mock_db

            mock_get_db.return_value = async_db_generator()

            # Mock Whisper model
            mock_model = MagicMock()
            mock_model.transcribe.return_value = {
                "text": "Hello, this is a test transcription",
                "language": "en",
                "segments": []
            }
            mock_load_model.return_value = mock_model

            # Mock database transcription object
            mock_transcription = MagicMock()
            mock_transcription.id = str(uuid.uuid4())
            mock_transcription.session_id = test_session_id
            mock_transcription.transcription_text = (
                "Hello, this is a test transcription"
            )
            mock_transcription.language = "en"
            mock_transcription.confidence_score = 0.95
            mock_transcription.duration_seconds = 3.0
            mock_transcription.audio_file_id = "test-file-id"
            mock_transcription.original_filename = "test.mp3"
            mock_transcription.model = "base"
            mock_transcription.processing_time_seconds = 1.5
            mock_transcription.created_at = "2025-01-09T15:00:00"
            mock_transcription.meta_data = {}

            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock(return_value=mock_transcription)

            # Test the tool function
            result = await transcribe_audio_tool(
                {},  # state parameter
                session_id=test_session_id,
                audio_content=audio_content,
                filename="test.mp3",
                language="en",
                whisper_model="base"
            )

            # Verify results
            assert "messages" in result
            assert "transcription_result" in result
            assert len(result["messages"]) == 1
            msg_content = result["messages"][0].content.lower()
            assert "transcription completed" in msg_content

            transcription_data = result["transcription_result"]
            expected_text = ("Hello, this is a test transcription")
            assert transcription_data["text"] == expected_text
            assert transcription_data["language"] == "en"
            assert transcription_data["filename"] == "test.mp3"

    @pytest.mark.asyncio
    async def test_error_handling(
        self,
        test_session_id: str,
        whisper_tool: WhisperTranscriptionTool
    ) -> None:
        """Test error handling scenarios"""
        # Test unsupported file format
        with pytest.raises(ValueError, match="Unsupported audio format"):
            await whisper_tool.transcribe_audio(
                session_id=test_session_id,
                audio_content=b"fake content",
                filename="test.txt",  # Unsupported format
                language="en"
            )

        # Test transcribe_audio_tool error handling
        result = await transcribe_audio_tool(
            {},  # state parameter
            session_id=test_session_id,
            audio_content=b"fake content",
            filename="test.txt",  # This will cause an error
            language="en"
        )

        # Should return error message
        assert "messages" in result
        assert "transcription_error" in result
        assert "failed" in result["messages"][0].content.lower()


class TestWhisperIntegration:
    """Integration tests for Whisper functionality"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_file_extension_detection(
            self, whisper_tool: WhisperTranscriptionTool
    ) -> None:
        """Test file extension detection"""
        test_cases = [
            ("audio.mp3", ".mp3"),
            ("audio.WAV", ".wav"),
            ("AUDIO.M4A", ".m4a"),
            ("test_file.MP4", ".mp4"),
        ]

        for filename, expected_ext in test_cases:
            result = whisper_tool._get_file_extension(filename)
            assert result == expected_ext

    @pytest.mark.parametrize("model", ["base", "small", "medium", "large"])
    def test_model_initialization_parametrized(self, model) -> None:
        """Test initialization with different models using parametrize"""
        tool = WhisperTranscriptionTool(whisper_model=model)
        assert tool.whisper_model == model

    @pytest.mark.parametrize("filename,expected", [
        ("test.mp3", True),
        ("test.wav", True),
        ("test.txt", False),
        ("test.pdf", False),
    ])
    def test_supported_format_parametrized(
        self, whisper_tool, filename, expected
    ) -> None:
        """Test file format support using parametrize"""
        assert whisper_tool._is_supported_format(filename) == expected


# Pytest markers for test organization
pytestmark = [
    pytest.mark.whisper,
    pytest.mark.transcription,
]


def test_import_dependencies() -> None:
    """Test that all required dependencies can be imported"""
    # This test is mainly to verify the imports work
    assert WhisperTranscriptionTool is not None
    assert transcribe_audio_tool is not None
    assert _create_whisper_tool is not None
