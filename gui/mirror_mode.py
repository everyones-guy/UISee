# mirror_mode.py
# This module provides an interface for toggling 'Mirror Mode', where the UI aligns with the controller's current page and visible widgets.

import tkinter as tk
from tkinter import ttk, messagebox

class MirrorModeController:
    def __init__(self, app, root):
        self.app = app
        self.root = root
        self.active = False
        self.current_page = None

        # Placeholder for hook-ins (can be replaced when MQTT feedback is integrated)
        self.on_enter_callback = None
        self.on_exit_callback = None

    def toggle_mirror_mode(self):
        self.active = not self.active
        if self.active:
            self.enter_mirror_mode()
        else:
            self.exit_mirror_mode()

    def enter_mirror_mode(self):
        self.active = True
        messagebox.showinfo("Mirror Mode", "Mirror Mode activated. UI will reflect controller's screen.")
        if self.on_enter_callback:
            self.on_enter_callback()
        self.fetch_and_display_current_page()

    def exit_mirror_mode(self):
        self.active = False
        messagebox.showinfo("Mirror Mode", "Mirror Mode deactivated.")
        if self.on_exit_callback:
            self.on_exit_callback()

    def fetch_and_display_current_page(self):
        """
        Simulate fetching the current screen from the controller.
        This should eventually be replaced with MQTT or SSH commands to detect active page.
        """
        try:
            result = self.app.run_ssh_command("ec detect_current_screen")
            if result:
                self.current_page = result.strip()
                self.app.page_name = self.current_page
                self.app.apply_filters()
                self.app.output_console.insert(tk.END, f"\n[Mirror Mode] Synced to: {self.current_page}\n")
        except Exception as e:
            self.app.output_console.insert(tk.END, f"\n[Mirror Mode Error] {e}\n")

    def sync_on_page_change(self, page_name):
        """
        Optional: Trigger UI update based on MQTT or button click reflecting actual controller page.
        """
        if self.active:
            self.current_page = page_name
            self.app.page_name = page_name
            self.app.apply_filters()
            self.app.output_console.insert(tk.END, f"\n[Mirror Mode] UI updated to: {page_name}\n")

    def bind_hooks(self, on_enter=None, on_exit=None):
        self.on_enter_callback = on_enter
        self.on_exit_callback = on_exit


# Usage example (in core.py or toolbar_controls):
#
#   from mirror_mode import MirrorModeController
#   self.mirror_mode = MirrorModeController(self, self.root)
#   ttk.Button(toolbar, text="Toggle Mirror Mode", command=self.mirror_mode.toggle_mirror_mode).pack(side=tk.LEFT)
#

