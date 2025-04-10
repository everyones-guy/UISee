# toolbar controls
import tkinter as tk
from tkinter import ttk

def setup_toolbar(root, ui_instance):
    """
    Build the main toolbar and attach button actions.
    Context-sensitive logic (e.g. mirror mode) should be injected by the ui_instance.
    """
    toolbar = ttk.Frame(root)
    toolbar.pack(fill=tk.X, padx=5, pady=2)

    def add_button(label, command, tooltip_text=None):
        btn = ttk.Button(toolbar, text=label, command=command)
        btn.pack(side=tk.LEFT, padx=(0, 5))
        if tooltip_text:
            create_hover_tooltip(btn, tooltip_text)
        return btn

    # Basic actions
    add_button("Connect to Controller", ui_instance.connect_ssh, "Establish SSH session with test device")
    add_button("Subscribe to MQTT", ui_instance.subscribe_mqtt, "Subscribe to MQTT broker for telemetry")
    add_button("Close SSH Connection", ui_instance.close_ssh, "Safely terminate SSH session")

    # Interactive tools
    add_button("Simulate Input", ui_instance.simulate_input_popup, "Send mock input via EC or controller API")
    add_button("Command Builder", ui_instance.open_command_builder, "Build and test MQTT commands")
    add_button("Test Queue", ui_instance.open_test_queue_builder, "Build automated step queues")

    # Mirror mode toggle (external method, defined in mirror_mode.py)
    if hasattr(ui_instance, "toggle_mirror_mode"):
        mirror_btn = add_button("Toggle Mirror Mode", ui_instance.toggle_mirror_mode, "Match controller UI and auto-sync")
        ui_instance.mirror_mode_button = mirror_btn

    return toolbar

def create_hover_tooltip(widget, text):
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


