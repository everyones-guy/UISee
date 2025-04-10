# gui/command_builder.py

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import time
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path("config/.env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    print(".env file not found at config/.env")

DEFAULT_TEST_CREDS = {
    "host": "127.0.0.1",
    "user": "pi"
}

DEFAULT_MQTT_CREDS = {
    "host": "localhost",
    "port": "1883",
    "username": "guest",
    "password": "guest"
}

class CommandBuilder:
    def __init__(self, app_context):
        self.app = app_context
        self.root = app_context.root
        self.conn = app_context.conn
        self.mqtt_adapter = app_context.mqtt_adapter
        self.parser_service = app_context.parser_service
        self.test_creds = app_context.test_creds
        self.configured_inputs = app_context.configured_inputs
        self.output_console = app_context.output_console

        self.selected_page = tk.StringVar()
        self.selected_widget = tk.StringVar()
        self.selected_property = tk.StringVar()
        self.value = tk.StringVar()
        self.steps = []

        self.available_pages = self.parser_service.get_all_pages()

    
        self.test_creds = {
            "host": os.getenv("SSH_HOST", DEFAULT_TEST_CREDS["host"]),
            "user": os.getenv("SSH_USER", DEFAULT_TEST_CREDS["user"])
        }

        self.mqtt_creds = {
            "host": os.getenv("MQTT_BROKER", DEFAULT_MQTT_CREDS["host"]),
            "port": os.getenv("MQTT_PORT", DEFAULT_MQTT_CREDS["port"]),
            "username": os.getenv("MQTT_USERNAME", DEFAULT_MQTT_CREDS["username"]),
            "password": os.getenv("MQTT_PASSWORD", DEFAULT_MQTT_CREDS["password"]),
        }


    def open_builder(self):
        win = tk.Toplevel(self.root)
        win.title("Assemble Test Commands")

        # --- Dropdown Row ---
        row = ttk.Frame(win)
        row.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(row, text="Page:").pack(side=tk.LEFT)

        self.page_combo = ttk.Combobox(row, values=self.available_pages, textvariable=self.selected_page, state="readonly")
        self.page_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.page_combo.bind("<<ComboboxSelected>>", self._populate_widgets)

        # Parse button next to the Page dropdown
        ttk.Button(row, text="Parse", width=8, command=self._reparse_and_reload_pages).pack(side=tk.LEFT)


        row2 = ttk.Frame(win)
        row2.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row2, text="Widget:").pack(side=tk.LEFT)
        self.widget_combo = ttk.Combobox(row2, textvariable=self.selected_widget, state="readonly")
        self.widget_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.widget_combo.bind("<<ComboboxSelected>>", self._populate_properties)

        row3 = ttk.Frame(win)
        row3.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row3, text="Property:").pack(side=tk.LEFT)
        self.property_combo = ttk.Combobox(row3, textvariable=self.selected_property, state="readonly")
        self.property_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row4 = ttk.Frame(win)
        row4.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row4, text="Value:").pack(side=tk.LEFT)
        ttk.Entry(row4, textvariable=self.value).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Command Output ---
        self.output = tk.Text(win, height=6, bg="#111", fg="#0f0")
        self.output.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # --- Buttons ---
        btn_row = ttk.Frame(win)
        btn_row.pack(pady=5)
        ttk.Button(btn_row, text="Preview", command=self.preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Send", command=self.send).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="Copy", command=self.copy).pack(side=tk.LEFT, padx=5)

        sep = ttk.Separator(win, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=10)

        # --- Add Step Buttons ---
        action_row = ttk.Frame(win)
        action_row.pack(pady=5)
        ttk.Button(action_row, text="Add MQTT", command=self.add_mqtt_step).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_row, text="Add SSH", command=self.add_ssh_step).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_row, text="Add Wait", command=self.add_wait_step).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_row, text="Run All", command=self.run_sequence).pack(side=tk.LEFT, padx=5)

        # --- Steps Preview (Scrollable) ---
        self.step_container = ttk.Frame(win)
        self.step_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.step_canvas = tk.Canvas(self.step_container)
        self.step_scrollbar = ttk.Scrollbar(self.step_container, orient="vertical", command=self.step_canvas.yview)
        self.step_frame = tk.Frame(self.step_canvas)

        self.step_frame.bind(
            "<Configure>",
            lambda e: self.step_canvas.configure(scrollregion=self.step_canvas.bbox("all"))
        )

        self.step_canvas.create_window((0, 0), window=self.step_frame, anchor="nw")
        self.step_canvas.configure(yscrollcommand=self.step_scrollbar.set)

        self.step_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.step_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Clear Steps button
        ttk.Button(win, text="Clear All Steps", command=self.clear_all_steps).pack(pady=(0, 10))

        self.refresh_steps()

    def clear_all_steps(self):
        self.steps = []
        self.refresh_steps()

    def _populate_widgets(self, event=None):
        cur = self.conn.cursor()
        cur.execute("SELECT widget_name FROM widgets WHERE page_name = ?", (self.selected_page.get(),))
        self.widget_combo['values'] = [row[0] for row in cur.fetchall()]
        if not self.widget_combo['values']:
            self.widget_combo['values'] = ["<No widgets found>"]

        self.selected_widget.set("")
        self.selected_property.set("")
        self.property_combo['values'] = []
        if not self.property_combo['values']:
            self.property_combo['values'] = ["<No properties found>"]


    def _populate_properties(self, event=None):
        cur = self.conn.cursor()
        cur.execute("""
            SELECT tag FROM widget_details WHERE widget_id IN (
                SELECT id FROM widgets WHERE page_name = ? AND widget_name = ?
            )
        """, (self.selected_page.get(), self.selected_widget.get()))
        self.property_combo['values'] = [row[0] for row in cur.fetchall()]
        self.selected_property.set("")

    def preview(self):
        cmd = f"Page.Widgets.{self.selected_widget.get()}.{self.selected_property.get()}={self.value.get()}"
        self.output.delete(1.0, tk.END)
        self.output.insert(tk.END, f"[PREVIEW] {cmd}")

    def send(self):
        path = f"Page.Widgets.{self.selected_widget.get()}.{self.selected_property.get()}"
        val = self.value.get()
        result = self.mqtt_adapter.send_command_and_wait(path, val)
        self.output.insert(tk.END, f"\n{result}\n")

    def copy(self):
        cmd = f"Page.Widgets.{self.selected_widget.get()}.{self.selected_property.get()}={self.value.get()}"
        self.root.clipboard_clear()
        self.root.clipboard_append(cmd)
        messagebox.showinfo("Copied", f"Copied:\n{cmd}")

    def add_mqtt_step(self):
        self.steps.append(("mqtt", f"Page.Widgets.{self.selected_widget.get()}.{self.selected_property.get()}={self.value.get()}"))
        self.refresh_steps()

    def _reparse_and_reload_pages(self):
        confirm = messagebox.askyesno("Re-parse Files", "This will reload widgets/functions from source files.\nContinue?")
        if not confirm:
            return

        try:
            sql_path, js_path = self.parser_service.ask_user_for_folders()
            if not sql_path or not js_path:
                messagebox.showwarning("Cancelled", "Parsing cancelled. No folders selected.")
                return

            self.parser_service.page_name = ""  # Optional reset
            self.parser_service.load_sql_and_js(sql_path, js_path)

            self.available_pages = self.parser_service.get_all_pages()
            self.selected_page.set("")
            self.selected_widget.set("")
            self.selected_property.set("")
            self.value.set("")
            self.widget_combo['values'] = []
            self.property_combo['values'] = []
            # After parsing completes:
            self._refresh_page_dropdowns()


            messagebox.showinfo("Success", "Files re-parsed and data reloaded.")

        except Exception as e:
            messagebox.showerror("Parse Error", f"Failed to parse:\n{str(e)}")

    def _refresh_page_dropdowns(self):
        self.available_pages = self.parser_service.get_all_pages()
        self.page_combo['values'] = self.available_pages
        self.page_combo.set('')
        self.widget_combo.set('')
        self.property_combo.set('')
        self.widget_combo['values'] = []
        self.property_combo['values'] = []


    def add_ssh_step(self):
        def submit():
            cmd = cmd_entry.get()
            if cmd:
                self.steps.append(("ssh", cmd))
                self.refresh_steps()
                modal.destroy()

        modal = tk.Toplevel(self.root)
        modal.title("Add SSH Command")
        ttk.Label(modal, text="SSH Command:").pack(anchor="w", padx=10, pady=5)
        cmd_entry = ttk.Entry(modal)
        cmd_entry.pack(fill=tk.X, padx=10)
        ttk.Button(modal, text="Add", command=submit).pack(pady=10)

    def add_wait_step(self):
        def submit():
            secs = entry.get()
            if secs.isdigit():
                self.steps.append(("wait", f"{secs} seconds"))
                self.refresh_steps()
                modal.destroy()

        modal = tk.Toplevel(self.root)
        modal.title("Add Wait")
        ttk.Label(modal, text="Wait (in seconds):").pack(anchor="w", padx=10, pady=5)
        entry = ttk.Entry(modal)
        entry.pack(fill=tk.X, padx=10)
        ttk.Button(modal, text="Add", command=submit).pack(pady=10)

    def refresh_steps(self):
        for widget in self.step_frame.winfo_children():
            widget.destroy()

        for idx, (step_type, val) in enumerate(self.steps):
            box = tk.Frame(self.step_frame, borderwidth=1, relief="ridge", bg="#f0f0f0")
            box.pack(fill=tk.X, pady=2, padx=2)

            label = tk.Label(
                box,
                text=f"{idx+1}. {step_type.upper()} - {val}",
                anchor="w",
                justify="left",
                bg="#f0f0f0"
            )
            label.pack(fill=tk.X, padx=5, pady=4)

            # Right-click menu
            def make_context_menu(i):
                menu = tk.Menu(box, tearoff=0)
                menu.add_command(label="Delete Step", command=lambda: self._delete_step(i))
                if i > 0:
                    menu.add_command(label="Move Up", command=lambda: self._move_step(i, i - 1))
                if i < len(self.steps) - 1:
                    menu.add_command(label="Move Down", command=lambda: self._move_step(i, i + 1))
                return menu

            def show_context_menu(event, i=idx):
                menu = make_context_menu(i)
                menu.tk_popup(event.x_root, event.y_root)

            label.bind("<Button-3>", lambda event, i=idx: show_context_menu(event, i))

    def _delete_step(self, index):
        if 0 <= index < len(self.steps):
            del self.steps[index]
            self.refresh_steps()

    def _move_step(self, from_idx, to_idx):
        if 0 <= from_idx < len(self.steps) and 0 <= to_idx < len(self.steps):
            self.steps[from_idx], self.steps[to_idx] = self.steps[to_idx], self.steps[from_idx]
            self.refresh_steps()


    def run_sequence(self):
        for step_type, val in self.steps:
            self.output_console.insert(tk.END, f"\n[STEP] {step_type.upper()} - {val}\n")
            self.root.update()

            if step_type == "mqtt":
                path, v = val.split("=")
                result = self.mqtt_adapter.send_command_and_wait(path.strip(), v.strip())
                self.output_console.insert(tk.END, f"{result}\n")

            elif step_type == "ssh":
                cmd = f"ssh {self.test_creds['user']}@{self.test_creds['host']} '{val.strip()}'"
                try:
                    output = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    self.output_console.insert(tk.END, output.stdout + output.stderr)
                except Exception as e:
                    self.output_console.insert(tk.END, f"SSH ERROR: {str(e)}\n")

            elif step_type == "wait":
                secs = int(val.split()[0])
                self.output_console.insert(tk.END, f"Waiting {secs} seconds...\n")
                time.sleep(secs)
