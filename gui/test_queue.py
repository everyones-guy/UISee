# gui/test_queue.py

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from datetime import datetime
import subprocess
import time
import threading

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
        self.last_template_path = None

    def build_tab(self):
        self.win = ttk.Frame(self.root)
        self.win.pack(fill=tk.BOTH, expand=True)
        self._build_controls()
        self._build_step_area()
        self._add_example_steps()
        self._refresh_step_list()
        self.progress = ttk.Progressbar(self.win, orient="horizontal", mode="determinate")
        self.progress.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.root.title(f"Test Queue - {datetime.now().strftime('%H:%M:%S')}")
        



    def _build_controls(self):
        controls = ttk.Frame(self.win)
        controls.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(controls, text="Run Sequence", command=self.run_sequence_threaded).pack(side=tk.LEFT)
        ttk.Button(controls, text="Delete Step", command=self._delete_selected_step).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Save as Template", command=self._save_as_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls, text="Load Template", command=self._load_template).pack(side=tk.LEFT, padx=5)

        # Thread-safe repeat
        self.repeat_var = tk.StringVar(value="1")
        ttk.Label(controls, text="Repeat:").pack(side=tk.LEFT, padx=(15, 0))
        repeat_entry = ttk.Entry(controls, textvariable=self.repeat_var, width=5)
        repeat_entry.pack(side=tk.LEFT)
        def update_repeat_val(*args):
            try:
                self.repeat_count_value = int(self.repeat_var.get())
            except ValueError:
                self.repeat_count_value = 1
        self.repeat_var.trace_add("write", update_repeat_val)
        update_repeat_val()

        # Thread-safe skip post-wait
        self.skip_post_wait_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(controls, text="Skip Post-Wait", variable=self.skip_post_wait_var).pack(side=tk.LEFT, padx=(10, 0))
        self.skip_post_wait_var.trace_add("write", lambda *a: setattr(self, "skip_post_wait_val", self.skip_post_wait_var.get()))
        setattr(self, "skip_post_wait_val", self.skip_post_wait_var.get())



    def _build_step_area(self):
        container = ttk.Frame(self.win)
        container.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(container)
        self.scrollable_frame = ttk.Frame(self.canvas)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrollable_frame.bind("<ButtonRelease-1>", self._handle_drop)
        self.drag_start_index = None


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
        self.steps.append({"type": "mqtt", "command": "Page.Widgets.Pump1.IsSet=1"})
        self.steps.append({"type": "wait", "value": 10})
        self.steps.append({"type": "ssh", "command": "ec simin a_tra1 55.5"})

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
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.preview_widgets.clear()
        self.toggle_vars.clear()

        for idx, step in enumerate(self.steps):
            frame = tk.Frame(self.scrollable_frame, borderwidth=1, relief="raised", bg="#222")
            frame.pack(fill=tk.X, padx=5, pady=2)

            def select(i=idx):
                self.selected_step_index.set(i)
                self._highlight_selected(i)

            def make_context_menu(index):
                def show_context(event):
                    self.selected_step_index.set(index)
                    self._highlight_selected(index)
                    menu = tk.Menu(self.root, tearoff=0)
                    menu.add_command(label="Delete Step", command=self._delete_selected_step)
                    menu.post(event.x_root, event.y_root)
                return show_context

            frame.bind("<Button-1>", lambda e, i=idx: select(i))
            frame.bind("<Button-3>", make_context_menu(idx))

            label_text = f"{step['type'].upper()}: {step.get('command', step.get('value', ''))}"
            entry_var = tk.StringVar(value=step.get("command", step.get("value", "")))

            def update_val(var, i=idx):
                if "command" in self.steps[i]:
                    self.steps[i]["command"] = var.get()
                else:
                    self.steps[i]["value"] = int(var.get()) if var.get().isdigit() else var.get()

            entry_var.trace_add("write", lambda *args, var=entry_var, i=idx: update_val(var, i))

            lbl = tk.Label(frame, text=step["type"].upper(), bg="#222", fg="white")
            lbl.pack(side=tk.LEFT, padx=5)
            ent = ttk.Entry(frame, textvariable=entry_var, width=60)
            ent.pack(side=tk.LEFT, padx=5)
            ent.bind("<Button-1>", lambda e, i=idx: select(i))
            ent.bind("<Button-3>", make_context_menu(idx))

    def _on_drag_start(self, index):
        self.drag_start_index = index

    def _on_drag_motion(self, event):
        y = event.y_root - self.scrollable_frame.winfo_rooty()
        height = self.scrollable_frame.winfo_height()
        step_height = height // max(1, len(self.steps))
        index = y // step_height
        index = max(0, min(len(self.steps) - 1, index))
        if index != self.drag_start_index:
            self.steps[self.drag_start_index], self.steps[index] = self.steps[index], self.steps[self.drag_start_index]
            self.drag_start_index = index
            self._refresh_step_list()

    def _handle_drop(self, event):
        self.drag_start_index = None

    def _delete_selected_step(self):
        idx = self.selected_step_index.get()
        if 0 <= idx < len(self.steps):
            self.steps.pop(idx)
            self.selected_step_index.set(-1)
            self._refresh_step_list()

    def _save_as_template(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if path:
            with open(path, "w") as f:
                json.dump(self.steps, f, indent=2)
            self.last_template_path = path
            messagebox.showinfo("Saved", f"Template saved to:\n{path}")

    def _load_template(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if path:
            with open(path, "r") as f:
                self.steps = json.load(f)
            self.last_template_path = path
            self._refresh_step_list()
            self.progress["maximum"] = len(self.steps)
            self.progress["value"] = 0


    def run_sequence_threaded(self):
        threading.Thread(target=self._run_timed_sequence, daemon=True).start()
        t = threading.Thread(target=self._run_timed_sequence, daemon=True)
        t.start()

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
        repeat_count = getattr(self, "repeat_count_value", 1)
        skip_post_wait = getattr(self, "skip_post_wait_val", False)
        total = len(self.steps) * repeat_count
        self.progress["maximum"] = total
        self.progress["value"] = 0

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
                        if "=" in step["command"]:
                            path, value = step["command"].split("=", 1)
                            r = self.mqtt_adapter.send_command_and_wait(path.strip(), value.strip())
                            result.update(r)
                        else:
                            result["status"] = "invalid"
                            result["output"] = f"Invalid MQTT command: {step['command']}"

                    elif step["type"] == "ssh":
                        ssh_cmd = f"ssh {self.test_creds['user']}@{self.test_creds['host']} \"{step['command']}\""
                        proc = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
                        result["status"] = "success" if proc.returncode == 0 else "fail"
                        result["output"] = proc.stdout.strip() + proc.stderr.strip()
                except Exception as e:
                    result["status"] = "error"
                    result["output"] = str(e)

                if not skip_post_wait:
                    time.sleep(step.get("post_wait", 2))
                result["end"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                result["duration_sec"] = (datetime.strptime(result["end"], "%Y-%m-%d %H:%M:%S") - start_time).total_seconds()
                results.append(result)
                self.progress["value"] += 1
                self.progress.update()

        export_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
            initialfile=f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
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

