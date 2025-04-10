# gui/test_queue.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from datetime import datetime
import subprocess
import time


class TestQueueBuilder:
    def __init__(self, parent, mqtt_adapter, test_creds, configured_inputs, output_console):
        self.root = parent
        self.mqtt_adapter = mqtt_adapter
        self.test_creds = test_creds
        self.configured_inputs = configured_inputs
        self.output_console = output_console

        self.steps = []
        self.outputs = []
        self.preview_widgets = []
        self.toggle_vars = []
        self.selected_step_index = tk.IntVar(value=-1)

    def open(self):
        self.win = tk.Toplevel(self.root)
        self.win.title("Test Queue Builder")

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
        ttk.Button(self.win, text="Close", command=self.win.destroy).pack(pady=(0, 10))

    def _add_example_steps(self):
        self.steps.append({"type": "mqtt", "command": "Page.Widgets.Pump1.IsSet=1", "pre_wait": 2, "post_wait": 2})
        self.outputs.append("[MQTT] Would publish to topic 'exec' with command: Page.Widgets.Pump1.IsSet=1")

        self.steps.append({"type": "wait", "value": 10})
        self.outputs.append("[WAIT] Would wait 10 seconds.")

        self.steps.append({"type": "ssh", "command": "ec simin a_tra1 55.5", "pre_wait": 2, "post_wait": 2})
        self.outputs.append("[SSH] Would send 'ec simin a_tra1 55.5' to remote controller")

    def _refresh_step_list(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.preview_widgets.clear()
        self.toggle_vars.clear()

        for idx, step in enumerate(self.steps):
            typ = step.get("type", "").upper()
            val = step.get("command", step.get("value", ""))

            frame = tk.Frame(self.scrollable_frame, borderwidth=1, relief="solid")
            frame.pack(fill=tk.X, padx=10, pady=5)
            frame.bind("<Button-1>", lambda e, i=idx: self.selected_step_index.set(i))

            header = tk.Frame(frame)
            header.pack(fill=tk.X)

            label = tk.Label(header, text=f"{idx+1}. {typ}: {val}", font=("Arial", 10, "bold"))
            label.pack(side=tk.LEFT, padx=5, pady=5)

            toggle_var = tk.BooleanVar(value=False)
            self.toggle_vars.append(toggle_var)

            def make_toggle(index):
                def toggle():
                    if self.toggle_vars[index].get():
                        self.preview_widgets[index].pack(fill=tk.X, padx=10, pady=(0, 10))
                    else:
                        self.preview_widgets[index].pack_forget()
                return toggle

            toggle_btn = ttk.Checkbutton(header, text="Show Output", variable=toggle_var, command=make_toggle(idx))
            toggle_btn.pack(side=tk.RIGHT, padx=5)

            preview = tk.Text(frame, height=5, bg="#111", fg="#0f0", insertbackground="white")
            preview.insert(tk.END, f"[PREVIEW] {typ} -- {val}")
            preview.configure(state="disabled")
            self.preview_widgets.append(preview)

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
