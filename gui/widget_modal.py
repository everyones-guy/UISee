def open_widget_modal(self, widget_data):
        modal = tk.Toplevel(self.root)
        modal.title(f"Widget: {widget_data['widget_name']}")

        frame = ttk.Frame(modal)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def label_pair(key, val):
            ttk.Label(frame, text=f"{key}: ", font=('Arial', 10, 'bold')).pack(anchor='w')
            ttk.Label(frame, text=val).pack(anchor='w', padx=(20, 0))

        label_pair("Page", widget_data["page_name"])
        label_pair("Name", widget_data["widget_name"])
        label_pair("Type", widget_data["widget_type"])
        label_pair("Index", widget_data["widget_index"])
        label_pair("WidgetConfigID", widget_data["config_id"])
        label_pair("WidgetID", widget_data["widget_id"])

        # Widget tag/values
        cur = self.conn.cursor()
        cur.execute("SELECT tag, value FROM widget_details WHERE widget_id = ?", (widget_data["db_id"],))
        tags = cur.fetchall()
        if tags:
            ttk.Label(frame, text="\nAttributes:", font=('Arial', 10, 'bold')).pack(anchor='w')
            for tag, value in tags:
                ttk.Label(frame, text=f"{tag}: {value}").pack(anchor='w', padx=(20, 0))

        # Inferred Options
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

        if options:
            ttk.Label(frame, text="\nOptions:", font=('Arial', 10, 'bold')).pack(anchor='w')
            for opt in sorted(set(options)):
                ttk.Label(frame, text=f"- {opt}").pack(anchor='w', padx=(20, 0))

        # JS function mapping
        cur.execute("SELECT function_name, parameters FROM js_functions WHERE page_name = ?", (widget_data["page_name"],))
        js_funcs = cur.fetchall()
        matching = [f"{fn}({params})" for fn, params in js_funcs if widget_data["widget_name"] in fn]

        if matching:
            ttk.Label(frame, text="\nJavaScript Functions:", font=('Arial', 10, 'bold')).pack(anchor='w')
            for fn_line in matching:
                ttk.Label(frame, text=f"- {fn_line}").pack(anchor='w', padx=(20, 0))

        # Emulator Snapshot
        def generate_snapshot():
            snapshot = {
                "widget_name": widget_data["widget_name"],
                "widget_type": widget_data["widget_type"],
                "widget_id": widget_data["widget_id"],
                "config_id": widget_data["config_id"],
                "tags": tags
            }
            print("[TikTest Snapshot]:", snapshot)
            messagebox.showinfo("Snapshot Created", "Snapshot data printed to console (future TikTest use).")

        ttk.Button(frame, text="Generate Emulator Snapshot", command=generate_snapshot).pack(pady=(10, 5))
            
        # Export snapshot as JSON
        def export_snapshot():
            import json
            snapshot = {
                "widget_name": widget_data["widget_name"],
                "widget_type": widget_data["widget_type"],
                "widget_id": widget_data["widget_id"],
                "config_id": widget_data["config_id"],
                "tags": tags
            }
            file_path = filedialog.asksaveasfilename(
                defaultextension=".json", filetypes=[("JSON Files", "*.json")])
            if file_path:
                with open(file_path, "w") as f:
                    json.dump(snapshot, f, indent=4)
                messagebox.showinfo("Exported", f"Snapshot exported to:\n{file_path}")

        ttk.Button(frame, text="Export Snapshot as JSON", command=export_snapshot).pack(pady=2)

