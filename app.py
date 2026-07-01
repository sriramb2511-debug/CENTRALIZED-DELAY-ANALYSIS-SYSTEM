from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3, hashlib, os, json
from datetime import datetime, timedelta
from init_db import init_db, DB_PATH

app = Flask(__name__)
app.secret_key = 'vizag_steel_delay_system_2024'

ROLES    = ['sys_admin', 'dept_user', 'dept_admin', 'ppm_user', 'ppm_admin']
AGENCIES = ['Operations', 'Mechanical', 'Electrical', 'Shutdown', 'Civil', 'Idle', 'Miscellaneous']

def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    from functools import wraps
    @wraps(f)
    def dec(*a, **kw):
        if 'user' not in session: return redirect(url_for('login'))
        return f(*a, **kw)
    return dec

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def dec(*a, **kw):
        if 'user' not in session: return redirect(url_for('login'))
        if session.get('role') not in ['sys_admin','dept_admin','ppm_admin']:
            flash('Access denied. Admin privileges required.','danger')
            return redirect(url_for('dashboard'))
        return f(*a, **kw)
    return dec

def entry_required(f):
    """Only roles that are allowed to enter delays."""
    from functools import wraps
    @wraps(f)
    def dec(*a, **kw):
        if 'user' not in session: return redirect(url_for('login'))
        if session.get('role') not in ['sys_admin','dept_admin','dept_user']:
            flash('Access denied. Delay entry is not available for your role.','danger')
            return redirect(url_for('dashboard'))
        return f(*a, **kw)
    return dec

def reports_required(f):
    """Only roles that are allowed to view reports."""
    from functools import wraps
    @wraps(f)
    def dec(*a, **kw):
        if 'user' not in session: return redirect(url_for('login'))
        if session.get('role') not in ['sys_admin','dept_admin','ppm_admin','ppm_user']:
            flash('Access denied. Reports are not available for your role.','danger')
            return redirect(url_for('dashboard'))
        return f(*a, **kw)
    return dec

# ── LOGIN ─────────────────────────────────────────────────────────────────────
@app.route('/', methods=['GET','POST'])
@app.route('/login', methods=['GET','POST'])
def login():
    if 'user' in session: return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        emp_no   = request.form['emp_no'].strip().upper()
        password = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE emp_no=? AND active=1",(emp_no,)).fetchone()
        conn.close()
        if user and user['password'] == hash_password(password):
            session.update({'user':user['emp_no'],'emp_name':user['emp_name'],
                            'role':user['role'],'dept':user['dept']})
            return redirect(url_for('dashboard'))
        error = 'Invalid Employee Number or Password'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    role = session.get('role')
    dept = session.get('dept','')
    user = session.get('user')

    dept_filter = ""
    dept_params = []
    if role == 'dept_user':
        dept_filter = "AND shop_desc=?"
        dept_params = [dept]

    # KPI cards
    total = conn.execute(f"SELECT COUNT(*) FROM delays WHERE 1=1 {dept_filter}", dept_params).fetchone()[0]
    total_mins = conn.execute(f"SELECT COALESCE(SUM(delay_duration),0) FROM delays WHERE 1=1 {dept_filter}", dept_params).fetchone()[0]
    avg_dur = conn.execute(f"SELECT COALESCE(AVG(delay_duration),0) FROM delays WHERE 1=1 {dept_filter}", dept_params).fetchone()[0]

    # This month
    month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    # Since data is 2003-2005, use relative to data's latest date
    latest = conn.execute("SELECT MAX(date(delay_from)) FROM delays").fetchone()[0] or '2005-03-31'
    lt = datetime.strptime(latest,'%Y-%m-%d')
    month_s = lt.replace(day=1).strftime('%Y-%m-%d')
    month_delays = conn.execute(
        f"SELECT COUNT(*) FROM delays WHERE date(delay_from)>=? {dept_filter}", [month_s]+dept_params
    ).fetchone()[0]

    # By agency
    agency_data = conn.execute(
        f"SELECT agency, COUNT(*) c, COALESCE(SUM(delay_duration),0) mins FROM delays WHERE 1=1 {dept_filter} GROUP BY agency ORDER BY mins DESC",
        dept_params
    ).fetchall()

    # By shop (top 8)
    shop_data = conn.execute(
        f"SELECT shop_desc, COUNT(*) c, COALESCE(SUM(delay_duration),0) mins FROM delays WHERE 1=1 {dept_filter} GROUP BY shop_desc ORDER BY mins DESC LIMIT 8",
        dept_params
    ).fetchall()

    # Monthly trend (last 12 months of data)
    trend_data = conn.execute(
        f"""SELECT strftime('%Y-%m', delay_from) mon, COUNT(*) c, COALESCE(SUM(delay_duration),0) mins
            FROM delays WHERE 1=1 {dept_filter}
            GROUP BY mon ORDER BY mon DESC LIMIT 12""", dept_params
    ).fetchall()
    trend_data = list(reversed(trend_data))

    # Top 10 equipment
    top_eqpt = conn.execute(
        f"SELECT eqpt_code, COUNT(*) c, COALESCE(SUM(delay_duration),0) mins FROM delays WHERE 1=1 {dept_filter} AND eqpt_code!='UNKNOWN' GROUP BY eqpt_code ORDER BY mins DESC LIMIT 10",
        dept_params
    ).fetchall()

    # Recent 8 delays
    recent = conn.execute(
        f"SELECT * FROM delays WHERE 1=1 {dept_filter} ORDER BY delay_from DESC LIMIT 8",
        dept_params
    ).fetchall()

    # User activity (admin only)
    user_activity = []
    if role in ['sys_admin','ppm_admin']:
        user_activity = conn.execute(
            "SELECT user_entered, COUNT(*) c FROM delays GROUP BY user_entered ORDER BY c DESC LIMIT 8"
        ).fetchall()

    # Heatmap: day-of-week vs hour
    heatmap_raw = conn.execute(
        f"""SELECT strftime('%w', delay_from) dow, CAST(strftime('%H', delay_from) AS INT) hr, COUNT(*) c
            FROM delays WHERE 1=1 {dept_filter}
            GROUP BY dow, hr""", dept_params
    ).fetchall()

    conn.close()

    return render_template('dashboard.html',
        total=total, total_mins=total_mins, avg_dur=avg_dur, month_delays=month_delays,
        agency_data=[dict(r) for r in agency_data],
        shop_data=[dict(r) for r in shop_data],
        trend_data=[dict(r) for r in trend_data],
        top_eqpt=[dict(r) for r in top_eqpt],
        recent=[dict(r) for r in recent],
        user_activity=[dict(r) for r in user_activity],
        heatmap_raw=[dict(r) for r in heatmap_raw],
        latest_date=latest
    )

