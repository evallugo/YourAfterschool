-- Your After School Inventory System — PostgreSQL Schema

CREATE TABLE IF NOT EXISTS schools (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    address    TEXT,
    notes      TEXT,
    active     INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name     TEXT,
    role          TEXT NOT NULL DEFAULT 'packer',
    school_id     INTEGER REFERENCES schools(id),
    active        INTEGER DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS program_sessions (
    id         SERIAL PRIMARY KEY,
    school_id  INTEGER NOT NULL REFERENCES schools(id),
    name       TEXT NOT NULL,
    start_date TEXT,
    end_date   TEXT
);

CREATE TABLE IF NOT EXISTS weeks (
    id           SERIAL PRIMARY KEY,
    session_id   INTEGER NOT NULL REFERENCES program_sessions(id),
    week_number  INTEGER NOT NULL,
    meeting_date TEXT,
    is_active    INTEGER DEFAULT 1,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS categories (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS subcategories (
    id          SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    name        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id             SERIAL PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT,
    subcategory_id INTEGER REFERENCES subcategories(id),
    unit           TEXT NOT NULL DEFAULT 'pcs',
    is_reusable    INTEGER DEFAULT 0,
    quantity       INTEGER NOT NULL DEFAULT 0,
    location       TEXT,
    notes          TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS item_categories (
    item_id     INTEGER NOT NULL REFERENCES items(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    PRIMARY KEY (item_id, category_id)
);

CREATE TABLE IF NOT EXISTS lessons (
    id            SERIAL PRIMARY KEY,
    class_type    TEXT,
    class_name    TEXT NOT NULL,
    lesson_name   TEXT NOT NULL,
    lesson_number INTEGER,
    school_id     INTEGER REFERENCES schools(id),
    teacher_name  TEXT,
    session_id    INTEGER REFERENCES program_sessions(id),
    week_id       INTEGER REFERENCES weeks(id),
    max_students  INTEGER DEFAULT 15,
    pack_to       INTEGER DEFAULT 15,
    status        TEXT DEFAULT 'unpacked',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lesson_items (
    id                SERIAL PRIMARY KEY,
    lesson_id         INTEGER NOT NULL REFERENCES lessons(id),
    item_id           INTEGER REFERENCES items(id),
    item_description  TEXT NOT NULL,
    essentials_type   TEXT,
    per_section_total TEXT,
    item_size         TEXT,
    unit              TEXT,
    return_required   INTEGER DEFAULT 0,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS packing_log (
    id             SERIAL PRIMARY KEY,
    lesson_id      INTEGER NOT NULL REFERENCES lessons(id),
    lesson_item_id INTEGER NOT NULL REFERENCES lesson_items(id),
    is_packed      INTEGER DEFAULT 0,
    packed_by      INTEGER REFERENCES users(id),
    packed_at      TIMESTAMP,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS incoming_orders (
    id               SERIAL PRIMARY KEY,
    item_id          INTEGER REFERENCES items(id),
    item_description TEXT NOT NULL,
    quantity         INTEGER NOT NULL,
    unit             TEXT DEFAULT 'pcs',
    source           TEXT,
    expected_arrival TEXT,
    actual_arrival   TEXT,
    status           TEXT DEFAULT 'pending',
    notes            TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS returns (
    id                   SERIAL PRIMARY KEY,
    lesson_id            INTEGER NOT NULL REFERENCES lessons(id),
    lesson_item_id       INTEGER NOT NULL REFERENCES lesson_items(id),
    school_id            INTEGER REFERENCES schools(id),
    expected_quantity    INTEGER,
    received_quantity    INTEGER,
    logged_by            INTEGER REFERENCES users(id),
    logged_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    received_by          INTEGER REFERENCES users(id),
    received_at          TIMESTAMP,
    readded_to_inventory INTEGER DEFAULT 0,
    written_off          INTEGER DEFAULT 0,
    notes                TEXT
);

INSERT INTO categories (name)
    SELECT v FROM (VALUES ('Art'),('Sports'),('Crafts'),('Science'),('Cooking'),('Building'),('General')) AS t(v)
    WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = v);
