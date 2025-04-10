# gui/test_queue.py

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from datetime import datetime
import subprocess
import time

from dotenv import load_dotenv
from pathlib import Path

env_path = Path("config/.env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    print(".env file not found at config/.env")

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

class TestQueueBuilder:
    def __init__(self, app_context):
        self.app = app_context
        self.root = app_context.root
        self.mqtt_adapter = app_context.mqtt_adapter
        self.test_creds = app_context.test_creds
        self.configured_inputs = app_context.configured_inputs
        self.output_console = app_context.output_console

        # Optionally share command_builder steps
        self.command_builder = getattr(app_context, "command_builder_instance", None)

        self.steps = []
        self.outputs = []
        self.preview_widgets = []
        self.toggle_vars = []
        self.selected_step_index = tk.IntVar(value=-1)

    def build_tab(self):
        self.win = ttk.Frame(self.root)
        self.win.pack(fill=tk.BOTH, expand=True)

        self.repeat_var = tk.IntVar(value=1)
        self.skip_post_wait = tk.BooleanVar(value=False)
        self.logging_enabled = tk.BooleanVar(value=False)

        self._build_main_ui()
        self._add_example_steps()
        self._refresh_step_list()

    def _build_main_ui(self):
        container = tk.Frame(self.win)
        container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(container)
        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        collapse_controls = ttk.Frame(self.win)
        collapse_controls.pack(fill=tk.X, padx=10, pady=(0, 5))
        ttk.Button(collapse_controls, text="Collapse All", command=self._collapse_all).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(collapse_controls, text="Expand All", command=self._expand_all).pack(side=tk.LEFT)

        self.log_frame = tk.Frame(self.win)
        self.log_console = tk.Text(self.log_frame, height=10, bg="black", fg="lime", state="disabled")
        self.log_console.pack(fill=tk.BOTH, expand=True)

        ttk.Checkbutton(self.win, text="Enable Logging Console", variable=self.logging_enabled, command=self._toggle_log).pack(anchor="w", padx=10, pady=(0, 5))

        controls = tk.Frame(self.win)
        controls.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(controls, text="Repeat:").pack(side=tk.LEFT)
        ttk.Entry(controls, textvariable=self.repeat_var, width=5).pack(side=tk.LEFT, padx=(5, 15))
        ttk.Checkbutton(controls, text="Skip Post-Wait", variable=self.skip_post_wait).pack(side=tk.LEFT)

        ttk.Button(self.win, text="Run Sequence with Timing", command=self._run_timed_sequence).pack(pady=5)
        ttk.Button(self.win, text="Delete Selected Step", command=self._delete_selected_step).pack(pady=5)


    def _add_example_steps(self):
        self.steps.append({"type": "mqtt", "command": "Page.Widgets.Pump1.IsSet=1", "pre_wait": 2, "post_wait": 2})
        self.outputs.append("[MQTT] Would publish to topic 'exec' with command: Page.Widgets.Pump1.IsSet=1")
        self.steps.append({"type": "wait", "value": 10})
        self.outputs.append("[WAIT] Would wait 10 seconds.")
        self.steps.append({"type": "ssh", "command": "ec simin a_tra1 55.5", "pre_wait": 2, "post_wait": 2})
        self.outputs.append("[SSH] Would send 'ec simin a_tra1 55.5' to remote controller")

    def _delete_selected_step(self):
        index = self.selected_step_index.get()
        if 0 <= index < len(self.steps):
            deleted = self.steps.pop(index)
            self.outputs.pop(index)
            self.selected_step_index.set(-1)
            self._refresh_step_list()
            messagebox.showinfo("Deleted", f"Removed step: {deleted.get('command', deleted.get('value', ''))}")
        else:
            messagebox.showwarning("No Selection", "Please click on a step first to delete.")


    def _refresh_step_list(self):
        # Clear all UI step widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Clear step-specific tracking lists
        self.preview_widgets.clear()
        self.toggle_vars.clear()

        # Reset selected index if out of range
        if self.selected_step_index.get() >= len(self.steps):
            self.selected_step_index.set(-1)

        def highlight_selected(selected_index):
            for i, frame in enumerate(self.scrollable_frame.winfo_children()):
                bg = "#333" if i == selected_index else "#222"
                frame.configure(bg=bg)
                for child in frame.winfo_children():
                    if isinstance(child, tk.Frame) or isinstance(child, tk.Label):
                        child.configure(bg=bg)

        for idx, step in enumerate(self.steps):
            typ = step.get("type", "").upper()
            val = step.get("command", step.get("value", ""))

            frame = tk.Frame(self.scrollable_frame, borderwidth=1, relief="solid", background="#222")
            frame.pack(fill=tk.X, padx=10, pady=5)

            header = tk.Frame(frame, bg="#222")
            header.pack(fill=tk.X)

            label = tk.Label(header, text=f"{idx+1}. {typ}: {val}", font=("Arial", 10, "bold"), bg="#222", fg="white")
            label.pack(side=tk.LEFT, padx=5, pady=5)

            toggle_var = tk.BooleanVar(value=False)
            self.toggle_vars.append(toggle_var)

            preview = tk.Text(frame, height=5, bg="#111", fg="#0f0", insertbackground="white")
            preview.insert(tk.END, f"[PREVIEW] {typ} -- {val}")
            preview.configure(state="disabled")
            self.preview_widgets.append(preview)

            toggle_btn = ttk.Checkbutton(header, text="Show Output", variable=toggle_var, command=lambda i=idx: preview.pack(fill=tk.X, padx=10, pady=(0, 10)) if toggle_var.get() else preview.pack_forget())
            toggle_btn.pack(side=tk.RIGHT, padx=5)

            # Selector logic
            def select(event, i=idx):
                self.selected_step_index.set(i)
                highlight_selected(i)

            def right_click(event, i=idx):
                self.selected_step_index.set(i)
                highlight_selected(i)
                menu = tk.Menu(self.root, tearoff=0)
                menu.add_command(label="Delete Step", command=self._delete_selected_step)
                menu.post(event.x_root, event.y_root)

            # Bind all clickable areas
            for widget in [frame, header, label]:
                widget.bind("<Button-1>", lambda e, i=idx: select(e, i))
                widget.bind("<Button-3>", lambda e, i=idx: right_click(e, i))



    def _highlight_selected(self, selected_index):
        for i, child in enumerate(self.scrollable_frame.winfo_children()):
            child.configure(bg="#444" if i == selected_index else "#222")
            for sub in child.winfo_children():
                if isinstance(sub, (tk.Frame, tk.Label)):
                    sub.configure(bg="#444" if i == selected_index else "#222")

    def _collapse_all(self):
        for i in range(len(self.preview_widgets)):
            self.preview_widgets[i].pack_forget()
            self.toggle_vars[i].set("Show Preview")

    def _expand_all(self):
        for i in range(len(self.preview_widgets)):
            self.preview_widgets[i].pack(fill=tk.X, padx=5, pady=(0, 5))
            self.toggle_vars[i].set("Hide Preview")

    def _toggle_log(self):
        if self.logging_enabled.get():
            self.log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        else:
            self.log_frame.pack_forget()

    def _log_message(self, msg):
        if self.logging_enabled.get():
            self.log_console.configure(state="normal")
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_console.insert(tk.END, f"[{timestamp}] {msg}\n")
            self.log_console.see(tk.END)
            self.log_console.configure(state="disabled")

    def _run_timed_sequence(self):
        results = []
        repeat_count = max(1, self.repeat_var.get())
        for repeat_index in range(repeat_count):
            for step in self.steps:
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
                if not self.skip_post_wait.get():
                    time.sleep(step.get("post_wait", 2))
                result["end"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                result["duration_sec"] = (datetime.strptime(result["end"], "%Y-%m-%d %H:%M:%S") - start_time).total_seconds()
                results.append(result)

        export_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if export_path:
            with open(export_path, "w") as f:
                json.dump(results, f, indent=2)
            messagebox.showinfo("Export Complete", f"Results exported to:\n{export_path}")

    def import_steps_from_command_builder(self):
        if self.command_builder and hasattr(self.command_builder, "steps"):
            for typ, cmd in self.command_builder.steps:
                if typ == "mqtt":
                    self.steps.append({"type": "mqtt", "command": cmd, "pre_wait": 1, "post_wait": 1})
                    self.outputs.append(f"[MQTT] Queued command: {cmd}")
                elif typ == "wait":
                    secs = int(cmd.split()[0])
                    self.steps.append({"type": "wait", "value": secs})
                    self.outputs.append(f"[WAIT] {secs} seconds")
                elif typ == "ssh":
                    self.steps.append({"type": "ssh", "command": cmd, "pre_wait": 1, "post_wait": 1})
                    self.outputs.append(f"[SSH] Queued: {cmd}")
            self._refresh_step_list()
            messagebox.showinfo("Imported", "Steps imported from Command Builder.")
        else:
            messagebox.showwarning("No Steps", "No Command Builder steps available.")

