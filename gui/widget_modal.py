# gui/widget_modal.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json

class WidgetModal:
    def __init__(self, app, conn):
        self.app = app
        self.conn = conn

    def open(self, widget_data):
        modal = tk.Toplevel(self.app.root)
        modal.title(f"Widget: {widget_data['widget_name']}")

        frame = ttk.Frame(modal)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def label_pair(key, val):
            ttk.Label(frame, text=f"{key}: ", font=('Arial', 10, 'bold')).pack(anchor='w')
            ttk.Label(frame, text=val).pack(anchor='w', padx=(20, 0))

        # Basic metadata
        label_pair("Page", widget_data["page_name"])
        label_pair("Name", widget_data["widget_name"])
        label_pair("Type", widget_data["widget_type"])
        label_pair("Index", widget_data["widget_index"])
        label_pair("WidgetConfigID", widget_data["config_id"])
        label_pair("WidgetID", widget_data["widget_id"])

        # Widget tag/values from DB
        cur = self.conn.cursor()
        cur.execute("SELECT tag, value FROM widget_details WHERE widget_id = ?", (widget_data["db_id"],))
        tags = cur.fetchall()
        if tags:
            ttk.Label(frame, text="\nAttributes:", font=('Arial', 10, 'bold')).pack(anchor='w')
            for tag, value in tags:
                ttk.Label(frame, text=f"{tag}: {value}").pack(anchor='w', padx=(20, 0))

        # Inferred Options
        options = self._infer_options(tags)
        if options:
            ttk.Label(frame, text="\nOptions:", font=('Arial', 10, 'bold')).pack(anchor='w')
            for opt in sorted(set(options)):
                ttk.Label(frame, text=f"- {opt}").pack(anchor='w', padx=(20, 0))

        # Mapped JS functions
        cur.execute("SELECT function_name, parameters FROM js_functions WHERE page_name = ?", (widget_data["page_name"],))
        js_funcs = cur.fetchall()
        matching = [f"{fn}({params})" for fn, params in js_funcs if widget_data["widget_name"] in fn]

        if matching:
            ttk.Label(frame, text="\nJavaScript Functions:", font=('Arial', 10, 'bold')).pack(anchor='w')
            for fn_line in matching:
                ttk.Label(frame, text=f"- {fn_line}").pack(anchor='w', padx=(20, 0))

        # Emulator Snapshot
        ttk.Button(frame, text="Generate Emulator Snapshot", command=lambda: self._generate_snapshot(widget_data, tags)).pack(pady=(10, 5))
        ttk.Button(frame, text="Export Snapshot as JSON", command=lambda: self._export_snapshot(widget_data, tags)).pack(pady=2)

    def _infer_options(self, tags):
        options = []
        for tag, value in tags:
            tag_lower = tag.lower()
            value_lower = str(value).lower()
            if "text" in tag_lower or "value" in tag_lower:
                options.append("Enter Text")
            if "isclicked" in tag_lower or "actionwhen" in tag_lower:
                options.append("Clickable")
            if "save" in value_lower:
                options.append("Save Action")
            if "cancel" in value_lower:
                options.append("Cancel Action")
            if "set" in tag_lower:
                options.append("Set Flag")
        return options

    def _generate_snapshot(self, widget_data, tags):
        snapshot = {
            "widget_name": widget_data["widget_name"],
            "widget_type": widget_data["widget_type"],
            "widget_id": widget_data["widget_id"],
            "config_id": widget_data["config_id"],
            "tags": tags
        }
        print("[TikTest Snapshot]:", snapshot)
        messagebox.showinfo("Snapshot Created", "Snapshot data printed to console (future TikTest use).")

    def _export_snapshot(self, widget_data, tags):
        snapshot = {
            "widget_name": widget_data["widget_name"],
            "widget_type": widget_data["widget_type"],
            "widget_id": widget_data["widget_id"],
            "config_id": widget_data["config_id"],
            "tags": tags
        }
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if file_path:
            with open(file_path, "w") as f:
                json.dump(snapshot, f, indent=4)
            messagebox.showinfo("Exported", f"Snapshot exported to:\n{file_path}")
