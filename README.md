# Centralized Delay Analysis System
## Vizag Steel Plant — Rashtriya Ispat Nigam Ltd.

---

## Setup Instructions

### 1. Install Python
Make sure Python 3.8+ is installed on your PC.

### 2. Install Dependencies
Open a terminal/command prompt in the project folder and run:
```
pip install -r requirements.txt
```

### 3. Run the Application
```
python app.py
```

### 4. Open in Browser
Go to: **http://localhost:5000**

---

## Default Login Credentials

| Employee No. | Password   | Role       |
|-------------|------------|------------|
| ADMIN       | admin123   | sys_admin  |
| USER1       | user123    | dept_user  |

> **Change these passwords after first login via User Management.**

---

## Pages

| Page | URL | Access |
|------|-----|--------|
| Login | `/login` | All |
| Delay Entry | `/delay-entry` | All logged-in users |
| User Management | `/user-management` | Admins only |
| Reports | `/reports` | All logged-in users |

---

## Roles

| Role | Permissions |
|------|------------|
| `sys_admin` | Full access to all pages and all departments |
| `dept_admin` | Manage department users + view reports |
| `dept_user` | Delay entry only |
| `ppm_admin` | Reports and analysis + manage ppm users |
| `ppm_user` | View reports only |

---

## Project Structure

```
delay_system/
├── app.py              ← Main Flask application
├── init_db.py          ← Database setup script
├── database.db         ← SQLite database (auto-created)
├── requirements.txt    ← Python dependencies
├── data/               ← Master data Excel files
│   ├── master_data.xlsx
│   ├── GRADE_MASTER.XLSX
│   ├── MILL_MASTER.XLSX
│   └── MATL_DESC.xlsx
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── delay_entry.html
│   ├── user_management.html
│   └── reports.html
└── static/
    ├── css/
    └── js/
```

---

## Notes
- The database is auto-created on first run with all master data pre-loaded.
- All 123 equipment records from the master list are pre-loaded.
- All 343 steel grades are available in the Grade dropdown.
- Reports support export to CSV.
- Graphical reports include: Agency-wise, Shop-wise, Equipment-wise, and Trend charts.
