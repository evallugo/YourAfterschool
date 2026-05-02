"""Your After School — Inventory Management System"""
from __future__ import annotations

import re
import os
import base64
from io import BytesIO
from datetime import datetime
from functools import wraps

import psycopg2
import psycopg2.extras
import pandas as pd
import qrcode
from flask import (Flask, render_template, redirect, url_for, request,
                   flash, jsonify, send_file, session as fsession)
from flask_login import (LoginManager, UserMixin, login_user,
                         login_required, logout_user, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

# ──────────────────────────────────────────────────────────
# App setup
# ──────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'yas-dev-secret-change-in-prod')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/yas')
# Railway provides postgres:// but psycopg2 requires postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to continue.'
login_manager.login_message_category = 'warning'


class _DbConn:
    """Wraps psycopg2 to behave like sqlite3 for our call patterns."""
    def __init__(self, conn):
        self._conn = conn
        self._cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    def execute(self, sql, params=None):
        self._cur.execute(sql, params or ())
        return self._cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._cur.close()
        self._conn.close()


def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return _DbConn(conn)


# ──────────────────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, row):
        self.id        = row['id']
        self.username  = row['username']
        self.role      = row['role']
        self.school_id = row['school_id']
        self.full_name = row['full_name']

    @property
    def display_role(self):
        return {'admin': 'Admin', 'packer': 'Packer',
                'site_director': 'Site Director',
                'teacher': 'Teacher'}.get(self.role, self.role)


@login_manager.user_loader
def load_user(uid):
    db = get_db()
    row = db.execute('SELECT * FROM users WHERE id = %s', [uid]).fetchone()
    db.close()
    return User(row) if row else None


def role_required(*roles):
    def dec(f):
        @wraps(f)
        @login_required
        def wrapped(*args, **kw):
            if current_user.role == 'site_director':
                return redirect(url_for('director_portal'))
            if current_user.role not in roles:
                flash('You do not have permission to view that page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kw)
        return wrapped
    return dec


def warehouse_only(f):
    """Redirect site directors to their portal; all other authenticated users pass through."""
    @wraps(f)
    @login_required
    def wrapped(*args, **kw):
        if current_user.role == 'site_director':
            return redirect(url_for('director_portal'))
        return f(*args, **kw)
    return wrapped


# ──────────────────────────────────────────────────────────
# Excel processing — preserved from Streamlit app + extended
# ──────────────────────────────────────────────────────────
def norm_text(x) -> str:
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip().lower()


def clean_series(s: pd.Series) -> pd.Series:
    s = s.where(~pd.isna(s), "")
    s = s.astype(str).str.strip()
    return s.replace({"nan": "", "NaN": ""})


def kit_label(raw: str) -> str:
    v = norm_text(raw)
    if v == "":
        return ""
    if "instructor" in v:
        return "Instructor Kit"
    if "essential" in v:
        return "Essential Kit"
    return str(raw).strip().title()


def safe_sheet_name(name: str, used: set) -> str:
    name = re.sub(r"[:\/?*\[\]]", "-", name)
    name = re.sub(r"\s+", " ", name).strip()
    base = name[:31] if len(name) > 31 else name
    if not base:
        base = "Sheet"
    if base not in used:
        used.add(base)
        return base
    i = 2
    while True:
        suffix = f"_{i}"
        cut = 31 - len(suffix)
        candidate = (base[:cut] if cut > 0 else base) + suffix
        if candidate not in used:
            used.add(candidate)
            return candidate
        i += 1


def guess_column(df: pd.DataFrame, candidates: list):
    norm_map = {norm_text(c): c for c in df.columns}
    for cand in candidates:
        if cand in norm_map:
            return norm_map[cand]
    return None


def parse_lesson_tokens(value) -> list:
    if pd.isna(value):
        return [""]
    s = str(value).strip()
    if s == "" or s.lower() in ["nan", "none"]:
        return [""]
    if s.strip().lower() == "all":
        return ["__ALL__"]
    parts = [p.strip() for p in s.split(",")]
    tokens = [p for p in parts if p]
    return tokens if tokens else [""]


def build_output_excel(df, col_class, col_lesson, col_lesson_num, col_item,
                       col_per_section, col_size, col_notes, col_kit_src,
                       col_class_type, col_return=None,
                       include_kit_column=False, put_kit_under_lesson_num=True):
    """
    Preserved from Streamlit app. Returns (xlsx_bytes, tab_count, processed_df).
    processed_df carries _kit_raw and _return_raw for DB storage.
    """
    data = df.copy()
    data["_class_clean"]      = clean_series(data[col_class])
    data["_lesson_clean"]     = clean_series(data[col_lesson])
    data["_item_clean"]       = clean_series(data[col_item])
    lesson_num_clean          = data[col_lesson_num].where(~pd.isna(data[col_lesson_num]), "")
    data["_lessonnum_raw"]    = lesson_num_clean.astype(str).str.strip().replace({"nan": "", "NaN": ""})
    data["_per_section"]      = data[col_per_section].where(~pd.isna(data[col_per_section]), "")
    data["_size_clean"]       = clean_series(data[col_size])       if col_size       else ""
    data["_notes_clean"]      = clean_series(data[col_notes])      if col_notes      else ""
    data["_kit"]              = data[col_kit_src].apply(kit_label)  if col_kit_src    else ""
    data["_class_type_clean"] = clean_series(data[col_class_type]) if col_class_type else ""
    data["_return_raw"]       = clean_series(data[col_return])     if col_return     else ""

    base_group = ["_class_type_clean", "_class_clean", "_lesson_clean"]

    data["_lesson_tokens"] = data["_lessonnum_raw"].apply(parse_lesson_tokens)
    data = data.explode("_lesson_tokens", ignore_index=True)
    data["_lessonnum_clean"] = (data["_lesson_tokens"].astype(str)
                                .str.strip().replace({"nan": "", "NaN": ""}))

    all_mask = data["_lessonnum_clean"] == "__ALL__"
    if all_mask.any():
        lessons_by_group = (data.loc[~all_mask, base_group + ["_lessonnum_clean"]]
                            .copy()
                            .pipe(lambda d: d[d["_lessonnum_clean"] != ""])
                            .drop_duplicates())
        lesson_sets = (lessons_by_group.groupby(base_group)["_lessonnum_clean"]
                       .apply(lambda s: sorted({str(x).strip() for x in s if str(x).strip()}))
                       .to_dict())
        expanded = []
        for _, r in data.loc[all_mask].iterrows():
            key = (r["_class_type_clean"], r["_class_clean"], r["_lesson_clean"])
            for ln in lesson_sets.get(key, [""]):
                rr = r.copy()
                rr["_lessonnum_clean"] = ln
                expanded.append(rr)
        data = pd.concat([data.loc[~all_mask], pd.DataFrame(expanded)], ignore_index=True)

    def _blank(col):
        if not isinstance(col, pd.Series):
            return pd.Series([True] * len(data))
        return col == ""

    per_blank = (data["_per_section"].where(~pd.isna(data["_per_section"]), "")
                 .astype(str).str.strip().replace({"nan": "", "NaN": ""}) == "")
    fully_blank = (
        (data["_class_clean"] == "") & (data["_lesson_clean"] == "") &
        (data["_lessonnum_clean"] == "") & (data["_item_clean"] == "") &
        per_blank & _blank(data.get("_size_clean")) &
        _blank(data.get("_notes_clean")) &
        (data["_kit"] == "") & (data["_class_type_clean"] == "")
    )
    data = data.loc[~fully_blank].copy()

    def pick_rep(series):
        for v in series:
            v = "" if pd.isna(v) else str(v).strip()
            if v:
                return v
        return ""

    rep_map = (data.groupby(base_group, dropna=False)["_lessonnum_clean"]
               .apply(pick_rep).rename("_lessonnum_rep").reset_index())
    data = data.merge(rep_map, how="left", on=base_group)
    data["_lessonnum_group"] = data["_lessonnum_clean"]
    mask = data["_lessonnum_group"] == ""
    data.loc[mask, "_lessonnum_group"] = data.loc[mask, "_lessonnum_rep"]

    disp = []
    for ln, kit in zip(data["_lessonnum_clean"], data["_kit"]):
        ln  = "" if pd.isna(ln)  else str(ln).strip()
        kit = "" if pd.isna(kit) else str(kit).strip()
        if not put_kit_under_lesson_num:
            disp.append(ln)
        elif ln and kit:
            disp.append(f"{ln}\n{kit}")
        elif ln:
            disp.append(ln)
        elif kit:
            disp.append(kit)
        else:
            disp.append("")
    data["Lesson #"] = disp

    out = pd.DataFrame({
        "Packed":            "",
        "Received":          "",
        "Class Type":        data["_class_type_clean"],
        "Class Name":        data["_class_clean"],
        "Lesson Name":       data["_lesson_clean"],
        "Lesson #":          data["Lesson #"],
        "Item Description":  data["_item_clean"],
        "Per Section total": data["_per_section"],
        "Item Size":         data["_size_clean"]  if isinstance(data["_size_clean"],  pd.Series) else "",
        "Notes":             data["_notes_clean"] if isinstance(data["_notes_clean"], pd.Series) else "",
    })
    if include_kit_column:
        out["Kit"] = data["_kit"]
    out["_lessonnum_group"] = data["_lessonnum_group"]
    out["_kit_raw"]         = data["_kit"]
    out["_return_raw"]      = data["_return_raw"] if isinstance(data["_return_raw"], pd.Series) else ""

    is_unassigned = (
        (out["Class Name"] == "") & (out["Lesson Name"] == "") &
        (out["_lessonnum_group"] == "") & (out["Item Description"] == "") &
        (out["Per Section total"].astype(str).str.strip().replace({"nan": "", "NaN": ""}) == "")
    )

    export_cols = [c for c in out.columns if not c.startswith("_")]
    output = BytesIO()
    used   = set()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        normal = out[~is_unassigned].copy()
        normal = normal.sort_values(["Class Type", "Class Name", "Lesson Name",
                                     "_lessonnum_group", "Item Description"])
        for (ctype, cname, lname, lnum), g in normal.groupby(
                ["Class Type", "Class Name", "Lesson Name", "_lessonnum_group"], dropna=False):
            parts  = [str(x).strip() for x in [cname, lname] if str(x).strip()]
            lnum_s = str(lnum).strip() if not pd.isna(lnum) else ""
            if lnum_s:
                parts.append(f"Lesson {lnum_s}")
            sheet  = safe_sheet_name(" - ".join(parts) or "Unassigned", used)
            g[export_cols].to_excel(writer, index=False, sheet_name=sheet)
            ws = writer.sheets[sheet]
            ws.freeze_panes = "A2"
            header = [cell.value for cell in ws[1]]
            if "Lesson #" in header:
                ci = header.index("Lesson #") + 1
                for r in range(2, ws.max_row + 1):
                    c = ws.cell(row=r, column=ci)
                    c.alignment = c.alignment.copy(wrapText=True)
            widths = {"Packed": 10, "Received": 10, "Class Type": 18, "Class Name": 22,
                      "Lesson Name": 28, "Lesson #": 16, "Item Description": 32,
                      "Per Section total": 16, "Item Size": 14, "Notes": 18, "Kit": 14}
            for i, col_name in enumerate(header, 1):
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = widths.get(col_name, 16)

        unassigned = out[is_unassigned].copy()
        if len(unassigned):
            sheet = safe_sheet_name("Unassigned Rows", used)
            unassigned[export_cols].to_excel(writer, index=False, sheet_name=sheet)
            writer.sheets[sheet].freeze_panes = "A2"

    return output.getvalue(), len(used), out


def import_to_db(processed_df, db):
    """Write processed DataFrame into lessons + lesson_items tables."""
    df = processed_df.copy()
    is_data = ~(
        (df["Class Name"] == "") & (df["Lesson Name"] == "") &
        (df["_lessonnum_group"] == "") & (df["Item Description"] == "")
    )
    df = df[is_data]

    new_count = 0
    for (ctype, cname, lname, lnum), group in df.groupby(
            ["Class Type", "Class Name", "Lesson Name", "_lessonnum_group"], dropna=False):
        ctype    = str(ctype or "").strip()
        cname    = str(cname or "").strip()
        lname    = str(lname or "").strip()
        lnum_str = str(lnum  or "").strip()
        lnum_int = None
        try:
            lnum_int = int(float(lnum_str)) if lnum_str else None
        except (ValueError, TypeError):
            pass

        existing = db.execute(
            'SELECT id FROM lessons WHERE class_type=%s AND class_name=%s AND lesson_name=%s AND lesson_number=%s',
            [ctype, cname, lname, lnum_int]
        ).fetchone()

        if existing:
            lesson_id = existing['id']
            db.execute('DELETE FROM lesson_items WHERE lesson_id=%s', [lesson_id])
        else:
            cur = db.execute(
                'INSERT INTO lessons (class_type, class_name, lesson_name, lesson_number) VALUES (%s,%s,%s,%s) RETURNING id',
                [ctype, cname, lname, lnum_int]
            )
            lesson_id = cur.fetchone()[0]
            new_count += 1

        for _, row in group.iterrows():
            item_desc  = str(row.get("Item Description", "") or "").strip()
            if not item_desc:
                continue
            kit        = str(row.get("_kit_raw", "")    or "").strip()
            return_raw = str(row.get("_return_raw", "") or "").strip()
            return_req = 1 if return_raw and return_raw.lower() not in ["", "nan", "0", "no", "false"] else 0
            db.execute(
                '''INSERT INTO lesson_items
                   (lesson_id, item_description, essentials_type, per_section_total, item_size, return_required)
                   VALUES (%s,%s,%s,%s,%s,%s)''',
                [lesson_id, item_desc, kit or None,
                 str(row.get("Per Section total", "") or "").strip() or None,
                 str(row.get("Item Size", "")          or "").strip() or None,
                 return_req]
            )
    db.commit()
    return new_count


# ──────────────────────────────────────────────────────────
# Auth routes
# ──────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        db  = get_db()
        row = db.execute('SELECT * FROM users WHERE username=%s AND active=1', [username]).fetchone()
        db.close()
        if row and check_password_hash(row['password_hash'], password):
            login_user(User(row))
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ──────────────────────────────────────────────────────────
# Site Director Portal
# ──────────────────────────────────────────────────────────
@app.route('/director')
@login_required
def director_portal():
    if current_user.role != 'site_director':
        return redirect(url_for('dashboard'))
    if not current_user.school_id:
        return render_template('director/portal.html',
                               school=None, lessons=[], returns=[], returnable=[])
    db = get_db()
    school = db.execute('SELECT * FROM schools WHERE id=%s', [current_user.school_id]).fetchone()
    lessons = db.execute(
        '''SELECT l.*, COUNT(li.id) AS total_items,
                  SUM(CASE WHEN pl.id IS NOT NULL THEN 1 ELSE 0 END) AS packed_items
           FROM lessons l
           LEFT JOIN lesson_items li ON l.id = li.lesson_id
           LEFT JOIN packing_log pl  ON li.id = pl.lesson_item_id
           WHERE l.school_id = %s
           GROUP BY l.id
           ORDER BY l.status, l.class_name, l.lesson_number''',
        [current_user.school_id]
    ).fetchall()
    returns = db.execute(
        '''SELECT r.*, li.item_description, l.class_name, l.lesson_number
           FROM returns r
           JOIN lesson_items li ON r.lesson_item_id = li.id
           JOIN lessons l       ON r.lesson_id      = l.id
           WHERE r.school_id = %s
           ORDER BY (r.received_at IS NOT NULL), r.logged_at DESC''',
        [current_user.school_id]
    ).fetchall()
    returnable = db.execute(
        '''SELECT li.*, l.class_name, l.lesson_number, l.id AS lesson_id
           FROM lesson_items li
           JOIN lessons l ON li.lesson_id = l.id
           WHERE li.return_required = 1 AND l.school_id = %s
           ORDER BY l.class_name, l.lesson_number''',
        [current_user.school_id]
    ).fetchall()
    db.close()
    return render_template('director/portal.html',
                           school=school, lessons=lessons,
                           returns=returns, returnable=returnable)


@app.route('/director/log-return', methods=['POST'])
@login_required
def director_log_return():
    if current_user.role != 'site_director' or not current_user.school_id:
        return redirect(url_for('director_portal'))
    db             = get_db()
    lesson_item_id = request.form.get('lesson_item_id')
    expected_qty   = int(request.form.get('expected_quantity', 0) or 0)
    li = db.execute('SELECT * FROM lesson_items WHERE id=%s', [lesson_item_id]).fetchone()
    if li:
        db.execute(
            'INSERT INTO returns (lesson_id, lesson_item_id, school_id, expected_quantity, logged_by) VALUES (%s,%s,%s,%s,%s)',
            [li['lesson_id'], lesson_item_id, current_user.school_id, expected_qty, current_user.id]
        )
        db.commit()
        flash('Return logged. The warehouse will confirm receipt.', 'success')
    db.close()
    return redirect(url_for('director_portal'))


# ──────────────────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────────────────
@app.route('/')
@login_required
def dashboard():
    if current_user.role == 'site_director':
        return redirect(url_for('director_portal'))
    db = get_db()
    stats = {
        'total_items':     db.execute('SELECT COUNT(*) FROM items').fetchone()[0],
        'low_stock':       db.execute('SELECT COUNT(*) FROM items WHERE quantity > 0 AND quantity <= 10').fetchone()[0],
        'out_of_stock':    db.execute('SELECT COUNT(*) FROM items WHERE quantity = 0').fetchone()[0],
        'total_lessons':   db.execute('SELECT COUNT(*) FROM lessons').fetchone()[0],
        'packed':          db.execute("SELECT COUNT(*) FROM lessons WHERE status='packed'").fetchone()[0],
        'in_progress':     db.execute("SELECT COUNT(*) FROM lessons WHERE status='in_progress'").fetchone()[0],
        'pending_orders':  db.execute("SELECT COUNT(*) FROM incoming_orders WHERE status='pending'").fetchone()[0],
        'pending_returns': db.execute('SELECT COUNT(*) FROM returns WHERE received_at IS NULL').fetchone()[0],
    }
    incoming = db.execute(
        "SELECT * FROM incoming_orders WHERE status != 'shelved' ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    school_returns = db.execute(
        '''SELECT r.*, l.class_name, l.lesson_name, l.lesson_number,
                  s.name AS school_name, li.item_description
           FROM returns r
           JOIN lessons l      ON r.lesson_id      = l.id
           LEFT JOIN lesson_items li ON r.lesson_item_id = li.id
           LEFT JOIN schools s ON r.school_id      = s.id
           WHERE r.received_at IS NULL
           ORDER BY r.logged_at DESC LIMIT 10'''
    ).fetchall()
    db.close()
    return render_template('dashboard.html', stats=stats,
                           incoming=incoming, school_returns=school_returns,
                           now=datetime.now())


# ──────────────────────────────────────────────────────────
# Inventory
# ──────────────────────────────────────────────────────────
@app.route('/inventory')
@warehouse_only
def inventory():
    db       = get_db()
    q        = request.args.get('q', '').strip()
    cat_id   = request.args.get('cat', '')
    page     = max(1, int(request.args.get('page', 1) or 1))
    per_page = 50

    where, params = [], []
    if q:
        where.append('(i.name LIKE %s OR i.description LIKE %s)')
        params += [f'%{q}%', f'%{q}%']
    if cat_id:
        where.append('ic.category_id = %s')
        params.append(cat_id)
    wc = ('WHERE ' + ' AND '.join(where)) if where else ''

    total = db.execute(
        f'SELECT COUNT(DISTINCT i.id) FROM items i LEFT JOIN item_categories ic ON i.id=ic.item_id {wc}',
        params
    ).fetchone()[0]
    items = db.execute(
        f'''SELECT i.*, sc.name AS subcategory_name,
                   STRING_AGG(DISTINCT c.name, ',') AS category_names
            FROM items i
            LEFT JOIN item_categories ic ON i.id = ic.item_id
            LEFT JOIN categories c       ON ic.category_id = c.id
            LEFT JOIN subcategories sc   ON i.subcategory_id = sc.id
            {wc}
            GROUP BY i.id
            ORDER BY i.name
            LIMIT %s OFFSET %s''',
        params + [per_page, (page - 1) * per_page]
    ).fetchall()
    categories = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
    db.close()
    return render_template('inventory/index.html',
                           items=items, categories=categories,
                           q=q, cat_id=cat_id, page=page,
                           per_page=per_page, total=total)


@app.route('/inventory/add', methods=['GET', 'POST'])
@role_required('admin', 'packer')
def inventory_add():
    db = get_db()
    categories    = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
    subcategories = db.execute(
        'SELECT sc.*, c.name AS cat_name FROM subcategories sc JOIN categories c ON sc.category_id=c.id ORDER BY c.name, sc.name'
    ).fetchall()

    if request.method == 'POST':
        name           = request.form.get('name', '').strip()
        description    = request.form.get('description', '').strip() or None
        unit           = request.form.get('unit', 'pcs').strip()
        is_reusable    = 1 if request.form.get('is_reusable') else 0
        quantity       = int(request.form.get('quantity', 0) or 0)
        location       = request.form.get('location', '').strip() or None
        subcategory_id = request.form.get('subcategory_id') or None
        selected_cats  = request.form.getlist('categories')
        if not name:
            flash('Item name is required.', 'danger')
        else:
            cur = db.execute(
                'INSERT INTO items (name, description, unit, is_reusable, quantity, location, subcategory_id) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id',
                [name, description, unit, is_reusable, quantity, location, subcategory_id]
            )
            new_item_id = cur.fetchone()[0]
            for cid in selected_cats:
                db.execute('INSERT INTO item_categories (item_id, category_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                           [new_item_id, cid])
            db.commit()
            db.close()
            flash(f'Item "{name}" added.', 'success')
            return redirect(url_for('inventory'))

    db.close()
    return render_template('inventory/item_form.html', item=None,
                           categories=categories, subcategories=subcategories, selected_cats=[])


@app.route('/inventory/<int:item_id>/edit', methods=['GET', 'POST'])
@role_required('admin', 'packer')
def inventory_edit(item_id):
    db   = get_db()
    item = db.execute('SELECT * FROM items WHERE id=%s', [item_id]).fetchone()
    if not item:
        flash('Item not found.', 'danger')
        db.close()
        return redirect(url_for('inventory'))

    categories    = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
    subcategories = db.execute(
        'SELECT sc.*, c.name AS cat_name FROM subcategories sc JOIN categories c ON sc.category_id=c.id ORDER BY c.name, sc.name'
    ).fetchall()
    selected_cats = [str(r['category_id']) for r in
                     db.execute('SELECT category_id FROM item_categories WHERE item_id=%s', [item_id]).fetchall()]

    if request.method == 'POST':
        name           = request.form.get('name', '').strip()
        description    = request.form.get('description', '').strip() or None
        unit           = request.form.get('unit', 'pcs').strip()
        is_reusable    = 1 if request.form.get('is_reusable') else 0
        quantity       = int(request.form.get('quantity', 0) or 0)
        location       = request.form.get('location', '').strip() or None
        subcategory_id = request.form.get('subcategory_id') or None
        new_cats       = request.form.getlist('categories')
        if not name:
            flash('Item name is required.', 'danger')
        else:
            db.execute(
                'UPDATE items SET name=%s,description=%s,unit=%s,is_reusable=%s,quantity=%s,location=%s,subcategory_id=%s WHERE id=%s',
                [name, description, unit, is_reusable, quantity, location, subcategory_id, item_id]
            )
            db.execute('DELETE FROM item_categories WHERE item_id=%s', [item_id])
            for cid in new_cats:
                db.execute('INSERT INTO item_categories (item_id, category_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                           [item_id, cid])
            db.commit()
            db.close()
            flash(f'Item "{name}" updated.', 'success')
            return redirect(url_for('inventory'))

    db.close()
    return render_template('inventory/item_form.html', item=item,
                           categories=categories, subcategories=subcategories,
                           selected_cats=selected_cats)


@app.route('/inventory/<int:item_id>/delete', methods=['POST'])
@role_required('admin')
def inventory_delete(item_id):
    db   = get_db()
    item = db.execute('SELECT name FROM items WHERE id=%s', [item_id]).fetchone()
    if item:
        db.execute('DELETE FROM item_categories WHERE item_id=%s', [item_id])
        db.execute('DELETE FROM items WHERE id=%s', [item_id])
        db.commit()
        flash(f'"{item["name"]}" deleted.', 'success')
    db.close()
    return redirect(url_for('inventory'))


@app.route('/inventory/import', methods=['GET', 'POST'])
@role_required('admin', 'packer')
def inventory_import():
    """Bulk import inventory items from CSV or Excel."""
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not (file.filename.endswith('.xlsx') or file.filename.endswith('.csv')):
            flash('Please upload a .xlsx or .csv file.', 'danger')
            return redirect(url_for('inventory_import'))
        try:
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)

            name_col     = guess_column(df, ['name', 'item name', 'item'])
            qty_col      = guess_column(df, ['quantity', 'qty', 'stock', 'count'])
            unit_col     = guess_column(df, ['unit', 'units'])
            loc_col      = guess_column(df, ['location', 'loc', 'shelf', 'rack'])
            desc_col     = guess_column(df, ['description', 'desc', 'notes'])
            reusable_col = guess_column(df, ['reusable', 'is_reusable', 'return'])
            cat_col      = guess_column(df, ['category', 'categories'])

            if not name_col:
                flash('Could not find a Name column. Make sure your file has a column called "Name" or "Item Name".', 'danger')
                return redirect(url_for('inventory_import'))

            db = get_db()
            categories = {row['name'].lower(): row['id']
                          for row in db.execute('SELECT id, name FROM categories').fetchall()}
            created = updated = skipped = 0

            for _, row in df.iterrows():
                name = str(row.get(name_col, '') or '').strip()
                if not name or name.lower() == 'nan':
                    skipped += 1
                    continue

                qty       = 0
                if qty_col:
                    try: qty = int(float(str(row.get(qty_col, 0) or 0)))
                    except: pass
                unit      = str(row.get(unit_col, 'pcs') or 'pcs').strip() if unit_col else 'pcs'
                location  = str(row.get(loc_col, '') or '').strip() if loc_col else None
                desc      = str(row.get(desc_col, '') or '').strip() if desc_col else None
                reusable  = 0
                if reusable_col:
                    rv = str(row.get(reusable_col, '') or '').strip().lower()
                    reusable = 1 if rv in ['yes', 'y', '1', 'true', 'x'] else 0
                cat_name  = str(row.get(cat_col, '') or '').strip().lower() if cat_col else ''

                existing = db.execute('SELECT id FROM items WHERE name=%s', [name]).fetchone()
                if existing:
                    db.execute(
                        'UPDATE items SET quantity=quantity+%s, unit=%s, location=COALESCE(%s,location), is_reusable=%s WHERE id=%s',
                        [qty, unit, location or None, reusable, existing['id']]
                    )
                    updated += 1
                    item_id = existing['id']
                else:
                    cur = db.execute(
                        'INSERT INTO items (name, description, unit, is_reusable, quantity, location) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id',
                        [name, desc or None, unit, reusable, qty, location or None]
                    )
                    item_id = cur.fetchone()[0]
                    created += 1

                if cat_name and cat_name in categories:
                    db.execute('INSERT INTO item_categories (item_id, category_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',
                               [item_id, categories[cat_name]])

            db.commit()
            db.close()
            flash(f'Import complete: {created} items created, {updated} updated, {skipped} rows skipped.', 'success')
            return redirect(url_for('inventory'))

        except Exception as e:
            flash(f'Error reading file: {e}', 'danger')
            return redirect(url_for('inventory_import'))

    return render_template('inventory/import.html')


@app.route('/inventory/auto-create-from-lessons', methods=['POST'])
@role_required('admin', 'packer')
def inventory_auto_create():
    """Create inventory records (qty=0) for every unique item in lesson lists."""
    db = get_db()
    all_descs = db.execute(
        'SELECT DISTINCT item_description FROM lesson_items WHERE item_description != ""'
    ).fetchall()
    created = 0
    for row in all_descs:
        desc = row['item_description'].strip()
        if not desc:
            continue
        existing = db.execute('SELECT id FROM items WHERE name=%s', [desc]).fetchone()
        if not existing:
            db.execute('INSERT INTO items (name, quantity, unit) VALUES (%s,0,%s)', [desc, 'pcs'])
            created += 1
    db.commit()
    db.close()
    flash(f'Created {created} new inventory items from lesson lists (quantity set to 0 — update counts manually).', 'success')
    return redirect(url_for('inventory'))


@app.route('/inventory/<int:item_id>/adjust', methods=['POST'])
@role_required('admin', 'packer')
def inventory_adjust(item_id):
    delta = int(request.form.get('delta', 0) or 0)
    db = get_db()
    db.execute('UPDATE items SET quantity = GREATEST(0, quantity + %s) WHERE id=%s', [delta, item_id])
    db.commit()
    new_qty = db.execute('SELECT quantity FROM items WHERE id=%s', [item_id]).fetchone()['quantity']
    db.close()
    return jsonify({'quantity': new_qty})


@app.route('/inventory/categories', methods=['GET', 'POST'])
@role_required('admin')
def manage_categories():
    db = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_category':
            name = request.form.get('name', '').strip()
            if name:
                try:
                    db.execute('INSERT INTO categories (name) VALUES (%s)', [name])
                    db.commit()
                    flash(f'Category "{name}" added.', 'success')
                except psycopg2.IntegrityError:
                    flash('Category already exists.', 'warning')
        elif action == 'add_subcategory':
            cid  = request.form.get('category_id')
            name = request.form.get('subname', '').strip()
            if cid and name:
                db.execute('INSERT INTO subcategories (category_id, name) VALUES (%s,%s)', [cid, name])
                db.commit()
                flash(f'Subcategory "{name}" added.', 'success')
        elif action == 'delete_category':
            cid = request.form.get('cat_id')
            db.execute('DELETE FROM categories WHERE id=%s', [cid])
            db.commit()
            flash('Category deleted.', 'success')
        elif action == 'delete_subcategory':
            sid = request.form.get('sub_id')
            db.execute('DELETE FROM subcategories WHERE id=%s', [sid])
            db.commit()
            flash('Subcategory deleted.', 'success')
    categories    = db.execute('SELECT * FROM categories ORDER BY name').fetchall()
    subcategories = db.execute(
        'SELECT sc.*, c.name AS cat_name FROM subcategories sc JOIN categories c ON sc.category_id=c.id ORDER BY c.name, sc.name'
    ).fetchall()
    db.close()
    return render_template('inventory/categories.html',
                           categories=categories, subcategories=subcategories)


# ──────────────────────────────────────────────────────────
# Packing
# ──────────────────────────────────────────────────────────
@app.route('/packing')
@warehouse_only
def packing():
    db         = get_db()
    school_id  = request.args.get('school', '')
    class_name = request.args.get('class', '')
    status     = request.args.get('status', '')
    q          = request.args.get('q', '').strip()

    where, params = [], []
    if school_id:
        where.append('l.school_id = %s'); params.append(school_id)
    if class_name:
        where.append('l.class_name = %s'); params.append(class_name)
    if status:
        where.append('l.status = %s'); params.append(status)
    if q:
        where.append('(l.class_name LIKE %s OR l.lesson_name LIKE %s)'); params += [f'%{q}%', f'%{q}%']
    wc = ('WHERE ' + ' AND '.join(where)) if where else ''

    lessons = db.execute(f'''
        SELECT l.*, s.name AS school_name,
               COUNT(DISTINCT li.id)                                           AS total_items,
               COUNT(DISTINCT CASE WHEN pl.is_packed=1 THEN pl.id END)        AS packed_items,
               COUNT(DISTINCT CASE WHEN li.return_required=1 THEN li.id END)  AS return_items
        FROM lessons l
        LEFT JOIN schools s      ON l.school_id  = s.id
        LEFT JOIN lesson_items li ON l.id        = li.lesson_id
        LEFT JOIN packing_log pl  ON li.id       = pl.lesson_item_id
        {wc}
        GROUP BY l.id
        ORDER BY l.class_name, l.lesson_name, l.lesson_number
    ''', params).fetchall()

    schools     = db.execute('SELECT * FROM schools ORDER BY name').fetchall()
    class_names = db.execute('SELECT DISTINCT class_name FROM lessons ORDER BY class_name').fetchall()
    low_stock   = db.execute(
        '''SELECT i.*, STRING_AGG(DISTINCT c.name, ',') AS category_names
           FROM items i
           LEFT JOIN item_categories ic ON i.id = ic.item_id
           LEFT JOIN categories c       ON ic.category_id = c.id
           WHERE i.quantity <= 10
           GROUP BY i.id ORDER BY i.quantity ASC LIMIT 30'''
    ).fetchall()
    db.close()

    return render_template('packing/index.html',
                           lessons=lessons, schools=schools, class_names=class_names,
                           low_stock=low_stock,
                           school_id=school_id, class_name=class_name, status=status, q=q)


@app.route('/packing/import', methods=['GET', 'POST'])
@role_required('admin', 'packer')
def packing_import():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
            flash('Please upload a valid Excel file (.xlsx or .xls).', 'danger')
            return redirect(url_for('packing_import'))
        try:
            xls = pd.ExcelFile(file)
            if 'Master' not in xls.sheet_names:
                flash('File must contain a sheet named "Master".', 'danger')
                return redirect(url_for('packing_import'))
            df = pd.read_excel(xls, sheet_name='Master')

            col_class       = guess_column(df, ['class name', 'class'])
            col_lesson      = guess_column(df, ['lesson name'])
            col_lesson_num  = guess_column(df, ['lesson #', 'lesson number', 'lesson num', 'lesson number '])
            col_item        = guess_column(df, ['item description', 'item'])
            col_per_section = guess_column(df, ['per section total', 'per section'])
            col_size        = guess_column(df, ['item size', 'size'])
            col_notes       = guess_column(df, ['notes', 'note'])
            col_kit_src     = guess_column(df, ['essential items', 'essential', 'essentials'])
            col_class_type  = guess_column(df, ['class type', 'class type (name)'])
            col_return      = guess_column(df, ['return'])

            missing = [k for k, v in {
                'Class Name': col_class, 'Lesson Name': col_lesson,
                'Lesson #': col_lesson_num, 'Item Description': col_item,
                'Per Section total': col_per_section
            }.items() if not v]
            if missing:
                flash(f'Could not detect required columns: {", ".join(missing)}. Check your Master sheet headers.', 'danger')
                return redirect(url_for('packing_import'))

            xlsx_bytes, tab_count, processed_df = build_output_excel(
                df, col_class, col_lesson, col_lesson_num, col_item, col_per_section,
                col_size, col_notes, col_kit_src, col_class_type, col_return=col_return
            )

            db = get_db()
            new_lessons = import_to_db(processed_df, db)
            db.close()

            fsession['last_export']      = base64.b64encode(xlsx_bytes).decode()
            fsession['last_export_tabs'] = tab_count

            flash(f'Imported: {tab_count} lesson tabs generated, {new_lessons} new lessons added to database.', 'success')
            return redirect(url_for('packing'))

        except Exception as e:
            flash(f'Error processing file: {e}', 'danger')
            return redirect(url_for('packing_import'))

    return render_template('packing/import.html')


@app.route('/packing/download-last')
@warehouse_only
def packing_download_last():
    data = fsession.get('last_export')
    if not data:
        flash('No export available. Import a master sheet first.', 'warning')
        return redirect(url_for('packing_import'))
    return send_file(
        BytesIO(base64.b64decode(data)),
        download_name='packing_lists_by_lesson.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/packing/lesson/<int:lesson_id>')
@warehouse_only
def packing_lesson(lesson_id):
    db     = get_db()
    lesson = db.execute(
        'SELECT l.*, s.name AS school_name FROM lessons l LEFT JOIN schools s ON l.school_id=s.id WHERE l.id=%s',
        [lesson_id]
    ).fetchone()
    if not lesson:
        flash('Lesson not found.', 'danger')
        db.close()
        return redirect(url_for('packing'))

    items = db.execute(
        '''SELECT li.*,
                  COALESCE(pl.is_packed, 0) AS is_packed,
                  pl.packed_by, pl.packed_at, pl.notes AS pack_notes,
                  u.full_name AS packer_name
           FROM lesson_items li
           LEFT JOIN packing_log pl ON li.id = pl.lesson_item_id
           LEFT JOIN users u        ON pl.packed_by = u.id
           WHERE li.lesson_id = %s
           ORDER BY li.return_required DESC, li.essentials_type NULLS LAST, li.item_description''',
        [lesson_id]
    ).fetchall()

    total  = len(items)
    packed = sum(1 for i in items if i['is_packed'])
    pct    = int(packed / total * 100) if total else 0
    schools = db.execute('SELECT * FROM schools WHERE active=1 ORDER BY name').fetchall()
    db.close()
    return render_template('packing/lesson.html',
                           lesson=lesson, items=items,
                           total=total, packed=packed, pct=pct, schools=schools)


@app.route('/packing/lesson/<int:lesson_id>/toggle', methods=['POST'])
@warehouse_only
def packing_toggle(lesson_id):
    item_id = request.json.get('item_id')
    db      = get_db()
    # Verify this item actually belongs to this lesson
    if not db.execute('SELECT id FROM lesson_items WHERE id=%s AND lesson_id=%s',
                      [item_id, lesson_id]).fetchone():
        db.close()
        return jsonify({'error': 'invalid item for this lesson'}), 400
    existing = db.execute('SELECT * FROM packing_log WHERE lesson_item_id=%s', [item_id]).fetchone()
    if existing:
        new_state = 0 if existing['is_packed'] else 1
        db.execute(
            'UPDATE packing_log SET is_packed=%s, packed_by=%s, packed_at=%s WHERE lesson_item_id=%s',
            [new_state, current_user.id,
             datetime.now().isoformat() if new_state else None, item_id]
        )
    else:
        db.execute(
            'INSERT INTO packing_log (lesson_id, lesson_item_id, is_packed, packed_by, packed_at) VALUES (%s,%s,1,%s,%s)',
            [lesson_id, item_id, current_user.id, datetime.now().isoformat()]
        )
        new_state = 1

    total  = db.execute('SELECT COUNT(*) FROM lesson_items WHERE lesson_id=%s', [lesson_id]).fetchone()[0]
    packed = db.execute('SELECT COUNT(*) FROM packing_log WHERE lesson_id=%s AND is_packed=1', [lesson_id]).fetchone()[0]
    status = 'unpacked' if packed == 0 else ('packed' if packed >= total else 'in_progress')
    db.execute('UPDATE lessons SET status=%s WHERE id=%s', [status, lesson_id])
    db.commit()
    db.close()
    return jsonify({'is_packed': bool(new_state), 'status': status, 'packed': packed, 'total': total})


@app.route('/packing/lesson/<int:lesson_id>/print')
@warehouse_only
def packing_lesson_print(lesson_id):
    db     = get_db()
    lesson = db.execute(
        'SELECT l.*, s.name AS school_name FROM lessons l LEFT JOIN schools s ON l.school_id=s.id WHERE l.id=%s',
        [lesson_id]
    ).fetchone()
    items  = db.execute(
        '''SELECT li.*, COALESCE(pl.is_packed, 0) AS is_packed
           FROM lesson_items li
           LEFT JOIN packing_log pl ON li.id = pl.lesson_item_id
           WHERE li.lesson_id=%s
           ORDER BY li.return_required DESC, li.essentials_type NULLS LAST, li.item_description''',
        [lesson_id]
    ).fetchall()
    db.close()
    return render_template('packing/lesson_print.html', lesson=lesson, items=items)


@app.route('/packing/lesson/<int:lesson_id>/qr')
@warehouse_only
def packing_lesson_qr(lesson_id):
    url = request.host_url.rstrip('/') + url_for('packing_lesson', lesson_id=lesson_id)
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')


@app.route('/packing/lesson/<int:lesson_id>/assign', methods=['POST'])
@role_required('admin', 'packer')
def packing_assign(lesson_id):
    school_id    = request.form.get('school_id') or None
    teacher_name = request.form.get('teacher_name', '').strip() or None
    db = get_db()
    db.execute('UPDATE lessons SET school_id=%s, teacher_name=%s WHERE id=%s',
               [school_id, teacher_name, lesson_id])
    db.commit()
    db.close()
    flash('School assignment saved.', 'success')
    return redirect(url_for('packing_lesson', lesson_id=lesson_id))


# ──────────────────────────────────────────────────────────
# Arriving
# ──────────────────────────────────────────────────────────
@app.route('/arriving')
@warehouse_only
def arriving():
    db     = get_db()
    orders = db.execute(
        '''SELECT o.*, i.name AS item_name, i.unit AS item_unit
           FROM incoming_orders o
           LEFT JOIN items i ON o.item_id = i.id
           ORDER BY CASE o.status WHEN 'pending' THEN 0 WHEN 'arrived' THEN 1 ELSE 2 END,
                    o.created_at DESC'''
    ).fetchall()
    items   = db.execute('SELECT id, name, unit FROM items ORDER BY name').fetchall()
    schools = db.execute('SELECT * FROM schools WHERE active=1 ORDER BY name').fetchall()
    db.close()
    return render_template('arriving/index.html', orders=orders, items=items, schools=schools)


@app.route('/arriving/add', methods=['POST'])
@role_required('admin', 'packer')
def arriving_add():
    db          = get_db()
    item_id     = request.form.get('item_id') or None
    item_desc   = request.form.get('item_description', '').strip()
    quantity    = int(request.form.get('quantity', 0) or 0)
    unit        = request.form.get('unit', 'pcs').strip()
    source      = request.form.get('source', '').strip() or None
    expected    = request.form.get('expected_arrival', '').strip() or None
    notes       = request.form.get('notes', '').strip() or None
    if not item_desc and item_id:
        row = db.execute('SELECT name FROM items WHERE id=%s', [item_id]).fetchone()
        if row:
            item_desc = row['name']
    if item_desc and quantity > 0:
        db.execute(
            'INSERT INTO incoming_orders (item_id, item_description, quantity, unit, source, expected_arrival, notes) VALUES (%s,%s,%s,%s,%s,%s,%s)',
            [item_id, item_desc, quantity, unit, source, expected, notes]
        )
        db.commit()
        flash('Incoming order added.', 'success')
    else:
        flash('Item description and quantity are required.', 'danger')
    db.close()
    return redirect(url_for('arriving'))


@app.route('/arriving/<int:order_id>/mark-arrived', methods=['POST'])
@role_required('admin', 'packer')
def arriving_mark_arrived(order_id):
    db = get_db()
    updated = db.execute(
        "UPDATE incoming_orders SET status='arrived', actual_arrival=%s WHERE id=%s AND status='pending'",
        [datetime.now().strftime('%Y-%m-%d'), order_id]
    ).rowcount
    db.commit()
    db.close()
    if updated:
        flash('Order marked as arrived.', 'success')
    else:
        flash('Order could not be updated — it may already be arrived or shelved.', 'warning')
    return redirect(url_for('arriving'))


@app.route('/arriving/<int:order_id>/shelve', methods=['POST'])
@role_required('admin', 'packer')
def arriving_shelve(order_id):
    db    = get_db()
    order = db.execute(
        "SELECT * FROM incoming_orders WHERE id=%s AND status='arrived'", [order_id]
    ).fetchone()
    if not order:
        db.close()
        flash('This order must be marked as arrived before it can be shelved.', 'warning')
        return redirect(url_for('arriving'))
    if order['item_id']:
        db.execute('UPDATE items SET quantity = quantity + %s WHERE id=%s',
                   [order['quantity'], order['item_id']])
    db.execute("UPDATE incoming_orders SET status='shelved' WHERE id=%s", [order_id])
    db.commit()
    db.close()
    flash('Order shelved and inventory updated.' if order['item_id']
          else 'Order shelved. No inventory item linked — update stock manually.', 'success')
    return redirect(url_for('arriving'))


# ──────────────────────────────────────────────────────────
# Schools
# ──────────────────────────────────────────────────────────
@app.route('/schools')
@warehouse_only
def schools():
    db      = get_db()
    schools = db.execute(
        '''SELECT s.*, COUNT(l.id) AS lesson_count
           FROM schools s
           LEFT JOIN lessons l ON s.id = l.school_id
           GROUP BY s.id ORDER BY s.name'''
    ).fetchall()
    db.close()
    return render_template('schools/index.html', schools=schools)


@app.route('/schools/add', methods=['GET', 'POST'])
@role_required('admin')
def schools_add():
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip() or None
        notes   = request.form.get('notes', '').strip() or None
        if name:
            db = get_db()
            db.execute('INSERT INTO schools (name, address, notes) VALUES (%s,%s,%s)',
                       [name, address, notes])
            db.commit()
            db.close()
            flash(f'School "{name}" added.', 'success')
            return redirect(url_for('schools'))
        flash('School name is required.', 'danger')
    return render_template('schools/form.html', school=None)


@app.route('/schools/<int:school_id>', methods=['GET', 'POST'])
@warehouse_only
def school_detail(school_id):
    db     = get_db()
    school = db.execute('SELECT * FROM schools WHERE id=%s', [school_id]).fetchone()
    if not school:
        flash('School not found.', 'danger')
        db.close()
        return redirect(url_for('schools'))
    if request.method == 'POST':
        notes = request.form.get('notes', '').strip()
        db.execute('UPDATE schools SET notes=%s WHERE id=%s', [notes, school_id])
        db.commit()
        flash('Notes saved.', 'success')
    lessons = db.execute(
        'SELECT * FROM lessons WHERE school_id=%s ORDER BY class_name, lesson_number',
        [school_id]
    ).fetchall()
    pending_returns = db.execute(
        '''SELECT r.*, li.item_description, l.class_name, l.lesson_name
           FROM returns r
           JOIN lesson_items li ON r.lesson_item_id = li.id
           JOIN lessons l       ON r.lesson_id      = l.id
           WHERE r.school_id=%s AND r.received_at IS NULL
           ORDER BY r.logged_at DESC''',
        [school_id]
    ).fetchall()
    db.close()
    return render_template('schools/detail.html',
                           school=school, lessons=lessons, pending_returns=pending_returns)


@app.route('/schools/<int:school_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def school_edit(school_id):
    db     = get_db()
    school = db.execute('SELECT * FROM schools WHERE id=%s', [school_id]).fetchone()
    if request.method == 'POST':
        db.execute(
            'UPDATE schools SET name=%s, address=%s, notes=%s, active=%s WHERE id=%s',
            [request.form.get('name', '').strip(),
             request.form.get('address', '').strip() or None,
             request.form.get('notes', '').strip() or None,
             1 if request.form.get('active') else 0,
             school_id]
        )
        db.commit()
        db.close()
        flash('School updated.', 'success')
        return redirect(url_for('school_detail', school_id=school_id))
    db.close()
    return render_template('schools/form.html', school=school)


# ──────────────────────────────────────────────────────────
# Returns
# ──────────────────────────────────────────────────────────
@app.route('/returns')
@warehouse_only
def returns():
    db          = get_db()
    all_returns = db.execute(
        '''SELECT r.*, li.item_description, li.item_id AS inventory_item_id,
                  l.class_name, l.lesson_name, l.lesson_number,
                  s.name AS school_name, u1.full_name AS logged_by_name, u2.full_name AS received_by_name
           FROM returns r
           JOIN lesson_items li ON r.lesson_item_id = li.id
           JOIN lessons l       ON r.lesson_id      = l.id
           LEFT JOIN schools s  ON r.school_id      = s.id
           LEFT JOIN users u1   ON r.logged_by      = u1.id
           LEFT JOIN users u2   ON r.received_by    = u2.id
           ORDER BY (r.received_at IS NOT NULL), r.logged_at DESC'''
    ).fetchall()
    returnable = db.execute(
        '''SELECT li.*, l.class_name, l.lesson_name, l.lesson_number, s.name AS school_name
           FROM lesson_items li
           JOIN lessons l      ON li.lesson_id  = l.id
           LEFT JOIN schools s ON l.school_id   = s.id
           WHERE li.return_required = 1
           ORDER BY s.name, l.class_name'''
    ).fetchall()
    schools = db.execute('SELECT * FROM schools WHERE active=1 ORDER BY name').fetchall()
    db.close()
    return render_template('returns/index.html',
                           all_returns=all_returns, returnable=returnable, schools=schools)


@app.route('/returns/log', methods=['POST'])
@warehouse_only
def returns_log():
    db             = get_db()
    lesson_item_id = request.form.get('lesson_item_id')
    school_id      = request.form.get('school_id') or None
    expected_qty   = int(request.form.get('expected_quantity', 0) or 0)
    li = db.execute('SELECT * FROM lesson_items WHERE id=%s', [lesson_item_id]).fetchone()
    if li:
        db.execute(
            'INSERT INTO returns (lesson_id, lesson_item_id, school_id, expected_quantity, logged_by) VALUES (%s,%s,%s,%s,%s)',
            [li['lesson_id'], lesson_item_id, school_id, expected_qty, current_user.id]
        )
        db.commit()
        flash('Return logged.', 'success')
    db.close()
    return redirect(url_for('returns'))


@app.route('/returns/<int:return_id>/receive', methods=['POST'])
@role_required('admin', 'packer')
def returns_receive(return_id):
    db           = get_db()
    received_qty = int(request.form.get('received_quantity', 0) or 0)

    if received_qty <= 0:
        flash('Please enter the quantity received (must be at least 1).', 'danger')
        db.close()
        return redirect(url_for('returns'))

    r = db.execute('SELECT * FROM returns WHERE id=%s', [return_id]).fetchone()
    if r:
        expected_qty = r['expected_quantity'] or 0

        # Mark this return as received with however many actually arrived
        db.execute(
            'UPDATE returns SET received_quantity=%s, received_by=%s, received_at=%s WHERE id=%s',
            [received_qty, current_user.id, datetime.now().isoformat(), return_id]
        )

        # Add to inventory if item is linked
        li = db.execute('SELECT * FROM lesson_items WHERE id=%s', [r['lesson_item_id']]).fetchone()
        if li and li['item_id']:
            db.execute('UPDATE items SET quantity = quantity + %s WHERE id=%s',
                       [received_qty, li['item_id']])
            db.execute('UPDATE returns SET readded_to_inventory=1 WHERE id=%s', [return_id])

        # If partial — create a new pending return for the remainder
        remainder = expected_qty - received_qty
        if remainder > 0:
            db.execute(
                '''INSERT INTO returns
                   (lesson_id, lesson_item_id, school_id, expected_quantity, logged_by)
                   VALUES (%s,%s,%s,%s,%s)''',
                [r['lesson_id'], r['lesson_item_id'], r['school_id'],
                 remainder, current_user.id]
            )

        db.commit()

        if li and li['item_id']:
            msg = f'{received_qty} received and added to inventory.'
        else:
            msg = (f'{received_qty} received, but this item has no inventory record — '
                   f'add {received_qty} unit(s) manually in Inventory.')

        if remainder > 0:
            msg += f' {remainder} still outstanding — a new pending return has been created.'

        flash(msg, 'success' if (li and li['item_id']) else 'warning')

    db.close()
    return redirect(url_for('returns'))


@app.route('/returns/<int:return_id>/write-off', methods=['POST'])
@role_required('admin', 'packer')
def returns_write_off(return_id):
    db = get_db()
    r  = db.execute('SELECT * FROM returns WHERE id=%s', [return_id]).fetchone()
    if r:
        db.execute(
            '''UPDATE returns
               SET received_quantity=0, received_by=%s, received_at=%s, written_off=1
               WHERE id=%s''',
            [current_user.id, datetime.now().isoformat(), return_id]
        )
        db.commit()
        flash('Return cleared — marked as written off. Inventory was not adjusted.', 'warning')
    db.close()
    return redirect(url_for('returns'))


# ──────────────────────────────────────────────────────────
# Admin
# ──────────────────────────────────────────────────────────
@app.route('/admin/users')
@role_required('admin')
def admin_users():
    db      = get_db()
    users   = db.execute(
        'SELECT u.*, s.name AS school_name FROM users u LEFT JOIN schools s ON u.school_id=s.id ORDER BY u.role, u.username'
    ).fetchall()
    schools = db.execute('SELECT * FROM schools ORDER BY name').fetchall()
    db.close()
    return render_template('admin/users.html', users=users, schools=schools)


@app.route('/admin/users/add', methods=['POST'])
@role_required('admin')
def admin_users_add():
    db        = get_db()
    username  = request.form.get('username', '').strip()
    full_name = request.form.get('full_name', '').strip() or None
    password  = request.form.get('password', '').strip()
    role      = request.form.get('role', 'packer')
    school_id = request.form.get('school_id') or None
    if not username or not password:
        flash('Username and password are required.', 'danger')
    else:
        try:
            db.execute(
                'INSERT INTO users (username, password_hash, full_name, role, school_id) VALUES (%s,%s,%s,%s,%s)',
                [username, generate_password_hash(password), full_name, role, school_id]
            )
            db.commit()
            flash(f'User "{username}" created.', 'success')
        except psycopg2.IntegrityError:
            flash('Username already exists.', 'danger')
    db.close()
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@role_required('admin')
def admin_reset_password(user_id):
    new_pw = request.form.get('password', '').strip()
    if new_pw:
        db = get_db()
        db.execute('UPDATE users SET password_hash=%s WHERE id=%s',
                   [generate_password_hash(new_pw), user_id])
        db.commit()
        db.close()
        flash('Password reset.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@role_required('admin')
def admin_users_toggle(user_id):
    if user_id == current_user.id:
        flash("You can't deactivate your own account.", 'danger')
        return redirect(url_for('admin_users'))
    db  = get_db()
    cur = db.execute('SELECT active FROM users WHERE id=%s', [user_id]).fetchone()
    if cur:
        db.execute('UPDATE users SET active=%s WHERE id=%s', [0 if cur['active'] else 1, user_id])
        db.commit()
    db.close()
    flash('User status updated.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@role_required('admin')
def admin_users_delete(user_id):
    if user_id == current_user.id:
        flash("You can't delete your own account.", 'danger')
        return redirect(url_for('admin_users'))
    db = get_db()
    db.execute('DELETE FROM users WHERE id=%s', [user_id])
    db.commit()
    db.close()
    flash('User deleted.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/assign-school', methods=['POST'])
@role_required('admin')
def admin_assign_school(user_id):
    school_id = request.form.get('school_id') or None
    db = get_db()
    db.execute('UPDATE users SET school_id=%s WHERE id=%s', [school_id, user_id])
    db.commit()
    db.close()
    flash('School assignment updated.', 'success')
    return redirect(url_for('admin_users'))


# ──────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5001)))
