from services.mqtt_service import MQTTService
from db_bootstrap import init_db, parse_sql_and_js, ask_user_for_folders
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

        # self.tabs = {
        #    "All": tk.Listbox(self.root, height=10),
        #    "System": tk.Listbox(self.root, height=10),
        #    "Service": tk.Listbox(self.root, height=10),
        #    "Manual": tk.Listbox(self.root, height=10),
        #    "Issues": tk.Listbox(self.root, height=10),
        #    
        #}
        # for tab_name, listbox in self.tabs.items():
        #    label = tk.Label(self.root, text=tab_name)
        #    label.pack(anchor="w")
        #    listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=2)
        #    listbox.bind("<<ListboxSelect>>", self.on_page_select)


        self.init_function_map_table()
        self.setup_ui()
        self.fetch_configured_inputs()
        self.load_pages()
        self.mqtt_topics = set()

    def setup_ui(self):
        self.output_console = tk.Text(self.root, height=6, bg="black", fg="lime", insertbackground="white")
        self.output_console.pack(fill=tk.X, padx=5, pady=(0, 5))
        self.output_console.insert(tk.END, "Console ready.\n")

        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(toolbar, text="Connect to Controller", command=self.connect_ssh).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(toolbar, text="Assemble Command", command=self.open_command_builder).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Test Queue Builder", command=self.open_test_queue_builder).pack(side=tk.LEFT, padx=(5,0))
        ttk.Button(toolbar, text="Simulate Input", command=self.simulate_input_popup).pack(side=tk.LEFT, padx=(5,0))
        ttk.Button(toolbar, text="Subscribe to MQTT", command=self.subscribe_mqtt).pack(side=tk.LEFT, padx=(5,0))
        ttk.Button(toolbar, text="Close SSH Connection", command=self.close_ssh).pack(side=tk.LEFT, padx=(5,0))

    def init_function_map_table(self):
        cur = self.conn.cursor()
    
        # Widget to Function map
        cur.execute("""
            CREATE TABLE IF NOT EXISTS widget_function_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_name TEXT,
                widget_name TEXT,
                property TEXT,
                function_name TEXT
            )
        """)
    def init_mqtt_topic_table(self):
        cur = self.conn.cursor()
        # MQTT Topics Table 
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mqtt_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_name TEXT,
                topic TEXT
            )
        """)

        self.conn.commit()

    def connect_ssh(self):
        win = tk.Toplevel(self.root)
        win.title("SSH to Test Controller")

        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ssh_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                host TEXT,
                user TEXT
            )
        """)
        self.conn.commit()

        ttk.Label(win, text="Saved Targets:").pack(anchor="w")
        target_combo = ttk.Combobox(win, state="readonly")
        cur.execute("SELECT id, host, user FROM ssh_targets ORDER BY id DESC")
        rows = cur.fetchall()
        target_map = {}
        options = []
        for row in rows:
            label = f"{row[2]}@{row[1]}"
            target_map[label] = row
            options.append(label)
        target_combo['values'] = options
        target_combo.pack(fill=tk.X)

        ttk.Label(win, text="Host:").pack(anchor="w")
        host_entry = ttk.Entry(win)
        host_entry.pack(fill=tk.X)

        ttk.Label(win, text="Username:").pack(anchor="w")
        user_entry = ttk.Entry(win)
        user_entry.pack(fill=tk.X)

        def on_select(event):
            label = target_combo.get()
            if label in target_map:
                _, host, user = target_map[label]
                host_entry.delete(0, tk.END)
                host_entry.insert(0, host)
                user_entry.delete(0, tk.END)
                user_entry.insert(0, user)

        target_combo.bind("<<ComboboxSelected>>", on_select)

        def launch_ssh():
            host = host_entry.get().strip()
            user = user_entry.get().strip()
            if host and user:
                self.test_creds = {"host": host, "user": user}
                ssh_cmd = f"ssh {user}@{host}"
                self.ssh_process = subprocess.Popen(["cmd.exe", "/k", ssh_cmd])
                win.destroy()

        def save_connection():
            host = host_entry.get().strip()
            user = user_entry.get().strip()
            if host and user:
                cur.execute("INSERT INTO ssh_targets (host, user) VALUES (?, ?)", (host, user))
                self.conn.commit()
                messagebox.showinfo("Saved", f"Saved {user}@{host} to DB.")

        ttk.Button(win, text="Connect", command=launch_ssh).pack(pady=5)
        ttk.Button(win, text="Save Connection", command=save_connection).pack(pady=5)

    def close_ssh(self):
        if self.ssh_process:
            self.ssh_process.terminate()
            self.output_console.insert(tk.END, "\n[SSH Closed] Connection terminated.\n")
            self.ssh_process = None
        else:
            messagebox.showinfo("No Active Connection", "There is no SSH connedction to close.")

    def setup_command_history_table(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT,
                result TEXT,
                timestamp TEXT
            )
        """)
        self.conn.commit()

    def log_command_history(self, command, result):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO command_history (command, result, timestamp) VALUES (?, ?, ?)",
                    (command, result, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        self.conn.commit()

    def subscribe_mqtt(self):
        win = tk.Toplevel(self.root)
        win.title("MQTT Subscription")

        ttk.Label(win, text="MQTT Username:").pack(anchor="w")
        user_entry = ttk.Entry(win)
        user_entry.insert(0, self.mqtt_creds.get("username", ""))
        user_entry.pack(fill=tk.X)

        ttk.Label(win, text="MQTT Password:").pack(anchor="w")
        pass_entry = ttk.Entry(win, show="*")
        pass_entry.insert(0, self.mqtt_creds.get("password", ""))
        pass_entry.pack(fill=tk.X)

        ttk.Label(win, text="Broker Host:").pack(anchor="w")
        host_entry = ttk.Entry(win)
        host_entry.insert(0, self.mqtt_creds.get("host", ""))
        host_entry.pack(fill=tk.X)

        ttk.Label(win, text="Port:").pack(anchor="w")
        port_entry = ttk.Entry(win)
        port_entry.insert(0, self.mqtt_creds.get("port", "1883"))
        port_entry.pack(fill=tk.X)

        def save_and_subscribe():
            self.mqtt_creds["username"] = user_entry.get()
            self.mqtt_creds["password"] = pass_entry.get()
            self.mqtt_creds["host"] = host_entry.get()
            self.mqtt_creds["port"] = port_entry.get()
            try:
                self.mqtt_adapter.client.subscribe("#")
                self.output_console.insert(tk.END, f"\n[MQTT Subscribed] Topic: #\n")
            except Exception as e:
                self.output_console.insert(tk.END, f"[MQTT ERROR] {str(e)}\n")
            win.destroy()

        def test_connection():
            try:
                self.output_console.insert(tk.END, "\n[MQTT TEST] Attempting connection...\n")
                self.mqtt_adapter.client.publish("test/connection", json.dumps({"test": "true"}))
                self.output_console.insert(tk.END, f"[MQTT TEST] Test command sent.\n")
            except Exception as e:
                self.output_console.insert(tk.END, f"[MQTT ERROR] {str(e)}\n")

        ttk.Button(win, text="Subscribe", command=save_and_subscribe).pack(pady=5)
        ttk.Button(win, text="Test MQTT Connection", command=test_connection).pack(pady=5)

    def send_mqtt_command(self, cmd):
        self.output_console.insert(tk.END, f"\n[MQTT IN] {cmd}")
        response = self.mqtt_adapter.send_command_and_wait(cmd.split("=")[0], cmd.split("=")[1])
        if response["success"]:
            self.output_console.insert(tk.END, f"\n[MQTT OUT] {response['response']}")
            self.log_command_history(cmd, response['response'])
        else:
            self.output_console.insert(tk.END, f"\n[MQTT ERROR] {response['error']}")
            self.log_command_history(cmd, response['error'])
    
    def open_queue_window(self):
        win = tk.Toplevel(self.root)
        win.title("Command Queue")
        queue_list = tk.Listbox(win, height=10)
        queue_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def add_command():
            cmd = cmd_entry.get().strip()
            if cmd:
                self.command_queue.append(("command", cmd))
                queue_list.insert(tk.END, f"CMD: {cmd}")
                cmd_entry.delete(0, tk.END)

        def add_wait():
            wait_text = wait_combo.get()
            if wait_text:
                seconds = int(wait_text.split("(")[1].split()[0])
                self.command_queue.append(("wait", seconds))
                queue_list.insert(tk.END, f"WAIT: {seconds} sec")

        def clear_queue():
            self.command_queue.clear()
            queue_list.delete(0, tk.END)

        cmd_frame = ttk.Frame(win)
        cmd_frame.pack(fill=tk.X, padx=5)

        cmd_entry = ttk.Entry(cmd_frame)
        cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(cmd_frame, text="Add Command", command=add_command).pack(side=tk.LEFT, padx=(5, 0))

        wait_frame = ttk.Frame(win)
        wait_frame.pack(fill=tk.X, padx=5, pady=2)

        wait_options = [f"{i} sec" for i in range(5, 65, 5)]
        wait_options += [f"{i} min ({i*60} sec)" for i in range(1, 11)]
        wait_combo = ttk.Combobox(wait_frame, values=wait_options)
        wait_combo.set("5 sec")
        wait_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(wait_frame, text="Add Wait", command=add_wait).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(wait_frame, text="Clear Queue", command=clear_queue).pack(side=tk.LEFT, padx=(5, 0))

    def run_command_queue(self):
        self.mqtt_output_buffer.clear()
        for step_type, value in self.command_queue:
            if step_type == "command":
                cmd = value
                self.send_mqtt_command(cmd)
                time.sleep(1.5)
                if self.mqtt_output_buffer:
                    last_response = self.mqtt_output_buffer[-1]
                    self.log_command_history(cmd, last_response)
                    self.mqtt_output_buffer.clear()

            elif step_type == "wait":
                self.output_console.insert(tk.END, f"\n[Waiting {value} seconds...]")
                self.root.update()
                time.sleep(value)

        messagebox.showinfo("Queue Complete", "All commands executed.")

    def view_command_history(self):
        win = tk.Toplevel(self.root)
        win.title("Command History")

        text = tk.Text(win, height=20, width=100)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        cur = self.conn.cursor()
        cur.execute("SELECT timestamp, command, result FROM command_history ORDER BY id DESC LIMIT 100")
        for ts, cmd, res in cur.fetchall():
            text.insert(tk.END, f"[{ts}]\n$ {cmd}\n{res}\n{'-'*60}\n")
        
    def export_bvt_json(self):
        if not self.selected_widgets_for_bvt:
            messagebox.showinfo("No Widgets", "No widgets have been selected.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if file_path:
            with open(file_path, "w") as f:
                json.dump(self.selected_widgets_for_bvt, f, indent=4)
            messagebox.showinfo("Exported", f"BVT Test exported to:\n{file_path}")

    def connect_to_test_controller(self):
        cur = self.conn.cursor() if self.conn else sqlite3.connect(DB_FILE).cursor()
        cur.execute("SELECT host, user FROM ssh_credentials ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()

        creds = {"host": row[0], "user": row[1]} if row else {"host": "", "user": ""}

        def save_and_connect():
            creds["host"] = host_entry.get()
            creds["user"] = user_entry.get()
            self.test_creds = creds

            cur.execute("DELETE FROM ssh_credentials")
            cur.execute("INSERT INTO ssh_credentials (host, user) VALUES (?, ?)", (creds['host'], creds['user']))
            self.conn.commit()

            #recreate MQTT adapter with our updated credentials
            self.mqtt_adapter = UIMQTTAdapter(self.test_creds)
            
            ssh_cmd = f"ssh {creds['user']}@{creds['host']}"
            subprocess.Popen(["cmd.exe", "/k", ssh_cmd])
            connect_win.destroy()

        connect_win = tk.Toplevel(self.root)
        connect_win.title("SSH to Test Controller")

        ttk.Label(connect_win, text="Host:").pack(anchor="w")
        host_entry = ttk.Entry(connect_win)
        host_entry.pack(fill=tk.X)
        host_entry.insert(0, creds.get("host", ""))

        ttk.Label(connect_win, text="Username:").pack(anchor="w")
        user_entry = ttk.Entry(connect_win)
        user_entry.pack(fill=tk.X)
        user_entry.insert(0, creds.get("user", ""))

        ttk.Button(connect_win, text="Connect", command=save_and_connect).pack(pady=10)

    def run_test_command(self):
        if not self.test_creds:
            messagebox.showwarning("Not Connected", "Please connect to a test controller first.")
            return

        def execute():
            cmd = command_entry.get().strip()
            if not cmd:
                return
            ssh_cmd = f"ssh {self.test_creds['user']}@{self.test_creds['host']} {cmd}"
            try:
                result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
                self.output_console.insert(tk.END, f"\n$ {cmd}\n{result.stdout}{result.stderr}")
            except Exception as e:
                self.output_console.insert(tk.END, f"\nError: {str(e)}")

        win = tk.Toplevel(self.root)
        win.title("Run Remote Command")
        ttk.Label(win, text="Command to run on controller:").pack(anchor="w")
        command_entry = ttk.Entry(win)
        command_entry.pack(fill=tk.X, padx=5)
        ttk.Button(win, text="Execute", command=execute).pack(pady=10)

    def assign_js_file(self):
        from tkinter import filedialog
        js_path = filedialog.askopenfilename(title="Select JS file to assign to page", filetypes=[("JavaScript files", "*.js")])
        if not js_path:
            return

        page_name = self.page_name
        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("DELETE FROM js_functions WHERE page_name = ?", (page_name,))

        matches = re.findall(r'(?:function|var)\s+([a-zA-Z0-9_]+)\s*=?\s*function\s*\((.*?)\)', content)
        for fn_name, args in matches:
            cur.execute("INSERT INTO js_functions (page_name, function_name, parameters) VALUES (?, ?, ?)",
                        (page_name, fn_name, args.strip()))
        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"{len(matches)} functions assigned to page '{page_name}'.")
        self.apply_filters()


    def on_page_select(self, event):
        for tab_name, listbox in self.tabs.items():
            selected = listbox.curselection()
            if selected:
                page_text = listbox.get(selected[0])
                self.page_name = page_text.split(" - ")[0]  # Handles "missing/unlinked" tab formatting
                self.apply_filters()
                break


    def apply_filters(self, event=None):
        if not hasattr(self, 'page_name'):
            return

        search_text = self.search_entry.get().lower()
        selected_type = self.type_filter.get()

        self.widget_tree.delete(*self.widget_tree.get_children())
        self.details_text.delete(1.0, tk.END)

        cur = self.conn.cursor()

        # Get widgets for the current page
        cur.execute("""
            SELECT id, widget_type, widget_name, widget_index,
                   widget_config_id, widget_id FROM widgets
            WHERE page_name = ?
        """, (self.page_name,))
        rows = cur.fetchall()

        # Get all JS functions for the page
        cur.execute("SELECT function_name FROM js_functions WHERE page_name = ?", (self.page_name,))
        fn_results = [row[0] for row in cur.fetchall()]
        function_string = ", ".join(fn_results[:3]) + ("..." if len(fn_results) > 3 else "")

        for row in rows:
            db_id, widget_type, widget_name, widget_index, config_id, widget_id = row
            if (selected_type == "All" or widget_type.lower() == selected_type.lower()) and \
               (search_text in widget_name.lower() or search_text in widget_type.lower()):
                self.widget_tree.insert('', tk.END, values=(widget_type, widget_name, widget_index, function_string),
                                        tags=(db_id, config_id, widget_id))

        self.details_text.insert(tk.END, f"Widgets on page: {self.page_name}\n")

        # Navigation info
        cur.execute("SELECT function FROM navigations WHERE target_page = ?", (self.page_name,))
        navs = cur.fetchall()
        if navs:
            self.details_text.insert(tk.END, "\nNavigation Paths:\n")
            for row in navs:
                nav = row[0]
                if search_text in nav.lower() or not search_text:
                    self.details_text.insert(tk.END, f"- {nav}\n")

        # Page configuration
        cur.execute("SELECT tag, value FROM page_details WHERE page_name = ?", (self.page_name,))
        page_tags = cur.fetchall()
        if page_tags:
            self.details_text.insert(tk.END, "\nPage Configuration:\n")
            for tag, value in page_tags:
                self.details_text.insert(tk.END, f"{tag}: {value}\n")


    def on_widget_select(self, event):
        selected_item = self.widget_tree.focus()
        values = self.widget_tree.item(selected_item, 'values')
        tags = self.widget_tree.item(selected_item, 'tags')
        if not values or len(tags) < 3:
            return

        widget_type, widget_name, widget_index, _ = values
        db_id, config_id, widget_id = tags

        widget_data = {
            "db_id": db_id,
            "config_id": config_id,
            "widget_id": widget_id,
            "page_name": self.page_name,
            "widget_name": widget_name,
            "widget_type": widget_type,
            "widget_index": widget_index
        }

        self.open_widget_modal(widget_data)

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


    def copy_to_clipboard(self):
        if not self.selected_widget_info:
            return
        path = self.selected_widget_info["path"]
        self.root.clipboard_clear()
        self.root.clipboard_append(path)
        messagebox.showinfo("Copied", f"Copied to clipboard:\n{path}")

    def preview_full_page(self):
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
            SELECT id, widget_type, widget_name FROM widgets WHERE page_name = ?
        """, (self.page_name,))
        widgets = cur.fetchall()

        row = 0
        for db_id, widget_type, widget_name in widgets:
            display = widget_name or f"Widget_{db_id}"
            widget_type = widget_type.lower()

            if widget_type == "button":
                w = ttk.Button(scroll_frame, text=display,
                               command=lambda name=widget_name: self.generate_bvt_sequence(name))
            elif widget_type == "textbox":
                w = ttk.Entry(scroll_frame)
                w.insert(0, display)
            elif widget_type == "label":
                w = ttk.Label(scroll_frame, text=display)
            else:
                w = ttk.Label(scroll_frame, text=f"[{widget_type}] {display}")
            w.grid(row=row, column=0, padx=10, pady=5, sticky="w")
            row += 1

    def generate_bvt_sequence(self, widget_name):
        lines = []
        lines.append(f"NavigateTo('{self.page_name}')")

        # Smart guess: helper method based on known patterns
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

    def fetch_configured_inputs(self):
        # This function would realistically query the controller or cached JS to get configured inputs
        try:
            result = subprocess.run("ssh {}@{} ec get_input_config".format(
                self.test_creds['user'], self.test_creds['host']),
                shell=True, capture_output=True, text=True)
            if result.stdout:
                data = json.loads(result.stdout.strip())
                self.configured_inputs = [d['name'] for d in data if 'name' in d]
        except Exception as e:
            self.output_console.insert(tk.END, f"\n[Input Config Error] {e}\n")

    def simulate_input_popup(self):
        win = tk.Toplevel(self.root)
        win.title("Simulate Sensor Input")

        ttk.Label(win, text="Input Name:").pack(anchor="w", padx=10, pady=(10, 0))
        input_combo = ttk.Combobox(win, values=self.configured_inputs)
        input_combo.pack(fill=tk.X, padx=10)

        ttk.Label(win, text="Value:").pack(anchor="w", padx=10, pady=(10, 0))
        value_entry = ttk.Entry(win)
        value_entry.pack(fill=tk.X, padx=10)

        def send_input():
            name = input_combo.get().strip()
            value = value_entry.get().strip()
            if not name or not value:
                messagebox.showerror("Missing Info", "Both input name and value are required.")
                return
            command = f"ec -s simin {name} {value}"
            output = self.run_ssh_command(command)
            self.output_console.insert(tk.END, f"\n$ {command}\n{output}\n")
            win.destroy()

        ttk.Button(win, text="Send", command=send_input).pack(pady=10)

    def run_ssh_command(self, command):
        if not self.test_creds or not self.test_creds.get("host") or not self.test_creds.get("user"):
            messagebox.showwarning("Not Connected", "Connect to a test controller first.")
            return "Not connected."

        host = self.test_creds.get("host")
        user = self.test_creds.get("user")
        ssh_cmd = f"ssh {user}@{host} '{command}'"

        try:
            result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
            return result.stdout.strip() or result.stderr.strip()
        except Exception as e:
            return f"SSH Error: {str(e)}"

    def simulate_ec_input(self):
        if not self.test_creds:
            messagebox.showwarning("Not Connected", "Please connect to a controller first.")
            return

        win = tk.Toplevel(self.root)
        win.title("Simulate EC Input")

        ttk.Label(win, text="Widget Path (e.g., Page.Widgets.MyWidget.TextBox1):").pack(anchor="w")
        path_entry = ttk.Entry(win)
        path_entry.pack(fill=tk.X, padx=10)

        ttk.Label(win, text="Value to Send:").pack(anchor="w")
        value_entry = ttk.Entry(win)
        value_entry.pack(fill=tk.X, padx=10)

        ttk.Label(win, text="Override Host (optional):").pack(anchor="w")
        host_entry = ttk.Entry(win)
        host_entry.insert(0, self.test_creds.get("host", ""))
        host_entry.pack(fill=tk.X, padx=10)

        ttk.Label(win, text="Override User (optional):").pack(anchor="w")
        user_entry = ttk.Entry(win)
        user_entry.insert(0, self.test_creds.get("user", ""))
        user_entry.pack(fill=tk.X, padx=10)

        def simulate():
            widget_path = path_entry.get().strip()
            value = value_entry.get().strip()
            host = host_entry.get().strip() or self.test_creds.get("host", "")
            user = user_entry.get().strip() or self.test_creds.get("user", "")

            if not widget_path or not value or not host or not user:
                messagebox.showerror("Missing Input", "Please fill all required fields.")
                return

            ec_command = f"echo '{widget_path}={value}' > /dev/ttyGS0"

            ssh_cmd = f"ssh {user}@{host} \"{ec_command}\""
            try:
                result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
                output = result.stdout + result.stderr
                self.output_console.insert(tk.END, f"\n[EC SIMULATION]\n{output}")
            except Exception as e:
                self.output_console.insert(tk.END, f"\n[EC SIM ERROR] {str(e)}")

        ttk.Button(win, text="Simulate", command=simulate).pack(pady=10)

    def activate_selected_function(self):
        prompt_win = tk.Toplevel(self.root)
        prompt_win.title("Activate JS Function")

        ttk.Label(prompt_win, text="Function Path (e.g. Page.Widgets.MyButton.Action)").pack(padx=10, pady=(10, 0))
        func_var = tk.StringVar()
        ttk.Entry(prompt_win, textvariable=func_var).pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(prompt_win, text="Value to Send:").pack(padx=10, pady=(10, 0))
        value_var = tk.StringVar()
        ttk.Entry(prompt_win, textvariable=value_var).pack(fill=tk.X, padx=10, pady=(0, 10))

        def send():
            func_name = func_var.get().strip()
            value = value_var.get().strip()
            if not func_name:
                messagebox.showwarning("Missing Info", "Function path is required.")
                return
            mqtt_path = f"{func_name}={value}"
            result = self.mqtt_adapter.send_command_and_wait(func_name, value)
            self.output_console.insert(tk.END, f"\n[ACTIVATE] Sent: {mqtt_path}\n")
            if result.get("success"):
                self.output_console.insert(tk.END, f"[RESPONSE] {result['response']}\n")
            else:
                self.output_console.insert(tk.END, f"[ERROR] {result['error']}\n")
            prompt_win.destroy()

        ttk.Button(prompt_win, text="Send", command=send).pack(pady=(5, 10))

    def activate_selected_step(self, step):
        prompt_win = tk.Toplevel(self.root)
        prompt_win.title("Activate Test Step")

        step_type = step.get("type", "")
        command = step.get("command", "")
        value = step.get("value", "")

        ttk.Label(prompt_win, text=f"Step Type: {step_type.upper()}").pack(padx=10, pady=(10, 0))
        ttk.Label(prompt_win, text="Command:").pack(anchor="w", padx=10)
        cmd_var = tk.StringVar(value=command)
        ttk.Entry(prompt_win, textvariable=cmd_var).pack(fill=tk.X, padx=10)

        if step_type != "wait":
            ttk.Label(prompt_win, text="Value:").pack(anchor="w", padx=10, pady=(5, 0))
            val_var = tk.StringVar(value=value)
            ttk.Entry(prompt_win, textvariable=val_var).pack(fill=tk.X, padx=10)
        else:
            val_var = tk.StringVar(value=value)

        def send():
            updated_cmd = cmd_var.get().strip()
            updated_val = val_var.get().strip()

            if step_type == "mqtt":
                result = self.mqtt_adapter.send_command_and_wait(updated_cmd, updated_val)
                self.output_console.insert(tk.END, f"\n[MQTT] Sent: {updated_cmd}={updated_val}\n")
                self.output_console.insert(tk.END, f"[RESULT] {result.get('response') if result.get('success') else result.get('error')}\n")

            elif step_type == "ssh":
                ssh_output = self.run_ssh_command(f"{updated_cmd} {updated_val}")
                self.output_console.insert(tk.END, f"\n[SSH] Sent: {updated_cmd} {updated_val}\n{ssh_output}\n")

            elif step_type == "wait":
                try:
                    wait_time = int(updated_val)
                    self.output_console.insert(tk.END, f"\n[WAIT] Sleeping {wait_time} seconds...\n")
                    self.root.update()
                    time.sleep(wait_time)
                except ValueError:
                    self.output_console.insert(tk.END, f"\n[WAIT] Invalid wait value: {updated_val}\n")

            else:
                self.output_console.insert(tk.END, f"\n[UNHANDLED TYPE] {step_type}: {updated_cmd}\n")

            prompt_win.destroy()

        ttk.Button(prompt_win, text="Send", command=send).pack(pady=10)

    def extract_mqtt_topics(self, js_content):
        topics = set()
        for match in MQTT_TOPIC_REGEX.findall(js_content):
            if '/' in match and not match.startswith("http"):
                topics.add(match)
        return topics

    def register_js_file(self, js_path):
        if not js_path:
            return

        page_name = self.page_name
        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()

        cur = self.conn.cursor()
        cur.execute("DELETE FROM js_functions WHERE page_name = ?", (page_name,))

        matches = re.findall(r'(?:function|var)\s+([a-zA-Z0-9_]+)\s*=?\s*function\s*\((.*?)\)', content)
        for fn_name, args in matches:
            cur.execute("INSERT INTO js_functions (page_name, function_name, parameters) VALUES (?, ?, ?)",
                        (page_name, fn_name, args.strip()))
        self.conn.commit()

        topics_found = self.extract_mqtt_topics(content)
        self.mqtt_topics.update(topics_found)

        messagebox.showinfo("Success", f"{len(matches)} functions assigned to page '{page_name}'.\n{len(topics_found)} MQTT topics detected.")

        for topic in topics_found:
            cur.execute("INSERT INTO mqtt_topics (page_name, topic) VALUES (?, ?)", (page_name, topic))

        self.apply_filters()

    def view_js_structure(self):
        win = tk.Toplevel(self.root)
        win.title("JavaScript File Structures")

        text = tk.Text(win, wrap="none")
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        dump = json.dumps(self.js_structure_by_file, indent=4)
        text.insert(tk.END, dump)

        scrollbar_y = ttk.Scrollbar(win, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar_y.set)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)

        scrollbar_x = ttk.Scrollbar(win, orient="horizontal", command=text.xview)
        text.configure(xscrollcommand=scrollbar_x.set)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

    def get_mqtt_topics(self):
        return sorted(list(self.mqtt_topics))

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

    def load_pages(self):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM pages ORDER BY name")
        self.available_pages = [row[0] for row in cur.fetchall()]

    def get_all_pages(self):
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT page_name FROM widgets ORDER BY page_name")
        return [row[0] for row in cur.fetchall()]

    def open_test_queue_builder(self):
        win = tk.Toplevel(self.root)
        win.title("Test Queue Builder")

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

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        repeat_var = tk.IntVar(value=1)
        skip_post_wait = tk.BooleanVar(value=False)

        # Logging panel toggle
        logging_enabled = tk.BooleanVar(value=False)
        log_frame = tk.Frame(win)
        log_console = tk.Text(log_frame, height=10, bg="black", fg="lime", state="disabled")
        log_console.pack(fill=tk.BOTH, expand=True)

        collapse_controls = ttk.Frame(win)
        collapse_controls.pack(fill=tk.X, padx=10, pady=(0, 5))

        def collapse_all():
            for i in range(len(preview_widgets)):
                preview_widgets[i].pack_forget()
                toggle_vars[i].set("Show Preview")

        def expand_all():
            for i in range(len(preview_widgets)):
                preview_widgets[i].pack(fill=tk.X, padx=5, pady=(0, 5))
                toggle_vars[i].set("Hide Preview")

        ttk.Button(collapse_controls, text="Collapse All", command=collapse_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collapse_controls, text="Expand All", command=expand_all).pack(side=tk.LEFT)

        def toggle_log():
            if logging_enabled.get():
                log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
            else:
                log_frame.pack_forget()

        ttk.Checkbutton(win, text="Enable Logging Console", variable=logging_enabled, command=toggle_log).pack(anchor="w", padx=10, pady=(0, 5))

        def log_message(msg):
            if logging_enabled.get():
                log_console.configure(state="normal")
                timestamp = datetime.now().strftime("%H:%M:%S")
                log_console.insert(tk.END, f"[{timestamp}] {msg}\n")
                log_console.see(tk.END)
                log_console.configure(state="disabled")

        def refresh_steps():
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            preview_widgets.clear()
            toggle_vars.clear()

            for idx, step in enumerate(steps):
                typ = step.get("type", "").upper()
                val = step.get("command", step.get("value", ""))

                frame = tk.Frame(scrollable_frame, borderwidth=1, relief="solid")
                frame.pack(fill=tk.X, padx=10, pady=5)
                frame.bind("<Button-1>", lambda e, i=idx: selected_step_index.set(i))

                header = tk.Frame(frame)
                header.pack(fill=tk.X)

                label = tk.Label(header, text=f"{idx+1}. {typ}: {val}", font=("Arial", 10, "bold"))
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

                toggle_btn = ttk.Checkbutton(header, text="Show Output", variable=toggle_var, command=make_toggle(idx))
                toggle_btn.pack(side=tk.RIGHT, padx=5)

                preview = tk.Text(frame, height=5, bg="#111", fg="#0f0", insertbackground="white")
                preview.insert(tk.END, f"[PREVIEW] {typ} -- {val}")
                preview.configure(state="disabled")
                preview_widgets.append(preview)

        def add_example_steps():
            steps.append({"type": "mqtt", "command": "Page.Widgets.Pump1.IsSet=1"})
            steps.append({"type": "wait", "value": 10})
            steps.append({"type": "ssh", "command": "ec simin a_tra1 55.5"})
            refresh_steps()

        add_example_steps()
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)


        def run_timed_sequence():
            results = []
            repeat_count = max(1, repeat_var.get())
            for repeat_index in range(repeat_count):
                for step in steps:
                    start_time = datetime.now()
                    time.sleep(step.get("pre_wait", 2))
                    result = {
                        "repeat": repeat_index + 1,
                        "type": step["type"],
                        "start": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "command": step.get("command", step.get("value", ""))
                    }
                    try:
                        if step["type"] == "wait":
                            time.sleep(step["value"])
                            result["status"] = "waited"
                            result["output"] = f"Waited {step['value']} seconds"
                        elif step["type"] == "mqtt":
                            r = self.mqtt_adapter.send_command_and_wait(*step["command"].split("="))
                            result.update(r)
                        elif step["type"] == "ssh":
                            ssh_cmd = f"ssh {self.test_creds['user']}@{self.test_creds['host']} \"{step['command']}\""
                            proc = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
                            result["status"] = "success" if proc.returncode == 0 else "fail"
                            result["output"] = proc.stdout.strip() + proc.stderr.strip()
                    except Exception as e:
                        result["status"] = "error"
                        result["output"] = str(e)
                    if not skip_post_wait.get():
                        time.sleep(step.get("post_wait", 2))
                    result["end"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    result["duration_sec"] = (datetime.strptime(result["end"], "%Y-%m-%d %H:%M:%S") - start_time).total_seconds()
                    results.append(result)

            export_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
            if export_path:
                with open(export_path, "w") as f:
                    json.dump(results, f, indent=2)
                messagebox.showinfo("Export Complete", f"Results exported to:\n{export_path}")

        controls = tk.Frame(win)
        controls.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(controls, text="Repeat:").pack(side=tk.LEFT)
        ttk.Entry(controls, textvariable=repeat_var, width=5).pack(side=tk.LEFT, padx=(5, 15))
        ttk.Checkbutton(controls, text="Skip Post-Wait", variable=skip_post_wait).pack(side=tk.LEFT)

        ttk.Button(win, text="Run Sequence with Timing", command=run_timed_sequence).pack(pady=5)
        ttk.Button(win, text="Activate", command=self.activate_selected_step).pack(pady=(0, 10))

        # Scrollable Frame for Test Steps
        canvas_frame = tk.Frame(win)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_step_frame = tk.Frame(canvas)

        scrollable_step_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_step_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        step_frame = scrollable_step_frame  # hook it into the original references

        steps.append({"type": "mqtt", "command": "Page.Widgets.Pump1.IsSet=1", "pre_wait": 2, "post_wait": 2})
        outputs.append("[MQTT] Would publish to topic 'exec' with command: Page.Widgets.Pump1.IsSet=1")

        steps.append({"type": "wait", "value": 10})
        outputs.append("[WAIT] Would wait 10 seconds.")

        steps.append({"type": "ssh", "command": "ec simin a_tra1 55.5", "pre_wait": 2, "post_wait": 2})
        outputs.append("[SSH] Would send 'ec simin a_tra1 55.5' to remote controller")

        refresh_steps()

        def reorder_listboxes(event):
            idx = step_list.nearest(event.y)
            sel = step_list.curselection()
            if not sel:
                return
            src = sel[0]
            if src != idx:
                step = steps.pop(src)
                steps.insert(idx, step)
                refresh_list()
                step_list.selection_set(idx)

        step_list.bind("<B1-Motion>", reorder_listboxes)
        step_list.bind("<Double-Button-1>", lambda e: edit_selected())

        def edit_selected():
            selected = step_list.curselection()
            if not selected:
                return
            idx = selected[0]
            step = steps[idx]
            typ = step.get("type")

            modal = tk.Toplevel(win)
            modal.title(f"Edit Step {idx+1}: {typ.upper()}")

            if typ == "mqtt":
                ttk.Label(modal, text="Widget Path:").pack(anchor="w")
                path_entry = ttk.Entry(modal)
                path_entry.pack(fill=tk.X)
                ttk.Label(modal, text="Value:").pack(anchor="w")
                value_entry = ttk.Entry(modal)
                value_entry.pack(fill=tk.X)
                path_entry.insert(0, step["command"].split("=")[0])
                value_entry.insert(0, step["command"].split("=")[1])

                def apply():
                    step["command"] = f"{path_entry.get()}={value_entry.get()}"
                    refresh_list()
                    modal.destroy()

            elif typ == "ssh":
                ttk.Label(modal, text="System Command:").pack(anchor="w")
                cmd_entry = ttk.Entry(modal)
                cmd_entry.pack(fill=tk.X)
                cmd_entry.insert(0, step["command"])

                def apply():
                    step["command"] = cmd_entry.get()
                    refresh_list()
                    modal.destroy()

            elif typ == "wait":
                ttk.Label(modal, text="Seconds to wait:").pack(anchor="w")
                wait_entry = ttk.Entry(modal)
                wait_entry.pack(fill=tk.X)
                wait_entry.insert(0, str(step["value"]))

                def apply():
                    try:
                        step["value"] = int(wait_entry.get())
                        refresh_list()
                        modal.destroy()
                    except ValueError:
                        messagebox.showerror("Invalid", "Must be a number")

            elif typ == "simin":
                ttk.Label(modal, text="Input Name:").pack(anchor="w")
                input_combo = ttk.Combobox(modal, values=self.configured_inputs)
                input_combo.pack(fill=tk.X)
                name, val = step["command"].split()
                input_combo.set(name)

                ttk.Label(modal, text="Value:").pack(anchor="w")
                value_entry = ttk.Entry(modal)
                value_entry.pack(fill=tk.X)
                value_entry.insert(0, val)

                def apply():
                    step["command"] = f"{input_combo.get()} {value_entry.get()}"
                    refresh_list()
                    modal.destroy()

            ttk.Button(modal, text="Apply", command=apply).pack(pady=5)

        def on_right_click(event):
            try:
                step_list.selection_clear(0, tk.END)
                idx = step_list.nearest(event.y)
                step_list.selection_set(idx)
                context = tk.Menu(win, tearoff=0)
                context.add_command(label="Edit", command=edit_selected)
                context.add_command(label="Remove", command=remove_selected)
                context.add_command(label="Move Up", command=move_up)
                context.add_command(label="Move Down", command=move_down)
                context.post(event.x_root, event.y_root)
            except Exception as e:
                print("Context menu error:", e)

        step_list.bind("<Button-3>", on_right_click)
        win.bind_all("<Control-s>", lambda e: save_queue())
        win.bind_all("<Control-l>", lambda e: load_queue())
        win.bind_all("<Control-Return>", lambda e: run_sequence())
        win.bind_all("<Delete>", lambda e: remove_selected())

        def remove_selected():
            selected = selected_step_index.get()
            if selected == -1 or selected >= len(steps):
                messagebox.showwarning("No Selection", "Please select a step first")
                return
            confirm = messagebox.askyesno("Remove Step", f"Are you sure you want to delete step {selected+1}?")
            if confirm:
                steps.pop(selected)
                if selected < len(outputs):
                    outputs.pop(selected)
                refresh_list()
                selected_step_index.set(-1)

        def move_up():
            idx = selected_step_index.get()
            if idx <= 0 or idx >= len(steps):
                return
            steps[idx - 1], steps[idx] = steps[idx], steps[idx - 1]
            if idx < len(outputs):
                outputs[idx - 1], outputs[idx] = outputs[idx], outputs[idx - 1]
            selected_step_index.set(idx - 1)
            refresh_list()

        def move_down():
            idx = selected_step_index.get()
            if idx < 0 or idx >= len(steps) - 1:
                return
            steps[idx], steps[idx + 1] = steps[idx + 1], steps[idx]
            if idx < len(outputs) - 1:
                outputs[idx], outputs[idx + 1] = outputs[idx + 1], outputs[idx]
            selected_step_index.set(idx + 1)
            refresh_list()


        def add_mqtt():
            def submit():
                path = path_entry.get()
                val = value_entry.get()
                if path and val:
                    steps.append({"type": "mqtt", "command": f"{path}={val}"})
                    refresh_list()
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
                    steps.append({"type": "ssh", "command": cmd})
                    refresh_list()
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
                    steps.append({"type": "wait", "value": int(sec)})
                    refresh_list()
                    modal.destroy()

            modal = tk.Toplevel(win)
            modal.title("Wait")
            ttk.Label(modal, text="Seconds to wait:").pack(anchor="w")
            wait_entry = ttk.Entry(modal)
            wait_entry.pack(fill=tk.X)
            ttk.Button(modal, text="Add", command=submit).pack(pady=5)

        def add_simin():
            def submit():
                input_name = input_combo.get().strip()
                value = value_entry.get().strip()
                if input_name and value:
                    steps.append({"type": "simin", "command": f"{input_name} {value}"})
                    refresh_list()
                    modal.destroy()

            modal = tk.Toplevel(win)
            modal.title("Simulate Sensor Input")
            ttk.Label(modal, text="Input Name:").pack(anchor="w")
            input_combo = ttk.Combobox(modal, values=self.configured_inputs)
            input_combo.pack(fill=tk.X)

            ttk.Label(modal, text="Value:").pack(anchor="w")
            value_entry = ttk.Entry(modal)
            value_entry.pack(fill=tk.X)

            ttk.Button(modal, text="Add", command=submit).pack(pady=5)

        def run_sequence():
            for step in steps:
                typ = step.get("type")
                self.output_console.insert(tk.END, f"\n[STEP] {typ.upper()}\n")
                if typ == "mqtt":
                    cmd = step["command"]
                    path, v = cmd.split("=")
                    result = self.mqtt_adapter.send_command_and_wait(path.strip(), v.strip())
                    self.output_console.insert(tk.END, f"Result: {result}\n")
                elif typ == "ssh":
                    cmd = step["command"]
                    full_cmd = f"ssh {self.test_creds['user']}@{self.test_creds['host']} '{cmd}'"
                    try:
                        out = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
                        self.output_console.insert(tk.END, out.stdout + out.stderr)
                    except Exception as e:
                        self.output_console.insert(tk.END, f"SSH ERROR: {str(e)}\n")
                elif typ == "wait":
                    secs = step.get("value", 1)
                    self.output_console.insert(tk.END, f"Waiting {secs} seconds...\n")
                    self.root.update()
                    time.sleep(secs)
                elif typ == "simin":
                    name, value = step["command"].split()
                    cmd = f"ec -s simin {name} {value}"
                    output = self.run_ssh_command(cmd)
                    self.output_console.insert(tk.END, f"{output}\n")

        def save_queue():
            file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
            if file_path:
                with open(file_path, "w") as f:
                    json.dump(steps, f, indent=4)
                messagebox.showinfo("Saved", f"Test queue saved to {file_path}")

        def load_queue():
            file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
            if file_path:
                try:
                    with open(file_path, "r") as f:
                        loaded = json.load(f)
                    steps.clear()
                    steps.extend(loaded)
                    refresh_list()
                    messagebox.showinfo("Loaded", f"Loaded {len(loaded)} steps from {file_path}")
                except Exception as e:
                    messagebox.showerror("Error", str(e))

        button_frame = ttk.Frame(win)
        button_frame.pack(pady=5)
        ttk.Button(button_frame, text="Add MQTT", command=add_mqtt).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Add System Command", command=add_ssh).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Add Simulated Input", command=add_simin).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Add Wait", command=add_wait).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Run Queue", command=run_sequence).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save", command=save_queue).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Load", command=load_queue).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Edit Selected", command=edit_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Remove Selected", command=remove_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Move Up", command=move_up).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Move Down", command=move_down).pack(side=tk.LEFT, padx=5)

if __name__ == '__main__':
    sql_path, js_path = ask_user_for_folders()
    init_db()
    parse_sql_and_js(sql_path, js_path)

    root = tk.Tk()
    app = UIMapperGUI(root)
    root.mainloop()
