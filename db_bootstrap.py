import os
import re
import json
import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox

DB_FILE = "ui_map.db"

def extract_resources(config_str):
    try:
        config = json.loads(config_str)
        resources = config.get("Resources", {}).get("resource", [])
        return [(entry.get("tag"), entry.get("value")) for entry in resources if "tag" in entry]
    except Exception:
        return []

def init_db(conn=None):
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    internal_conn = conn or sqlite3.connect(DB_FILE)
    cur = internal_conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS widgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_name TEXT,
        widget_type TEXT,
        widget_name TEXT,
        widget_index TEXT,
        widget_config TEXT,
        widget_config_id INTEGER,
        widget_id INTEGER
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS navigations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        function TEXT,
        target_page TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS page_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_name TEXT,
        tag TEXT,
        value TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS widget_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        widget_id INTEGER,
        tag TEXT,
        value TEXT,
        FOREIGN KEY (widget_id) REFERENCES widgets(id)
    )""")
    
    cur.execute("""CREATE TABLE IF NOT EXISTS js_functions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_name TEXT,
        function_name TEXT,
        parameters TEXT
    )""")


    internal_conn.commit()
    if not conn:  # Only close if we opened it
        internal_conn.close()

def parse_sql_and_js(sql_folder, js_folder, conn=None):
    internal_conn = conn or sqlite3.connect(DB_FILE)
    cur = internal_conn.cursor()

    # SQL parsing
    for filename in os.listdir(sql_folder):
        if not filename.endswith(".sql"):
            continue

        page_name = os.path.splitext(filename)[0]
        with open(os.path.join(sql_folder, filename), 'r', encoding='utf-8') as f:
            content = f.read()

            cur.execute("INSERT OR IGNORE INTO pages (name) VALUES (?)", (page_name,))

            # PagesInstalled
            for match in re.finditer(
                r'INSERT INTO\s+"?PagesInstalled"?\s*\(\s*"PageName"\s*,\s*"PageID"\s*,\s*"PageConfig"\s*\)\s*VALUES\s*\(\s*\'(.*?)\'\s*,\s*(\d+)\s*,\s*\'(.*?)\'\s*\);?',
                content, re.DOTALL | re.IGNORECASE):
                page_name_sql, _, json_str = match.groups()
                json_str = json_str.replace('""', '"')
                for tag, value in extract_resources(json_str):
                    cur.execute("INSERT INTO page_details (page_name, tag, value) VALUES (?, ?, ?)",
                                (page_name_sql, tag, value))

            # WidgetsInstalled
            for match in re.finditer(
                r'INSERT INTO\s+"?WidgetsInstalled"?\s*\(\s*"WidgetConfigID"\s*,\s*"WidgetID"\s*,\s*"WidgetConfig"\s*\)\s*VALUES\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*\'(.*?)\'\s*\);?',
                content, re.DOTALL | re.IGNORECASE):
                widget_config_id, widget_id, config_str = match.groups()
                config_str = config_str.replace('""', '"')
                widget_type = widget_name = widget_index = ""

                try:
                    config_data = json.loads(config_str)
                    for entry in config_data.get("Resources", {}).get("resource", []):
                        tag = entry.get("tag")
                        if tag == "Name":
                            widget_name = entry.get("value")
                        elif tag == "ButtonType":
                            widget_type = entry.get("value")
                        elif tag == "WidgetIndex":
                            widget_index = entry.get("value")
                except:
                    pass

                cur.execute("""INSERT INTO widgets (
                    page_name, widget_type, widget_name, widget_index,
                    widget_config, widget_config_id, widget_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""", (
                    page_name, widget_type, widget_name, widget_index,
                    config_str, widget_config_id, widget_id
                ))
                db_widget_id = cur.lastrowid

                for tag, value in extract_resources(config_str):
                    cur.execute("INSERT INTO widget_details (widget_id, tag, value) VALUES (?, ?, ?)",
                                (db_widget_id, tag, value))

        # JS parsing: NavigateTo AND all functions
        for filename in os.listdir(js_folder):
            if not filename.endswith(".js"):
                continue

            page_name = os.path.splitext(filename)[0]

            with open(os.path.join(js_folder, filename), 'r', encoding='utf-8') as f:
                content = f.read()

                # NavigateTo(...) detection
                for match in re.finditer(r"NavigateTo\((\w+)\)", content):
                    target_page = match.group(1)
                    cur.execute("INSERT INTO navigations (function, target_page) VALUES (?, ?)",
                                (f"NavigateTo({target_page})", target_page))

                # All function types
                all_functions = re.findall(
                    r'(?:function|var)\s+([a-zA-Z0-9_]+)\s*=?\s*function\s*\((.*?)\)', content)
                for fn_name, args in all_functions:
                    cur.execute("""
                        INSERT INTO js_functions (page_name, function_name, parameters)
                        VALUES (?, ?, ?)
                    """, (page_name, fn_name, args.strip()))


    internal_conn.commit()
    if not conn:  # Only close if we opened it
        internal_conn.close()

def ask_user_for_folders():
    root = tk.Tk()
    root.withdraw()
    sql_folder = filedialog.askdirectory(title="Select SQL Folder (UIPages)")
    js_folder = filedialog.askdirectory(title="Select JS Folder (Scripts)")
    if not sql_folder or not js_folder:
        messagebox.showerror("Missing Folder", "You must select both folders to proceed.")
        exit()
    return sql_folder, js_folder

