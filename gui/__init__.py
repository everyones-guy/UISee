
# gui/__init__.py

"""
UI-See GUI Components Package

This package contains all the core GUI modules used by the UI Structure Mapper.
Each module represents a distinct functional component of the UI tool such as:

- Core GUI wiring and layout
- Command Builder and Test Queue Manager
- Toolbar actions and Mirror mode logic
- Widget Modal popups and metadata handling
"""

from .core import UIMapperGUI
from .command_builder import CommandBuilder
from .test_queue import TestQueueBuilder
from .toolbar_controls import ToolbarControls
from .widget_modal import open_widget_modal
from .mirror_mode import MirrorModeController
# Add more imports here as more modules are created (e.g., mirror_mode, preview_page, etc.)
