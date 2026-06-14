"""Tests for platforms/*/virtual_desktop.py — Virtual Desktop abstraction."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from platforms.abstract.virtual_desktop import BaseVirtualDesktop
from platforms.factory import get_virtual_desktop


class TestBaseVirtualDesktop:
    """Test suite for the virtual desktop ABC."""

    def test_base_methods_raise_not_implemented(self):
        """Calling abstract methods on a subclass that delegates to super should raise NotImplementedError."""
        class MinimalDesktop(BaseVirtualDesktop):
            def create_desktop(self, name: str) -> str:
                return super().create_desktop(name)
            def switch_to_desktop(self, desktop_id: str) -> None:
                return super().switch_to_desktop(desktop_id)
            def move_window_to_desktop(self, window_handle: int, desktop_id: str) -> None:
                return super().move_window_to_desktop(window_handle, desktop_id)
            def close_desktop(self, desktop_id: str) -> None:
                return super().close_desktop(desktop_id)
            def list_desktops(self):
                return super().list_desktops()
            def current_desktop(self) -> str:
                return super().current_desktop()

        desktop = MinimalDesktop()
        with pytest.raises(NotImplementedError):
            desktop.create_desktop("test")
        with pytest.raises(NotImplementedError):
            desktop.switch_to_desktop("1")
        with pytest.raises(NotImplementedError):
            desktop.close_desktop("1")
        with pytest.raises(NotImplementedError):
            desktop.list_desktops()
        with pytest.raises(NotImplementedError):
            desktop.current_desktop()


class TestFactory:
    """Test suite for virtual desktop factory."""

    def test_factory_returns_instance(self):
        """Factory should return a platform-specific instance."""
        vd = get_virtual_desktop()
        assert isinstance(vd, BaseVirtualDesktop)

    def test_factory_is_cached(self):
        """Factory should return the same instance on repeated calls."""
        vd1 = get_virtual_desktop()
        vd2 = get_virtual_desktop()
        assert vd1 is vd2
