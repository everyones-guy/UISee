# gui/command_builder.py

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import time
import json

class CommandBuilder:
    def __init__(self, parent, mqtt_adapter, available_pages, test_creds, db_conn, configured_inputs, output_console):
        self.root = parent
        self.mqtt_adapter = mqtt_adapter
        self.available_pages = available_pages
        self.test_creds = test_creds
        self.conn = db_conn
        self.configured_inputs = configured_inputs
        self.output_console = output_console

        self.selected_page = tk.StringVar()
        self.selected_widget = tk.StringVar()
        self.selected_property = tk.StringVar()
        self.value = tk.StringVar()
        self.selected_step_index = tk.IntVar(value=-1)

        self.steps = []
        self.preview_widgets = []
        self.toggle_vars = []
        self.outputs = []

    def build(self):
        win = tk.Toplevel(self.root)
        win.title("Assemble MQTT Command")

        container = tk.Frame(win)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._refresh_steps(scrollable_frame)

        ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)

    def _refresh_steps(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()
        self.preview_widgets.clear()
        self.toggle_vars.clear()

        for idx, (typ, val) in enumerate(self.steps):
            box = tk.Frame(frame, borderwidth=1, relief="solid")
            box.pack(fill=tk.X, padx=10, pady=5)

            box.bind("<Button-1>", lambda e, i=idx: self.selected_step_index.set(i))

            header = tk.Frame(box)
            header.pack(fill=tk.X)

            label = tk.Label(header, text=f"{idx+1}. {typ.upper()}: {val}", font=("Arial", 10, "bold"))
            label.pack(side=tk.LEFT, padx=5, pady=5)

            toggle_var = tk.BooleanVar(value=False)
            self.toggle_vars.append(toggle_var)

            def make_toggle(index):
                def toggle():
                    if self.toggle_vars[index].get():
                        self.preview_widgets[index].pack(fill=tk.X, padx=10, pady=(0, 10))
                    else:
                        self.preview_widgets[index].pack_forget()
                return toggle

            btn = ttk.Checkbutton(header, text="Show Output", variable=toggle_var, command=make_toggle(idx))
            btn.pack(side=tk.RIGHT, padx=5)

            preview = tk.Text(box, height=5, bg="#111", fg="#0f0", insertbackground="white")
            preview.insert(tk.END, f"[PREVIEW] {typ.upper()} -- {val}")
            preview.configure(state="disabled")
            self.preview_widgets.append(preview)

    # More methods will be added here later as we continue modularizing...

    def open_command_builder(self):
            win = tk.Toplevel(self.root)
            win.title("Assemble MQTT Command")

            selected_page = tk.StringVar()
            selected_widget = tk.StringVar()
            selected_property = tk.StringVar()
            value = tk.StringVar()

            steps = []
            preview_widgets = []
            toggle_vars = []
            outputs = []
            selected_step_index = tk.IntVar(value=-1)

            container = tk.Frame(win)
            container.pack(fill=tk.BOTH, expand=True)

            canvas = tk.Canvas(container)
            scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            def refresh_steps():
                for widget in scrollable_frame.winfo_children():
                    widget.destroy()
                preview_widgets.clear()
                toggle_vars.clear()

                for idx, (typ, val) in enumerate(steps):
                    frame = tk.Frame(scrollable_frame, borderwidth=1, relief="solid")
                    frame.pack(fill=tk.X, padx=10, pady=5)
                    frame.bind("<Button-1>", lambda e, i=idx: selected_step_index.set(i))

                    header = tk.Frame(frame)
                    header.pack(fill=tk.X)

                    label = tk.Label(header, text=f"{idx+1}. {typ.upper()}: {val}", font=("Arial", 10, "bold"))
                    label.pack(side=tk.LEFT, padx=5, pady=5)

                    toggle_var = tk.BooleanVar(value=False)
                    toggle_vars.append(toggle_var)

                    def make_toggle(index):
                        def toggle():
                            if toggle_vars[index].get():
                                preview_widgets[index].pack(fill=tk.X, padx=10, pady=(0, 10))
                            else:
                                preview_widgets[index].pack_forget()
                        return toggle

                    btn = ttk.Checkbutton(header, text="Show Output", variable=toggle_var, command=make_toggle(idx))
                    btn.pack(side=tk.RIGHT, padx=5)

                    preview = tk.Text(frame, height=5, bg="#111", fg="#0f0", insertbackground="white")
                    preview.insert(tk.END, f"[PREVIEW] {typ.upper()} -- {val}")
                    preview.configure(state="disabled")
                    preview_widgets.append(preview)

            def add_dummy_steps():
                steps.append(("mqtt", "Page.Widgets.Button1.IsSet=1"))
                steps.append(("wait", "10 seconds"))
                steps.append(("ssh", "ec simin a_tra1 55.5"))
                refresh_steps()

            add_dummy_steps()

            def refresh_list():
                for child in scrollable_frame.winfo_children():
                    child.destroy()

                preview_widgets.clear()
                toggle_vars.clear()

                def make_select(index):
                    def select(event):
                        selected_step_index.set(index)
                    return select

                def make_context_menu(index):
                    def show_context(event):
                        selected_step_index.set(index)
                        menu = tk.Menu(win, tearoff=0)
                        menu.add_command(label="Edit", command=edit_selected)
                        menu.add_command(label="Remove", command=remove_selected)
                        menu.add_command(label="Move Up", command=move_up)
                        menu.add_command(label="Move Down", command=move_down)
                        menu.post(event.x_root, event.y_root)
                    return show_context

                for idx, step in enumerate(steps):
                    frame = tk.Frame(step_frame, borderwidth=1, relief="solid", padx=5, pady=3)
                    frame.pack(fill=tk.X, padx=5, pady=2)

                    frame.bind("<Button-1>", make_select(idx))
                    frame.bind("<Button-3>", make_context_menu(idx))  # right-click support

                    label = step.get("command", step.get("value", ""))
                    header_var = tk.StringVar(value=f"{idx + 1}. {step['type'].upper()}: {label}")

                    header = tk.Label(frame, textvariable=header_var, font=("Arial", 10, "bold"))
                    header.pack(anchor="w")

                    command_var = tk.StringVar(value=label)
                    cmd_entry = tk.Entry(frame, textvariable=command_var)
                    cmd_entry.pack(fill=tk.X, padx=5, pady=(2, 5))

                    def update_step(e=None, i=idx):
                        val = command_var.get().strip()
                        if "=" in val:
                            steps[i]["command"] = val
                        elif steps[i]["type"] == "wait" and val.isdigit():
                            steps[i]["value"] = int(val)
                        if i < len(outputs):
                            outputs[i] = f"[UPDATED] {val}"

                    cmd_entry.bind("<FocusOut>", update_step)

                    # Collapse/expand preview
                    toggle_text = tk.StringVar(value="Show Preview")

                    def toggle_preview(preview_widget, var):
                        if preview_widget.winfo_viewable():
                            preview_widget.pack_forget()
                            var.set("Show Preview")
                        else:
                            preview_widget.pack(fill=tk.X, padx=5, pady=(0, 5))
                            var.set("Hide Preview")

                    toggle_button = ttk.Button(
                        frame,
                        textvariable=toggle_text,
                        command=lambda pw=None, v=toggle_text, p=None: toggle_preview(preview, v)
                    )
                    toggle_button.pack(anchor="e", padx=5, pady=(0, 5))

                    preview = tk.Text(frame, height=5, bg="#111", fg="#0f0", insertbackground="white")
                    preview.insert(tk.END, f"[PREVIEW] {step['type'].upper()} -- {label}")
                    preview.configure(state="disabled")

                    preview_widgets.append(preview)
                    toggle_vars.append(toggle_text)

            ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)

            search_var = tk.StringVar()

            search_frame = ttk.Frame(win)
            search_frame.pack(fill=tk.X, padx=10, pady=(5, 0))

            ttk.Label(search_frame, text="Search Widgets:").pack(side=tk.LEFT)
            search_entry = ttk.Entry(search_frame, textvariable=search_var)
            search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            ttk.Button(search_frame, text="Search", command=lambda: search_widgets(search_var.get())).pack(side=tk.LEFT)

            # Define the search function within the same open_command_builder scope
            def search_widgets(query):
                query = query.strip().lower()
                if not query:
                    return
                cur = self.conn.cursor()
                cur.execute("SELECT page_name, widget_name FROM widgets")
                matches = [(p, w) for p, w in cur.fetchall() if query in w.lower() or query in p.lower()]

                if not matches:
                    messagebox.showinfo("No Results", "No matching widgets found.")
                    return

                result_win = tk.Toplevel(win)
                result_win.title("Matching Widgets")
                result_list = tk.Listbox(result_win, height=10)
                result_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                for page, widget in matches:
                    result_list.insert(tk.END, f"{page} > {widget}")

                def on_select(event):
                    sel = result_list.curselection()
                    if sel:
                        selection = result_list.get(sel[0])
                        page, widget = selection.split(" > ")
                        selected_page.set(page.strip())
                        selected_widget.set(widget.strip())
                        selected_property.set("")  # reset property dropdown
                        on_page_select(None)

                result_list.bind("<<ListboxSelect>>", on_select)

            def add_mqtt():
                def submit():
                    path = path_entry.get()
                    val = value_entry.get()
                    if path and val:
                        steps.append(("mqtt", f"{path}={val}"))
                        refresh_steps()
                        modal.destroy()

                modal = tk.Toplevel(win)
                modal.title("MQTT Command")
                ttk.Label(modal, text="Widget Path:").pack(anchor="w")
                path_entry = ttk.Entry(modal)
                path_entry.pack(fill=tk.X)
                ttk.Label(modal, text="Value:").pack(anchor="w")
                value_entry = ttk.Entry(modal)
                value_entry.pack(fill=tk.X)
                ttk.Button(modal, text="Add", command=submit).pack(pady=5)

            def add_ssh():
                def submit():
                    cmd = cmd_entry.get()
                    if cmd:
                        steps.append(("ssh", cmd))
                        refresh_steps()
                        modal.destroy()

                modal = tk.Toplevel(win)
                modal.title("System Command")
                ttk.Label(modal, text="Command:").pack(anchor="w")
                cmd_entry = ttk.Entry(modal)
                cmd_entry.pack(fill=tk.X)
                ttk.Button(modal, text="Add", command=submit).pack(pady=5)

            def add_wait():
                def submit():
                    sec = wait_entry.get()
                    if sec.isdigit():
                        steps.append(("wait", f"{sec} seconds"))
                        refresh_steps()
                        modal.destroy()

                modal = tk.Toplevel(win)
                modal.title("Wait")
                ttk.Label(modal, text="Seconds to wait:").pack(anchor="w")
                wait_entry = ttk.Entry(modal)
                wait_entry.pack(fill=tk.X)
                ttk.Button(modal, text="Add", command=submit).pack(pady=5)

            def run_sequence():
                for typ, val in steps:
                    self.output_console.insert(tk.END, f"\n[STEP] {typ.upper()} - {val}\n")
                    if typ == "mqtt":
                        path, v = val.split("=")
                        result = self.mqtt_adapter.send_command_and_wait(path.strip(), v.strip())
                        self.output_console.insert(tk.END, f"Result: {result}\n")
                    elif typ == "ssh":
                        cmd = val.strip()
                        full_cmd = f"ssh {self.test_creds['user']}@{self.test_creds['host']} '{cmd}'"
                        try:
                            out = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
                            self.output_console.insert(tk.END, out.stdout + out.stderr)
                        except Exception as e:
                            self.output_console.insert(tk.END, f"SSH ERROR: {str(e)}\n")
                    elif typ == "wait":
                        secs = int(val.split()[0])
                        self.output_console.insert(tk.END, f"Waiting {secs} seconds...\n")
                        self.root.update()
                        time.sleep(secs)

            def show_page_details():
                details_win = tk.Toplevel(win)
                details_win.title("Page JS + MQTT Info")
                text = tk.Text(details_win)
                text.pack(fill=tk.BOTH, expand=True)

                cur = self.conn.cursor()
                cur.execute("SELECT function_name, parameters FROM js_functions WHERE page_name = ?", (selected_page.get(),))
                for fn, params in cur.fetchall():
                    text.insert(tk.END, f"{fn}({params})\n")

                cur.execute("SELECT DISTINCT topic FROM mqtt_topics WHERE page_name = ?", (selected_page.get(),))
                for row in cur.fetchall():
                    text.insert(tk.END, f"[MQTT] {row[0]}\n")

            def manage_mapping():
                fn_win = tk.Toplevel(win)
                fn_win.title("Map or Edit Function Mapping")
                fn_label = ttk.Label(fn_win, text="Select Function to Map:")
                fn_label.pack(anchor="w")
                fn_combo = ttk.Combobox(fn_win)
                fn_combo.pack(fill=tk.X)

                cur = self.conn.cursor()
                cur.execute("SELECT function_name FROM js_functions WHERE page_name = ?", (selected_page.get(),))
                options = [row[0] for row in cur.fetchall()]
                fn_combo["values"] = options

                # Preload existing mapping if any
                cur.execute("""
                    SELECT function_name FROM widget_function_map
                    WHERE page_name=? AND widget_name=? AND property=?
                """, (selected_page.get(), selected_widget.get(), selected_property.get()))
                row = cur.fetchone()
                if row:
                    fn_combo.set(row[0])

                def save_mapping():
                    function = fn_combo.get().strip()
                    if not function:
                        messagebox.showwarning("Missing", "Select a valid function")
                        return
                    cur.execute("DELETE FROM widget_function_map WHERE page_name=? AND widget_name=? AND property=?",
                                (selected_page.get(), selected_widget.get(), selected_property.get()))
                    cur.execute("INSERT INTO widget_function_map (page_name, widget_name, property, function_name) VALUES (?, ?, ?, ?)",
                                (selected_page.get(), selected_widget.get(), selected_property.get(), function))
                    self.conn.commit()
                    messagebox.showinfo("Mapped", f"Mapped to function: {function}")
                    fn_win.destroy()

                def delete_mapping():
                    cur.execute("DELETE FROM widget_function_map WHERE page_name=? AND widget_name=? AND property=?",
                                (selected_page.get(), selected_widget.get(), selected_property.get()))
                    self.conn.commit()
                    messagebox.showinfo("Removed", "Mapping removed.")
                    fn_win.destroy()

                button_frame = ttk.Frame(fn_win)
                button_frame.pack(pady=5)
                ttk.Button(button_frame, text="Save Mapping", command=save_mapping).pack(side=tk.LEFT, padx=5)
                ttk.Button(button_frame, text="Delete Mapping", command=delete_mapping).pack(side=tk.LEFT, padx=5)

            button_frame = ttk.Frame(win)
            button_frame.pack(pady=5)
            ttk.Button(button_frame, text="Add MQTT", command=add_mqtt).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Add System Command", command=add_ssh).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Add Wait", command=add_wait).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Run Queue", command=run_sequence).pack(side=tk.LEFT, padx=5)

            ttk.Label(win, text="Page:").pack(anchor="w")
            page_frame = ttk.Frame(win)
            page_frame.pack(fill=tk.X)
            page_dropdown = ttk.Combobox(page_frame, values=self.available_pages, textvariable=selected_page)
            page_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ttk.Button(page_frame, text="Details", command=show_page_details).pack(side=tk.LEFT, padx=5)

            ttk.Label(win, text="Widget:").pack(anchor="w")
            widget_dropdown = ttk.Combobox(win, textvariable=selected_widget)
            widget_dropdown.pack(fill=tk.X)

            ttk.Label(win, text="Property:").pack(anchor="w")
            property_dropdown = ttk.Combobox(win, textvariable=selected_property)
            property_dropdown.pack(fill=tk.X)

            ttk.Label(win, text="Value:").pack(anchor="w")
            ttk.Entry(win, textvariable=value).pack(fill=tk.X)

            def send():
                path = f"Page.Widgets.{selected_widget.get()}.{selected_property.get()}"
                command = f"{path}={value.get()}"
                result = self.mqtt_adapter.send_command_and_wait(path, value.get())

                cur = self.conn.cursor()
                cur.execute("""
                    SELECT function_name FROM widget_function_map
                    WHERE page_name=? AND widget_name=? AND property=?
                """, (selected_page.get(), selected_widget.get(), selected_property.get()))
                mapped_fn = cur.fetchone()

                self.output_console.insert(tk.END, f"\n[SENT] {command}\n{result}\n")
                if mapped_fn:
                    self.output_console.insert(tk.END, f"[Expected JS Function] {mapped_fn[0]}\n")

            def copy():
                cmd = f"Page.Widgets.{selected_widget.get()}.{selected_property.get()}={value.get()}"
                self.root.clipboard_clear()
                self.root.clipboard_append(cmd)
                messagebox.showinfo("Copied", "Command copied to clipboard.")

            def on_page_select(event):
                cur = self.conn.cursor()
                cur.execute("SELECT widget_name FROM widgets WHERE page_name = ?", (selected_page.get(),))
                widget_dropdown["values"] = [row[0] for row in cur.fetchall()]
                selected_widget.set("")
                selected_property.set("")

            def on_widget_select(event):
                cur = self.conn.cursor()
                cur.execute("SELECT tag FROM widget_details WHERE widget_id IN (SELECT id FROM widgets WHERE page_name = ? AND widget_name = ?)",
                            (selected_page.get(), selected_widget.get()))
                property_dropdown["values"] = [row[0] for row in cur.fetchall()]
                selected_property.set("")

            ttk.Button(win, text="Send", command=send).pack(pady=5)
            ttk.Button(win, text="Copy to Clipboard", command=copy).pack()
            ttk.Button(win, text="Manage Function Mapping", command=manage_mapping).pack(pady=5)

            page_dropdown.bind("<<ComboboxSelected>>", on_page_select)
            widget_dropdown.bind("<<ComboboxSelected>>", on_widget_select)