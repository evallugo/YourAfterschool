-- Your After School Inventory System
-- Schema

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    full_name     TEXT,
    role          TEXT    NOT NULL DEFAULT 'packer', -- admin, packer, site_director, teacher
    school_id     INTEGER,
    active        INTEGER DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id) REFERENCES schools(id)
);

CREATE TABLE IF NOT EXISTS schools (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    address    TEXT,
    notes      TEXT,
    active     INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS program_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id  INTEGER NOT NULL,
    name       TEXT NOT NULL,
    start_date TEXT,
    end_date   TEXT,
    FOREIGN KEY (school_id) REFERENCES schools(id)
);

CREATE TABLE IF NOT EXISTS weeks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL,
    week_number  INTEGER NOT NULL,
    meeting_date TEXT,
    is_active    INTEGER DEFAULT 1,
    notes        TEXT,
    FOREIGN KEY (session_id) REFERENCES program_sessions(id)
);

CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS subcategories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    name        TEXT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    description    TEXT,
    subcategory_id INTEGER,
    unit           TEXT    NOT NULL DEFAULT 'pcs',
    is_reusable    INTEGER DEFAULT 0,
    quantity       INTEGER NOT NULL DEFAULT 0,
    location       TEXT,
    notes          TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subcategory_id) REFERENCES subcategories(id)
);

CREATE TABLE IF NOT EXISTS item_categories (
    item_id     INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (item_id, category_id),
    FOREIGN KEY (item_id)     REFERENCES items(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS lessons (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    class_type   TEXT,
    class_name   TEXT NOT NULL,
    lesson_name  TEXT NOT NULL,
    lesson_number INTEGER,
    school_id    INTEGER,
    teacher_name TEXT,
    session_id   INTEGER,
    week_id      INTEGER,
    max_students INTEGER DEFAULT 15,
    pack_to      INTEGER DEFAULT 15,
    status       TEXT DEFAULT 'unpacked', -- unpacked, in_progress, packed, delivered
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (school_id)  REFERENCES schools(id),
    FOREIGN KEY (session_id) REFERENCES program_sessions(id),
    FOREIGN KEY (week_id)    REFERENCES weeks(id)
);

CREATE TABLE IF NOT EXISTS lesson_items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id         INTEGER NOT NULL,
    item_id           INTEGER,
    item_description  TEXT NOT NULL,
    essentials_type   TEXT,
    per_section_total TEXT,
    item_size         TEXT,
    unit              TEXT,
    return_required   INTEGER DEFAULT 0,
    notes             TEXT,
    FOREIGN KEY (lesson_id) REFERENCES lessons(id),
    FOREIGN KEY (item_id)   REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS packing_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id      INTEGER NOT NULL,
    lesson_item_id INTEGER NOT NULL,
    is_packed      INTEGER DEFAULT 0,
    packed_by      INTEGER,
    packed_at      TIMESTAMP,
    notes          TEXT,
    FOREIGN KEY (lesson_id)      REFERENCES lessons(id),
    FOREIGN KEY (lesson_item_id) REFERENCES lesson_items(id),
    FOREIGN KEY (packed_by)      REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS incoming_orders (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id          INTEGER,
    item_description TEXT NOT NULL,
    quantity         INTEGER NOT NULL,
    unit             TEXT DEFAULT 'pcs',
    source           TEXT,
    expected_arrival TEXT,
    actual_arrival   TEXT,
    status           TEXT DEFAULT 'pending', -- pending, arrived, shelved
    notes            TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS returns (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id            INTEGER NOT NULL,
    lesson_item_id       INTEGER NOT NULL,
    school_id            INTEGER,
    expected_quantity    INTEGER,
    received_quantity    INTEGER,
    logged_by            INTEGER,
    logged_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    received_by          INTEGER,
    received_at          TIMESTAMP,
    readded_to_inventory INTEGER DEFAULT 0,
    written_off          INTEGER DEFAULT 0,
    notes                TEXT,
    FOREIGN KEY (lesson_id)      REFERENCES lessons(id),
    FOREIGN KEY (lesson_item_id) REFERENCES lesson_items(id),
    FOREIGN KEY (school_id)      REFERENCES schools(id)
);

-- Default categories
INSERT OR IGNORE INTO categories (name) VALUES
    ('Art'), ('Sports'), ('Crafts'), ('Science'), ('Cooking'), ('Building'), ('General');
