import sqlite3
import pandas as pd
import hashlib
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── USER TABLE ──────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        emp_no      TEXT PRIMARY KEY,
        password    TEXT NOT NULL,
        emp_name    TEXT NOT NULL,
        dept        TEXT,
        designation TEXT,
        role        TEXT NOT NULL DEFAULT 'dept_user',
        active      INTEGER NOT NULL DEFAULT 1
    )''')

    # ── EQUIPMENT MASTER ─────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS eqpt_master (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_code     INTEGER NOT NULL,
        shop_desc     TEXT NOT NULL,
        eqpt_code     TEXT NOT NULL,
        sub_eqpt_code TEXT
    )''')

    # ── GRADE MASTER ─────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS grade_master (
        grade_code INTEGER PRIMARY KEY,
        grade_desc TEXT NOT NULL
    )''')

    # ── MILL MASTER ──────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS mill_master (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        mill_code   INTEGER,
        sec_code    INTEGER,
        size_code   INTEGER,
        mill_desc   TEXT,
        sec_desc    TEXT,
        sec_uentry  TEXT,
        size_uentry TEXT
    )''')

    # ── DELAYS DATA ──────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS delays (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_code      INTEGER NOT NULL,
        shop_desc      TEXT NOT NULL,
        eqpt_code      TEXT NOT NULL,
        sub_eqpt_code  TEXT,
        agency         TEXT NOT NULL,
        delay_from     TEXT NOT NULL,
        delay_upto     TEXT NOT NULL,
        delay_duration REAL,
        delay_desc     TEXT,
        grade_code     INTEGER,
        user_entered   TEXT,
        timestamp      TEXT DEFAULT (datetime('now','localtime'))
    )''')

    conn.commit()

    # ── SEED DEFAULT ADMIN USER ──────────────────────────────────
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)", (
            'ADMIN', hash_password('admin123'), 'System Administrator',
            'IT', 'Administrator', 'sys_admin', 1
        ))
        c.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)", (
            'USER1', hash_password('user123'), 'Demo User',
            'RMHP', 'Engineer', 'dept_user', 1
        ))
        conn.commit()
        print("Default users created: ADMIN/admin123, USER1/user123")

    # ── LOAD EQUIPMENT MASTER ────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM eqpt_master")
    if c.fetchone()[0] == 0:
        df = pd.read_excel(os.path.join(os.path.dirname(__file__), 'data', 'master_data.xlsx'))
        df.columns = ['shop_code', 'shop_desc', 'eqpt_code', 'sub_eqpt_code']
        df.to_sql('eqpt_master', conn, if_exists='append', index=False)
        print(f"Loaded {len(df)} equipment records")

    # ── LOAD GRADE MASTER ────────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM grade_master")
    if c.fetchone()[0] == 0:
        gdf = pd.read_excel(os.path.join(os.path.dirname(__file__), 'data', 'GRADE_MASTER.XLSX'))
        gdf.columns = ['grade_code', 'grade_desc']
        gdf.to_sql('grade_master', conn, if_exists='append', index=False)
        print(f"Loaded {len(gdf)} grade records")

    # ── LOAD MILL MASTER ─────────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM mill_master")
    if c.fetchone()[0] == 0:
        mdf = pd.read_excel(os.path.join(os.path.dirname(__file__), 'data', 'MILL_MASTER.XLSX'))
        mdf.columns = ['mill_code','sec_code','size_code','mill_desc','sec_desc','sec_uentry','size_uentry']
        mdf.to_sql('mill_master', conn, if_exists='append', index=False)
        print(f"Loaded {len(mdf)} mill records")

    # ── LOAD HISTORICAL DELAYS ───────────────────────────────────
    c.execute("SELECT COUNT(*) FROM delays")
    if c.fetchone()[0] == 0:
        csv_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_delays_data.csv')
        if os.path.exists(csv_path):
            AGENCY_MAP = {
                'O':'Operations','M':'Mechanical','E':'Electrical',
                'SD':'Shutdown','S':'Shutdown','MIS':'Miscellaneous',
                'ID':'Idle','C':'Civil','CR':'Operations','MS':'Miscellaneous',
                'P':'Operations','R':'Operations','IR':'Operations',
                'I':'Idle','0':'Miscellaneous',
            }
            SHOP_MAP = {
                1:'RMHP',2:'RMHP',3:'CO',4:'SP',5:'BF',6:'SMS',
                7:'BAR MILL',8:'WRM',9:'MMSM',10:'TPP',11:'UTIL',
                12:'OTHER',13:'OTHER',14:'DNW',15:'CRMP'
            }
            def dec_to_hhmm(dec):
                try:
                    dec = float(dec); h = int(dec); m = round((dec-h)*100)
                    if m >= 60: h+=1; m-=60
                    return f'{min(h,23):02d}:{m:02d}'
                except: return '00:00'
            def parse_dt(date_str, time_dec):
                try:
                    from datetime import datetime
                    d = datetime.strptime(str(date_str).strip(),'%d-%m-%Y')
                    return d.strftime('%Y-%m-%d')+'T'+dec_to_hhmm(time_dec)
                except: return None
            import pandas as pd
            df = pd.read_csv(csv_path)
            records = []
            for _, row in df.iterrows():
                df_val = parse_dt(row['DEL_DATE'], row['DELAY_FROM'])
                du_val = parse_dt(row['DEL_DATE'], row['DELAY_TO'])
                if not df_val or not du_val: continue
                sc = int(row['SHOP_CODE']) if pd.notna(row['SHOP_CODE']) else 0
                records.append((
                    sc, SHOP_MAP.get(sc,'UNKNOWN'),
                    str(row['EQPT']).strip() if pd.notna(row['EQPT']) else 'UNKNOWN',
                    str(row['SUB_EQPT']).strip() if pd.notna(row['SUB_EQPT']) else None,
                    AGENCY_MAP.get(str(row['AGENCY_CODE']).strip(), str(row['AGENCY_CODE']).strip()),
                    df_val, du_val,
                    float(row['DELAY_DURN']) if pd.notna(row['DELAY_DURN']) else None,
                    str(row['REMARKS']).strip() if pd.notna(row['REMARKS']) else None,
                    None,
                    str(row['USER_ENTERED']).strip() if pd.notna(row['USER_ENTERED']) else 'IMPORTED',
                    str(row['TMSTP_ENTERED']).strip() if pd.notna(row['TMSTP_ENTERED']) else None,
                ))
            c.executemany('''INSERT INTO delays
                (shop_code,shop_desc,eqpt_code,sub_eqpt_code,agency,
                 delay_from,delay_upto,delay_duration,delay_desc,
                 grade_code,user_entered,timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', records)
            conn.commit()
            print(f"Loaded {len(records)} historical delay records")

    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()
