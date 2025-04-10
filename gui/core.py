from gui.command_builder import CommandBuilder
from gui.test_queue import TestQueueBuilder

# Add imports here for other split components as needed

from services.mqtt_service import MQTTService
from ui_mapper_app import init_db, parse_sql_and_js, ask_user_for_folders
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
from utils.ui_mapper_adapter import UIMQTTAdapter
from dotenv import load_dotenv
import re

load_dotenv()
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
        ttk.Button(toolbar, text="Test Queue Builder", command=self.open_test_queue_builder).pack(side=tk.LEFT, padx=(5,0))

    def open_command_builder(self):
        CommandBuilder(self)

    def open_test_queue_builder(self):
        TestQueueBuilder(self)

if __name__ == '__main__':
    sql_path, js_path = ask_user_for_folders()
    init_db()
    parse_sql_and_js(sql_path, js_path)

    root = tk.Tk()
    app = UIMapperGUI(root)
    root.mainloop()
