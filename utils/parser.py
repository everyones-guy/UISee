
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

    

    def load_pages(self):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM pages ORDER BY name")
        self.available_pages = [row[0] for row in cur.fetchall()]

    def get_all_pages(self):
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT page_name FROM widgets ORDER BY page_name")
        return [row[0] for row in cur.fetchall()]
