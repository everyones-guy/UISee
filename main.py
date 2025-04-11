# main.py
import os
import sys
import argparse
import tkinter as tk
from tkinter import messagebox, filedialog, Toplevel, Label, ttk
from datetime import datetime
import threading
import logging
import json
import time
import sqlite3

from db_bootstrap import init_db, parse_sql_and_js
from gui.core import UIMapperGUI

DB_FILE = "ui_map.db"
LOG_DIR = "logs"
SNAPSHOT_DIR = "snapshots"

class UISeeLauncher:
    def __init__(self):
        self.auto_login_credentials = {}
        self.root = tk.Tk()
        self.root.withdraw()

    def ensure_directories(self):
        for folder in [LOG_DIR, SNAPSHOT_DIR]:
            os.makedirs(folder, exist_ok=True)

    def setup_logging(self):
        self.ensure_directories()
        log_file = f"ui_mapper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_path = os.path.join(LOG_DIR, log_file)

        logging.basicConfig(
            filename=log_path,
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s"
        )
        logging.info("Logging initialized.")

    def show_splash(self, callback):
        splash = Toplevel(self.root)
        splash.overrideredirect(True)
        splash.geometry("400x200+600+300")
        splash.configure(bg="#222")

        Label(splash, text="UI-See", font=("Arial", 26, "bold"), fg="white", bg="#222").pack(pady=(40, 5))
        Label(splash, text="Visualize. Validate. Victory.", font=("Arial", 12), fg="#aaa", bg="#222").pack()
        Label(splash, text="Loading UI Mapper...", font=("Arial", 10), fg="#888", bg="#222").pack(pady=(20, 10))

        progress = ttk.Progressbar(splash, mode="indeterminate")
        progress.pack(fill=tk.X, padx=40, pady=10)
        progress.start(10)

        def close_splash():
            progress.stop()
            splash.destroy()

        callback(close_splash)

    def ask_user_for_folders(self):
        sql_folder = filedialog.askdirectory(title="Select SQL Folder (UIPages)")
        js_folder = filedialog.askdirectory(title="Select JS Folder (Scripts)")
        if not sql_folder or not js_folder:
            messagebox.showerror("Missing Folder", "You must select both folders to proceed.")
            return None, None
        return sql_folder, js_folder

    def save_widget_tree_snapshot(self):
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("SELECT page_name, widget_type, widget_name, widget_index FROM widgets")
            rows = cur.fetchall()
            snapshot = {}
            for page_name, widget_type, widget_name, widget_index in rows:
                snapshot.setdefault(page_name, []).append({
                    "type": widget_type,
                    "name": widget_name,
                    "index": widget_index
                })
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(SNAPSHOT_DIR, f"startup_snapshot_{timestamp}.json")
            with open(filepath, "w") as f:
                json.dump(snapshot, f, indent=4)
            logging.info(f"Widget tree snapshot saved: {filepath}")
        except Exception as e:
            logging.warning(f"Snapshot error: {e}")
        finally:
            if conn:
                conn.close()

    def auto_login_if_needed(self, app):
        try:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("SELECT value FROM page_details WHERE tag='Name' AND value='login'")
            result = cur.fetchone()
            if result:
                if not self.auto_login_credentials.get("username"):
                    username = tk.simpledialog.askstring("Login Required", "Enter Admin Username:")
                    password = tk.simpledialog.askstring("Password", "Enter Password:", show='*')
                    self.auto_login_credentials["username"] = username
                    self.auto_login_credentials["password"] = password

                app.send_mqtt_command(f"Page.Widgets.UsernameSelection.Value={self.auto_login_credentials['username']}")
                app.send_mqtt_command(f"Page.Widgets.PasswordEntry.Value={self.auto_login_credentials['password']}")
                logging.info("Auto login injected for 'login' page.")
        except Exception as e:
            logging.warning(f"Auto-login failed: {e}")
        finally:
            if conn:
                conn.close()

    def launch_gui(self, close_splash):
        self.root.deiconify()
        close_splash()
        app = UIMapperGUI(self.root)
        self.auto_login_if_needed(app)
        app.load_pages()
        logging.info("UI loaded.")

    def start(self, reparse=False):
        def post_splash(close_splash):
            def backend_task():
                if reparse or not os.path.exists(DB_FILE):
                    sql_path, js_path = self.ask_user_for_folders()
                    if not sql_path or not js_path:
                        return
                    if os.path.exists(DB_FILE):
                        os.remove(DB_FILE)
                    init_db()
                    parse_sql_and_js(sql_path, js_path)
                    logging.info("Database re-parsed and loaded.")

                self.save_widget_tree_snapshot()
                self.root.after(0, lambda: self.launch_gui(close_splash))

            threading.Thread(target=backend_task).start()

        self.show_splash(post_splash)
        self.root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Launch the UI Structure Mapper")
    parser.add_argument("--reparse", action="store_true", help="Force re-parse of SQL and JS folders")
    args = parser.parse_args()

    launcher = UISeeLauncher()
    launcher.setup_logging()
    logging.info("Starting UI Mapper Launcher")
    launcher.start(reparse=args.reparse)

if __name__ == "__main__":
    main()
