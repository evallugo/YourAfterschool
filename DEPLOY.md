# Deploying YAS to Railway

## One-time setup

### 1. Push your code to GitHub
```bash
git init  # if not already a repo
git add .
git commit -m "migrate to postgresql"
git remote add origin https://github.com/YOUR_USERNAME/your-afterschool.git
git push -u origin main
```

### 2. Create a Railway project
1. Go to railway.app and sign up / log in
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repository

### 3. Add a PostgreSQL database
1. Inside your Railway project, click "+ New" → "Database" → "PostgreSQL"
2. Railway creates the database and automatically sets DATABASE_URL in your environment

### 4. Set your secret key
In Railway → your app service → Variables, add:
```
SECRET_KEY=some-long-random-string-change-this
```
Generate one with: `python -c "import secrets; print(secrets.token_hex(32))"`

### 5. Initialise the database (run once)
In Railway → your app service → Settings → "Run command" temporarily set to:
```
python init_db.py
```
Run it, then switch back to:
```
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```
(Or just add an init step to your Procfile — see below.)

### 6. Migrate your existing data (optional)
If you have real data in the SQLite backup you want to keep:
```bash
DATABASE_URL=your-railway-postgres-url python migrate_to_pg.py
```
Get the URL from Railway → PostgreSQL service → Connect tab.

---

## Environment variables needed
| Variable | Value |
|---|---|
| `DATABASE_URL` | Set automatically by Railway when you add PostgreSQL |
| `SECRET_KEY` | A long random string — never commit this |
| `PORT` | Set automatically by Railway |

---

## Local development (without PostgreSQL installed)
Install PostgreSQL locally, create a database called `yas`, then:
```bash
DATABASE_URL=postgresql://localhost/yas python init_db.py
DATABASE_URL=postgresql://localhost/yas python seed_data.py
DATABASE_URL=postgresql://localhost/yas python app.py
```

Or use Railway's PostgreSQL directly for local dev (copy the DATABASE_URL from Railway).
