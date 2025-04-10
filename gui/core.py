from services.mqtt_service import MQTTService
from ui_mapper_app import init_db, parse_sql_and_js, ask_user_for_folders
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import subprocess
import time
from datetime import datetime
from utils.ui_mapper_adapter import UIMQTTAdapter
from dotenv import load_dotenv
import re

load_dotenv()
DB_FILE = "ui_map.db"
MQTT_TOPIC_REGEX = re.compile(r"[\"']([a-zA-Z0-9_/\\-]+)[\"']")

class UIMapperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("UI Structure Mapper")
        self.conn = sqlite3.connect(DB_FILE)
        self.test_creds = {
            "host": os.getenv("SSH_HOST", ""),
            "user": os.getenv("SSH_USER", "")
        }
        self.mqtt_creds = {
            "username": os.getenv("MQTT_USERNAME"),
            "password": os.getenv("MQTT_PASSWORD"),
            "host": os.getenv("MQTT_BROKER"),
            "port": os.getenv("MQTT_PORT", "1883")
        }

        self.mqtt_adapter = UIMQTTAdapter(self.test_creds)
        self.ssh_process = None
        self.configured_inputs = []
        self.command_queue = []
        self.mqtt_output_buffer = []
        self.mqtt_topics = set()

        self.init_function_map_table()
        self.init_mqtt_topic_table()
        self.setup_ui()
        self.fetch_configured_inputs()
        self.load_pages()

    def init_function_map_table(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS widget_function_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_name TEXT,
                widget_name TEXT,
                property TEXT,
                function_name TEXT
            )
        """)
        self.conn.commit()

    def init_mqtt_topic_table(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mqtt_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_name TEXT,
                topic TEXT
            )
        """)
        self.conn.commit()

    def setup_ui(self):
        self.output_console = tk.Text(self.root, height=6, bg="black", fg="lime", insertbackground="white")
        self.output_console.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.output_console.insert(tk.END, "Console ready.\n")

        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=5, pady=2)

        # Top-level interaction buttons
        buttons = [
            ("Connect to Controller", self.connect_ssh),
            ("Assemble Command", self.open_command_builder),
            ("Test Queue Builder", self.open_test_queue_builder),
            ("Simulate Input", self.simulate_input_popup),
            ("Subscribe to MQTT", self.subscribe_mqtt),
            ("Close SSH Connection", self.close_ssh),
        ]

        for label, command in buttons:
            ttk.Button(toolbar, text=label, command=command).pack(side=tk.LEFT, padx=3)

    def load_pages(self):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM pages ORDER BY name")
        self.available_pages = [row[0] for row in cur.fetchall()]

    def export_bvt_json(self):
        if not hasattr(self, 'selected_widgets_for_bvt') or not self.selected_widgets_for_bvt:
            messagebox.showinfo("No Widgets", "No widgets have been selected.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if file_path:
            with open(file_path, "w") as f:
                json.dump(self.selected_widgets_for_bvt, f, indent=4)
            messagebox.showinfo("Exported", f"BVT Test exported to:\n{file_path}")

    def show_bvt_output(self, lines):
        win = tk.Toplevel(self.root)
        win.title("Generated BVT Sequence")

        text = tk.Text(win, height=10, width=80)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, "\n".join(lines))

        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(lines))
            messagebox.showinfo("Copied", "BVT sequence copied to clipboard.")

        ttk.Button(win, text="Copy to Clipboard", command=copy).pack(pady=5)

    def generate_bvt_sequence(self, widget_name):
        lines = [f"NavigateTo('{self.page_name}')"]

        if "system" in self.page_name.lower():
            lines.append("NavigateSystemMenu()")
        elif "service" in self.page_name.lower():
            lines.append("NavigateServiceMenu()")

        widget_path = f"Page.Widgets.{widget_name}"
        if "Button" in widget_name:
            lines.append(f'formatAsExecCommand("{widget_path}.IsSet=1")')
        elif "Selection" in widget_name:
            lines.append(f'formatAsExecCommand("{widget_path}.SelectedIndex=0")')
        elif "Clicked" in widget_name:
            lines.append(f'formatAsExecCommand("{widget_path}()")')
        else:
            lines.append(f'formatAsExecCommand("{widget_path}")')

        self.show_bvt_output(lines)

    def fetch_configured_inputs(self):
        try:
            result = subprocess.run("ssh {}@{} ec get_input_config".format(
                self.test_creds['user'], self.test_creds['host']),
                shell=True, capture_output=True, text=True)
            if result.stdout:
                data = json.loads(result.stdout.strip())
                self.configured_inputs = [d['name'] for d in data if 'name' in d]
        except Exception as e:
            self.output_console.insert(tk.END, f"\n[Input Config Error] {e}\n")

if __name__ == '__main__':
    sql_path, js_path = ask_user_for_folders()
    init_db()
    parse_sql_and_js(sql_path, js_path)

    root = tk.Tk()
    app = UIMapperGUI(root)
    root.mainloop()