# ── DELAY ENTRY ────────────────────────────────────────────────────────────────
@app.route('/delay-entry', methods=['GET','POST'])
@entry_required
def delay_entry():
    conn = get_db()
    shops  = conn.execute("SELECT DISTINCT shop_code, shop_desc FROM eqpt_master ORDER BY shop_code").fetchall()
    grades = conn.execute("SELECT grade_code, grade_desc FROM grade_master ORDER BY grade_desc").fetchall()
    # My recent entries
    my_recent = conn.execute(
        "SELECT * FROM delays WHERE user_entered=? ORDER BY delay_from DESC LIMIT 10",
        (session['user'],)
    ).fetchall()
    conn.close()
    return render_template('delay_entry.html', shops=shops, agencies=AGENCIES, grades=grades, my_recent=[dict(r) for r in my_recent])

@app.route('/api/equipment/<int:shop_code>')
@login_required
def get_equipment(shop_code):
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT eqpt_code FROM eqpt_master WHERE shop_code=? ORDER BY eqpt_code",(shop_code,)).fetchall()
    conn.close()
    return jsonify([r['eqpt_code'] for r in rows])

@app.route('/api/sub-equipment/<int:shop_code>/<eqpt_code>')
@login_required
def get_sub_equipment(shop_code, eqpt_code):
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT sub_eqpt_code FROM eqpt_master WHERE shop_code=? AND eqpt_code=? AND sub_eqpt_code IS NOT NULL ORDER BY sub_eqpt_code",(shop_code,eqpt_code)).fetchall()
    conn.close()
    return jsonify([r['sub_eqpt_code'] for r in rows])

@app.route('/submit-delay', methods=['POST'])
@entry_required
def submit_delay():
    try:
        shop_code  = int(request.form['shop_code'])
        agency     = request.form['agency']
        delay_from = request.form['delay_from']
        delay_upto = request.form['delay_upto']
        delay_desc = request.form.get('delay_desc','')
        eqpt_code  = request.form['eqpt_code']
        sub_eqpt   = request.form.get('sub_eqpt_code','')
        grade_code = request.form.get('grade_code') or None
        conn = get_db()
        try:
            shop = conn.execute("SELECT shop_desc FROM eqpt_master WHERE shop_code=? LIMIT 1",(shop_code,)).fetchone()
            shop_desc = shop['shop_desc'] if shop else ''
            fmt = '%Y-%m-%dT%H:%M'
            dt_from = datetime.strptime(delay_from, fmt)
            dt_upto = datetime.strptime(delay_upto, fmt)
            if dt_upto <= dt_from:
                raise ValueError("Delay Upto must be after Delay From.")
            duration = (dt_upto - dt_from).total_seconds() / 60
            conn.execute('''INSERT INTO delays (shop_code,shop_desc,eqpt_code,sub_eqpt_code,agency,
                delay_from,delay_upto,delay_duration,delay_desc,grade_code,user_entered,timestamp)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))''',
                (shop_code,shop_desc,eqpt_code,sub_eqpt,agency,delay_from,delay_upto,duration,delay_desc,grade_code,session['user']))
            conn.commit()
            flash(f'Delay recorded! Duration: {duration:.0f} min','success')
        finally:
            conn.close()
    except Exception as e:
        flash(f'Error: {e}','danger')
    return redirect(url_for('delay_entry'))

