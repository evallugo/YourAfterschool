"""
Migrate all data from yas_sqlite_backup.db → PostgreSQL.

Usage:
    DATABASE_URL=postgresql://user:pass@host/dbname python migrate_to_pg.py

Run init_db.py first to create the tables, then run this script.
"""
import os
import sqlite3
import psycopg2

SQLITE_PATH  = os.path.join(os.path.dirname(__file__), 'yas_sqlite_backup.db')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/yas')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

src = sqlite3.connect(SQLITE_PATH)
src.row_factory = sqlite3.Row

dst     = psycopg2.connect(DATABASE_URL)
dst_cur = dst.cursor()

TABLES = [
    'schools',
    'users',
    'program_sessions',
    'weeks',
    'categories',
    'subcategories',
    'items',
    'item_categories',
    'lessons',
    'lesson_items',
    'packing_log',
    'incoming_orders',
    'returns',
]


def migrate_table(table):
    rows = src.execute(f'SELECT * FROM {table}').fetchall()
    if not rows:
        print(f'  {table}: empty, skipping')
        return

    cols        = rows[0].keys()
    col_list    = ', '.join(cols)
    placeholders = ', '.join(['%s'] * len(cols))

    # Clear existing data in the target table (safe since we just ran init_db)
    dst_cur.execute(f'DELETE FROM {table}')

    for row in rows:
        dst_cur.execute(
            f'INSERT INTO {table} ({col_list}) VALUES ({placeholders})',
            list(row)
        )

    # Reset the SERIAL sequence to max(id) + 1 so future inserts don't conflict
    if 'id' in cols:
        dst_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table}")

    print(f'  {table}: {len(rows)} row(s) migrated')


print(f'Migrating from {SQLITE_PATH} → PostgreSQL...')
print('Disabling FK checks during migration...')
dst_cur.execute('SET session_replication_role = replica')

for table in TABLES:
    try:
        migrate_table(table)
    except Exception as e:
        print(f'  ERROR on {table}: {e}')
        dst.rollback()
        raise

dst_cur.execute('SET session_replication_role = DEFAULT')
dst.commit()
dst_cur.close()
dst.close()
src.close()
print('\nMigration complete.')
