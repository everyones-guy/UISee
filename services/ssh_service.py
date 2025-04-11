# services/ssh_service.py

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import paramiko
import threading
import json
from pathlib import Path

CRED_FILE = Path("config/ssh_credentials.json")
KEY_HISTORY_FILE = Path("config/ssh_keys.json")

if not KEY_HISTORY_FILE.parent.exists():
    KEY_HISTORY_FILE.parent.mkdir(parents=True)

def load_key_history():
    if KEY_HISTORY_FILE.exists():
        try:
            return json.load(open(KEY_HISTORY_FILE))
        except:
            return []
    return []

def save_key_to_history(path):
    history = load_key_history()
    if path not in history:
        history.insert(0, path)
        with open(KEY_HISTORY_FILE, "w") as f:
            json.dump(history[:10], f)

class SSHService:
    def __init__(self, root, conn, output_console):
        self.root = root
        self.conn = conn
        self.output_console = output_console
        self.ssh_client = None
        self.test_creds = {"host": "", "user": ""}
        self.session_passphrase = None  # clear when reloaded

    def connect(self):
        win = tk.Toplevel(self.root)
        win.title("SSH to Test Controller")

        # Entry fields
        ttk.Label(win, text="Host:").pack(anchor="w")
        host_entry = ttk.Entry(win)
        host_entry.pack(fill=tk.X)

        ttk.Label(win, text="Username:").pack(anchor="w")
        user_entry = ttk.Entry(win)
        user_entry.pack(fill=tk.X)

        ttk.Label(win, text="Password:").pack(anchor="w")
        pass_entry = ttk.Entry(win, show="*")
        pass_entry.pack(fill=tk.X)

        # Restore saved credentials
        if CRED_FILE.exists():
            try:
                creds = json.load(open(CRED_FILE))
                host_entry.insert(0, creds.get("host", ""))
                user_entry.insert(0, creds.get("user", ""))
                pass_entry.insert(0, creds.get("password", ""))
            except Exception:
                pass

        # Key auth UI
        use_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(win, text="Use Private Key", variable=use_key_var).pack(anchor="w", padx=10, pady=(5, 0))

        key_history = load_key_history()
        key_var = tk.StringVar(value=key_history[0] if key_history else str(Path.home() / ".ssh" / "id_rsa"))
        key_dropdown = ttk.Combobox(win, textvariable=key_var, values=key_history + [str(Path.home() / ".ssh" / "id_rsa")])
        key_dropdown.pack(fill=tk.X, padx=10, pady=(0, 3))

        def browse_key():
            path = filedialog.askopenfilename(title="Select Private Key File", filetypes=[("Key files", "*.pem *.ppk"), ("All files", "*.*")])
            if path:
                key_var.set(path)

        ttk.Button(win, text="Browse...", command=browse_key).pack(padx=10, pady=(0, 5), anchor="e")

        remember_pass_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(win, text="Remember key passphrase this session", variable=remember_pass_var).pack(anchor="w", padx=10, pady=(0, 5))

        # Target history from DB
        cur = self.conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS ssh_targets (id INTEGER PRIMARY KEY AUTOINCREMENT, host TEXT, user TEXT)""")
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
            passwd = pass_entry.get().strip()
            use_key = use_key_var.get()
            key_path = key_var.get().strip()

            if host and user and (passwd or use_key):
                self.test_creds = {"host": host, "user": user}
                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                try:
                    if use_key and key_path:
                        try:
                            if self.session_passphrase:
                                private_key = paramiko.RSAKey.from_private_key_file(key_path, password=self.session_passphrase)
                            else:
                                try:
                                    private_key = paramiko.RSAKey.from_private_key_file(key_path)
                                except paramiko.ssh_exception.PasswordRequiredException:
                                    pw = simpledialog.askstring("Key Passphrase", f"Enter passphrase for key:\n{key_path}", show="*")
                                    private_key = paramiko.RSAKey.from_private_key_file(key_path, password=pw)
                                    if remember_pass_var.get():
                                        self.session_passphrase = pw

                            self.ssh_client.connect(hostname=host, username=user, pkey=private_key)
                            save_key_to_history(key_path)
                            self.output_console.insert(tk.END, f"[SSH] Connected using key: {key_path}\n")
                            self.exec_command("echo Connected to $(hostname) as $(whoami); uname -a", log_prefix="[Remote Info]")
                            win.destroy()

                        except Exception as e:
                            messagebox.showerror("Key Auth Error", f"Could not connect using private key:\n{e}")
                    else:
                        self.ssh_client.connect(hostname=host, username=user, password=passwd)
                        self.output_console.insert(tk.END, f"[SSH] Connected to {user}@{host}\n")
                        win.destroy()

                except Exception as e:
                    messagebox.showerror("SSH Connection Error", str(e))

        def save_connection():
            host = host_entry.get().strip()
            user = user_entry.get().strip()
            if host and user:
                cur.execute("INSERT INTO ssh_targets (host, user) VALUES (?, ?)", (host, user))
                self.conn.commit()
                messagebox.showinfo("Saved", f"Saved {user}@{host} to DB.")

        ttk.Button(win, text="Connect", command=launch_ssh).pack(pady=5)
        ttk.Button(win, text="Save Connection", command=save_connection).pack(pady=5)

    def exec_command(self, command, log_prefix="[SSH]"):
        if not self.ssh_client:
            messagebox.showwarning("Not Connected", "You must connect first.")
            return

        def run():
            try:
                stdin, stdout, stderr = self.ssh_client.exec_command(command)
                output = stdout.read().decode()
                error = stderr.read().decode()
                if output:
                    self.output_console.insert(tk.END, f"\n{log_prefix} Output:\n{output}")
                if error:
                    self.output_console.insert(tk.END, f"\n{log_prefix} Error:\n{error}")
            except Exception as e:
                self.output_console.insert(tk.END, f"\n{log_prefix} Exception:\n{str(e)}\n")

        threading.Thread(target=run, daemon=True).start()

    def run_command_prompt(self):
        cmd = simpledialog.askstring("Run SSH Command", "Enter command to run on controller:")
        if cmd:
            self.exec_command(cmd)

    def close(self):
        if self.ssh_client:
            self.ssh_client.close()
            self.output_console.insert(tk.END, "\n[SSH] Connection closed.\n")
            self.ssh_client = None
        else:
            messagebox.showinfo("No Active Connection", "There is no SSH connection to close.")
