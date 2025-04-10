
from services.mqtt_service import MQTTService
from ui_mapper_app import init_db, parse_sql_and_js, ask_user_for_folders
from utils.ui_mapper_adapter import UIMQTTAdapter
from services.parser_service import ParserService


import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os
import json
import re
import subprocess


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
        self.client = MQTTService()

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
        ttk.Button(toolbar, text="Open New Test Queue", command=self.open_test_queue_builder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Close All Queues", command=self.close_all_test_queues).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Connect to Controller", command=self.connect_ssh).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Subscribe to MQTT", command=self.subscribe_mqtt).pack(side=tk.LEFT, padx=(0, 5))



    def load_remote_config_inputs(self):
        try:
            cmd = "cat /usr/share/Configfiles/*.json"
            ssh_cmd = f"ssh {self.test_creds['user']}@{self.test_creds['host']} \"{cmd}\""
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)

            if result.returncode != 0:
                self.output_console.insert(tk.END, f"[CONFIG] Failed to fetch config files:\n{result.stderr}\n")
                return

            # Try to parse all combined JSONs (one big array or object)
            try:
                raw = result.stdout.strip()
                # Handle multiple files concatenated
                configs = [json.loads(part) for part in raw.split("}\n{")]
                self.remote_inputs = []
                for cfg in configs:
                    self.remote_inputs.extend(cfg.get("hardwareInputs", []))
            except Exception as e:
                self.output_console.insert(tk.END, f"[CONFIG] JSON parse error: {str(e)}\n")
                return

            self.output_console.insert(tk.END, f"[CONFIG] Found {len(self.remote_inputs)} hardware inputs.\n")

        except Exception as e:
            self.output_console.insert(tk.END, f"[CONFIG] Error: {str(e)}\n")


    # builders
    def open_command_builder(self):
        from gui.command_builder import CommandBuilder
        self.command_builder_instance = CommandBuilder(self)  # store reference
        self.command_builder_instance.open_builder()

    def open_test_queue_builder(self):
        from gui.test_queue import TestQueueBuilder
        from datetime import datetime

        # Create a new Toplevel window
        new_win = tk.Toplevel(self.root)
        new_win.title(f"Test Queue - {datetime.now().strftime('%H:%M:%S')}")

        # Build a new TestQueueBuilder instance tied to the new window
        builder = TestQueueBuilder(self)
        builder.root = new_win
        builder.build_tab()

        # Track multiple windows
        if not hasattr(self, 'test_queue_windows'):
            self.test_queue_windows = []
        self.test_queue_windows.append(builder)

        # Optionally load from Command Builder if user agrees
        if hasattr(self, "command_builder_instance"):
            if messagebox.askyesno("Import", "Import steps from Command Builder?"):
                builder.import_steps_from_command_builder()

    def close_all_test_queues(self):
        if hasattr(self, "test_queue_windows"):
            for q in self.test_queue_windows:
                try:
                    q.root.destroy()
                except Exception as e:
                    print(f"Error closing window: {e}")
            self.test_queue_windows.clear()
            self.output_console.insert(tk.END, "[INFO] All Test Queue windows closed.\n")
        else:
            self.output_console.insert(tk.END, "[INFO] No Test Queue windows to close.\n")


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

        self.load_remote_config_inputs()


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

        input_options = getattr(self, "remote_inputs", [])
        input_var = tk.StringVar()
        val_var = tk.StringVar()

        ttk.Label(popup, text="Hardware Input:").pack(pady=(10, 0))
        input_combo = ttk.Combobox(popup, values=input_options, textvariable=input_var, state="readonly")
        input_combo.pack(padx=10, fill=tk.X)

        ttk.Label(popup, text="Value to Simulate:").pack(pady=(10, 0))
        ttk.Entry(popup, textvariable=val_var).pack(padx=10, fill=tk.X)

        def send_simulated():
            val = val_var.get().strip()
            hw = input_var.get().strip()
            if hw and val:
                result = self.mqtt_adapter.send_command_and_wait(f"Simulated.{hw}", val)
                self.output_console.insert(tk.END, f"[SIMULATE] Simulated.{hw} = {val} => {result}\n")
                popup.destroy()
            else:
                messagebox.showwarning("Missing Input", "Select input and value first.")

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
