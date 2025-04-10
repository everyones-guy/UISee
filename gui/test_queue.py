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

        def refresh_list():
            for child in step_frame.winfo_children():
                child.destroy()

            preview_widgets.clear()
            toggle_vars.clear()

            def make_select(index):
                def select(event):
                    selected_step_index.set(index)
                return select

            def make_context_menu(index):
                def show_context(event):
                    selected_step_index.set(index)
                    menu = tk.Menu(win, tearoff=0)
                    menu.add_command(label="Edit", command=edit_selected)
                    menu.add_command(label="Remove", command=remove_selected)
                    menu.add_command(label="Move Up", command=move_up)
                    menu.add_command(label="Move Down", command=move_down)
                    menu.post(event.x_root, event.y_root)
                return show_context

            for idx, step in enumerate(steps):
                frame = tk.Frame(step_frame, borderwidth=1, relief="solid", padx=5, pady=3)
                frame.pack(fill=tk.X, padx=5, pady=2)

                frame.bind("<Button-1>", make_select(idx))
                frame.bind("<Button-3>", make_context_menu(idx))  # right-click support

                label = step.get("command", step.get("value", ""))
                header_var = tk.StringVar(value=f"{idx + 1}. {step['type'].upper()}: {label}")

                header = tk.Label(frame, textvariable=header_var, font=("Arial", 10, "bold"))
                header.pack(anchor="w")

                command_var = tk.StringVar(value=label)
                cmd_entry = tk.Entry(frame, textvariable=command_var)
                cmd_entry.pack(fill=tk.X, padx=5, pady=(2, 5))

                def update_step(e=None, i=idx):
                    val = command_var.get().strip()
                    if "=" in val:
                        steps[i]["command"] = val
                    elif steps[i]["type"] == "wait" and val.isdigit():
                        steps[i]["value"] = int(val)
                    if i < len(outputs):
                        outputs[i] = f"[UPDATED] {val}"

                cmd_entry.bind("<FocusOut>", update_step)

                # Collapse/expand preview
                toggle_text = tk.StringVar(value="Show Preview")

                def toggle_preview(preview_widget, var):
                    if preview_widget.winfo_viewable():
                        preview_widget.pack_forget()
                        var.set("Show Preview")
                    else:
                        preview_widget.pack(fill=tk.X, padx=5, pady=(0, 5))
                        var.set("Hide Preview")

                toggle_button = ttk.Button(
                    frame,
                    textvariable=toggle_text,
                    command=lambda pw=None, v=toggle_text, p=None: toggle_preview(preview, v)
                )
                toggle_button.pack(anchor="e", padx=5, pady=(0, 5))

                preview = tk.Text(frame, height=5, bg="#111", fg="#0f0", insertbackground="white")
                preview.insert(tk.END, f"[PREVIEW] {step['type'].upper()} -- {label}")
                preview.configure(state="disabled")

                preview_widgets.append(preview)
                toggle_vars.append(toggle_text)


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
