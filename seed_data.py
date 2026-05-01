"""Populate the database with realistic sample data."""
from __future__ import annotations
import sqlite3, os
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash

DATABASE = os.path.join(os.path.dirname(__file__), 'yas.db')

def seed():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    # ── Users ──────────────────────────────────────────────────────────────
    users = [
        ('jayne',    'jayne123',    'Jayne Mitchell',      'admin',         None),
        ('hayley',   'hayley123',   'Hayley Brooks',       'admin',         None),
        ('marcus',   'marcus123',   'Marcus Rivera',       'packer',        None),
        ('priya',    'priya123',    'Priya Okonkwo',       'packer',        None),
        ('director1','director123', 'Sandra Kim',          'site_director', None),
        ('director2','director123', 'Tom Walsh',           'site_director', None),
    ]
    for username, pw, name, role, school_id in users:
        existing = db.execute('SELECT id FROM users WHERE username=?', [username]).fetchone()
        if not existing:
            db.execute(
                'INSERT INTO users (username, password_hash, full_name, role, school_id) VALUES (?,?,?,?,?)',
                [username, generate_password_hash(pw), name, role, school_id]
            )

    # ── Schools ─────────────────────────────────────────────────────────────
    schools_data = [
        ('Milton Elementary',  '142 Oak Street, Springfield',
         'Teacher prefers extra tablecloths for messy projects. Director: Sandra Kim.'),
        ('Osborn Academy',     '800 West Ave, Riverdale',
         'Large gym space available. Lessons often moved to gym on Fridays.'),
        ('Roosevelt Middle',   '55 Elm Drive, Maplewood',
         'No peanut products allowed anywhere in building.'),
        ('Lincoln Elementary', '301 Pine Road, Lakeside',    None),
    ]
    school_ids = {}
    for name, address, notes in schools_data:
        existing = db.execute('SELECT id FROM schools WHERE name=?', [name]).fetchone()
        if existing:
            school_ids[name] = existing['id']
        else:
            cur = db.execute('INSERT INTO schools (name, address, notes) VALUES (?,?,?)',
                             [name, address, notes])
            school_ids[name] = cur.lastrowid

    # ── Categories (schema seeds these, just grab ids) ──────────────────────
    cat_ids = {r['name']: r['id'] for r in db.execute('SELECT id, name FROM categories').fetchall()}

    # ── Subcategories ────────────────────────────────────────────────────────
    subcats = [
        ('Art',     'Acrylic Paint'),
        ('Art',     'Watercolor'),
        ('Cooking', '2oz Dixie Cups'),
        ('Cooking', '8oz Clear Plastic Cups'),
        ('Science', 'Safety Goggles'),
        ('Crafts',  'Glue Sticks'),
        ('Crafts',  'Foam Sheets'),
    ]
    subcat_ids = {}
    for cat_name, sub_name in subcats:
        existing = db.execute(
            'SELECT id FROM subcategories WHERE name=? AND category_id=?',
            [sub_name, cat_ids[cat_name]]
        ).fetchone()
        if existing:
            subcat_ids[sub_name] = existing['id']
        else:
            cur = db.execute('INSERT INTO subcategories (category_id, name) VALUES (?,?)',
                             [cat_ids[cat_name], sub_name])
            subcat_ids[sub_name] = cur.lastrowid

    # ── Inventory items ──────────────────────────────────────────────────────
    items_data = [
        # (name, description, unit, is_reusable, quantity, location, [category_names])
        ('Popsicle Sticks',         '4-inch natural wood',          'pcs',    0, 850,  'Rack A, Bin 1',  ['Crafts', 'Art']),
        ('Clear Plastic Cups',      '4-8 oz clear',                 'pcs',    0, 220,  'Rack A, Bin 4',  ['Cooking', 'Science']),
        ('Paper Plates',            '9-inch white',                 'pcs',    0, 180,  'Rack B, Shelf 2',['Cooking', 'General']),
        ('Glue Sticks',             '0.21oz school glue sticks',    'pcs',    0, 95,   'Rack A, Bin 2',  ['Crafts', 'Art']),
        ('Scissors',                'Blunt tip safety scissors',    'pcs',    1, 42,   'Rack C, Shelf 1',['General', 'Art', 'Crafts']),
        ('Crayons',                 '16-count box',                 'boxes',  0, 4,    'Rack B, Shelf 3',['Art']),
        ('Markers',                 'Washable 10-count',            'sets',   0, 2,    'Rack B, Shelf 3',['Art']),
        ('White Construction Paper','9x12 sheets',                  'sheets', 0, 310,  'Rack D, Shelf 1',['Art', 'Crafts']),
        ('Measuring Cups',          'Set of 5 stainless steel',     'sets',   1, 18,   'Rack C, Shelf 2',['Cooking', 'Science']),
        ('Plastic Spoons',          'Disposable',                   'pcs',    0, 0,    'Rack A, Bin 5',  ['Cooking']),
        ('Paper Towel Rolls',       '2-ply standard roll',          'rolls',  0, 24,   'Rack D, Shelf 3',['General']),
        ('Plastic Table Cover',     'Disposable 54x108in',          'pcs',    0, 30,   'Rack B, Shelf 1',['General']),
        ('Tape',                    'Scotch transparent tape',      'rolls',  0, 15,   'Rack A, Bin 3',  ['Crafts', 'General']),
        ('Pencils',                 '#2 standard pencils',          'pcs',    0, 200,  'Rack A, Bin 6',  ['General']),
        ('Food Coloring',           'Liquid, 4-color set',          'sets',   0, 12,   'Rack C, Shelf 3',['Cooking', 'Science']),
        ('Baking Soda',             '1 lb box',                     'boxes',  0, 8,    'Rack C, Shelf 3',['Science', 'Cooking']),
        ('Vinegar',                 'White distilled 32oz',         'bottles',0, 6,    'Rack C, Shelf 3',['Science', 'Cooking']),
        ('Clay Tools Set',          '5-piece plastic sculpting set','sets',   1, 25,   'Rack C, Shelf 4',['Art', 'Crafts']),
        ('Air Dry Clay',            'White 2lb bag',                'bags',   0, 14,   'Rack B, Shelf 4',['Art', 'Crafts']),
        ('Yarn',                    'Assorted colors, 200yd skeins','skeins', 0, 22,   'Rack D, Shelf 2',['Crafts']),
        ('Hole Punch',              'Single hole punch',            'pcs',    1, 10,   'Rack C, Shelf 1',['Crafts', 'General']),
        ('Cardboard Rolls',         'Paper towel/TP cores',         'pcs',    0, 60,   'Rack D, Shelf 4',['Building', 'Crafts']),
        ('Craft Tubes',             '2-inch cardboard tubes',       'pcs',    0, 45,   'Rack D, Shelf 4',['Building', 'Crafts']),
        ('Tissue Paper',            'Assorted colors 20x26in',      'sheets', 0, 120,  'Rack D, Shelf 1',['Art', 'Crafts']),
        ('Plastic Bowls',           '16oz reusable mixing bowls',   'pcs',    1, 30,   'Rack C, Shelf 2',['Cooking', 'Science']),
    ]
    item_ids = {}
    for row in items_data:
        name, desc, unit, reusable, qty, location, categories = row
        existing = db.execute('SELECT id FROM items WHERE name=?', [name]).fetchone()
        if existing:
            item_ids[name] = existing['id']
        else:
            cur = db.execute(
                'INSERT INTO items (name, description, unit, is_reusable, quantity, location) VALUES (?,?,?,?,?,?)',
                [name, desc, unit, reusable, qty, location]
            )
            item_ids[name] = cur.lastrowid
            for cat_name in categories:
                if cat_name in cat_ids:
                    db.execute('INSERT OR IGNORE INTO item_categories (item_id, category_id) VALUES (?,?)',
                               [item_ids[name], cat_ids[cat_name]])

    # ── Lessons ──────────────────────────────────────────────────────────────
    # Each lesson: (class_type, class_name, lesson_name, lesson_number, school_name, teacher, status, pack_to)
    lessons_data = [
        ('LM', 'Culinary Chemistry', 'Celery Stalks & Food Coloring', 1, 'Milton Elementary',  'Ms. Rivera',   'packed',      15),
        ('LM', 'Culinary Chemistry', 'Frozen Smoothie Bowls',         2, 'Milton Elementary',  'Ms. Rivera',   'in_progress', 15),
        ('LM', 'Culinary Chemistry', 'Pineapple Salsa',               3, 'Milton Elementary',  'Ms. Rivera',   'unpacked',    15),
        ('LM', 'Culinary Chemistry', 'Celery Stalks & Food Coloring', 1, 'Osborn Academy',     'Mr. Chen',     'packed',      12),
        ('LM', 'Culinary Chemistry', 'Frozen Smoothie Bowls',         2, 'Osborn Academy',     'Mr. Chen',     'unpacked',    12),
        ('LM', 'Clay Studio',        'Breakfast for Champions',       1, 'Milton Elementary',  'Ms. Park',     'packed',      15),
        ('LM', 'Clay Studio',        'Clay Cars',                     2, 'Milton Elementary',  'Ms. Park',     'in_progress', 15),
        ('LM', 'Clay Studio',        'Colorful Puzzles',              3, 'Milton Elementary',  'Ms. Park',     'unpacked',    15),
        ('LM', 'Clay Studio',        'Breakfast for Champions',       1, 'Roosevelt Middle',   'Mr. Davis',    'unpacked',    12),
        ('LM', 'Science Explorers',  'Baking Soda Volcanoes',         1, 'Osborn Academy',     'Ms. Johnson',  'packed',      15),
        ('LM', 'Science Explorers',  'Rainbow Density Tower',         2, 'Osborn Academy',     'Ms. Johnson',  'unpacked',    15),
        ('LM', 'Science Explorers',  'Baking Soda Volcanoes',         1, 'Lincoln Elementary', 'Mr. Thompson', 'in_progress', 10),
        ('M',  'Blueprints & Bridges','Build Session',                None,'Roosevelt Middle',  'Ms. Garcia',   'unpacked',    15),
        ('LM', 'Art Adventures',     'Watercolor Landscapes',         1, 'Lincoln Elementary', 'Mr. Thompson', 'packed',      10),
        ('LM', 'Art Adventures',     'Clay Animal Faces',             2, 'Lincoln Elementary', 'Mr. Thompson', 'unpacked',    10),
    ]
    lesson_ids = {}
    for class_type, class_name, lesson_name, lesson_num, school_name, teacher, status, pack_to in lessons_data:
        school_id = school_ids.get(school_name)
        key = (class_name, lesson_name, lesson_num, school_name)
        existing = db.execute(
            'SELECT id FROM lessons WHERE class_name=? AND lesson_name=? AND lesson_number IS ? AND school_id=?',
            [class_name, lesson_name, lesson_num, school_id]
        ).fetchone()
        if existing:
            lesson_ids[key] = existing['id']
        else:
            cur = db.execute(
                '''INSERT INTO lessons
                   (class_type, class_name, lesson_name, lesson_number, school_id, teacher_name, status, pack_to)
                   VALUES (?,?,?,?,?,?,?,?)''',
                [class_type, class_name, lesson_name, lesson_num, school_id, teacher, status, pack_to]
            )
            lesson_ids[key] = cur.lastrowid

    # ── Lesson Items ──────────────────────────────────────────────────────────
    # (lesson_key, item_description, essentials_type, per_section_total, item_size, return_required)
    lesson_items_data = {
        ('Culinary Chemistry', 'Celery Stalks & Food Coloring', 1, 'Milton Elementary'): [
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Clear Plastic Cups',      'essentials',    '4',   '4-8 oz', 0),
            ('Food Coloring',           'instructor',    '1',   '4-color', 0),
            ('Paper Towel Rolls',       'essentials',    '2',   None,     0),
            ('Celery stalks',           None,            '15',  None,     0),
            ('White Construction Paper',None,            '15',  '9x12',   0),
            ('Plastic Bowls',           'essentials',    '4',   '16oz',   1),
            ('Measuring Cups',          'instructor kit','1',   'set of 5',1),
        ],
        ('Culinary Chemistry', 'Frozen Smoothie Bowls', 2, 'Milton Elementary'): [
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Clear Plastic Cups',      'essentials',    '15',  '8oz',    0),
            ('Plastic Spoons',          None,            '15',  None,     0),
            ('Plastic Bowls',           'essentials',    '4',   '16oz',   1),
            ('Measuring Cups',          'instructor kit','1',   'set of 5',1),
            ('Paper Towel Rolls',       'essentials',    '2',   None,     0),
            ('Frozen banana',           None,            '15',  None,     0),
            ('Pineapple juice',         None,            '1',   '1 cup',  0),
        ],
        ('Culinary Chemistry', 'Pineapple Salsa', 3, 'Milton Elementary'): [
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Clear Plastic Cups',      'essentials',    '15',  '4-8 oz', 0),
            ('Paper Plates',            'essentials',    '15',  '9 inch', 0),
            ('Plastic Spoons',          None,            '15',  None,     0),
            ('Plastic Bowls',           'essentials',    '4',   '16oz',   1),
            ('Paper Towel Rolls',       'essentials',    '2',   None,     0),
        ],
        ('Culinary Chemistry', 'Celery Stalks & Food Coloring', 1, 'Osborn Academy'): [
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Clear Plastic Cups',      'essentials',    '4',   '4-8 oz', 0),
            ('Food Coloring',           'instructor',    '1',   '4-color', 0),
            ('Paper Towel Rolls',       'essentials',    '2',   None,     0),
            ('Celery stalks',           None,            '12',  None,     0),
            ('Plastic Bowls',           'essentials',    '4',   '16oz',   1),
            ('Measuring Cups',          'instructor kit','1',   'set of 5',1),
        ],
        ('Culinary Chemistry', 'Frozen Smoothie Bowls', 2, 'Osborn Academy'): [
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Clear Plastic Cups',      'essentials',    '12',  '8oz',    0),
            ('Plastic Spoons',          None,            '12',  None,     0),
            ('Paper Towel Rolls',       'essentials',    '2',   None,     0),
            ('Frozen banana',           None,            '12',  None,     0),
        ],
        ('Clay Studio', 'Breakfast for Champions', 1, 'Milton Elementary'): [
            ('Clay Tools Set',          'instructor kit','1',   'set',    1),
            ('Air Dry Clay',            None,            '30',  'Individual Bag', 0),
            ('Paper Plates',            'essentials',    '15',  'Standard',0),
            ('Parchment Paper',         None,            '1',   '1 sheet', 0),
            ('Rolling Pins',            None,            '15',  'Standard',1),
            ('Scissors',                None,            '15',  'Standard',1),
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
        ],
        ('Clay Studio', 'Clay Cars', 2, 'Milton Elementary'): [
            ('Clay Tools Set',          'instructor kit','1',   'set',    1),
            ('Air Dry Clay',            None,            '15',  'Individual Bag',0),
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Paper Plates',            'essentials',    '15',  'Standard',0),
            ('Toothpicks',              None,            '30',  None,     0),
        ],
        ('Clay Studio', 'Colorful Puzzles', 3, 'Milton Elementary'): [
            ('Clay Tools Set',          'instructor kit','1',   'set',    1),
            ('Air Dry Clay',            None,            '15',  'Individual Bag',0),
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Markers',                 None,            '1',   'set',    0),
            ('Paper Plates',            'essentials',    '15',  'Standard',0),
        ],
        ('Clay Studio', 'Breakfast for Champions', 1, 'Roosevelt Middle'): [
            ('Clay Tools Set',          'instructor kit','1',   'set',    1),
            ('Air Dry Clay',            None,            '24',  'Individual Bag',0),
            ('Paper Plates',            'essentials',    '12',  'Standard',0),
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Scissors',                None,            '12',  'Standard',1),
        ],
        ('Science Explorers', 'Baking Soda Volcanoes', 1, 'Osborn Academy'): [
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Clear Plastic Cups',      'essentials',    '15',  '4-8 oz', 0),
            ('Baking Soda',             None,            '1',   '1 lb',   0),
            ('Vinegar',                 None,            '1',   '32oz',   0),
            ('Food Coloring',           None,            '1',   '4-color', 0),
            ('Paper Towel Rolls',       'essentials',    '2',   None,     0),
            ('Measuring Cups',          'instructor kit','1',   'set of 5',1),
            ('Plastic Bowls',           'essentials',    '4',   '16oz',   1),
        ],
        ('Science Explorers', 'Rainbow Density Tower', 2, 'Osborn Academy'): [
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Clear Plastic Cups',      'essentials',    '15',  '8oz',    0),
            ('Measuring Cups',          'instructor kit','1',   'set of 5',1),
            ('Food Coloring',           None,            '1',   '4-color', 0),
            ('Corn syrup',              None,            '1',   '1 cup',  0),
            ('Dish soap',               None,            '1',   None,     0),
            ('Paper Towel Rolls',       'essentials',    '2',   None,     0),
        ],
        ('Science Explorers', 'Baking Soda Volcanoes', 1, 'Lincoln Elementary'): [
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Clear Plastic Cups',      'essentials',    '10',  '4-8 oz', 0),
            ('Baking Soda',             None,            '1',   '1 lb',   0),
            ('Vinegar',                 None,            '1',   '32oz',   0),
            ('Food Coloring',           None,            '1',   '4-color', 0),
            ('Paper Towel Rolls',       'essentials',    '1',   None,     0),
            ('Measuring Cups',          'instructor kit','1',   'set of 5',1),
        ],
        ('Blueprints & Bridges', 'Build Session', None, 'Roosevelt Middle'): [
            ('Cardboard Rolls',         None,            '30',  None,     0),
            ('Craft Tubes',             None,            '15',  '2 inch', 0),
            ('Tape',                    None,            '3',   'rolls',  0),
            ('Glue Sticks',             'essentials',    '15',  None,     0),
            ('Plastic Table Cover',     'essentials',    '2',   None,     0),
            ('Scissors',                'essentials',    '12',  None,     1),
        ],
        ('Art Adventures', 'Watercolor Landscapes', 1, 'Lincoln Elementary'): [
            ('White Construction Paper','essentials',    '10',  '9x12',   0),
            ('Tissue Paper',            None,            '20',  '20x26',  0),
            ('Plastic Bowls',           'essentials',    '3',   '16oz',   1),
            ('Paper Towel Rolls',       'essentials',    '1',   None,     0),
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Food Coloring',           'instructor',    '1',   '4-color', 0),
        ],
        ('Art Adventures', 'Clay Animal Faces', 2, 'Lincoln Elementary'): [
            ('Clay Tools Set',          'instructor kit','1',   'set',    1),
            ('Air Dry Clay',            None,            '10',  'Individual Bag',0),
            ('Plastic Table Cover',     'essentials',    '1',   None,     0),
            ('Toothpicks',              None,            '20',  None,     0),
            ('Paper Plates',            'essentials',    '10',  'Standard',0),
        ],
    }

    lesson_item_ids = {}  # (lesson_id, item_desc) -> lesson_item_id
    for key, items in lesson_items_data.items():
        lesson_id = lesson_ids.get(key)
        if not lesson_id:
            continue
        for item_desc, essentials_type, per_section, item_size, return_req in items:
            existing = db.execute(
                'SELECT id FROM lesson_items WHERE lesson_id=? AND item_description=?',
                [lesson_id, item_desc]
            ).fetchone()
            if existing:
                lesson_item_ids[(lesson_id, item_desc)] = existing['id']
            else:
                # Try to link to inventory item
                inv_item = db.execute('SELECT id FROM items WHERE name=?', [item_desc]).fetchone()
                cur = db.execute(
                    '''INSERT INTO lesson_items
                       (lesson_id, item_id, item_description, essentials_type, per_section_total, item_size, return_required)
                       VALUES (?,?,?,?,?,?,?)''',
                    [lesson_id, inv_item['id'] if inv_item else None,
                     item_desc, essentials_type, per_section, item_size, return_req]
                )
                lesson_item_ids[(lesson_id, item_desc)] = cur.lastrowid

    # ── Packing Log (mark items packed for 'packed' and 'in_progress' lessons) ──
    packer_id = db.execute("SELECT id FROM users WHERE username='marcus'").fetchone()['id']
    packed_at  = (datetime.now() - timedelta(days=2)).isoformat()

    for key, items in lesson_items_data.items():
        lesson_id = lesson_ids.get(key)
        if not lesson_id:
            continue
        lesson = db.execute('SELECT status FROM lessons WHERE id=?', [lesson_id]).fetchone()
        if not lesson:
            continue

        for idx, (item_desc, *_) in enumerate(items):
            li_id = lesson_item_ids.get((lesson_id, item_desc))
            if not li_id:
                continue
            existing = db.execute('SELECT id FROM packing_log WHERE lesson_item_id=?', [li_id]).fetchone()
            if existing:
                continue
            if lesson['status'] == 'packed':
                is_packed = 1
            elif lesson['status'] == 'in_progress':
                # Pack roughly half the items
                is_packed = 1 if idx % 2 == 0 else 0
            else:
                is_packed = 0

            if is_packed or lesson['status'] == 'in_progress':
                db.execute(
                    '''INSERT INTO packing_log
                       (lesson_id, lesson_item_id, is_packed, packed_by, packed_at)
                       VALUES (?,?,?,?,?)''',
                    [lesson_id, li_id, is_packed,
                     packer_id if is_packed else None,
                     packed_at if is_packed else None]
                )

    # ── Incoming Orders ───────────────────────────────────────────────────────
    today = date.today()
    orders_data = [
        # (item_name, quantity, unit, source, expected_arrival, actual_arrival, status, notes)
        ('Crayons',        24, 'boxes', 'Amazon',       str(today + timedelta(days=2)), None,              'pending',  'Order #AMZ-88421'),
        ('Markers',        12, 'sets',  'Amazon',       str(today + timedelta(days=2)), None,              'pending',  'Order #AMZ-88421'),
        ('Plastic Spoons', 500,'pcs',   'Bulk Order',   str(today - timedelta(days=1)), str(today),        'arrived',  'Arrived this morning, needs to be shelved'),
        ('Paper Plates',   200,'pcs',   'Inventory',    str(today - timedelta(days=3)), str(today - timedelta(days=3)),'shelved', None),
        ('Glue Sticks',    50, 'pcs',   'Dollar Store', str(today + timedelta(days=4)), None,              'pending',  'Backup order — primary shipment was short'),
        ('Baking Soda',    12, 'boxes', 'Amazon',       str(today - timedelta(days=1)), str(today),        'arrived',  None),
        ('Tissue Paper',   200,'sheets','Bulk Order',   str(today + timedelta(days=7)), None,              'pending',  'Spring session restock'),
    ]
    for item_name, qty, unit, source, expected, actual, status, notes in orders_data:
        inv = db.execute('SELECT id FROM items WHERE name=?', [item_name]).fetchone()
        existing = db.execute(
            'SELECT id FROM incoming_orders WHERE item_description=? AND status=?',
            [item_name, status]
        ).fetchone()
        if not existing:
            db.execute(
                '''INSERT INTO incoming_orders
                   (item_id, item_description, quantity, unit, source, expected_arrival, actual_arrival, status, notes)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                [inv['id'] if inv else None, item_name, qty, unit,
                 source, expected, actual, status, notes]
            )

    # ── Returns ───────────────────────────────────────────────────────────────
    # Log returns for items from packed lessons
    milton_id   = school_ids['Milton Elementary']
    osborn_id   = school_ids['Osborn Academy']
    lincoln_id  = school_ids['Lincoln Elementary']
    director_id = db.execute("SELECT id FROM users WHERE username='director1'").fetchone()['id']
    packer_id2  = db.execute("SELECT id FROM users WHERE username='priya'").fetchone()['id']

    returns_data = [
        # (lesson_key, item_desc, school_id, expected_qty, received_qty, received)
        (('Culinary Chemistry','Celery Stalks & Food Coloring',1,'Milton Elementary'),
         'Measuring Cups',       milton_id,  1, 1,    True),
        (('Culinary Chemistry','Celery Stalks & Food Coloring',1,'Milton Elementary'),
         'Plastic Bowls',        milton_id,  4, 4,    True),
        (('Clay Studio','Breakfast for Champions',1,'Milton Elementary'),
         'Clay Tools Set',       milton_id,  1, None, False),
        (('Clay Studio','Breakfast for Champions',1,'Milton Elementary'),
         'Rolling Pins',         milton_id,  15, None,False),
        (('Science Explorers','Baking Soda Volcanoes',1,'Osborn Academy'),
         'Measuring Cups',       osborn_id,  1, None, False),
        (('Art Adventures','Watercolor Landscapes',1,'Lincoln Elementary'),
         'Plastic Bowls',        lincoln_id, 3, None, False),
    ]
    logged_ago = (datetime.now() - timedelta(days=1)).isoformat()
    received_ago = (datetime.now() - timedelta(hours=3)).isoformat()

    for lesson_key, item_desc, school_id, exp_qty, rec_qty, received in returns_data:
        lesson_id = lesson_ids.get(lesson_key)
        if not lesson_id:
            continue
        li = db.execute(
            'SELECT id FROM lesson_items WHERE lesson_id=? AND item_description=?',
            [lesson_id, item_desc]
        ).fetchone()
        if not li:
            continue
        existing = db.execute(
            'SELECT id FROM returns WHERE lesson_id=? AND lesson_item_id=?',
            [lesson_id, li['id']]
        ).fetchone()
        if existing:
            continue

        if received:
            db.execute(
                '''INSERT INTO returns
                   (lesson_id, lesson_item_id, school_id, expected_quantity, received_quantity,
                    logged_by, logged_at, received_by, received_at, readded_to_inventory)
                   VALUES (?,?,?,?,?,?,?,?,?,1)''',
                [lesson_id, li['id'], school_id, exp_qty, rec_qty,
                 director_id, logged_ago, packer_id2, received_ago]
            )
        else:
            db.execute(
                '''INSERT INTO returns
                   (lesson_id, lesson_item_id, school_id, expected_quantity,
                    logged_by, logged_at)
                   VALUES (?,?,?,?,?,?)''',
                [lesson_id, li['id'], school_id, exp_qty, director_id, logged_ago]
            )

    db.commit()
    db.close()
    print("Sample data loaded successfully.")
    print("\nUser accounts created:")
    print("  admin      / admin123    (Administrator)")
    print("  jayne      / jayne123    (Admin)")
    print("  hayley     / hayley123   (Admin)")
    print("  marcus     / marcus123   (Packer)")
    print("  priya      / priya123    (Packer)")
    print("  director1  / director123 (Site Director)")
    print("  director2  / director123 (Site Director)")

if __name__ == '__main__':
    seed()
