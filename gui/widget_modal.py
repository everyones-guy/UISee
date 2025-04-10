import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json


def open_widget_modal(root, conn, widget_data):
    """
    Displays a modal with detailed widget metadata, attributes, inferred options,
    and JavaScript function mappings. Also supports snapshot export.
    
    Args:
        root: Tk root or parent window
        conn: sqlite3 connection object
        widget_data: Dictionary containing widget metadata
    """
    modal = tk.Toplevel(root)
    modal.title(f"Widget: {widget_data['widget_name']}")
    modal.geometry("500x600")

    frame = ttk.Frame(modal)
    frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def label_pair(key, val):
        ttk.Label(frame, text=f"{key}: ", font=('Arial', 10, 'bold')).pack(anchor='w')
        ttk.Label(frame, text=val).pack(anchor='w', padx=(20, 0))

    # Metadata
    label_pair("Page", widget_data["page_name"])
    label_pair("Name", widget_data["widget_name"])
    label_pair("Type", widget_data["widget_type"])
    label_pair("Index", widget_data["widget_index"])
    label_pair("WidgetConfigID", widget_data["config_id"])
    label_pair("WidgetID", widget_data["widget_id"])

    # Fetch widget tags
    tags = []
    try:
        cur = conn.cursor()
        cur.execute("SELECT tag, value FROM widget_details WHERE widget_id = ?", (widget_data["db_id"],))
        tags = cur.fetchall()
    except Exception as e:
        messagebox.showwarning("DB Error", f"Could not load widget details: {e}")
        return

    if tags:
        ttk.Label(frame, text="\nAttributes:", font=('Arial', 10, 'bold')).pack(anchor='w')
        for tag, value in tags:
            ttk.Label(frame, text=f"{tag}: {value}").pack(anchor='w', padx=(20, 0))

    # Infer actions
    inferred_options = set()
    for tag, value in tags:
        t = tag.lower()
        v = str(value).lower()
        if "text" in t or "value" in t:
            inferred_options.add("Enter Text")
        if "isclicked" in t or "actionwhen" in t:
            inferred_options.add("Clickable")
        if "save" in v:
            inferred_options.add("Save Action")
        if "cancel" in v:
            inferred_options.add("Cancel Action")
        if "set" in t:
            inferred_options.add("Set Flag")

    if inferred_options:
        ttk.Label(frame, text="\nOptions:", font=('Arial', 10, 'bold')).pack(anchor='w')
        for opt in sorted(inferred_options):
            ttk.Label(frame, text=f"- {opt}").pack(anchor='w', padx=(20, 0))

    # Show mapped JS functions
    try:
        cur.execute("SELECT function_name, parameters FROM js_functions WHERE page_name = ?", (widget_data["page_name"],))
        js_funcs = cur.fetchall()
        matching = [f"{fn}({params})" for fn, params in js_funcs if widget_data["widget_name"] in fn]

        if matching:
            ttk.Label(frame, text="\nJavaScript Functions:", font=('Arial', 10, 'bold')).pack(anchor='w')
            for fn_line in matching:
                ttk.Label(frame, text=f"- {fn_line}").pack(anchor='w', padx=(20, 0))
    except Exception as e:
        messagebox.showwarning("DB Error", f"Could not load JS functions: {e}")

    # Snapshot Generation
    def generate_snapshot():
        snapshot = {
            "widget_name": widget_data["widget_name"],
            "widget_type": widget_data["widget_type"],
            "widget_id": widget_data["widget_id"],
            "config_id": widget_data["config_id"],
            "tags": tags
        }
        print("[TikTest Snapshot]:", snapshot)
        messagebox.showinfo("Snapshot Created", "Snapshot printed to console.")

    ttk.Button(frame, text="Generate Emulator Snapshot", command=generate_snapshot).pack(pady=(10, 5))

    # JSON Export
    def export_snapshot():
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
            messagebox.showinfo("Exported", f"Snapshot saved to:\n{file_path}")

    ttk.Button(frame, text="Export Snapshot as JSON", command=export_snapshot).pack(pady=2)
