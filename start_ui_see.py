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

from ui_see_app import init_db, parse_sql_and_js
import UISee

DB_FILE = "ui_map.db"
LOG_DIR = "logs"
SNAPSHOT_DIR = "snapshots"

# Global credentials cache
auto_login_credentials = {}

def ensure_directories():
    for folder in [LOG_DIR, SNAPSHOT_DIR]:
        if not os.path.exists(folder):
            os.makedirs(folder)

def show_splash(root, progress_callback):
    splash = Toplevel(root)
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

    progress_callback(close_splash)

def ask_user_for_folders():
    sql_folder = filedialog.askdirectory(title="Select SQL Folder (UIPages)")
    js_folder = filedialog.askdirectory(title="Select JS Folder (Scripts)")
    if not sql_folder or not js_folder:
        messagebox.showerror("Missing Folder", "You must select both folders to proceed.")
        return None, None
    return sql_folder, js_folder

def setup_logging():
    ensure_directories()
    log_file = f"ui_mapper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = os.path.join(LOG_DIR, log_file)

    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logging.info("Logging initialized.")
    return log_path

def save_widget_tree_snapshot():
    conn = None
    try:
        conn = UISee.sqlite3.connect(DB_FILE)
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

# def create_windows_shortcut(script_path):
    # try:
        # import winshell
        # from win32com.client import Dispatch

        # desktop = winshell.desktop()
        # shortcut_path = os.path.join(desktop, "UI-See.lnk")

        # shell = Dispatch('WScript.Shell')
        # shortcut = shell.CreateShortCut(shortcut_path)
        # shortcut.TargetPath = sys.executable
        # shortcut.Arguments = f'"{script_path}"'
        # shortcut.WorkingDirectory = os.path.dirname(script_path)
        # shortcut.IconLocation = sys.executable
        # shortcut.save()

        # logging.info(f"Shortcut created: {shortcut_path}")
        # messagebox.showinfo("Shortcut Created", f"Shortcut created on desktop:\n{shortcut_path}")
    # except Exception as e:
        # logging.warning(f"Shortcut creation failed: {e}")
        # messagebox.showwarning("Shortcut Error", str(e))

def auto_login_if_needed(app):
    try:
        conn = UISee.sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT value FROM page_details WHERE tag='Name' AND value='login'")
        result = cur.fetchone()
        if result:
            page_name = result[0]
            if not auto_login_credentials.get("username"):
                username = tk.simpledialog.askstring("Login Required", "Enter Admin Username:")
                password = tk.simpledialog.askstring("Password", "Enter Password:", show='*')
                auto_login_credentials["username"] = username
                auto_login_credentials["password"] = password

            app.send_mqtt_command(f"Page.Widgets.UsernameSelection.Value={auto_login_credentials['username']}")
            app.send_mqtt_command(f"Page.Widgets.PasswordEntry.Value={auto_login_credentials['password']}")
            logging.info("Auto login injected for 'login' page.")
    except Exception as e:
        logging.warning(f"Auto-login failed: {e}")
    finally:
        if conn:
            conn.close()

def main():
    parser = argparse.ArgumentParser(description="Launch the UI Structure Mapper")
    parser.add_argument("--reparse", action="store_true", help="Force re-parse of SQL and JS folders")
    parser.add_argument("--shortcut", action="store_true", help="Create desktop shortcut")
    args = parser.parse_args()

    setup_logging()
    logging.info("Starting UI Mapper Launcher")

    root = tk.Tk()
    root.withdraw()

    def post_splash(close_splash):
        def task():
            if args.reparse or not os.path.exists(DB_FILE):
                sql_path, js_path = ask_user_for_folders()
                if not sql_path or not js_path:
                    return
                if os.path.exists(DB_FILE):
                    os.remove(DB_FILE)
                init_db()
                parse_sql_and_js(sql_path, js_path)
                logging.info("Database re-parsed and loaded.")

            save_widget_tree_snapshot()
            root.deiconify()
            close_splash()
            app = UISee.UIMapperGUI(root)
            auto_login_if_needed(app)
            logging.info("UI loaded.")
            root.mainloop()

        threading.Thread(target=task).start()

    show_splash(root, post_splash)

    #if args.shortcut:
        #create_windows_shortcut(os.path.abspath(__file__))


if __name__ == "__main__":
    main()

