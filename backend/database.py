import sqlite3
import os
import json
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'faculty.db')

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize the database schema"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
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
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_faculty_name ON faculty(name)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_faculty_department ON faculty(department)
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized at: {DB_PATH}")

def load_faculty_from_db() -> List[Dict]:
    """Load all faculty from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, name, department, position, name_variants FROM faculty ORDER BY name')
    rows = cursor.fetchall()
    conn.close()
    
    faculty_list = []
    for row in rows:
        name_variants = []
        if row['name_variants']:
            try:
                name_variants = json.loads(row['name_variants'])
            except:
                name_variants = []
        
        faculty_list.append({
            'id': row['id'],
            'name': row['name'],
            'department': row['department'],
            'position': row['position'] or '',
            'name_variants': name_variants,
            'original_name': row['name']
        })
    
    return faculty_list

def import_faculty_from_list(faculty_list: List[Dict], clear_existing: bool = True, skip_duplicates: bool = True):
    """
    Import faculty list into database
    
    Returns:
        dict: {'imported': count, 'skipped': count, 'duplicates': list}
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if clear_existing:
        cursor.execute('DELETE FROM faculty')
        print("Cleared existing faculty data")
    
    imported_count = 0
    skipped_count = 0
    duplicates = []
    
    for faculty in faculty_list:
        name_clean = faculty['name'].strip()
        
        # Check for duplicates if not clearing existing
        if skip_duplicates and not clear_existing:
            cursor.execute('SELECT id FROM faculty WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))', (name_clean,))
            if cursor.fetchone():
                skipped_count += 1
                duplicates.append(name_clean)
                continue
        
        name_variants_json = json.dumps(faculty.get('name_variants', []))
        cursor.execute('''
            INSERT INTO faculty (name, department, position, name_variants)
            VALUES (?, ?, ?, ?)
        ''', (
            name_clean,
            faculty.get('department', '').strip(),
            faculty.get('position', '').strip(),
            name_variants_json
        ))
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
    """Get total number of faculty in database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as count FROM faculty')
    count = cursor.fetchone()['count']
    conn.close()
    return count

def faculty_exists(name: str) -> bool:
    """Check if a faculty member with the same name already exists"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM faculty WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))', (name,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_faculty(name: str, department: str, position: str = '', skip_duplicate: bool = True) -> tuple:
    """
    Add a single faculty member
    
    Returns:
        tuple: (faculty_id, is_new) - faculty_id is None if duplicate and skip_duplicate=True
    """
    from faculty_reader import _generate_name_variants
    
    name_clean = name.strip()
    
    # Check for duplicates
    if skip_duplicate and faculty_exists(name_clean):
        return (None, False)
    
    name_variants = _generate_name_variants(name_clean)
    name_variants_json = json.dumps(name_variants)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO faculty (name, department, position, name_variants)
        VALUES (?, ?, ?, ?)
    ''', (name_clean, department.strip(), position.strip(), name_variants_json))
    
    faculty_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return (faculty_id, True)

def update_faculty(faculty_id: int, name: str, department: str, position: str = '') -> bool:
    """Update a faculty member"""
    from faculty_reader import _generate_name_variants
    
    name_variants = _generate_name_variants(name)
    name_variants_json = json.dumps(name_variants)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE faculty 
        SET name = ?, department = ?, position = ?, name_variants = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (name.strip(), department.strip(), position.strip(), name_variants_json, faculty_id))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def delete_faculty(faculty_id: int) -> bool:
    """Delete a faculty member"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM faculty WHERE id = ?', (faculty_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def get_faculty_by_id(faculty_id: int) -> Optional[Dict]:
    """Get a single faculty member by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, department, position, name_variants FROM faculty WHERE id = ?', (faculty_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    name_variants = []
    if row['name_variants']:
        try:
            name_variants = json.loads(row['name_variants'])
        except:
            name_variants = []
    
    return {
        'id': row['id'],
        'name': row['name'],
        'department': row['department'],
        'position': row['position'] or '',
        'name_variants': name_variants
    }
