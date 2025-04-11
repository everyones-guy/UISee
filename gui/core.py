import os
import json
import re
import time
import sqlite3
import subprocess
from pathlib import Path
from dotenv import load_dotenv

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from services.mqtt_service import MQTTService
from services.parser_service import ParserService
from utils.ui_mapper_adapter import UIMQTTAdapter
from ui_mapper_app import init_db, parse_sql_and_js, ask_user_for_folders

# Optional but incorrect import in your version:
# from pip._vendor.rich.control import i  <-- remove this line, it does nothing and throws an error

env_path = Path("config/.env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    print(".env file not found at config/.env")

DB_FILE = "ui_map.db"

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
        self.client = MQTTService()
        self.parser_service = ParserService(self.root, self.conn)

        self.command_queue = []
        self.mqtt_output_buffer = []
        self.configured_inputs = []

        self.init_function_map_table()
        self.init_mqtt_topic_table()
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
        self.output_console = tk.Text(self.root, height=6, bg="black", fg="lime", insertbackground="white")
        self.output_console.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.output_console.insert(tk.END, "Console ready.\n")

        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(toolbar, text="Assemble Command", command=self.open_command_builder).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Test Queue Builder", command=self.open_test_queue_builder).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(toolbar, text="Send SIMIN", command=self.send_simin_command).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Open New Test Queue", command=self.open_test_queue_builder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Close All Queues", command=self.close_all_test_queues).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Connect to Controller", command=self.connect_ssh).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Subscribe to MQTT", command=self.subscribe_mqtt).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Run Remote Command", command=self.run_remote_command).pack(side=tk.LEFT, padx=(0, 5))

    def load_remote_config_inputs(self):
        try:
            if not hasattr(self, "ssh_service") or not self.ssh_service.ssh_client:
                self.output_console.insert(tk.END, "[CONFIG] SSH connection not established.\n")
                return

            cmd = "cat /usr/share/ConfigFiles/*.json"
            stdin, stdout, stderr = self.ssh_service.ssh_client.exec_command(cmd)

            raw = stdout.read().decode().strip()
            error = stderr.read().decode().strip()

            if error:
                self.output_console.insert(tk.END, f"[CONFIG] Failed to fetch config files:\n{error}\n")
                return

            try:
                # Attempt to parse as one JSON array or multiple objects
                if raw.startswith("{") and raw.endswith("}"):
                    parts = re.split(r"}\s*{", raw)
                    configs = [json.loads("{" + part + "}" if not part.startswith("{") else part) for part in parts]
                elif raw.startswith("["):
                    configs = json.loads(raw)
                else:
                    raise ValueError("Unexpected JSON structure.")

                self.remote_inputs = []
                for cfg in configs:
                    self.remote_inputs.extend(cfg.get("hardwareInputs", []))

                self.output_console.insert(tk.END, f"[CONFIG] Found {len(self.remote_inputs)} hardware inputs.\n")

            except Exception as e:
                self.output_console.insert(tk.END, f"[CONFIG] JSON parse error: {str(e)}\n")

        except Exception as e:
            self.output_console.insert(tk.END, f"[CONFIG] Error: {str(e)}\n")

    def open_command_builder(self):
        from gui.command_builder import CommandBuilder
        builder = CommandBuilder(self.root, self.mqtt_adapter, [], self.test_creds, self.conn, self.configured_inputs, self.output_console)
        builder.open_command_builder()

    def open_test_queue_builder(self):
        from gui.test_queue import TestQueueBuilder
        from datetime import datetime
        new_win = tk.Toplevel(self.root)
        new_win.title(f"Test Queue - {datetime.now().strftime('%H:%M:%S')}")
        builder = TestQueueBuilder(self)
        builder.root = new_win
        builder.build_tab()

        if not hasattr(self, 'test_queue_windows'):
            self.test_queue_windows = []
        self.test_queue_windows.append(builder)

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

    def connect_ssh(self):
        from services.ssh_service import SSHService
        self.ssh_service = SSHService(self.root, self.conn, self.output_console)
        self.ssh_service.connect()

    def run_remote_command(self):
        if hasattr(self, "ssh_service"):
            self.ssh_service.run_command_prompt()
        else:
            messagebox.showwarning("SSH Not Ready", "SSH service not initialized yet.")

    def subscribe_mqtt(self):
        popup = tk.Toplevel(self.root)
        popup.title("Subscribe to MQTT")

        host_var = tk.StringVar(value=self.mqtt_creds.get("host", "localhost"))
        port_var = tk.StringVar(value=self.mqtt_creds.get("port", "1883"))
        user_var = tk.StringVar(value=self.mqtt_creds.get("username", ""))
        pass_var = tk.StringVar(value=self.mqtt_creds.get("password", ""))

        fields = [("Host", host_var), ("Port", port_var), ("Username", user_var), ("Password", pass_var)]
        for label, var in fields:
            ttk.Label(popup, text=label + ":").pack(padx=10, anchor="w")
            ttk.Entry(popup, textvariable=var, show="*" if "password" in label.lower() else "").pack(fill=tk.X, padx=10, pady=(0, 5))

        def subscribe():
            self.mqtt_creds.update({
                "host": host_var.get(),
                "port": port_var.get(),
                "username": user_var.get(),
                "password": pass_var.get()
            })
            try:
                self.mqtt_adapter.client.connect(**self.mqtt_creds)
                self.mqtt_adapter.client.subscribe("exec")
                self.output_console.insert(tk.END, "[MQTT] Subscribed to topic 'exec'\n")
                popup.destroy()
            except Exception as e:
                messagebox.showerror("MQTT Error", str(e))

        ttk.Button(popup, text="Subscribe", command=subscribe).pack(pady=5)

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

    def reparse_files(self):
        confirm = messagebox.askyesno("Reparse Files", "This will create a new database version and reload.\nContinue?")
        if not confirm:
            return

        try:
            sql_path, js_path = ask_user_for_folders()
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            new_db_path = f"ui_map_{timestamp}.db"

            if self.conn:
                self.conn.close()

            self.conn = sqlite3.connect(new_db_path)
            self.active_db_file = new_db_path

            init_db(conn=self.conn)
            parse_sql_and_js(sql_path, js_path, conn=self.conn)

            messagebox.showinfo("Success", f"New DB created:\n{new_db_path}")
            self.output_console.insert(tk.END, f"[DB] New database loaded: {new_db_path}\n")
            if hasattr(self, "load_pages"):
                self.load_pages()

        except Exception as e:
            messagebox.showerror("Parse Error", f"An error occurred:\n{str(e)}")


# ---------- Entry Point ----------
if __name__ == '__main__':
    sql_path, js_path = ask_user_for_folders()
    init_db()
    parse_sql_and_js(sql_path, js_path)

    root = tk.Tk()
    app = UIMapperGUI(root)
    root.mainloop()
