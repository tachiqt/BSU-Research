"""
Migration script to import Excel faculty data into SQLite database
Run this script once to migrate data from Excel to database
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from faculty_reader import load_faculty_from_excel
from database import init_database, import_faculty_from_list, get_faculty_count

def migrate_excel_to_db(excel_path: str = None, sheet_name: str = 'Reference', clear_existing: bool = True):
    """
    Migrate Excel faculty data to SQLite database
    
    Args:
        excel_path: Path to Excel file (defaults to img/ref.xlsx)
        sheet_name: Sheet name to read from (defaults to 'Reference')
        clear_existing: Whether to clear existing data before import
    """
    print("=" * 60)
    print("Excel to Database Migration")
    print("=" * 60)
    
    # Initialize database
    print("\n1. Initializing database...")
    init_database()
    
    # Load faculty from Excel
    print(f"\n2. Loading faculty from Excel...")
    if excel_path:
        print(f"   Excel file: {excel_path}")
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        excel_path = os.path.join(project_root, 'img', 'ref.xlsx')
        print(f"   Excel file: {excel_path} (default)")
    
    print(f"   Sheet name: {sheet_name}")
    
    try:
        faculty_list = load_faculty_from_excel(excel_path, sheet_name=sheet_name)
        print(f"   ✓ Loaded {len(faculty_list)} faculty members from Excel")
    except Exception as e:
        print(f"   ✗ Error loading Excel: {str(e)}")
        return False
    
    # Import to database
    print(f"\n3. Importing to database...")
    try:
        import_faculty_from_list(faculty_list, clear_existing=clear_existing)
        print(f"   ✓ Successfully imported {len(faculty_list)} faculty members")
    except Exception as e:
        print(f"   ✗ Error importing to database: {str(e)}")
        return False
    
    # Verify
    print(f"\n4. Verifying database...")
    count = get_faculty_count()
    print(f"   ✓ Database contains {count} faculty members")
    
    print("\n" + "=" * 60)
    print("Migration completed successfully!")
    print("=" * 60)
    return True

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate Excel faculty data to SQLite database')
    parser.add_argument('--excel', type=str, help='Path to Excel file (defaults to img/ref.xlsx)')
    parser.add_argument('--sheet', type=str, default='Reference', help='Sheet name (default: Reference)')
    parser.add_argument('--keep-existing', action='store_true', help='Keep existing data (append instead of replace)')
    
    args = parser.parse_args()
    
    success = migrate_excel_to_db(
        excel_path=args.excel,
        sheet_name=args.sheet,
        clear_existing=not args.keep_existing
    )
    
    sys.exit(0 if success else 1)
