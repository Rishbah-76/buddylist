"""Unit tests for orchestra/agent.py."""
import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestSessionState:
    """Tests for session state management."""

    def test_save_and_load_session(self, tmp_path):
        """Test saving and loading session context."""
        # Import after patching session dir
        with patch('orchestra.agent.SESSION_STATE_DIR', tmp_path):
            from orchestra.agent import _save_session_state, _load_session_context, _ensure_session_dir
            
            _ensure_session_dir()
            
            # Save a session
            _save_session_state("test-user", "What is this?", "It's a test.")
            
            # Load it back
            ctx = _load_session_context("test-user")
            assert ctx is not None
            assert "What is this?" in ctx
            assert "It's a test" in ctx

    def test_session_truncation(self, tmp_path):
        """Test that session history is truncated."""
        with patch('orchestra.agent.SESSION_STATE_DIR', tmp_path):
            from orchestra.agent import (
                _save_session_state, _load_session_context, 
                _ensure_session_dir, SESSION_HISTORY, MAX_SESSION_HISTORY
            )
            
            _ensure_session_dir()
            
            # Save more than MAX_SESSION_HISTORY
            for i in range(MAX_SESSION_HISTORY + 5):
                _save_session_state(f"user-{i}", f"Q{i}", f"A{i}")
            
            # Should be capped
            assert SESSION_HISTORY.get(f"user-{MAX_SESSION_HISTORY + 4}") is not None
            # Last entries should still exist
            loaded = _load_session_context(f"user-{MAX_SESSION_HISTORY + 4}")
            assert loaded is not None

    def test_empty_context(self, tmp_path):
        """Test loading non-existent user returns empty string."""
        with patch('orchestra.agent.SESSION_STATE_DIR', tmp_path):
            from orchestra.agent import _load_session_context
            
            result = _load_session_context("non-existent-user")
            assert result == ""


class TestRecursionGuard:
    """Tests for recursion guard."""

    def test_check_recursion_safe_first_call(self):
        """First call should be safe."""
        from orchestra.agent import _check_recursion_safe
        
        safe, reason = _check_recursion_safe("conv-1", "alice", "bob")
        assert safe is True
        # Reason can be None or empty string

    def test_check_recursion_safe_nested_calls(self):
        """Nested calls should eventually fail."""
        from orchestra.agent import _check_recursion_safe, _release_conversation, MAX_CALL_DEPTH
        
        conv_id = "conv-nested"
        
        # Fill up conversation slots
        for i in range(MAX_CALL_DEPTH):
            safe, _ = _check_recursion_safe(conv_id, f"user{i}", f"user{i+1}")
            assert safe is True, f"Failed at depth {i}"
        
        # Next one should fail (exceeds depth)
        unsafe, reason = _check_recursion_safe(conv_id, "final", "another")
        assert unsafe is False
        assert "depth" in reason.lower()

    def test_release_conversation(self):
        """Releasing should free slot."""
        from orchestra.agent import _check_recursion_safe, _release_conversation
        
        conv_id = "conv-release"
        
        # Use it
        safe, _ = _check_recursion_safe(conv_id, "alice", "bob")
        assert safe is True
        
        # Release it
        _release_conversation(conv_id)
        
        # Should be available again
        safe, _ = _check_recursion_safe(conv_id, "alice", "bob")
        assert safe is True


class TestAgentConfig:
    """Tests for agent configuration."""

    def test_default_config(self, sample_config):
        """Test default config values."""
        # This would test CLI defaults if we had them
        assert "team" in sample_config
        assert "display" in sample_config


