from unittest.mock import Mock

from core.wiztype.suggestion_overlay import SuggestionOverlay


def test_suggestion_overlay_init():
    overlay = SuggestionOverlay()
    try:
        assert overlay is not None
        assert overlay.visible is False
        assert overlay.current_suggestion is None
    finally:
        overlay.cleanup()


def test_suggestion_overlay_show():
    overlay = SuggestionOverlay()
    try:
        overlay.show_suggestion("hello")
        assert overlay.visible is True
        assert overlay.current_suggestion == "hello"
    finally:
        overlay.cleanup()


def test_suggestion_overlay_hide():
    overlay = SuggestionOverlay()
    try:
        overlay.show_suggestion("hello")
        overlay.hide()
        assert overlay.visible is False
    finally:
        overlay.cleanup()


def test_suggestion_overlay_accept():
    overlay = SuggestionOverlay()
    callback = Mock()
    overlay.on_accept = callback
    try:
        overlay.show_suggestion("hello")
        overlay.accept()
        assert callback.called is True
        assert callback.call_args[0][0] == "hello"
    finally:
        overlay.cleanup()


def test_suggestion_overlay_dismiss():
    overlay = SuggestionOverlay()
    try:
        overlay.show_suggestion("hello")
        overlay.dismiss()
        assert overlay.visible is False
        assert overlay.current_suggestion is None
    finally:
        overlay.cleanup()
