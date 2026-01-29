from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
from dotenv import load_dotenv
from scopus import fetch_scopus_data, search_organization_id, filter_publications_by_faculty

load_dotenv()
app = Flask(__name__)
CORS(app)

# Initialize database on startup and auto-seed from Excel if empty (e.g. on Render/Replit)
try:
    from database import init_database, get_faculty_count, import_faculty_from_list
    init_database()
    if get_faculty_count() == 0:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(backend_dir)
        # Try multiple paths: repo root (../img/ref.xlsx), then backend folder (ref.xlsx)
        for excel_path in [
            os.path.join(project_root, 'img', 'ref.xlsx'),
            os.path.join(backend_dir, 'ref.xlsx'),
        ]:
            if os.path.exists(excel_path):
                try:
                    from faculty_reader import load_faculty_from_excel
                    faculty_list = load_faculty_from_excel(excel_path, sheet_name=None)
                    if faculty_list:
                        result = import_faculty_from_list(faculty_list, clear_existing=True, skip_duplicates=False)
                        print(f"Auto-seeded {result['imported']} faculty from {excel_path}")
                    break
                except Exception as seed_err:
                    print(f"Auto-seed from {excel_path} failed: {seed_err}")
                break
        else:
            print("No ref.xlsx found for auto-seed (checked ../img/ref.xlsx and backend/ref.xlsx)")
except Exception as e:
    print(f"Warning: Could not initialize database: {e}")

