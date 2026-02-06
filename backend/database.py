import os
import json
from typing import List, Dict, Optional, Any

DATABASE_URL = os.getenv('DATABASE_URL')
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'faculty.db')

_use_postgres = bool(DATABASE_URL and DATABASE_URL.startswith('postgresql'))

if _use_postgres:
    import psycopg2
    from psycopg2 import extras as pg_extras
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = 'postgresql://' + DATABASE_URL.split('://', 1)[1]


def _placeholder(n: int) -> str:
    return '?' if not _use_postgres else '%s'


def get_db_connection():
    if _use_postgres:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _cursor(conn):
    if _use_postgres:
        return conn.cursor(cursor_factory=pg_extras.RealDictCursor)
    return conn.cursor()


def _row_to_dict(row, keys=None) -> Optional[Dict]:
    if row is None:
        return None
    if hasattr(row, 'keys'):
        return dict(row) if keys is None else {k: row.get(k) for k in keys}
    return dict(zip(keys or [], row))


def init_database():
    conn = get_db_connection()
    cur = _cursor(conn)

    if _use_postgres:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS faculty (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                position TEXT,
                name_variants TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_faculty_name ON faculty(name)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_faculty_department ON faculty(department)')
    else:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS faculty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                position TEXT,
                name_variants TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_faculty_name ON faculty(name)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_faculty_department ON faculty(department)')

    conn.commit()
    conn.close()
    print(f"Database initialized ({'PostgreSQL' if _use_postgres else 'SQLite'})")


def get_distinct_departments() -> List[str]:
    p = _placeholder(1)
    conn = get_db_connection()
    cur = _cursor(conn)
    cur.execute(
        "SELECT DISTINCT department FROM faculty WHERE department IS NOT NULL AND TRIM(department) != '' ORDER BY department"
    )
    rows = cur.fetchall()
    conn.close()
    return [row['department'] for row in rows]


def load_faculty_from_db() -> List[Dict]:
    conn = get_db_connection()
    cur = _cursor(conn)
    cur.execute('SELECT id, name, department, position, name_variants FROM faculty ORDER BY name')
    rows = cur.fetchall()
    conn.close()

    faculty_list = []
    for row in rows:
        r = dict(row) if _use_postgres else row
        name_variants = []
        if r.get('name_variants'):
            try:
                name_variants = json.loads(r['name_variants'])
            except Exception:
                name_variants = []
        faculty_list.append({
            'id': r['id'],
            'name': r['name'],
            'department': r['department'],
            'position': r.get('position') or '',
            'name_variants': name_variants,
            'original_name': r['name']
        })
    return faculty_list


def import_faculty_from_list(faculty_list: List[Dict], clear_existing: bool = True, skip_duplicates: bool = True):
    p = _placeholder(1)
    conn = get_db_connection()
    cur = _cursor(conn)

    if clear_existing:
        cur.execute('DELETE FROM faculty')
        print("Cleared existing faculty data")

    imported_count = 0
    skipped_count = 0
    duplicates = []

    for faculty in faculty_list:
        name_clean = faculty['name'].strip()

        if skip_duplicates and not clear_existing:
            cur.execute(
                'SELECT id FROM faculty WHERE LOWER(TRIM(name)) = LOWER(TRIM(' + p + '))',
                (name_clean,)
            )
            if cur.fetchone():
                skipped_count += 1
                duplicates.append(name_clean)
                continue

        name_variants_json = json.dumps(faculty.get('name_variants', []))
        cur.execute(
            'INSERT INTO faculty (name, department, position, name_variants) VALUES (' + p + ', ' + p + ', ' + p + ', ' + p + ')',
            (
                name_clean,
                faculty.get('department', '').strip(),
                faculty.get('position', '').strip(),
                name_variants_json
            )
        )
        imported_count += 1

    conn.commit()
    conn.close()
    print(f"Imported {imported_count} faculty members, skipped {skipped_count} duplicates")
    return {
        'imported': imported_count,
        'skipped': skipped_count,
        'duplicates': duplicates
    }


def get_faculty_count() -> int:
    conn = get_db_connection()
    cur = _cursor(conn)
    cur.execute('SELECT COUNT(*) as count FROM faculty')
    row = cur.fetchone()
    conn.close()
    return row['count']


def faculty_exists(name: str) -> bool:
    p = _placeholder(1)
    conn = get_db_connection()
    cur = _cursor(conn)
    cur.execute('SELECT id FROM faculty WHERE LOWER(TRIM(name)) = LOWER(TRIM(' + p + '))', (name,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def add_faculty(name: str, department: str, position: str = '', skip_duplicate: bool = True) -> tuple:
    from faculty_reader import _generate_name_variants

    name_clean = name.strip()
    if skip_duplicate and faculty_exists(name_clean):
        return (None, False)

    name_variants = _generate_name_variants(name_clean)
    name_variants_json = json.dumps(name_variants)
    p = _placeholder(4)

    conn = get_db_connection()
    cur = _cursor(conn)
    if _use_postgres:
        cur.execute(
            'INSERT INTO faculty (name, department, position, name_variants) VALUES (' + p + ', ' + p + ', ' + p + ', ' + p + ') RETURNING id',
            (name_clean, department.strip(), position.strip(), name_variants_json)
        )
        faculty_id = cur.fetchone()['id']
    else:
        cur.execute(
            'INSERT INTO faculty (name, department, position, name_variants) VALUES (' + p + ', ' + p + ', ' + p + ', ' + p + ')',
            (name_clean, department.strip(), position.strip(), name_variants_json)
        )
        faculty_id = cur.lastrowid
    conn.commit()
    conn.close()
    return (faculty_id, True)


def update_faculty(faculty_id: int, name: str, department: str, position: str = '') -> bool:
    from faculty_reader import _generate_name_variants

    name_variants = _generate_name_variants(name)
    name_variants_json = json.dumps(name_variants)
    p = _placeholder(5)
    conn = get_db_connection()
    cur = _cursor(conn)
    if _use_postgres:
        cur.execute(
            'UPDATE faculty SET name = ' + p + ', department = ' + p + ', position = ' + p + ', name_variants = ' + p + ', updated_at = CURRENT_TIMESTAMP WHERE id = ' + p,
            (name.strip(), department.strip(), position.strip(), name_variants_json, faculty_id)
        )
    else:
        cur.execute(
            'UPDATE faculty SET name = ?, department = ?, position = ?, name_variants = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (name.strip(), department.strip(), position.strip(), name_variants_json, faculty_id)
        )
    success = cur.rowcount > 0
    conn.commit()
    conn.close()
    return success


def delete_faculty(faculty_id: int) -> bool:
    p = _placeholder(1)
    conn = get_db_connection()
    cur = _cursor(conn)
    cur.execute('DELETE FROM faculty WHERE id = ' + p, (faculty_id,))
    success = cur.rowcount > 0
    conn.commit()
    conn.close()
    return success


def get_faculty_by_id(faculty_id: int) -> Optional[Dict]:
    p = _placeholder(1)
    conn = get_db_connection()
    cur = _cursor(conn)
    cur.execute('SELECT id, name, department, position, name_variants FROM faculty WHERE id = ' + p, (faculty_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None
    r = dict(row) if _use_postgres else row
    name_variants = []
    if r.get('name_variants'):
        try:
            name_variants = json.loads(r['name_variants'])
        except Exception:
            name_variants = []
    return {
        'id': r['id'],
        'name': r['name'],
        'department': r['department'],
        'position': r.get('position') or '',
        'name_variants': name_variants
    }
