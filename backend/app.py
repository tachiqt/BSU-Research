from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from io import BytesIO
from datetime import datetime
import os
from dotenv import load_dotenv
from scopus import fetch_scopus_data, search_organization_id, filter_publications_by_faculty
from openalex import (
    fetch_openalex_works_for_institution,
    fetch_openalex_works_by_dois,
    filter_openalex_publications_by_scopus,
    mix_scopus_with_openalex_when_available,
    search_institution_id,
)

load_dotenv()
app = Flask(__name__)
CORS(app)

try:
    from database import init_database
    init_database()
except Exception as e:
    print(f"Warning: Could not initialize database: {e}")


def _compute_h_index(citation_counts):
    citation_counts = sorted([int(c or 0) for c in citation_counts], reverse=True)
    h = 0
    for i, c in enumerate(citation_counts, 1):
        if c >= i:
            h = i
        else:
            break
    return h


def _fetch_publications_data(
    organization_name: str,
    organization_id: str = None,
    source: str = "mix",
    openalex_institution_id: str = None,
):
    src = (source or "openalex").strip().lower()

    scopus_data = fetch_scopus_data(
        organization_name=organization_name if organization_name else None,
        organization_id=organization_id if organization_id else None,
    )
    if src == "scopus":
        return scopus_data

    if scopus_data.get("error"):
        return scopus_data

    inst_id = (openalex_institution_id or os.getenv("OPENALEX_INSTITUTION_ID") or "").strip()
    if inst_id.startswith("https://openalex.org/"):
        inst_id = inst_id.replace("https://openalex.org/", "", 1).strip()
    if inst_id and inst_id[0].lower() == "i":
        inst_id = "I" + inst_id[1:]
    import re as _re
    if not inst_id or not _re.match(r"^I\d+$", inst_id):
        inst_id = search_institution_id(organization_name or "Batangas State University") or ""

    scopus_pubs = scopus_data.get("publications", []) or []
    scopus_dois = []
    for p in scopus_pubs:
        d = (p.get("doi") or "").strip()
        if d:
            scopus_dois.append(d)

    doi_lookup_data = fetch_openalex_works_by_dois(scopus_dois)
    works_by_doi = doi_lookup_data.get("works", []) or []

    works_by_inst_data = fetch_openalex_works_for_institution(inst_id) if inst_id else {"works": [], "total": 0, "processed": 0}
    if works_by_inst_data.get("error"):
        works_by_inst_data = {"works": [], "total": 0, "processed": 0, "error": works_by_inst_data.get("error")}

    if (doi_lookup_data.get("error") and not works_by_doi) and (works_by_inst_data.get("error") and not works_by_inst_data.get("works")):
        scopus_data["warning"] = doi_lookup_data.get("error") or works_by_inst_data.get("error")
        return scopus_data

    merged_works = []
    seen_ids = set()
    seen_dois = set()
    for w in (works_by_doi + (works_by_inst_data.get("works", []) or [])):
        oid = (w.get("id") or (w.get("ids") or {}).get("openalex") or "").strip()
        doi = (w.get("doi") or (w.get("ids") or {}).get("doi") or "").strip().lower()
        if oid and oid in seen_ids:
            continue
        if doi and doi in seen_dois:
            continue
        if oid:
            seen_ids.add(oid)
        if doi:
            seen_dois.add(doi)
        merged_works.append(w)

    if src == "openalex_matched":
        filtered = filter_openalex_publications_by_scopus(
            merged_works,
            scopus_pubs,
        )
        pubs = filtered.get("publications", [])
        match_stats = filtered.get("matched_by", {})
        openalex_used = len(pubs)
        scopus_used = 0
    else:
        mixed = mix_scopus_with_openalex_when_available(
            merged_works,
            scopus_pubs,
        )
        pubs = mixed.get("publications", [])
        match_stats = mixed.get("openalex_match_by", {})
        openalex_used = mixed.get("openalex_used", 0)
        scopus_used = mixed.get("scopus_used", 0)

    total_citations = sum(int(p.get("citations") or 0) for p in pubs)
    h_index = _compute_h_index([p.get("citations") or 0 for p in pubs])

    return {
        "publications": pubs,
        "total_publications": len(pubs),
        "processed_publications": len(pubs),
        "citations": {"total": total_citations, "h_index": h_index, "i10_index": 0},
        "statistics": {
            "organization_name": organization_name or "Batangas State University",
            "organization_id": organization_id,
            "source": ("openalex_filtered_by_scopus" if src == "openalex_matched" else "mix_scopus_with_openalex"),
            "openalex_institution_id": inst_id,
            "openalex_total_results": (works_by_inst_data.get("total", 0) if isinstance(works_by_inst_data, dict) else 0),
            "openalex_processed": len(merged_works),
            "openalex_doi_lookup_processed": doi_lookup_data.get("processed", 0),
            "scopus_api_total_results": scopus_data.get("statistics", {}).get("api_total_results", 0),
            "match_stats": match_stats,
            "openalex_used": openalex_used,
            "scopus_used": scopus_used,
        },
        "warning": works_by_inst_data.get("error") or doi_lookup_data.get("error"),
    }