# ── USER MANAGEMENT ────────────────────────────────────────────────────────────
@app.route('/user-management', methods=['GET','POST'])
@admin_required
def user_management():
    if request.method == 'POST':
        action = request.form.get('action')
        conn = get_db()
        try:
            if action == 'add':
                emp_no      = request.form.get('emp_no','').strip().upper()
                emp_name    = request.form.get('emp_name','').strip()
                dept        = request.form.get('dept','').strip()
                designation = request.form.get('designation','').strip()
                role        = request.form.get('role','').strip()
                password    = request.form.get('password','').strip()

                # Validate required fields
                if not emp_no:
                    flash('Employee ID is required.', 'danger')
                elif not emp_name:
                    flash('Employee Name is required.', 'danger')
                elif not password:
                    flash('Password is required.', 'danger')
                elif len(password) < 4:
                    flash('Password must be at least 4 characters.', 'danger')
                elif role not in ROLES:
                    flash('Invalid role selected.', 'danger')
                else:
                    try:
                        conn.execute(
                            "INSERT INTO users (emp_no,password,emp_name,dept,designation,role,active) VALUES (?,?,?,?,?,?,1)",
                            (emp_no, hash_password(password), emp_name, dept, designation, role)
                        )
                        conn.commit()
                        flash(f'User {emp_no} added successfully!', 'success')
                    except sqlite3.IntegrityError:
                        flash(f'Employee ID "{emp_no}" already exists.', 'danger')

            elif action == 'update_role':
                emp_no = request.form.get('emp_no','')
                role   = request.form.get('role','')
                if role not in ROLES:
                    flash('Invalid role.', 'danger')
                else:
                    conn.execute("UPDATE users SET role=? WHERE emp_no=?", (role, emp_no))
                    conn.commit()
                    flash(f'Role updated for {emp_no}.', 'success')

            elif action == 'toggle_status':
                emp_no = request.form.get('emp_no','')
                if emp_no == session.get('user'):
                    flash('You cannot deactivate your own account.', 'danger')
                else:
                    conn.execute(
                        "UPDATE users SET active=CASE WHEN active=1 THEN 0 ELSE 1 END WHERE emp_no=?",
                        (emp_no,)
                    )
                    conn.commit()
                    flash('User status updated.', 'success')

            elif action == 'reset_password':
                emp_no   = request.form.get('emp_no','')
                new_pass = request.form.get('new_password','').strip()
                if not new_pass:
                    flash('New password cannot be empty.', 'danger')
                elif len(new_pass) < 4:
                    flash('Password must be at least 4 characters.', 'danger')
                else:
                    conn.execute(
                        "UPDATE users SET password=? WHERE emp_no=?",
                        (hash_password(new_pass), emp_no)
                    )
                    conn.commit()
                    flash(f'Password reset for {emp_no}.', 'success')

        except Exception as e:
            flash(f'An unexpected error occurred: {str(e)}', 'danger')
        finally:
            conn.close()   # always close — this was the root cause of the 500

        return redirect(url_for('user_management'))

    # GET request
    conn = get_db()
    try:
        users      = conn.execute("SELECT * FROM users ORDER BY emp_no").fetchall()
        user_stats = {r['user_entered']: r['c'] for r in conn.execute("SELECT user_entered, COUNT(*) c FROM delays GROUP BY user_entered").fetchall()}
        depts      = [r['dept'] for r in conn.execute("SELECT DISTINCT dept FROM users WHERE dept IS NOT NULL AND dept != '' ORDER BY dept").fetchall()]
    finally:
        conn.close()
    return render_template('user_management.html', users=users, roles=ROLES, user_stats=user_stats, depts=depts)

# ── REPORTS ────────────────────────────────────────────────────────────────────
@app.route('/reports')
@reports_required
def reports():
    conn = get_db()
    shops = conn.execute("SELECT DISTINCT shop_code, shop_desc FROM eqpt_master ORDER BY shop_code").fetchall()
    conn.close()
    return render_template('reports.html', shops=shops, agencies=AGENCIES)

