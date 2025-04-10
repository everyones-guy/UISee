# gui/ssh_service.py
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess

class SSHService:
    def __init__(self, root, conn, output_console):
        self.root = root
        self.conn = conn
        self.output_console = output_console
        self.ssh_process = None
        self.test_creds = {"host": "", "user": ""}

    def connect(self):
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

    def close(self):
        if self.ssh_process:
            self.ssh_process.terminate()
            self.output_console.insert(tk.END, "\n[SSH Closed] Connection terminated.\n")
            self.ssh_process = None
        else:
            messagebox.showinfo("No Active Connection", "There is no SSH connection to close.")