@app.route('/api/scholar/publications', methods=['GET'])
def get_publications():
    try:
        organization_name = request.args.get('organization_name', 'Batangas State University')
        organization_id = request.args.get('organization_id')
        
        scopus_data = fetch_scopus_data(
            organization_name=organization_name if organization_name else None,
            organization_id=organization_id if organization_id else None
        )
        
        if scopus_data.get('error'):
            return jsonify({
                'error': scopus_data.get('error'),
                'organization_name': organization_name,
                'publications': [],
                'total_publications': 0,
                'citations': {},
                'statistics': {}
            }), 503  
        
        return jsonify({
            'organization_name': scopus_data.get('statistics', {}).get('organization_name', organization_name),
            'publications': scopus_data.get('publications', []),
            'total_publications': scopus_data.get('total_publications', 0),
            'citations': scopus_data.get('citations', {}),
            'statistics': scopus_data.get('statistics', {})
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/publications/titles', methods=['GET'])
def get_publication_titles():
    """Get publication titles from Scopus with pagination"""
    try:
        organization_name = request.args.get('organization_name', 'Batangas State University')
        organization_id = request.args.get('organization_id')
        year_filter = request.args.get('year', '').strip()
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        
        # Validate pagination parameters
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 10
        
        scopus_data = fetch_scopus_data(
            organization_name=organization_name if organization_name else None,
            organization_id=organization_id if organization_id else None
        )
        
        if scopus_data.get('error'):
            return jsonify({
                'error': scopus_data.get('error'),
                'titles': []
            }), 503
        
        all_publications = scopus_data.get('publications', [])
        
        # Apply year filter if provided
        if year_filter:
            try:
                filter_year = int(year_filter)
                filtered_publications = []
                for p in all_publications:
                    pub_year = p.get('year')
                    if pub_year:
                        if isinstance(pub_year, str):
                            try:
                                pub_year = int(pub_year.split('/')[0]) if '/' in pub_year else int(pub_year)
                            except (ValueError, AttributeError):
                                continue
                        if isinstance(pub_year, (int, float)) and int(pub_year) == filter_year:
                            filtered_publications.append(p)
                all_publications = filtered_publications
            except (ValueError, TypeError):
                pass
        
        # Calculate pagination
        total_count = len(all_publications)
        total_pages = (total_count + limit - 1) // limit  # Ceiling division
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        
        # Get paginated publications
        paginated_publications = all_publications[start_idx:end_idx]
        
        # Extract titles with additional info
        titles = []
        for idx, pub in enumerate(paginated_publications):
            global_number = start_idx + idx + 1  # Calculate global position
            titles.append({
                'number': global_number,
                'title': pub.get('title', 'Untitled Publication'),
                'year': pub.get('year'),
                'authors': pub.get('authors', ''),
                'venue': pub.get('venue', ''),
                'citations': pub.get('citations', 0),
                'link': pub.get('link', ''),
                'doi': pub.get('doi', '')
            })
        
        # Get available years from all publications (before filtering)
        all_pubs_for_years = scopus_data.get('publications', [])
        available_years = []
        for p in all_pubs_for_years:
            year = p.get('year')
            if year:
                try:
                    if isinstance(year, str):
                        year = int(year.split('/')[0]) if '/' in year else int(year)
                    if isinstance(year, (int, float)):
                        available_years.append(int(year))
                except (ValueError, TypeError):
                    continue
        available_years = sorted(set(available_years), reverse=True)
        
        return jsonify({
            'titles': titles,
            'total_count': total_count,
            'page': page,
            'limit': limit,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_previous': page > 1,
            'organization_name': scopus_data.get('statistics', {}).get('organization_name', organization_name),
            'available_years': available_years
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e), 'titles': []}), 500

@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    try:
        year_filter = request.args.get('year', '').strip()
        organization_name = request.args.get('organization_name', 'Batangas State University')
        organization_id = request.args.get('organization_id')
        
        scopus_data = fetch_scopus_data(
            organization_name=organization_name if organization_name else None,
            organization_id=organization_id if organization_id else None
        )
        
        if scopus_data.get('error'):
            return jsonify({
                'error': scopus_data.get('error'),
                'total_publications': 0,
                'college_counts': {
                    'engineering': 0,
                    'informatics_computing': 0,
                    'engineering_technology': 0,
                    'architecture_design': 0
                },
                'quarterly_counts': {
                    'q1': 0,
                    'q2': 0,
                    'q3': 0,
                    'q4': 0
                }
            }), 503  
        
        all_publications = scopus_data.get('publications', [])
        
        # Apply year filter FIRST (if specified) - this affects both totals and department counts
        if year_filter:
            try:
                filter_year = int(year_filter)
                year_filtered_publications = []
                for p in all_publications:
                    pub_year = p.get('year')
                    if pub_year:
                        if isinstance(pub_year, str):
                            try:
                                pub_year = int(pub_year.split('/')[0]) if '/' in pub_year else int(pub_year)
                            except (ValueError, AttributeError):
                                continue
                        if isinstance(pub_year, (int, float)) and int(pub_year) == filter_year:
                            year_filtered_publications.append(p)
                # Use year-filtered publications for all further processing
                publications = year_filtered_publications
                print(f"Applied year filter: {filter_year} - {len(publications)} publications")
            except (ValueError, TypeError) as e:
                print(f"Error filtering by year: {e}")
                publications = all_publications
        else:
            publications = all_publications
        
        # Apply faculty filtering for department counts (using year-filtered publications if year filter is active)
        department_counts = {}
        faculty_filtered_publications = []
        
        # Default Excel file path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        default_excel_path = os.path.join(project_root, 'img', 'ref.xlsx')
        
        # Use provided excel_file or default
        excel_file = request.args.get('excel_file')
        if not excel_file:
            excel_file = default_excel_path if os.path.exists(default_excel_path) else None
        
        if excel_file and os.path.exists(excel_file):
            try:
                from faculty_reader import load_faculty_from_db_or_excel
                sheet_name = request.args.get('sheet_name', 'Reference')
                faculty_list = load_faculty_from_db_or_excel(excel_file, sheet_name=sheet_name, prefer_db=True)
                
                if not faculty_list:
                    print(f"Warning: No faculty data loaded from {excel_file}")
                else:
                    # Filter by college if specified
                    college_filter = request.args.get('college_filter', '').strip()
                    if college_filter:
                        faculty_list = [f for f in faculty_list 
                                      if college_filter.lower() in f.get('department', '').lower()]
                    
                    if faculty_list:
                        # Use year-filtered publications for faculty matching (so department counts respect year filter)
                        faculty_results = filter_publications_by_faculty(publications, faculty_list)
                        faculty_filtered_publications = faculty_results['matched_publications']
                        department_counts = faculty_results['department_counts']
                        print(f"Applied faculty filtering: {len(faculty_filtered_publications)} publications matched across {len(department_counts)} departments")
                        if year_filter:
                            print(f"  (Year filter: {year_filter} is applied to department counts)")
                    else:
                        print(f"Warning: No faculty members found after filtering")
            except Exception as e:
                import traceback
                print(f"Warning: Could not apply faculty filtering: {str(e)}")
                print(f"Traceback: {traceback.format_exc()}")
        
        # Total publications: Use ALL Scopus publications (not filtered by faculty)
        total_publications = len(publications)
        
        # Calculate quarterly counts from ALL Scopus publications (not filtered by faculty)
        quarterly_counts = {
            'q1': 0, 
            'q2': 0,  
            'q3': 0, 
            'q4': 0  
        }
        
        # Also calculate quarterly counts per department (only for faculty-matched publications)
        department_quarterly_counts = {}
        
        # Create a set of matched publication IDs for quick lookup
        matched_pub_ids = set()
        matched_pub_dept_map = {}  # Map pub_id to departments
        if faculty_filtered_publications:
            for matched_pub in faculty_filtered_publications:
                pub_id = matched_pub.get('scopus_id') or matched_pub.get('title', '')
                matched_pub_ids.add(pub_id)
                if matched_pub.get('matched_departments'):
                    matched_pub_dept_map[pub_id] = matched_pub.get('matched_departments', [])
        
        # Calculate quarterly counts from ALL publications
        for pub in publications:
            month = pub.get('month')
            if not month:
                date_str = pub.get('date', '')
                if date_str and isinstance(date_str, str):
                    if '/' in date_str:
                        parts = date_str.split('/')
                        if len(parts) >= 2:
                            try:
                                potential_month = int(parts[1])
                                if 1 <= potential_month <= 12:
                                    month = potential_month
                            except (ValueError, IndexError):
                                pass
                    elif '-' in date_str:
                        parts = date_str.split('-')
                        if len(parts) >= 2:
                            try:
                                potential_month = int(parts[1])
                                if 1 <= potential_month <= 12:
                                    month = potential_month
                            except (ValueError, IndexError):
                                pass
            
            if month:
                try:
                    month = int(month)
                    quarter = None
                    if 1 <= month <= 3:
                        quarterly_counts['q1'] += 1
                        quarter = 'q1'
                    elif 4 <= month <= 6:
                        quarterly_counts['q2'] += 1
                        quarter = 'q2'
                    elif 7 <= month <= 9:
                        quarterly_counts['q3'] += 1
                        quarter = 'q3'
                    elif 10 <= month <= 12:
                        quarterly_counts['q4'] += 1
                        quarter = 'q4'
                    
                    # Track quarterly counts per department if this publication was matched to faculty
                    pub_id = pub.get('scopus_id') or pub.get('title', '')
                    if quarter and pub_id in matched_pub_ids and pub_id in matched_pub_dept_map:
                        for dept in matched_pub_dept_map[pub_id]:
                            if dept not in department_quarterly_counts:
                                department_quarterly_counts[dept] = {'q1': 0, 'q2': 0, 'q3': 0, 'q4': 0}
                            department_quarterly_counts[dept][quarter] += 1
                except (ValueError, TypeError) as e:
                    print(f"Error parsing month for publication: {pub.get('title', 'Unknown')}, month={month}, error={e}")
                    pass
        
        available_years = []
        for p in all_publications:
            year = p.get('year')
            if year:
                try:
                    if isinstance(year, str):
                        year = int(year.split('/')[0]) if '/' in year else int(year)
                    if isinstance(year, (int, float)):
                        available_years.append(int(year))
                except (ValueError, TypeError):
                    continue
        available_years = sorted(set(available_years), reverse=True)
        earliest_year = min(available_years) if available_years else None
        current_year = datetime.now().year
        
        # Map department names to college categories
        def map_department_to_college(dept_name):
            """Map department name to college category"""
            if not dept_name:
                return None
            dept_lower = dept_name.lower()
            if 'engineering technology' in dept_lower:
                return 'engineering_technology'
            elif 'informatics' in dept_lower or 'computing' in dept_lower or 'computer' in dept_lower:
                return 'informatics_computing'
            elif 'architecture' in dept_lower or 'design' in dept_lower or 'fine arts' in dept_lower:
                return 'architecture_design'
            elif 'engineering' in dept_lower and 'technology' not in dept_lower:
                return 'engineering'
            return None
        
        # Initialize college counts from department_counts if available
        college_counts = {
            'engineering': 0,
            'informatics_computing': 0,
            'engineering_technology': 0,
            'architecture_design': 0
        }
        
        # If we have department_counts from faculty filtering, use them
        if department_counts:
            for dept_name, count in department_counts.items():
                college = map_department_to_college(dept_name)
                if college:
                    college_counts[college] += count
        
        # Fallback to subject-based categorization if no faculty filtering
        if not department_counts:
            for pub in publications:
                subject_areas = pub.get('subject_areas', [])
            title = pub.get('title', '')
            categorized = False
            subject_strs = []
            if subject_areas:
                for s in subject_areas:
                    if isinstance(s, str):
                        subject_strs.append(s.strip())
                    elif isinstance(s, dict):
                        area_name = s.get('$', '') or s.get('@abbrev', '') or s.get('subject-area', '')
                        if area_name:
                            subject_strs.append(str(area_name).strip())
            
            all_subjects_lower = ' '.join(subject_strs).lower()
            title_lower = title.lower() if title else ''
            combined_text = f"{all_subjects_lower} {title_lower}".lower()
            informatics_keywords = [
                'computer science', 'mathematics', 'math', 'decision sciences', 
                'information systems', 'software', 'data science', 'artificial intelligence', 
                'machine learning', 'computational', 'algorithm', 'programming', 'database', 
                'informatics', 'computing', 'information technology', 'cyber', 
                'network', 'software engineering', 'computer engineering',
                'computer', 'digital system', 'information system', 'control system',
                'data mining', 'big data', 'cloud computing', 'web', 'internet',
                'artificial neural', 'deep learning', 'neural network'
            ]
            has_informatics = False
            if subject_strs:
                for sa in subject_strs:
                    sa_lower = sa.lower()
                    if any(kw in sa_lower for kw in informatics_keywords):
                        has_informatics = True
                        break
                    if 'computer' in sa_lower or 'mathematics' in sa_lower or 'information' in sa_lower:
                        has_informatics = True
                        break
            
            if not has_informatics:
                has_informatics = any(kw in combined_text for kw in informatics_keywords)
                if not has_informatics and title_lower:
                    if any(pattern in title_lower for pattern in ['computer', 'software', 'algorithm', 'data analysis', 'information system', 'computing']):
                        has_informatics = True
            
            if has_informatics:
                    college_counts['informatics_computing'] += 1
                    categorized = True
            if not categorized:
                architecture_keywords = [
                    'architecture', 'architectural', 'design', 'art', 'arts', 'humanities',
                    'visual arts', 'fine arts', 'urban planning', 'landscape architecture',
                    'interior design', 'graphic design', 'industrial design'
                ]
                
                has_architecture = False
                if subject_strs:
                    for sa in subject_strs:
                        sa_lower = sa.lower()
                        if any(kw in sa_lower for kw in architecture_keywords):
                            has_architecture = True
                            break
                
                if not has_architecture:
                    has_architecture = any(kw in combined_text for kw in architecture_keywords)
                
                if has_architecture:
                    college_counts['architecture_design'] += 1
                    categorized = True
            if not categorized:
                eng_tech_keywords = [
                    'engineering technology', 'industrial technology', 'manufacturing technology',
                    'applied technology', 'technology', 'automation', 'robotics', 'mechatronics',
                    'control engineering', 'instrumentation', 'process technology'
                ]
                has_engineering = any(keyword in combined_text for keyword in [
                    'engineering', 'mechanical', 'electrical', 'civil', 'chemical', 
                    'industrial', 'materials', 'energy', 'physics'
                ])
                has_tech_focus = any(kw in combined_text for kw in eng_tech_keywords)
                eng_tech_specific = any(kw in combined_text for kw in [
                    'automation', 'robotics', 'mechatronics', 'control system', 
                    'manufacturing', 'process control', 'industrial automation'
                ])
                
                if has_engineering and (has_tech_focus or eng_tech_specific):
                    college_counts['engineering_technology'] += 1
                    categorized = True
            if not categorized:
                engineering_keywords = [
                    'engineering', 'mechanical engineering', 'electrical engineering',
                    'civil engineering', 'chemical engineering', 'materials science',
                    'energy', 'physics', 'chemistry', 'environmental science',
                    'biochemistry', 'agricultural', 'biological sciences'
                ]
                
                has_engineering_subject = False
                if subject_strs:
                    for sa in subject_strs:
                        sa_lower = sa.lower()
                        if any(kw in sa_lower for kw in ['computer', 'information', 'software', 'computing', 'mathematics']):
                            continue
                        if any(kw in sa_lower for kw in engineering_keywords):
                            has_engineering_subject = True
                            break
                
                if not has_engineering_subject:
                    if not any(kw in combined_text for kw in ['computer science', 'informatics', 'computing', 'software', 'information system']):
                        has_engineering_subject = any(kw in combined_text for kw in engineering_keywords)
                
                if has_engineering_subject:
                    college_counts['engineering'] += 1
                    categorized = True
            if not categorized:
                if any(kw in combined_text for kw in ['engineering', 'mechanical', 'electrical', 'civil', 'chemical', 'materials', 'energy', 'physics', 'chemistry']):
                        college_counts['engineering'] += 1
                else:
                    college_counts['engineering'] += 1
        publications_with_month = sum(1 for p in publications if p.get('month') is not None)
        publications_with_year_only = sum(1 for p in publications if p.get('year') is not None and p.get('month') is None)
        
        return jsonify({
            'total_publications': total_publications,
            'college_counts': college_counts,
            'department_counts': department_counts,  # Department breakdown from Excel faculty matching
            'department_quarterly_counts': department_quarterly_counts,  # Quarterly counts per department
            'quarterly_counts': quarterly_counts,  # Overall quarterly counts (from faculty-filtered publications)
            'available_years': available_years,
            'earliest_year': earliest_year,
            'current_year': current_year,
            'citations': scopus_data.get('citations', {}),
            'statistics': scopus_data.get('statistics', {}),
            'date_statistics': {
                'with_month': publications_with_month,
                'with_year_only': publications_with_year_only,
                'without_date': total_publications - publications_with_month - publications_with_year_only
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/publications/by-faculty', methods=['POST'])
def get_publications_by_faculty():
    """
    Get publications filtered by faculty from Excel file and grouped by department.
    
    Uses the default Excel file: img/ref.xlsx, sheet: Reference
    
    Expected JSON body:
    {
        "excel_file_path": "C:/path/to/faculty.xlsx",  # optional, defaults to img/ref.xlsx
        "sheet_name": "Reference",  # optional, defaults to 'Reference'
        "organization_name": "Batangas State University",  # optional
        "organization_id": "60028180",  # optional
        "college_filter": "College of Engineering"  # optional, filter specific college
    }
    """
    try:
        data = request.get_json() or {}
        
        # Get file path (default to img/ref.xlsx)
        excel_path = data.get('excel_file_path')
        sheet_name = data.get('sheet_name', 'Reference')
        
        # If no path provided, use default
        if not excel_path:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            excel_path = os.path.join(project_root, 'img', 'ref.xlsx')
        
        # Validate file exists
        if not os.path.exists(excel_path):
            return jsonify({'error': f'Excel file not found: {excel_path}'}), 404
        
        # Load faculty data
        try:
            from faculty_reader import load_faculty_from_db_or_excel
            faculty_list = load_faculty_from_db_or_excel(excel_path, sheet_name=sheet_name, prefer_db=True)
        except Exception as e:
            return jsonify({'error': f'Error reading Excel file: {str(e)}'}), 400
        
        if not faculty_list:
            return jsonify({'error': 'No faculty data found in Excel file'}), 400
        
        # Apply college filter if specified
        college_filter = data.get('college_filter', '').strip()
        if college_filter:
            # Filter faculty by college/department name
            filtered_faculty = []
            for faculty in faculty_list:
                dept = faculty.get('department', '').lower()
                if college_filter.lower() in dept:
                    filtered_faculty.append(faculty)
            faculty_list = filtered_faculty
            print(f"Filtered to {len(faculty_list)} faculty members in '{college_filter}'")
        
        # Fetch Scopus data
        organization_name = data.get('organization_name', 'Batangas State University')
        organization_id = data.get('organization_id')
        
        scopus_data = fetch_scopus_data(
            organization_name=organization_name if organization_name else None,
            organization_id=organization_id if organization_id else None
        )
        
        if scopus_data.get('error'):
            return jsonify({
                'error': scopus_data.get('error'),
                'faculty_count': len(faculty_list)
            }), 503
        
        # Filter publications by faculty
        all_publications = scopus_data.get('publications', [])
        faculty_results = filter_publications_by_faculty(all_publications, faculty_list)
        
        # Build department statistics with faculty details
        department_stats = []
        for dept, count in sorted(faculty_results['department_counts'].items(), 
                                 key=lambda x: x[1], reverse=True):
            # Get all faculty in this department
            dept_faculty = [f for f in faculty_list if f.get('department', '').strip() == dept]
            
            # Count publications per faculty in this department
            faculty_members = []
            for faculty in dept_faculty:
                faculty_name = faculty['name']
                if faculty_name in faculty_results['faculty_publications']:
                    pub_count = len(faculty_results['faculty_publications'][faculty_name]['publications'])
                    faculty_members.append({
                        'name': faculty_name,
                        'position': faculty.get('position', ''),
                        'publications': pub_count
                    })
                else:
                    faculty_members.append({
                        'name': faculty_name,
                        'position': faculty.get('position', ''),
                        'publications': 0
                    })
            
            department_stats.append({
                'department': dept,
                'publication_count': count,  # Total publications for this department
                'faculty_count': len(dept_faculty),
                'faculty_members': faculty_members
            })
        
        # Faculty summary
        faculty_summary = {}
        for name, info in faculty_results['faculty_publications'].items():
            faculty_summary[name] = {
                'department': info['department'],
                'position': info['position'],
                'publication_count': len(info['publications'])
            }
        
        return jsonify({
            'total_faculty': len(faculty_list),
            'total_publications': len(all_publications),
            'matched_publications': faculty_results['total_matched'],
            'match_rate': f"{(faculty_results['total_matched'] / len(all_publications) * 100):.1f}%" if all_publications else "0%",
            'department_statistics': department_stats,
            'department_counts': faculty_results['department_counts'],
            'faculty_summary': faculty_summary,
            'sample_matched': faculty_results['matched_publications'][:20]  # Sample for verification
        }), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/scopus/organizations', methods=['GET'])
def search_organizations():
    """Search for Scopus organization IDs by name"""
    try:
        organization_name = request.args.get('organization_name')
        if not organization_name:
            return jsonify({'error': 'Organization name is required'}), 400
        
        organizations = search_organization_id(organization_name)
        return jsonify({
            'organizations': organizations,
            'count': len(organizations)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/all-data', methods=['GET'])
def get_all_data():
    """Get all research data at once - publications and dashboard stats"""
    try:
        organization_name = request.args.get('organization_name', 'Batangas State University')
        organization_id = request.args.get('organization_id')
        
        # Fetch Scopus data once
        scopus_data = fetch_scopus_data(
            organization_name=organization_name if organization_name else None,
            organization_id=organization_id if organization_id else None
        )
        
        if scopus_data.get('error'):
            return jsonify({
                'error': scopus_data.get('error'),
                'publications': [],
                'dashboard_stats': {
                    'total_publications': 0,
                    'college_counts': {
                        'engineering': 0,
                        'informatics_computing': 0,
                        'engineering_technology': 0,
                        'architecture_design': 0
                    },
                    'quarterly_counts': {
                        'q1': 0,
                        'q2': 0,
                        'q3': 0,
                        'q4': 0
                    }
                }
            }), 503
        
        all_publications = scopus_data.get('publications', [])
        
        def _normalize_pub_id(pub):
            sid = (pub.get('scopus_id') or '')
            tid = (pub.get('title') or '')
            if isinstance(sid, str):
                sid = sid.strip()
            else:
                sid = str(sid).strip()
            if isinstance(tid, str):
                tid = tid.strip()
            else:
                tid = str(tid).strip()
            return sid or tid or ''
        
        # Calculate dashboard stats (similar to get_dashboard_stats but without year filter)
        # Apply faculty filtering for department counts
        department_counts = {}
        faculty_filtered_publications = []
        
        # Default Excel file path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        default_excel_path = os.path.join(project_root, 'img', 'ref.xlsx')
        
        excel_file = default_excel_path if os.path.exists(default_excel_path) else None
        
        # Build pub_id -> set of college keys for year-filtered counts on frontend
        pub_id_to_colleges = {}
        if excel_file and os.path.exists(excel_file):
            try:
                from faculty_reader import load_faculty_from_db_or_excel
                faculty_list = load_faculty_from_db_or_excel(excel_file, sheet_name='Reference', prefer_db=True)
                
                if faculty_list:
                    faculty_results = filter_publications_by_faculty(all_publications, faculty_list)
                    faculty_filtered_publications = faculty_results['matched_publications']
                    department_counts = faculty_results['department_counts']
                    
                    # Map department -> college (defined below after map_department_to_college)
                    def _map_dept_to_college(dept_name):
                        if not dept_name:
                            return None
                        d = dept_name.lower()
                        if 'engineering technology' in d:
                            return 'engineering_technology'
                        if 'informatics' in d or 'computing' in d or 'computer' in d:
                            return 'informatics_computing'
                        if 'architecture' in d or 'design' in d or 'fine arts' in d:
                            return 'architecture_design'
                        if 'engineering' in d and 'technology' not in d:
                            return 'engineering'
                        return None
                    
                    for mpub in faculty_filtered_publications:
                        pub_id = _normalize_pub_id(mpub)
                        if not pub_id:
                            continue
                        depts = mpub.get('matched_departments') or []
                        colleges = set()
                        for dept in depts:
                            c = _map_dept_to_college(dept)
                            if c:
                                colleges.add(c)
                        if colleges:
                            pub_id_to_colleges[pub_id] = list(colleges)
            except Exception as e:
                print(f"Warning: Could not apply faculty filtering: {str(e)}")
        
        # Total publications
        total_publications = len(all_publications)
        
        # Calculate quarterly counts
        quarterly_counts = {'q1': 0, 'q2': 0, 'q3': 0, 'q4': 0}
        
        for pub in all_publications:
            month = pub.get('month')
            if not month:
                date_str = pub.get('date', '')
                if date_str and isinstance(date_str, str):
                    if '/' in date_str:
                        parts = date_str.split('/')
                        if len(parts) >= 2:
                            try:
                                potential_month = int(parts[1])
                                if 1 <= potential_month <= 12:
                                    month = potential_month
                            except (ValueError, IndexError):
                                pass
            
            if month:
                try:
                    month = int(month)
                    if 1 <= month <= 3:
                        quarterly_counts['q1'] += 1
                    elif 4 <= month <= 6:
                        quarterly_counts['q2'] += 1
                    elif 7 <= month <= 9:
                        quarterly_counts['q3'] += 1
                    elif 10 <= month <= 12:
                        quarterly_counts['q4'] += 1
                except (ValueError, TypeError):
                    pass
        
        # Get available years
        available_years = []
        for p in all_publications:
            year = p.get('year')
            if year:
                try:
                    if isinstance(year, str):
                        year = int(year.split('/')[0]) if '/' in year else int(year)
                    if isinstance(year, (int, float)):
                        available_years.append(int(year))
                except (ValueError, TypeError):
                    continue
        available_years = sorted(set(available_years), reverse=True)
        earliest_year = min(available_years) if available_years else None
        
        # Map department names to college categories
        def map_department_to_college(dept_name):
            if not dept_name:
                return None
            dept_lower = dept_name.lower()
            if 'engineering technology' in dept_lower:
                return 'engineering_technology'
            elif 'informatics' in dept_lower or 'computing' in dept_lower or 'computer' in dept_lower:
                return 'informatics_computing'
            elif 'architecture' in dept_lower or 'design' in dept_lower or 'fine arts' in dept_lower:
                return 'architecture_design'
            elif 'engineering' in dept_lower and 'technology' not in dept_lower:
                return 'engineering'
            return None
        
        # Initialize college counts
        college_counts = {
            'engineering': 0,
            'informatics_computing': 0,
            'engineering_technology': 0,
            'architecture_design': 0
        }
        
        # Use department_counts if available
        if department_counts:
            for dept_name, count in department_counts.items():
                college = map_department_to_college(dept_name)
                if college:
                    college_counts[college] += count
        
        # Prepare all publications for frontend (with numbering and college keys for year filtering)
        publications_list = []
        for idx, pub in enumerate(all_publications):
            pub_id = _normalize_pub_id(pub)
            colleges = pub_id_to_colleges.get(pub_id, []) if pub_id else []
            publications_list.append({
                'number': idx + 1,
                'title': pub.get('title', 'Untitled Publication'),
                'year': pub.get('year'),
                'authors': pub.get('authors', ''),
                'venue': pub.get('venue', ''),
                'citations': pub.get('citations', 0),
                'link': pub.get('link', ''),
                'doi': pub.get('doi', ''),
                'month': pub.get('month'),
                'date': pub.get('date', ''),
                'scopus_id': pub.get('scopus_id', ''),
                'colleges': colleges
            })
        
        return jsonify({
            'publications': publications_list,
            'dashboard_stats': {
                'total_publications': total_publications,
                'college_counts': college_counts,
                'department_counts': department_counts,
                'quarterly_counts': quarterly_counts,
                'available_years': available_years,
                'earliest_year': earliest_year,
                'current_year': datetime.now().year
            },
            'organization_name': scopus_data.get('statistics', {}).get('organization_name', organization_name),
            'citations': scopus_data.get('citations', {}),
            'statistics': scopus_data.get('statistics', {})
        }), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/faculty/refresh', methods=['POST'])
def refresh_faculty_from_excel():
    """
    Refresh faculty data from Excel file and import into database
    """
    try:
        data = request.get_json() or {}
        excel_path = data.get('excel_file_path')
        sheet_name = data.get('sheet_name', '').strip() or None  # Accept any sheet or use first
        clear_existing = data.get('clear_existing', True)
        
        # Use default Excel path if not provided
        if not excel_path:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            excel_path = os.path.join(project_root, 'img', 'ref.xlsx')
        
        if not os.path.exists(excel_path):
            return jsonify({'error': f'Excel file not found: {excel_path}'}), 404
        
        # Load from Excel
        from faculty_reader import load_faculty_from_excel
        from database import import_faculty_from_list, get_faculty_count
        
        faculty_list = load_faculty_from_excel(excel_path, sheet_name=sheet_name)
        
        if not faculty_list:
            return jsonify({'error': 'No faculty data found in Excel file'}), 400
        
        # Import to database with duplicate checking
        result = import_faculty_from_list(faculty_list, clear_existing=clear_existing, skip_duplicates=True)
        count = get_faculty_count()
        
        response_data = {
            'message': 'Faculty data refreshed successfully',
            'imported_count': result['imported'],
            'skipped_count': result['skipped'],
            'total_in_database': count
        }
        
        if result['skipped'] > 0:
            response_data['duplicates'] = result['duplicates'][:10]
            response_data['message'] = f"Refreshed {result['imported']} faculty members. {result['skipped']} duplicates skipped."
        
        return jsonify(response_data), 200
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/faculty/seed', methods=['POST'])
def seed_faculty_from_default():
    """
    Load faculty from default Excel (ref.xlsx) and import into DB.
    Use this when the database is empty on deploy (e.g. Render/Replit).
    Tries ../img/ref.xlsx then backend/ref.xlsx.
    """
    try:
        from database import import_faculty_from_list, get_faculty_count
        from faculty_reader import load_faculty_from_excel
        
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(backend_dir)
        for excel_path in [
            os.path.join(project_root, 'img', 'ref.xlsx'),
            os.path.join(backend_dir, 'ref.xlsx'),
        ]:
            if os.path.exists(excel_path):
                faculty_list = load_faculty_from_excel(excel_path, sheet_name=None)
                if not faculty_list:
                    return jsonify({'error': 'No faculty rows in Excel file'}), 400
                result = import_faculty_from_list(faculty_list, clear_existing=True, skip_duplicates=False)
                count = get_faculty_count()
                return jsonify({
                    'message': f"Loaded {result['imported']} faculty from default Excel.",
                    'imported_count': result['imported'],
                    'total_in_database': count
                }), 200
        return jsonify({
            'error': 'Default Excel file (ref.xlsx) not found. Add ref.xlsx to backend/ or ensure img/ref.xlsx exists in the repo.'
        }), 404
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/faculty/count', methods=['GET'])
def get_faculty_count_endpoint():
    """Get count of faculty in database"""
    try:
        from database import get_faculty_count
        count = get_faculty_count()
        return jsonify({'count': count}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/faculty/departments', methods=['GET'])
def get_faculty_departments():
    """Get distinct department names (for dropdowns)."""
    try:
        from database import get_distinct_departments
        departments = get_distinct_departments()
        return jsonify({'departments': departments}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/faculty/list', methods=['GET'])
def get_faculty_list():
    """Get all faculty members"""
    try:
        from database import load_faculty_from_db
        faculty_list = load_faculty_from_db()
        return jsonify({'faculty': faculty_list, 'count': len(faculty_list)}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/faculty/add', methods=['POST'])
def add_faculty_member():
    """Add a single faculty member"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        department = data.get('department', '').strip()
        position = data.get('position', '').strip()
        
        if not name:
            return jsonify({'error': 'Name is required'}), 400
        if not department:
            return jsonify({'error': 'Department is required'}), 400
        
        from database import add_faculty
        faculty_id, is_new = add_faculty(name, department, position, skip_duplicate=True)
        
        if not is_new:
            return jsonify({
                'error': f'Faculty member "{name}" already exists',
                'duplicate': True
            }), 409
        
        return jsonify({
            'message': 'Faculty member added successfully',
            'id': faculty_id,
            'name': name,
            'department': department,
            'position': position
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/faculty/<int:faculty_id>', methods=['GET'])
def get_faculty_member(faculty_id):
    """Get a single faculty member by ID"""
    try:
        from database import get_faculty_by_id
        faculty = get_faculty_by_id(faculty_id)
        
        if not faculty:
            return jsonify({'error': 'Faculty member not found'}), 404
        
        return jsonify(faculty), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/faculty/<int:faculty_id>', methods=['PUT'])
def update_faculty_member(faculty_id):
    """Update a faculty member"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        department = data.get('department', '').strip()
        position = data.get('position', '').strip()
        
        if not name:
            return jsonify({'error': 'Name is required'}), 400
        if not department:
            return jsonify({'error': 'Department is required'}), 400
        
        from database import update_faculty
        success = update_faculty(faculty_id, name, department, position)
        
        if not success:
            return jsonify({'error': 'Faculty member not found'}), 404
        
        return jsonify({
            'message': 'Faculty member updated successfully',
            'id': faculty_id
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/faculty/<int:faculty_id>', methods=['DELETE'])
def delete_faculty_member(faculty_id):
    """Delete a faculty member"""
    try:
        from database import delete_faculty
        success = delete_faculty(faculty_id)
        
        if not success:
            return jsonify({'error': 'Faculty member not found'}), 404
        
        return jsonify({'message': 'Faculty member deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/faculty/upload-excel', methods=['POST'])
def upload_excel_faculty():
    """Upload Excel file and import faculty"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({'error': 'Invalid file type. Please upload Excel file (.xlsx or .xls)'}), 400
        
        sheet_name = request.form.get('sheet_name', '').strip() or None  # Accept any sheet or use first
        clear_existing = request.form.get('clear_existing', 'true').lower() == 'true'
        
        # Save uploaded file temporarily
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        
        try:
            from faculty_reader import load_faculty_from_excel
            from database import import_faculty_from_list, get_faculty_count
            
            # Load from Excel (will use first sheet if sheet_name is None)
            faculty_list = load_faculty_from_excel(temp_path, sheet_name=sheet_name)
            
            if not faculty_list:
                return jsonify({'error': 'No faculty data found in Excel file'}), 400
            
            # Import with duplicate checking
            result = import_faculty_from_list(faculty_list, clear_existing=clear_existing, skip_duplicates=True)
            count = get_faculty_count()
            
            response_data = {
                'message': 'Faculty data imported successfully',
                'imported_count': result['imported'],
                'skipped_count': result['skipped'],
                'total_in_database': count
            }
            
            if result['skipped'] > 0:
                response_data['duplicates'] = result['duplicates'][:10]  # Show first 10 duplicates
                response_data['message'] = f"Imported {result['imported']} faculty members. {result['skipped']} duplicates skipped."
            
            return jsonify(response_data), 200
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        from database import get_faculty_count
        faculty_count = get_faculty_count()
        return jsonify({
            'status': 'healthy',
            'message': 'Backend is running',
            'faculty_in_database': faculty_count
        }), 200
    except:
        return jsonify({'status': 'healthy', 'message': 'Backend is running'}), 200

# Serve static files (HTML, CSS, JS, images)
# This allows Flask to serve the frontend files
@app.route('/')
def index():
    """Serve index.html"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return send_from_directory(project_root, 'index.html')

@app.route('/<path:filename>')
def serve_static_files(filename):
    """Serve static files (HTML, CSS, JS, images)"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Security: Prevent directory traversal
    safe_path = os.path.normpath(filename)
    if '..' in safe_path or safe_path.startswith('/'):
        return jsonify({'error': 'Invalid path'}), 403
    
    # Only serve allowed file types
    allowed_extensions = ['.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.xlsx']
    
    # Check if file has allowed extension or is a known HTML file
    if any(filename.endswith(ext) for ext in allowed_extensions) or filename in ['index.html', 'publications.html', 'faculty.html']:
        try:
            file_path = os.path.join(project_root, safe_path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                return send_from_directory(project_root, safe_path)
        except Exception as e:
            pass
    
    # For API routes, return 404 (they should be handled by other routes)
    if filename.startswith('api/'):
        return jsonify({'error': 'API endpoint not found'}), 404
    
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    import os
    # Determine if running in production
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    app.run(debug=debug_mode, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))