
from services.mqtt_service import MQTTService
from ui_mapper_app import init_db, parse_sql_and_js, ask_user_for_folders
from utils.ui_mapper_adapter import UIMQTTAdapter
from services.parser_service import ParserService
from ui_mapper_app import init_db, parse_sql_and_js, ask_user_for_folders


import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
import re

from services.parser_service import ParserService

from dotenv import load_dotenv
from pathlib import Path

env_path = Path("config/.env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    print(".env file not found at config/.env")

DB_FILE = "ui_map.db"

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

class UIMapperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("UI Structure Mapper")
        self.conn = sqlite3.connect(DB_FILE)

        # Environment-based credentials (can be overridden by UI)
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

        # Unified MQTT + SSH command adapter
        self.mqtt_adapter = UIMQTTAdapter(self.test_creds)
        self.parser_service = ParserService(self.root, self.conn)

        # State + buffers
        self.command_queue = []
        self.mqtt_output_buffer = []
        self.configured_inputs = []

        # Setup local DB tables
        self.init_function_map_table()
        self.init_mqtt_topic_table()

        # Build main UI
        self.setup_ui()

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
        # Live output window (CLI-style)
        self.output_console = tk.Text(self.root, height=6, bg="black", fg="lime", insertbackground="white")
        self.output_console.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.output_console.insert(tk.END, "Console ready.\n")

        # Top-level toolbar with core actions
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(toolbar, text="Assemble Command", command=self.open_command_builder).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Test Queue Builder", command=self.open_test_queue_builder).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(toolbar, text="Send SIMIN", command=self.send_simin_command).pack(side=tk.LEFT, padx=(0, 5))


    # builders
    def open_command_builder(self):
        from gui.command_builder import CommandBuilder
        self.command_builder_instance = CommandBuilder(self)  # store reference
        self.command_builder_instance.open_builder()

    def open_test_queue_builder(self):
        import tkinter as tk
        from gui.test_queue import TestQueueBuilder

        new_win = tk.Toplevel(self.root)
        new_win.title("Test Queue Builder")

        builder = TestQueueBuilder(self)
        builder.root = new_win  # assign this new window
        builder.build_tab()

        # prompt user to import steps
        if messagebox.askyesno("Import", "Import steps from Command Builder?"):
            self.test_queue_instance.import_steps_from_command_builder()


    # ----- SSH + MQTT Controls -----

    def connect_ssh(self):
        self.output_console.insert(tk.END, "[SSH] Connecting to controller...\n")
        try:
            self.mqtt_adapter.ssh_host = self.test_creds.get("host")
            self.mqtt_adapter.ssh_user = self.test_creds.get("user")
            self.mqtt_adapter.client.connect()
            self.output_console.insert(tk.END, f"Connected to {self.test_creds['host']} as {self.test_creds['user']}\n")
        except Exception as e:
            self.output_console.insert(tk.END, f"[SSH ERROR] {e}\n")

    def close_ssh(self):
        try:
            self.mqtt_adapter.client.disconnect()
            self.output_console.insert(tk.END, "[SSH] Disconnected from controller.\n")
        except Exception as e:
            self.output_console.insert(tk.END, f"[SSH Close Error] {e}\n")

    def subscribe_mqtt(self):
        try:
            self.mqtt_adapter.client.subscribe("exec")  # You can support dynamic topic input later
            self.output_console.insert(tk.END, "[MQTT] Subscribed to 'exec'\n")
        except Exception as e:
            self.output_console.insert(tk.END, f"[MQTT ERROR] {e}\n")

    def send_simin_command(self):
        cmd = simpledialog.askstring("SIMIN Command", "Enter SIMIN command to send:")
        if not cmd:
            return
        try:
            ssh_cmd = f"ssh {self.test_creds['user']}@{self.test_creds['host']} \"{cmd}\""
            out = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
            self.output_console.insert(tk.END, f"\n[SIMIN]\n{out.stdout}{out.stderr}\n")
            self.output_console.see(tk.END)
        except Exception as e:
            self.output_console.insert(tk.END, f"[SIMIN ERROR] {e}\n")


    def simulate_input_popup(self):
        popup = tk.Toplevel(self.root)
        popup.title("Simulate Input")

        tk.Label(popup, text="Simulated command or value:").pack(pady=5)
        entry = ttk.Entry(popup)
        entry.pack(padx=10, fill=tk.X)

        def send_simulated():
            val = entry.get().strip()
            if val:
                result = self.mqtt_adapter.send_command_and_wait("Simulated.Input", val)
                self.output_console.insert(tk.END, f"[SIMULATE] {val} => {result}\n")
                popup.destroy()

        ttk.Button(popup, text="Send", command=send_simulated).pack(pady=10)

    def toggle_mirror_mode(self):
        if not hasattr(self, 'mirror_mode'):
            from gui.mirror_mode import MirrorModeController
            self.mirror_mode = MirrorModeController(self, self.root)
        self.mirror_mode.toggle_mirror_mode()

    def run_ssh_command(self, cmd):
        result = self.mqtt_adapter.send_via_ssh(cmd)
        if isinstance(result, dict):
            return result.get("response", result.get("error", "Unknown result"))
        return result

    def reparse_files(self):
        confirm = messagebox.askyesno("Reparse Files", "This will clear and reload the database.\nContinue?")
        if not confirm:
            return

        try:
            sql_path, js_path = ask_user_for_folders()
            init_db()
            parse_sql_and_js(sql_path, js_path)
            messagebox.showinfo("Success", "Files re-parsed and database updated.")

            # Optional: refresh UI if needed
            if hasattr(self, "load_pages"):
                self.load_pages()
            if hasattr(self, "apply_filters"):
                self.apply_filters()
        except Exception as e:
            messagebox.showerror("Parse Error", f"An error occurred:\n{str(e)}")


# ----- Entry Point -----
if __name__ == '__main__':
    sql_path, js_path = ask_user_for_folders()
    init_db()
    parse_sql_and_js(sql_path, js_path)

    root = tk.Tk()
    app = UIMapperGUI(root)
    root.mainloop()