@app.route('/api/report-data')
@reports_required
def report_data():
    shop_code = request.args.get('shop_code','')
    from_date = request.args.get('from_date','')
    to_date   = request.args.get('to_date','')
    agency    = request.args.get('agency','')
    limit     = int(request.args.get('limit', 500))
    q, p = "SELECT * FROM delays WHERE 1=1", []
    if shop_code: q+=" AND shop_code=?"; p.append(int(shop_code))
    if from_date: q+=" AND date(delay_from)>=?"; p.append(from_date)
    if to_date:   q+=" AND date(delay_from)<=?"; p.append(to_date)
    if agency:    q+=" AND agency=?"; p.append(agency)
    q += f" ORDER BY delay_from DESC LIMIT {limit}"
    conn = get_db()
    rows = conn.execute(q,p).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/chart-data')
@reports_required
def chart_data():
    shop_code = request.args.get('shop_code','')
    from_date = request.args.get('from_date','')
    to_date   = request.args.get('to_date','')
    agency    = request.args.get('agency','')
    group_by  = request.args.get('group_by','monthly')

    p, f = [], "WHERE 1=1"
    if shop_code: f+=" AND shop_code=?"; p.append(int(shop_code))
    if from_date: f+=" AND date(delay_from)>=?"; p.append(from_date)
    if to_date:   f+=" AND date(delay_from)<=?"; p.append(to_date)
    if agency:    f+=" AND agency=?"; p.append(agency)

    grp_expr = {
        'daily':   "date(delay_from)",
        'weekly':  "strftime('%Y-W%W', delay_from)",
        'monthly': "strftime('%Y-%m', delay_from)",
        'yearly':  "strftime('%Y', delay_from)",
    }.get(group_by, "strftime('%Y-%m', delay_from)")

    conn = get_db()
    def q(sql): return conn.execute(sql, p).fetchall()

    agency_rows = q(f"SELECT agency,COUNT(*) c,COALESCE(SUM(delay_duration),0) mins FROM delays {f} GROUP BY agency ORDER BY mins DESC")
    shop_rows   = q(f"SELECT shop_desc,COUNT(*) c,COALESCE(SUM(delay_duration),0) mins FROM delays {f} GROUP BY shop_desc ORDER BY mins DESC")
    eqpt_rows   = q(f"SELECT eqpt_code,COUNT(*) c,COALESCE(SUM(delay_duration),0) mins FROM delays {f} AND eqpt_code!='UNKNOWN' GROUP BY eqpt_code ORDER BY mins DESC LIMIT 10")
    trend_rows  = q(f"SELECT {grp_expr} lbl,COUNT(*) c,COALESCE(SUM(delay_duration),0) mins FROM delays {f} GROUP BY lbl ORDER BY lbl")
    stacked_rows= q(f"SELECT shop_desc,agency,COALESCE(SUM(delay_duration),0) mins FROM delays {f} GROUP BY shop_desc,agency ORDER BY shop_desc")
    cause_rows  = q(f"SELECT delay_desc,COUNT(*) c FROM delays {f} AND delay_desc IS NOT NULL AND delay_desc!='' GROUP BY delay_desc ORDER BY c DESC LIMIT 10")

    conn.close()
    return jsonify({
        'agency':    [{'label':r['agency'],   'count':r['c'],'mins':r['mins']} for r in agency_rows],
        'shop':      [{'label':r['shop_desc'],'count':r['c'],'mins':r['mins']} for r in shop_rows],
        'equipment': [{'label':r['eqpt_code'],'count':r['c'],'mins':r['mins']} for r in eqpt_rows],
        'trend':     [{'label':r['lbl'],      'count':r['c'],'mins':r['mins']} for r in trend_rows],
        'stacked':   [{'shop':r['shop_desc'],'agency':r['agency'],'mins':r['mins']} for r in stacked_rows],
        'causes':    [{'label':r['delay_desc'],'count':r['c']} for r in cause_rows],
    })

@app.route('/api/dashboard-kpi')
@login_required
def dashboard_kpi():
    conn = get_db()
    data = {
        'total': conn.execute("SELECT COUNT(*) FROM delays").fetchone()[0],
        'total_hours': conn.execute("SELECT COALESCE(SUM(delay_duration),0)/60.0 FROM delays").fetchone()[0],
        'shops': conn.execute("SELECT COUNT(DISTINCT shop_desc) FROM delays").fetchone()[0],
        'users': conn.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0],
    }
    conn.close()
    return jsonify(data)

if __name__ == '__main__':
    import sqlite3 as _s, stat as _stat
    init_db()
    # Ensure database file is writable (fixes "readonly database" error)
    try:
        import os as _os
        _os.chmod(DB_PATH, _stat.S_IRUSR | _stat.S_IWUSR | _stat.S_IRGRP | _stat.S_IWGRP | _stat.S_IROTH)
    except Exception:
        pass
    app.run(host='0.0.0.0', debug=False, port=5000)
