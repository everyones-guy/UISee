-- Pages table
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE
);

-- Widgets table
CREATE TABLE IF NOT EXISTS widgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_name TEXT,
    widget_type TEXT,
    widget_name TEXT,
    widget_index TEXT,
    widget_config TEXT,
    widget_config_id INTEGER,
    widget_id INTEGER
);

-- Widget tag/value metadata
CREATE TABLE IF NOT EXISTS widget_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    widget_id INTEGER,
    tag TEXT,
    value TEXT,
    FOREIGN KEY (widget_id) REFERENCES widgets(id)
);

-- Page-level tags
CREATE TABLE IF NOT EXISTS page_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_name TEXT,
    tag TEXT,
    value TEXT
);

-- JS functions found per page
CREATE TABLE IF NOT EXISTS js_functions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_name TEXT,
    function_name TEXT,
    parameters TEXT
);

-- Navigation function mapping
CREATE TABLE IF NOT EXISTS navigations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    function TEXT,
    target_page TEXT
);

-- Mapping between widget props and JS functions
CREATE TABLE IF NOT EXISTS widget_function_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_name TEXT,
    widget_name TEXT,
    property TEXT,
    function_name TEXT
);

-- MQTT topics per page
CREATE TABLE IF NOT EXISTS mqtt_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_name TEXT,
    topic TEXT
);
