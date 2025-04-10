# gui/toolbar_controls.py
import tkinter as tk
from tkinter import ttk

class ToolbarControls:
    def __init__(self, root, ui_instance):
        self.root = root
        self.ui = ui_instance
        self.toolbar = None

    def build(self):
        self.toolbar = ttk.Frame(self.root)
        self.toolbar.pack(fill=tk.X, padx=5, pady=2)

        self._add_button("Connect to Controller", self.ui.connect_ssh, "Establish SSH session with test device")
        self._add_button("Subscribe to MQTT", self.ui.subscribe_mqtt, "Subscribe to MQTT broker for telemetry")
        self._add_button("Close SSH Connection", self.ui.close_ssh, "Safely terminate SSH session")

        self._add_button("Simulate Input", self.ui.simulate_input_popup, "Send mock input via EC or controller API")
        self._add_button("Command Builder", self.ui.open_command_builder, "Build and test MQTT commands")
        self._add_button("Test Queue", self.ui.open_test_queue_builder, "Build automated step queues")

        if hasattr(self.ui, "toggle_mirror_mode"):
            mirror_btn = self._add_button("Toggle Mirror Mode", self.ui.toggle_mirror_mode, "Match controller UI and auto-sync")
            self.ui.mirror_mode_button = mirror_btn

        return self.toolbar

    def _add_button(self, label, command, tooltip_text=None):
        btn = ttk.Button(self.toolbar, text=label, command=command)
        btn.pack(side=tk.LEFT, padx=(0, 5))
        if tooltip_text:
            self._create_hover_tooltip(btn, tooltip_text)
        return btn

    def _create_hover_tooltip(self, widget, text):
        tooltip = tk.Toplevel(widget)
        tooltip.wm_overrideredirect(True)
        tooltip.withdraw()

        label = tk.Label(
            tooltip, text=text, justify='left', background='#ffffe0', relief='solid', borderwidth=1,
            font=("tahoma", "8", "normal")
        )
        label.pack(ipadx=1)

        def on_enter(event):
            x = event.x_root + 10
            y = event.y_root + 10
            tooltip.geometry(f"+{x}+{y}")
            tooltip.deiconify()

        def on_leave(event):
            tooltip.withdraw()

        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)
