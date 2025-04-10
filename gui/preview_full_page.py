# gui/preview_page.py

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox


class PreviewPage:
    def __init__(self, root, conn, page_name, bvt_callback=None):
        self.root = root
        self.conn = conn
        self.page_name = page_name
        self.bvt_callback = bvt_callback

    def open(self):
        preview_win = tk.Toplevel(self.root)
        preview_win.title(f"Preview: {self.page_name}")

        canvas = tk.Canvas(preview_win, bg="#f0f0f0")
        scrollbar = tk.Scrollbar(preview_win, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, widget_type, widget_name, widget_index, widget_config_id, widget_id
            FROM widgets
            WHERE page_name = ?
            ORDER BY widget_index ASC
        """, (self.page_name,))
        widgets = cur.fetchall()

        for row_num, (db_id, widget_type, widget_name, widget_index, config_id, widget_id) in enumerate(widgets):
            display = widget_name or f"Widget_{db_id}"
            widget_type = widget_type.lower()

            # Wrap widget in a framed box
            box = ttk.Frame(scroll_frame, padding=5, relief="solid")
            box.grid(row=row_num, column=0, padx=10, pady=5, sticky="w")

            # Create widget and insert into the frame
            if widget_type == "button":
                w = ttk.Button(
                    box,
                    text=display,
                    command=(lambda name=widget_name: self.bvt_callback(name)) if self.bvt_callback else None
                )
            elif widget_type == "textbox":
                w = ttk.Entry(box)
                w.insert(0, display)
            elif widget_type == "label":
                w = ttk.Label(box, text=display)
            else:
                w = ttk.Label(box, text=f"[{widget_type}] {display}")
            w.pack()

            # Tooltip metadata string
            meta_text = (
                f"Widget Name: {widget_name or 'Unnamed'}\n"
                f"Type: {widget_type}\n"
                f"Index: {widget_index or 'N/A'}\n"
                f"Widget ID: {widget_id}\n"
                f"Config ID: {config_id}\n"
                f"Page: {self.page_name}"
            )

            self._attach_tooltip(w, meta_text)

    def _attach_tooltip(self, widget, text):
        tooltip = tk.Toplevel(widget)
        tooltip.wm_overrideredirect(True)
        tooltip.withdraw()
        tooltip_label = tk.Label(
            tooltip,
            text=text,
            justify='left',
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("tahoma", "8", "normal")
        )
        tooltip_label.pack(ipadx=1)

        def on_enter(event):
            x = event.x_root + 10
            y = event.y_root + 10
            tooltip.geometry(f"+{x}+{y}")
            tooltip.deiconify()

        def on_leave(event):
            tooltip.withdraw()

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
