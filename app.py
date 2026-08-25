from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os
from functools import wraps
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'hisab.db')
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key')

ACCOUNTS = [
    ('ريس نجيب','افغاني'),('ريس نجيب','ډالر'),
    ('حاجي صاحب','افغاني'),('حاجي صاحب','ډالر'),
    ('ريس نجيب ورور','افغاني'),('ريس نجيب ورور','ډالر'),
    ('اسلام الدين','افغاني'),('اسلام الدين','ډالر')
]


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      full_name TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'user',
      active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS entries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      jalali_date TEXT NOT NULL,
      description TEXT NOT NULL,
      amount REAL NOT NULL,
      currency TEXT NOT NULL,
      account TEXT NOT NULL,
      entry_type TEXT NOT NULL CHECK(entry_type IN ('income','expense')),
      house TEXT DEFAULT '',
      created_by INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(created_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS purchases (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      jalali_date TEXT NOT NULL,
      item TEXT NOT NULL,
      quantity REAL DEFAULT 0,
      unit TEXT DEFAULT '',
      amount REAL DEFAULT 0,
      currency TEXT NOT NULL,
      house TEXT DEFAULT '',
      created_by INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(created_by) REFERENCES users(id)
    );
    ''')
    if c.execute('SELECT COUNT(*) n FROM users').fetchone()['n'] == 0:
        c.execute('INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,?)',
                  ('admin', generate_password_hash('Admin@123'), 'اصلي اډمين', 'admin'))
    c.commit(); c.close()


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrap


def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('یوازې اډمین دې برخې ته لاسرسی لري.', 'error'); return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrap

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u=request.form['username'].strip(); p=request.form['password']
        c=db(); user=c.execute('SELECT * FROM users WHERE username=? AND active=1',(u,)).fetchone(); c.close()
        if user and check_password_hash(user['password_hash'], p):
            session.update(user_id=user['id'], username=user['username'], full_name=user['full_name'], role=user['role'])
            return redirect(url_for('dashboard'))
        flash('کارنوم یا پټ نوم ناسم دی.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    c=db()
    rows=c.execute('SELECT account,currency,entry_type,COALESCE(SUM(amount),0) total FROM entries GROUP BY account,currency,entry_type').fetchall()
    data={}
    for r in rows:
        k=f"{r['account']}|{r['currency']}"; data.setdefault(k, {'account':r['account'],'currency':r['currency'],'income':0,'expense':0})[r['entry_type']]=r['total']
    recent=c.execute('SELECT e.*,u.full_name FROM entries e JOIN users u ON u.id=e.created_by ORDER BY e.id DESC LIMIT 20').fetchall()
    c.close(); return render_template('dashboard.html', data=list(data.values()), recent=recent)

@app.route('/entries', methods=['GET','POST'])
@login_required
def entries():
    if request.method=='POST':
        c=db(); c.execute('INSERT INTO entries(jalali_date,description,amount,currency,account,entry_type,house,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
          (request.form['date'],request.form['description'],float(request.form['amount']),request.form['currency'],request.form['account'],request.form['entry_type'],request.form.get('house',''),session['user_id'],datetime.now().isoformat(timespec='seconds'))); c.commit(); c.close(); flash('معلومات ثبت شول.','ok'); return redirect(url_for('entries'))
    c=db(); rows=c.execute('SELECT e.*,u.full_name FROM entries e JOIN users u ON u.id=e.created_by ORDER BY e.id DESC LIMIT 200').fetchall(); c.close()
    return render_template('entries.html', rows=rows, accounts=ACCOUNTS)

@app.route('/purchases', methods=['GET','POST'])
@login_required
def purchases():
    if request.method=='POST':
        c=db(); c.execute('INSERT INTO purchases(jalali_date,item,quantity,unit,amount,currency,house,created_by,created_at) VALUES(?,?,?,?,?,?,?, ?,?)',
          (request.form['date'],request.form['item'],float(request.form.get('quantity') or 0),request.form.get('unit',''),float(request.form.get('amount') or 0),request.form['currency'],request.form.get('house',''),session['user_id'],datetime.now().isoformat(timespec='seconds'))); c.commit(); c.close(); flash('خریداري ثبت شوه.','ok'); return redirect(url_for('purchases'))
    c=db(); rows=c.execute('SELECT p.*,u.full_name FROM purchases p JOIN users u ON u.id=p.created_by ORDER BY p.id DESC LIMIT 200').fetchall(); c.close(); return render_template('purchases.html',rows=rows)

@app.route('/reports')
@login_required
def reports():
    c=db(); rows=c.execute('SELECT account,currency,entry_type,COALESCE(SUM(amount),0) total FROM entries GROUP BY account,currency,entry_type').fetchall(); c.close()
    data={}
    for r in rows:
        k=(r['account'],r['currency']); data.setdefault(k,{'account':r['account'],'currency':r['currency'],'income':0,'expense':0}); data[k][r['entry_type']]=r['total']
    return render_template('reports.html',data=list(data.values()))

@app.route('/users', methods=['GET','POST'])
@login_required
@admin_required
def users():
    c=db()
    if request.method=='POST':
        try:
            c.execute('INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,?)', (request.form['username'].strip(),generate_password_hash(request.form['password']),request.form['full_name'].strip(),request.form['role']))
            c.commit(); flash('نوی کارن اضافه شو.','ok')
        except sqlite3.IntegrityError: flash('دا Username مخکې موجود دی.','error')
    rows=c.execute('SELECT id,username,full_name,role,active FROM users ORDER BY id').fetchall(); c.close(); return render_template('users.html',rows=rows)

@app.route('/users/<int:uid>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(uid):
    c=db(); c.execute('UPDATE users SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(uid,)); c.commit(); c.close(); return redirect(url_for('users'))

@app.route('/users/<int:uid>/password', methods=['POST'])
@login_required
@admin_required
def change_password(uid):
    c=db(); c.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(request.form['password']),uid)); c.commit(); c.close(); flash('پټ نوم بدل شو.','ok'); return redirect(url_for('users'))

@app.route('/health')
def health(): return 'OK'

init_db()
if __name__ == '__main__': app.run(host='0.0.0.0', port=int(os.environ.get('PORT',5000)), debug=False)