@app.route('/api/scholar/publications', methods=['GET'])
def get_publications():
    try:
        organization_name = request.args.get('organization_name', 'Batangas State University')
        organization_id = request.args.get('organization_id')
        source = request.args.get('source', 'mix')
        openalex_institution_id = request.args.get('openalex_institution_id')
        
        publications_data = _fetch_publications_data(
            organization_name=organization_name,
            organization_id=organization_id,
            source=source,
            openalex_institution_id=openalex_institution_id,
        )
        
        if publications_data.get('error'):
            return jsonify({
                'error': publications_data.get('error'),
                'organization_name': organization_name,
                'publications': [],
                'total_publications': 0,
                'citations': {},
                'statistics': {}
            }), 503  
        
        return jsonify({
            'organization_name': publications_data.get('statistics', {}).get('organization_name', organization_name),
            'publications': publications_data.get('publications', []),
            'total_publications': publications_data.get('total_publications', 0),
            'citations': publications_data.get('citations', {}),
            'statistics': publications_data.get('statistics', {}),
            'warning': publications_data.get('warning'),
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/publications/titles', methods=['GET'])
def get_publication_titles():
    try:
        organization_name = request.args.get('organization_name', 'Batangas State University')
        organization_id = request.args.get('organization_id')
        source = request.args.get('source', 'mix')
        openalex_institution_id = request.args.get('openalex_institution_id')
        year_filter = request.args.get('year', '').strip()
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 10
        
        publications_data = _fetch_publications_data(
            organization_name=organization_name,
            organization_id=organization_id,
            source=source,
            openalex_institution_id=openalex_institution_id,
        )
        
        if publications_data.get('error'):
            return jsonify({
                'error': publications_data.get('error'),
                'titles': []
            }), 503
        
        all_publications = publications_data.get('publications', [])
        
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
        
        total_count = len(all_publications)
        total_pages = (total_count + limit - 1) // limit  
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_publications = all_publications[start_idx:end_idx]
        titles = []
        for idx, pub in enumerate(paginated_publications):
            global_number = start_idx + idx + 1  
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
        
        all_pubs_for_years = publications_data.get('publications', [])
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
            'organization_name': publications_data.get('statistics', {}).get('organization_name', organization_name),
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
        source = request.args.get('source', 'mix')
        openalex_institution_id = request.args.get('openalex_institution_id')
        
        publications_data = _fetch_publications_data(
            organization_name=organization_name,
            organization_id=organization_id,
            source=source,
            openalex_institution_id=openalex_institution_id,
        )
        
        if publications_data.get('error'):
            return jsonify({
                'error': publications_data.get('error'),
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
        
        all_publications = publications_data.get('publications', [])
        
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
                publications = year_filtered_publications
                print(f"Applied year filter: {filter_year} - {len(publications)} publications")
            except (ValueError, TypeError) as e:
                print(f"Error filtering by year: {e}")
                publications = all_publications
        else:
            publications = all_publications
        
        department_counts = {}
        faculty_filtered_publications = []
        try:
            from database import load_faculty_from_db
            faculty_list = load_faculty_from_db()
            if faculty_list:
                college_filter = request.args.get('college_filter', '').strip()
                if college_filter:
                    faculty_list = [f for f in faculty_list
                                   if college_filter.lower() in f.get('department', '').lower()]
                if faculty_list:
                    faculty_results = filter_publications_by_faculty(publications, faculty_list)
                    faculty_filtered_publications = faculty_results['matched_publications']
                    department_counts = faculty_results['department_counts']
                    print(f"Applied faculty filtering: {len(faculty_filtered_publications)} publications matched across {len(department_counts)} departments")
                    if year_filter:
                        print(f"  (Year filter: {year_filter} is applied to department counts)")
            else:
                print("Warning: No faculty in database; department counts will be empty")
        except Exception as e:
            import traceback
            print(f"Warning: Could not apply faculty filtering: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
        total_publications = len(publications)
        quarterly_counts = {
            'q1': 0, 
            'q2': 0,  
            'q3': 0, 
            'q4': 0  
        }
        
        department_quarterly_counts = {}
        matched_pub_ids = set()
        matched_pub_dept_map = {}  
        if faculty_filtered_publications:
            for matched_pub in faculty_filtered_publications:
                pub_id = matched_pub.get('scopus_id') or matched_pub.get('title', '')
                matched_pub_ids.add(pub_id)
                if matched_pub.get('matched_departments'):
                    matched_pub_dept_map[pub_id] = matched_pub.get('matched_departments', [])
        
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
        
        college_counts = {
            'engineering': 0,
            'informatics_computing': 0,
            'engineering_technology': 0,
            'architecture_design': 0
        }
        if department_counts:
            for dept_name, count in department_counts.items():
                college = map_department_to_college(dept_name)
                if college:
                    college_counts[college] += count
        
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
            'department_counts': department_counts,  
            'department_quarterly_counts': department_quarterly_counts,  
            'quarterly_counts': quarterly_counts,  
            'available_years': available_years,
            'earliest_year': earliest_year,
            'current_year': current_year,
            'citations': publications_data.get('citations', {}),
            'statistics': publications_data.get('statistics', {}),
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
    try:
        data = request.get_json() or {}
        try:
            from database import load_faculty_from_db
            faculty_list = load_faculty_from_db()
        except Exception as e:
            return jsonify({'error': f'Error loading faculty: {str(e)}'}), 400

        if not faculty_list:
            return jsonify({'error': 'No faculty data found. Add faculty in Faculty Management or import from Excel.'}), 400
        college_filter = data.get('college_filter', '').strip()
        if college_filter:
            filtered_faculty = []
            for faculty in faculty_list:
                dept = faculty.get('department', '').lower()
                if college_filter.lower() in dept:
                    filtered_faculty.append(faculty)
            faculty_list = filtered_faculty
            print(f"Filtered to {len(faculty_list)} faculty members in '{college_filter}'")
        
        organization_name = data.get('organization_name', 'Batangas State University')
        organization_id = data.get('organization_id')
        source = data.get('source', 'mix')
        openalex_institution_id = data.get('openalex_institution_id')
        
        publications_data = _fetch_publications_data(
            organization_name=organization_name,
            organization_id=organization_id,
            source=source,
            openalex_institution_id=openalex_institution_id,
        )
        
        if publications_data.get('error'):
            return jsonify({
                'error': publications_data.get('error'),
                'faculty_count': len(faculty_list)
            }), 503
        
        all_publications = publications_data.get('publications', [])
        faculty_results = filter_publications_by_faculty(all_publications, faculty_list)
        department_stats = []
        for dept, count in sorted(faculty_results['department_counts'].items(), 
                                 key=lambda x: x[1], reverse=True):
            dept_faculty = [f for f in faculty_list if f.get('department', '').strip() == dept]
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
                'publication_count': count,  
                'faculty_count': len(dept_faculty),
                'faculty_members': faculty_members
            })
        
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
            'sample_matched': faculty_results['matched_publications'][:20] 
        }), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

@app.route('/api/scopus/organizations', methods=['GET'])
def search_organizations():
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
    try:
        organization_name = request.args.get('organization_name', 'Batangas State University')
        organization_id = request.args.get('organization_id')
        source = request.args.get('source', 'mix')
        openalex_institution_id = request.args.get('openalex_institution_id')
        publications_data = _fetch_publications_data(
            organization_name=organization_name,
            organization_id=organization_id,
            source=source,
            openalex_institution_id=openalex_institution_id,
        )
        
        if publications_data.get('error'):
            return jsonify({
                'error': publications_data.get('error'),
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
        
        all_publications = publications_data.get('publications', [])
        
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
        department_counts = {}
        faculty_filtered_publications = []
        pub_id_to_colleges = {}
        try:
            from database import load_faculty_from_db
            faculty_list = load_faculty_from_db()
            if faculty_list:
                faculty_results = filter_publications_by_faculty(all_publications, faculty_list)
                faculty_filtered_publications = faculty_results['matched_publications']
                department_counts = faculty_results['department_counts']
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
        
        total_publications = len(all_publications)
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
        
        college_counts = {
            'engineering': 0,
            'informatics_computing': 0,
            'engineering_technology': 0,
            'architecture_design': 0
        }
        
        if department_counts:
            for dept_name, count in department_counts.items():
                college = map_department_to_college(dept_name)
                if college:
                    college_counts[college] += count
        
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
            'organization_name': publications_data.get('statistics', {}).get('organization_name', organization_name),
            'citations': publications_data.get('citations', {}),
            'statistics': publications_data.get('statistics', {}),
            'warning': publications_data.get('warning'),
        }), 200
        
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
    """Add a single faculty member. Saves to database only (PostgreSQL on Railway or SQLite locally)."""
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
            'position': position,
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
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({'error': 'Invalid file type. Please upload Excel file (.xlsx or .xls)'}), 400
        
        sheet_name = request.form.get('sheet_name', '').strip() or None  
        clear_existing = request.form.get('clear_existing', 'true').lower() == 'true'
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, file.filename)
        file.save(temp_path)
        
        try:
            from faculty_reader import load_faculty_from_excel
            from database import import_faculty_from_list, get_faculty_count
            faculty_list = load_faculty_from_excel(temp_path, sheet_name=sheet_name)
            
            if not faculty_list:
                return jsonify({'error': 'No faculty data found in Excel file'}), 400
            
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
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/report/preview', methods=['GET'])
def report_preview():
    try:
        year_filter = request.args.get('year', '').strip()
        quarter = request.args.get('quarter', '4th')
        campus = request.args.get('campus', 'ALANGILAN')
        organization_name = request.args.get('organization_name', 'Batangas State University')
        organization_id = request.args.get('organization_id')
        fiscal_year = request.args.get('fiscal_year', str(datetime.now().year))
        source = request.args.get('source', 'mix')
        openalex_institution_id = request.args.get('openalex_institution_id')

        publications_data = _fetch_publications_data(
            organization_name=organization_name,
            organization_id=organization_id,
            source=source,
            openalex_institution_id=openalex_institution_id,
        )
        if publications_data.get('error'):
            return jsonify({'error': publications_data.get('error'), 'publications': []}), 503

        all_publications = publications_data.get('publications', [])
        pub_id_to_college = {}
        try:
            from database import load_faculty_from_db
            faculty_list = load_faculty_from_db()
            if faculty_list:
                faculty_results = filter_publications_by_faculty(all_publications, faculty_list)
                for mpub in faculty_results.get('matched_publications', []):
                    pub_id = (mpub.get('scopus_id') or mpub.get('title') or '').strip()
                    depts = mpub.get('matched_departments') or []
                    if pub_id and depts:
                        pub_id_to_college[pub_id] = depts[0]
        except Exception:
            pass

        filtered = []
        for p in all_publications:
            pub_year = p.get('year')
            if pub_year is not None:
                if isinstance(pub_year, str):
                    try:
                        pub_year = int(pub_year.split('/')[0]) if '/' in pub_year else int(pub_year)
                    except (ValueError, TypeError):
                        pub_year = None
            if year_filter:
                try:
                    y = int(year_filter)
                    if pub_year is None or int(pub_year) != y:
                        continue
                except (ValueError, TypeError):
                    pass
            month = p.get('month')
            quarter_val = (quarter or '').strip().lower()
            if quarter_val and quarter_val != 'all' and pub_year is not None and month is not None:
                try:
                    qnum = {'1st': 1, '2nd': 2, '3rd': 3, '4th': 4}.get(quarter_val, 4)
                    q_months = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}.get(qnum, (10, 12))
                    m = int(month)
                    if m < q_months[0] or m > q_months[1]:
                        continue
                except (ValueError, TypeError, AttributeError):
                    pass
            pub_id = (p.get('scopus_id') or p.get('title') or '').strip()
            college_campus = pub_id_to_college.get(pub_id) or 'Batangas State University'
            filtered.append({
                'title': p.get('title', ''),
                'authors': p.get('authors', ''),
                'venue': p.get('venue', ''),
                'year': p.get('year'),
                'month': p.get('month'),
                'college_campus': college_campus,
                'link': p.get('link', ''),
                'doi': p.get('doi', ''),
                'publisher': p.get('publisher', ''),
            })

        from report_generator import get_preview_data
        report_rows = get_preview_data([{**p, 'college_campus': p.get('college_campus'), 'month': p.get('month'), 'link': p.get('link'), 'doi': p.get('doi'), 'publisher': p.get('publisher')} for p in filtered])

        quarter_display = 'All' if (quarter or '').strip().lower() == 'all' else quarter
        return jsonify({
            'filters': {
                'fiscal_year': fiscal_year,
                'quarter': quarter_display,
                'campus': campus,
                'year_filter': year_filter or None,
            },
            'publications': report_rows,
            'total_count': len(report_rows),
        }), 200
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/report/export', methods=['POST'])
def report_export():
    try:
        data = request.get_json() or {}
        fiscal_year = data.get('fiscal_year') or str(datetime.now().year)
        quarter = data.get('quarter', '4th')
        quarter_val = (quarter or '').strip().lower()
        quarter_display = 'All' if quarter_val == 'all' else quarter
        campus = data.get('campus', 'ALANGILAN')
        year_filter = (data.get('year') or data.get('year_filter') or '').strip()
        organization_name = data.get('organization_name', 'Batangas State University')
        organization_id = data.get('organization_id')
        source = data.get('source', 'mix')
        openalex_institution_id = data.get('openalex_institution_id')

        provided_rows = data.get('publications')
        report_rows = None
        if isinstance(provided_rows, list):
            report_rows = provided_rows

        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)

        from report_generator import build_report, get_preview_data

        if report_rows is None:
            publications_data = _fetch_publications_data(
                organization_name=organization_name,
                organization_id=organization_id,
                source=source,
                openalex_institution_id=openalex_institution_id,
            )
            if publications_data.get('error'):
                return jsonify({'error': publications_data.get('error')}), 503

            all_publications = publications_data.get('publications', [])
            pub_id_to_college = {}
            try:
                from database import load_faculty_from_db
                faculty_list = load_faculty_from_db()
                if faculty_list:
                    faculty_results = filter_publications_by_faculty(all_publications, faculty_list)
                    for mpub in faculty_results.get('matched_publications', []):
                        pub_id = (mpub.get('scopus_id') or mpub.get('title') or '').strip()
                        depts = mpub.get('matched_departments') or []
                        if pub_id and depts:
                            pub_id_to_college[pub_id] = depts[0]
            except Exception:
                pass

            filtered = []
            for p in all_publications:
                pub_year = p.get('year')
                if pub_year is not None and isinstance(pub_year, str):
                    try:
                        pub_year = int(pub_year.split('/')[0]) if '/' in pub_year else int(pub_year)
                    except (ValueError, TypeError):
                        pub_year = None
                if year_filter:
                    try:
                        y = int(year_filter)
                        if pub_year is None or int(pub_year) != y:
                            continue
                    except (ValueError, TypeError):
                        pass
                if quarter_val and quarter_val != 'all':
                    month = p.get('month')
                    if pub_year is not None and month is not None:
                        try:
                            qnum = {'1st': 1, '2nd': 2, '3rd': 3, '4th': 4}.get(quarter_val, 4)
                            q_months = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}.get(qnum, (10, 12))
                            m = int(month)
                            if m < q_months[0] or m > q_months[1]:
                                continue
                        except (ValueError, TypeError, AttributeError):
                            pass
                pub_id = (p.get('scopus_id') or p.get('title') or '').strip()
                college_campus = pub_id_to_college.get(pub_id) or 'Batangas State University'
                filtered.append({
                    'title': p.get('title', ''),
                    'authors': p.get('authors', ''),
                    'venue': p.get('venue', ''),
                    'year': p.get('year'),
                    'month': p.get('month'),
                    'college_campus': college_campus,
                    'link': p.get('link', ''),
                    'doi': p.get('doi', ''),
                    'publisher': p.get('publisher', ''),
                })

            report_rows = get_preview_data([{**p} for p in filtered])
        wb = build_report(fiscal_year, quarter_display, campus, report_rows, None, project_root)
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        q_slug = 'All' if quarter_display == 'All' else quarter.replace('th', '').replace('st', '').replace('nd', '').replace('rd', '')
        filename = f'RESEARCH_AL_Quarterly_Report_{fiscal_year}_Q{q_slug}_{campus}.xlsx'
        return send_file(
            buf,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
        )
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


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

def _static_roots():
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(backend_dir)
    return [repo_root, backend_dir]

@app.route('/')
def index():
    for root in _static_roots():
        path = os.path.join(root, 'index.html')
        if os.path.exists(path) and os.path.isfile(path):
            return send_from_directory(root, 'index.html')
    return jsonify({'error': 'File not found'}), 404

@app.route('/<path:filename>')
def serve_static_files(filename):
    safe_path = os.path.normpath(filename)
    if '..' in safe_path or safe_path.startswith('/') or safe_path.startswith('\\'):
        return jsonify({'error': 'Invalid path'}), 403
    allowed_extensions = ['.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.xlsx']
    if any(filename.endswith(ext) for ext in allowed_extensions) or filename in ['index.html', 'publications.html', 'faculty.html', 'reports.html']:
        try:
            for root in _static_roots():
                file_path = os.path.join(root, *filename.split('/'))
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    return send_from_directory(root, filename)
        except Exception:
            pass
    if filename.startswith('api/'):
        return jsonify({'error': 'API endpoint not found'}), 404
    
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    import os
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    app.run(debug=debug_mode, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))