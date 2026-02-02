import requests
import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
SCOPUS_API_KEY = os.environ.get('SCOPUS_API_KEY', '')
SCOPUS_API_URL = 'https://api.elsevier.com/content/search/scopus'
SCOPUS_HEADERS = {
    'Accept': 'application/json',
    'X-ELS-APIKey': SCOPUS_API_KEY
}

def _make_request_with_retry(url, params, headers, max_retries=3, retry_delay=2):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code < 500:
                return response
            
            if response.status_code >= 500:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt) 
                    print(f"Scopus API server error {response.status_code}, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Scopus API server error {response.status_code} after {max_retries} attempts")
                    return response
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                print(f"Request timeout, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                print("Request timeout after all retries")
                raise
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                print(f"Request error: {str(e)}, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                print(f"Request error after all retries: {str(e)}")
                raise
    
    return response

def _norm(s):
    return (s or '').strip().lower()

def _parse_publication_date(coverDate, pubDate=None):
    year = None
    month = None
    day = None
    date_str = None
    if coverDate:
        try:
            parts = coverDate.split('-')
            if len(parts) >= 1:
                year = int(parts[0])
            if len(parts) >= 2:
                month = int(parts[1])
            if len(parts) >= 3:
                day = int(parts[2])
            
            if year:
                if month and day:
                    date_str = f"{year}/{month:02d}/{day:02d}"
                elif month:
                    date_str = f"{year}/{month:02d}"
                else:
                    date_str = str(year)
        except (ValueError, AttributeError):
            pass
    if not year and pubDate:
        try:
            if isinstance(pubDate, (int, float)):
                year = int(pubDate)
                date_str = str(year)
            elif isinstance(pubDate, str):
                year_match = re.search(r'\b(19|20)\d{2}\b', pubDate)
                if year_match:
                    year = int(year_match.group(0))
                    date_str = str(year)
        except (ValueError, AttributeError):
            pass
    
    return year, month, day, date_str

def _extract_authors(authors_entry):
    authors_list = []
    authors_for_matching = [] 
    if not authors_entry:
        return '', ''
    
    if isinstance(authors_entry, list):
        for author in authors_entry:
            if isinstance(author, dict):
                given_name = (author.get('given-name') or author.get('given_name') or 
                             author.get('givenName') or author.get('@given-name', '') or '').strip()
                surname = (author.get('surname') or author.get('@surname', '') or '').strip()
                initials = (author.get('initials') or author.get('@initials', '') or '').strip()
                if len(authors_list) == 0:
                    print(f"DEBUG: Author dict keys: {list(author.keys())}")
                    print(f"DEBUG: given-name: '{given_name}', surname: '{surname}', initials: '{initials}'")
                
                if given_name or surname:
                    authors_list.append(f"{given_name} {surname}".strip())
                    if surname:
                        if initials:
                            clean_initials = initials.replace('.', '').replace(' ', '').upper()
                        elif given_name:
                            name_parts = given_name.split()
                            clean_initials = ''.join([p[0].upper() for p in name_parts if p and len(p) > 0])
                        else:
                            clean_initials = ''
                        
                        authors_for_matching.append(f"{surname}, {clean_initials}".strip())
    elif isinstance(authors_entry, dict):
        given_name = (authors_entry.get('given-name') or authors_entry.get('given_name') or 
                     authors_entry.get('givenName') or authors_entry.get('@given-name', '') or '').strip()
        surname = (authors_entry.get('surname') or authors_entry.get('@surname', '') or '').strip()
        initials = (authors_entry.get('initials') or authors_entry.get('@initials', '') or '').strip()
        
        if given_name or surname:
            authors_list.append(f"{given_name} {surname}".strip())
            if surname:
                if initials:
                    clean_initials = initials.replace('.', '').replace(' ', '').upper()
                elif given_name:
                    name_parts = given_name.split()
                    clean_initials = ''.join([p[0].upper() for p in name_parts if p and len(p) > 0])
                else:
                    clean_initials = ''
                authors_for_matching.append(f"{surname}, {clean_initials}".strip())
    elif isinstance(authors_entry, str):
        authors_list.append(authors_entry.strip())
        if ',' in authors_entry:
            parts = authors_entry.split(',')
            if len(parts) >= 2:
                authors_for_matching.append(f"{parts[0].strip()}, {parts[1].strip()}")
            else:
                authors_for_matching.append(authors_entry.strip())
        else:
            authors_for_matching.append(authors_entry.strip())
    
    display_authors = ', '.join(authors_list) if authors_list else ''
    matching_authors = ', '.join(authors_for_matching) if authors_for_matching else ''
    
    return display_authors, matching_authors

def _extract_affiliation(affiliation_entry):
    if isinstance(affiliation_entry, list):
        affiliations = []
        for affil in affiliation_entry:
            if isinstance(affil, dict):
                affil_name = affil.get('affilname', '')
                if affil_name:
                    affiliations.append(affil_name)
        return ', '.join(affiliations)
    elif isinstance(affiliation_entry, dict):
        return affiliation_entry.get('affilname', '')
    return ''

def fetch_scopus_data(organization_name=None, organization_id=None, include_all_doctypes=True):
    try:
        if organization_id:
            base_query = f'AF-ID({organization_id})'
        elif organization_name:
            base_query = f'AFFIL("{organization_name}")'
        else:
            base_query = 'AFFIL("Batangas State University")'
        query = base_query
        # Use view=COMPLETE to retrieve all authors per publication (STANDARD returns only first author).
        # Do not set 'field' — it overrides view and would revert to truncated author list.
        params = {
            'query': query,
            'count': 25,
            'start': 0,
            'view': 'COMPLETE',
        }
        
        all_publications = []
        document_type_counts = {}  
        start = 0
        max_results = 5000  
        api_total_count = 0  
        page_count = 0
        
        print(f"Scopus API Query: {query}")
        print(f"Including all document types: {include_all_doctypes}")
        
        while start < max_results:
            params['start'] = start
            
            response = _make_request_with_retry(
                SCOPUS_API_URL,
                params=params,
                headers=SCOPUS_HEADERS
            )
            
            if response.status_code != 200:
                error_msg = f"Error fetching Scopus data: {response.status_code}"
                
                content_type = response.headers.get('Content-Type', '').lower()
                is_html_error = 'text/html' in content_type or response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html')
                if response.status_code >= 500:
                    if is_html_error:
                        error_msg = "Scopus API server is temporarily unavailable (502/500 error). This is usually a temporary issue with Elsevier's servers. Please try again in a few minutes."
                    else:
                        error_msg = f"Scopus API server error ({response.status_code}). Please try again later."
                    
                    print(error_msg)
                    if all_publications:
                        print(f"Returning {len(all_publications)} publications retrieved before error")
                        break
                    else:
                        return {
                            'publications': [],
                            'total_publications': 0,
                            'citations': {},
                            'statistics': {},
                            'error': error_msg
                        }
                else:
                    error_detail = response.text[:200] if not is_html_error else "HTML error page received"
                    # If COMPLETE view is not allowed (401/403), fall back to STANDARD + field (may return only first author)
                    if response.status_code in (401, 403) and start == 0 and params.get('view') == 'COMPLETE':
                        print(f"COMPLETE view not available ({response.status_code}), falling back to STANDARD view (author list may be truncated).")
                        params.pop('view', None)
                        params['field'] = 'dc:title,dc:creator,prism:publicationName,prism:coverDate,prism:coverDisplayDate,prism:doi,prism:publisher,dc:publisher,citedby-count,affiliation,author,dc:identifier,subtypeDescription,subtype,subject-area,prism:aggregationType'
                        continue  # retry same page with STANDARD
                    print(f"{error_msg} - {error_detail}")
                    if all_publications:
                        print(f"Returning {len(all_publications)} publications retrieved before error")
                        break
                    else:
                        return {
                            'publications': [],
                            'total_publications': 0,
                            'citations': {},
                            'statistics': {},
                            'error': f"API error ({response.status_code}): {error_detail}"
                        }
            
            try:
                data = response.json()
            except ValueError as e:
                error_msg = "Scopus API returned invalid response. The server may be temporarily unavailable."
                print(f"{error_msg} Response preview: {response.text[:200]}")
                if all_publications:
                    print(f"Returning {len(all_publications)} publications retrieved before error")
                    break
                else:
                    return {
                        'publications': [],
                        'total_publications': 0,
                        'citations': {},
                        'statistics': {},
                        'error': error_msg
                    }
            
            search_results = data.get('search-results', {})
            entries = search_results.get('entry', [])
            
            if not entries:
                break
            
            page_count += 1
            print(f"Processing page {page_count}: start={start}, entries in page={len(entries)}")
            
            for entry in entries:
                title = entry.get('dc:title', '').strip()
                if not title:
                    title = entry.get('subtypeDescription', '') or entry.get('dc:identifier', 'Untitled Publication')
                    if title.startswith('SCOPUS_ID:'):
                        title = 'Untitled Publication'
                
                authors_entry = entry.get('author', [])
                dc_creator = entry.get('dc:creator', '')
                if len(all_publications) == 0:
                    print(f"DEBUG: 'author' field: {repr(entry.get('author', 'NOT_FOUND'))}")
                    print(f"DEBUG: 'dc:creator' field: {repr(dc_creator[:200]) if dc_creator else 'NOT_FOUND'}")
                
                if (not authors_entry or (isinstance(authors_entry, list) and len(authors_entry) == 0)) and dc_creator:
                    if isinstance(dc_creator, str) and dc_creator.strip():
                        author_strings = [a.strip() for a in dc_creator.split(';') if a.strip()]
                        authors_entry = []
                        for author_str in author_strings:
                            if ',' in author_str:
                                parts = [p.strip() for p in author_str.split(',')]
                                if len(parts) >= 2:
                                    surname = parts[0].strip()
                                    initials_str = ','.join(parts[1:]).strip()
                                    initials = initials_str.replace('.', '').replace(' ', '').upper()
                                    authors_entry.append({
                                        'surname': surname,
                                        'given-name': '',  
                                        'initials': initials
                                    })
                                else:
                                    authors_entry.append({
                                        'surname': author_str.strip(),
                                        'given-name': '',
                                        'initials': ''
                                    })
                            else:
                                authors_entry.append({
                                    'surname': author_str.strip(),
                                    'given-name': '',
                                    'initials': ''
                                })
                        if len(all_publications) == 0:
                            print(f"DEBUG: Converted dc:creator to {len(authors_entry)} author entries")
                            if authors_entry:
                                print(f"DEBUG: First converted author: {authors_entry[0]}")
                
                if not authors_entry or (isinstance(authors_entry, list) and len(authors_entry) == 0):
                    authors_entry = entry.get('authors', [])
                if not authors_entry or (isinstance(authors_entry, list) and len(authors_entry) == 0):
                    authors_entry = entry.get('authname', [])
                if len(all_publications) == 0:
                    print(f"\n=== DEBUG: First Publication Author Data ===")
                    print(f"Entry keys (first 20): {list(entry.keys())[:20]}")
                    print(f"'author' key exists: {'author' in entry}")
                    print(f"'authors' key exists: {'authors' in entry}")
                    print(f"'dc:creator' key exists: {'dc:creator' in entry}")
                    if 'dc:creator' in entry:
                        print(f"dc:creator value: {repr(entry.get('dc:creator', '')[:200])}")
                    print(f"Author entry type: {type(authors_entry)}")
                    print(f"Author entry value: {repr(authors_entry)}")
                    if authors_entry:
                        if isinstance(authors_entry, list):
                            print(f"Author entry is list with {len(authors_entry)} items")
                            if len(authors_entry) > 0:
                                print(f"First author entry: {authors_entry[0]}")
                                print(f"First author entry type: {type(authors_entry[0])}")
                                if isinstance(authors_entry[0], dict):
                                    print(f"First author entry keys: {list(authors_entry[0].keys())}")
                        elif isinstance(authors_entry, dict):
                            print(f"Author entry (dict) keys: {list(authors_entry.keys())}")
                            print(f"Author entry (dict): {authors_entry}")
                    else:
                        print("WARNING: authors_entry is empty or None!")
                    print("=" * 50)
                
                authors_display, authors_matching = _extract_authors(authors_entry)
                
                if len(all_publications) == 0:
                    print(f"DEBUG: Extracted authors_display: '{authors_display}'")
                    print(f"DEBUG: Extracted authors_matching: '{authors_matching}'")
                    if not authors_display and not authors_matching:
                        print("WARNING: No authors extracted! Check _extract_authors function.")
                
                authors = authors_display  
                authors_for_filter = authors_matching 
                cover_date = entry.get('prism:coverDate', '')
                cover_display_date = entry.get('prism:coverDisplayDate', '')
                year, month, day, date_str = _parse_publication_date(cover_date, cover_display_date)
                venue = entry.get('prism:publicationName', '')
                citations = entry.get('citedby-count', 0)
                try:
                    citations = int(citations) if citations else 0
                except (ValueError, TypeError):
                    citations = 0
                doi = entry.get('prism:doi', '')
                raw_id = entry.get('dc:identifier', '') or ''
                if isinstance(raw_id, str) and raw_id.strip().upper().startswith('SCOPUS_ID:'):
                    scopus_id = raw_id.strip().replace('SCOPUS_ID:', '', 1).strip()
                else:
                    scopus_id = (raw_id.strip() if isinstance(raw_id, str) else '') or ''
                subtype = entry.get('subtypeDescription', '')
                subtype_code = entry.get('subtype', '')
                aggregation_type = entry.get('prism:aggregationType', '')
                doc_type = subtype or subtype_code or aggregation_type or 'Unknown'
                document_type_counts[doc_type] = document_type_counts.get(doc_type, 0) + 1
                
                # Allow duplicates - do not skip publications with duplicate Scopus IDs
                # This helps retrieve all records including duplicates that may be in the API response
                
                affiliation = _extract_affiliation(entry.get('affiliation', []))
                link = f"https://www.scopus.com/record/display.uri?eid=2-s2.0-{scopus_id}" if scopus_id else ''
                
                subject_areas = []
                subject_area_entry = entry.get('subject-area', [])
                
                if isinstance(subject_area_entry, list):
                    for sa in subject_area_entry:
                        if isinstance(sa, dict):
                            area_name = sa.get('$', '') or sa.get('@abbrev', '') or sa.get('subject-area', '')
                            if area_name:
                                subject_areas.append(str(area_name).strip())
                        elif isinstance(sa, str):
                            subject_areas.append(sa.strip())
                elif isinstance(subject_area_entry, dict):
                    area_name = subject_area_entry.get('$', '') or subject_area_entry.get('@abbrev', '') or subject_area_entry.get('subject-area', '')
                    if area_name:
                        subject_areas.append(str(area_name).strip())
                elif isinstance(subject_area_entry, str):
                    subject_areas.append(subject_area_entry.strip())
                
                # Use actual publisher only (e.g. Elsevier B.V.); do not fall back to journal/conference title.
                # Try prism:publisher first (standard), then dc:publisher, then plain publisher.
                publisher = (entry.get('prism:publisher') or entry.get('dc:publisher') or entry.get('publisher') or '').strip()
                
                # DEBUG: Check why authors/publisher might be missing
                if len(all_publications) == 0:
                    print(f"DEBUG: First entry keys: {list(entry.keys())}")
                    print(f"DEBUG: prism:publisher: {repr(entry.get('prism:publisher'))}")
                    print(f"DEBUG: dc:publisher: {repr(entry.get('dc:publisher'))}")
                    print(f"DEBUG: publisher: {repr(entry.get('publisher'))}")
                    print(f"DEBUG: authors raw: {repr(entry.get('author') or entry.get('authors'))}")
                    print(f"DEBUG: dc:creator raw: {repr(entry.get('dc:creator'))}")
                    print(f"DEBUG: extracted authors: {authors}")
                publication = {
                    'title': title,
                    'authors': authors, 
                    'authors_matching': authors_for_filter,  
                    'year': year,
                    'month': month,
                    'day': day,
                    'date': date_str,
                    'venue': venue,
                    'publisher': publisher,
                    'citations': citations,
                    'link': link,
                    'doi': doi,
                    'affiliation': affiliation,
                    'subtype': subtype,
                    'subtype_code': subtype_code,
                    'aggregation_type': aggregation_type,
                    'document_type': doc_type,
                    'scopus_id': scopus_id,
                    'subject_areas': subject_areas
                }
                
                all_publications.append(publication)
            
            total_results = int(search_results.get('opensearch:totalResults', 0))
            items_per_page = int(search_results.get('opensearch:itemsPerPage', 25))
            if total_results > 0:
                api_total_count = total_results
            
            if start + items_per_page >= total_results or start + items_per_page >= max_results:
                break
            
            start += items_per_page
        
        total_citations = sum(p.get('citations', 0) for p in all_publications)
        citation_counts = sorted([p.get('citations', 0) for p in all_publications], reverse=True)
        h_index = 0
        for i, count in enumerate(citation_counts, 1):
            if count >= i:
                h_index = i
            else:
                break
        
        total_retrieved = len(all_publications)
        final_total = total_retrieved if total_retrieved > 0 else (api_total_count if api_total_count > 0 else 0)
        for doc_type, count in sorted(document_type_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {doc_type}: {count}")
        print("="*80 + "\n")
        
        if api_total_count > 0 and total_retrieved != api_total_count:
            discrepancy = api_total_count - total_retrieved
            print(f"NOTE: API reports {api_total_count} total results, retrieved {total_retrieved} records")
            if discrepancy > 0:
                print(f"      Difference: {discrepancy} records not retrieved")
                print(f"      Possible causes: suppressed records, indexing lag, or pagination limits")
            elif discrepancy < 0:
                print(f"      Retrieved {abs(discrepancy)} more records than API reported (may include duplicates)")
        
        return {
            'publications': all_publications,
            'total_publications': final_total,
            'processed_publications': len(all_publications), 
            'citations': {
                'total': total_citations,
                'h_index': h_index,
                'i10_index': 0  
            },
            'statistics': {
                'organization_name': organization_name or 'Batangas State University',
                'organization_id': organization_id,
                'source': 'scopus',
                'api_total_results': api_total_count
            }
        }
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Network error connecting to Scopus API: {str(e)}"
        print(error_msg)
        return {
            'publications': [],
            'total_publications': 0,
            'citations': {},
            'statistics': {},
            'error': 'Unable to connect to Scopus API. Please check your internet connection and try again.'
        }
    except Exception as e:
        error_msg = f"Error in fetch_scopus_data: {str(e)}"
        print(error_msg)
        return {
            'publications': [],
            'total_publications': 0,
            'citations': {},
            'statistics': {},
            'error': f'Error fetching data: {str(e)}'
        }

def search_organization_id(organization_name):
    try:
        affiliation_url = 'https://api.elsevier.com/content/search/affiliation'
        params = {
            'query': f'AFFILIATION({organization_name})',
            'count': 10
        }
        
        response = _make_request_with_retry(
            affiliation_url,
            params=params,
            headers=SCOPUS_HEADERS
        )
        
        if response.status_code != 200:
            if response.status_code >= 500:
                print(f"Error searching organization: {response.status_code} - Scopus API server error. Please try again later.")
            else:
                print(f"Error searching organization: {response.status_code} - {response.text[:200]}")
            return []
        
        data = response.json()
        search_results = data.get('search-results', {})
        entries = search_results.get('entry', [])
        
        organizations = []
        for entry in entries:
            affil_id = entry.get('dc:identifier', '').replace('AFFILIATION_ID:', '')
            affil_name = entry.get('affilname', '')
            city = entry.get('city', '')
            country = entry.get('country', '')
            
            if affil_id and affil_name:
                organizations.append({
                    'id': affil_id,
                    'name': affil_name,
                    'city': city,
                    'country': country
                })
        
        return organizations
        
    except Exception as e:
        print(f"Error in search_organization_id: {str(e)}")
        return []

def filter_publications_by_faculty(publications: list, faculty_list: list) -> dict:
    """
    Filter publications by faculty members and count by department.
    
    Logic:
    1. For each publication, check all authors
    2. If any author matches a faculty member in Excel
    3. Count that publication towards the faculty's department
    
    Args:
        publications: List of publication dictionaries from Scopus
        faculty_list: List of faculty dictionaries from Excel
    
    Returns:
        Dictionary with:
        - department_counts: Count of publications per department
        - faculty_publications: Publications grouped by faculty
        - matched_publications: List of matched publications with department info
    """
    from faculty_reader import match_author_to_faculty
    
    department_counts = {}
    faculty_publications = {}
    matched_publications = []
    matched_pub_ids = set()  # Track to avoid counting same publication twice
    
    print(f"\nFiltering {len(publications)} publications against {len(faculty_list)} faculty members...")
    
    # Debug: Show sample faculty names
    if faculty_list:
        print(f"Sample faculty names: {[f['name'] for f in faculty_list[:5]]}")
    
    match_attempts = 0
    match_failures = []
    
    for pub in publications:
        # Use authors_matching format if available, otherwise fall back to authors
        authors_str = pub.get('authors_matching', '') or pub.get('authors', '')
        
        # Debug: Check if authors field exists
        if match_attempts == 0:
            print(f"DEBUG: First publication - authors field exists: {'authors' in pub}")
            print(f"DEBUG: First publication - authors_matching field exists: {'authors_matching' in pub}")
            print(f"DEBUG: First publication - authors value: {repr(pub.get('authors', 'N/A')[:100])}")
            print(f"DEBUG: First publication - authors_matching value: {repr(pub.get('authors_matching', 'N/A')[:100])}")
            print(f"DEBUG: First publication - authors_str result: {repr(authors_str[:100])}")
        
        if not authors_str:
            if match_attempts == 0:
                print(f"DEBUG: WARNING - No authors string found in first publication!")
            continue
        
        # Parse authors - handle multiple formats:
        # Format 1: "Last, Initials, Last, Initials, ..." (e.g., "Sangalang, RGB, Manalo, AKG,")
        # Format 2: "Last Initials, Last Initials, ..." (e.g., "Tanglao R.S., Sangalang R.G.B.,")
        authors = []
        if ',' in authors_str:
            # Check if it's Format 1 (comma between last and initials) or Format 2 (space between)
            # Format 1: "Last, Initials" - comma separates last name from initials
            # Format 2: "Last Initials," - comma is just a separator between authors
            
            # Try Format 2 first: "Last Initials, Last Initials, ..."
            # Pattern: word(s) followed by initials (letters with dots), then comma
            import re
            # Match pattern like "Tanglao R.S.," or "Sangalang R.G.B.,"
            format2_pattern = r'([A-Za-z\s]+?)\s+([A-Z](?:\.[A-Z])*(?:\.[A-Z]+)?)\s*,'
            matches = re.findall(format2_pattern, authors_str + ',')  # Add comma at end for last match
            
            if matches:
                # Format 2 detected: "Last Initials,"
                for last_name, initials in matches:
                    # Clean last name (might have multiple words like "De Ocampo")
                    last_name = last_name.strip()
                    # Format as "Last, Initials" for matching
                    author = f"{last_name}, {initials}"
                    authors.append(author)
            else:
                # Format 1: "Last, Initials, Last, Initials, ..."
                parts = [p.strip() for p in authors_str.split(',')]
                i = 0
                while i < len(parts):
                    if i + 1 < len(parts):
                        # Combine "Last" and "Initials" as one author
                        author = f"{parts[i]}, {parts[i+1]}"
                        authors.append(author.rstrip(',').strip())
                        i += 2
                    else:
                        # Odd number of parts - might be just a last name
                        if parts[i].strip():
                            authors.append(parts[i].strip())
                        i += 1
        else:
            # No comma - might be single author "Last Initials" or "Last, Initials"
            # Try to parse as "Last Initials"
            import re
            match = re.match(r'^([A-Za-z\s]+?)\s+([A-Z](?:\.[A-Z])*(?:\.[A-Z]+)?)$', authors_str.strip())
            if match:
                last_name, initials = match.groups()
                authors.append(f"{last_name.strip()}, {initials}")
            else:
                authors = [authors_str.strip()]
        
        # Debug: Show sample authors from first publication
        if match_attempts == 0 and authors:
            print(f"Sample authors from first publication (matching format): {authors[:3]}")
            print(f"Original authors field: {pub.get('authors', 'N/A')[:100]}")
        
        # Match authors to faculty
        matched_faculty = []
        for author in authors:
            if not author:
                continue
            match_attempts += 1
            faculty = match_author_to_faculty(author, faculty_list)
            if faculty:
                matched_faculty.append(faculty)
            elif match_attempts <= 10:  # Log first 10 failed matches for debugging
                match_failures.append(author)
        
        # If any faculty matched, count publication towards their department(s)
        if matched_faculty:
            pub_id = pub.get('scopus_id') or pub.get('title', '')
            
            # Only process once per publication (even if multiple faculty match)
            if pub_id not in matched_pub_ids:
                matched_pub_ids.add(pub_id)
                
                # Get unique departments for this publication
                departments_for_pub = set()
                for faculty in matched_faculty:
                    dept = faculty.get('department', '').strip()
                    if dept:  # Only count if department is specified
                        departments_for_pub.add(dept)
                
                # Count publication towards each department (once per department)
                for dept in departments_for_pub:
                    department_counts[dept] = department_counts.get(dept, 0) + 1
                
                # Track publications per faculty member
                for faculty in matched_faculty:
                    faculty_name = faculty['name']
                    dept = faculty.get('department', '')
                    
                    if faculty_name not in faculty_publications:
                        faculty_publications[faculty_name] = {
                            'department': dept,
                            'position': faculty.get('position', ''),
                            'publications': []
                        }
                    
                    # Add publication to faculty's list (avoid duplicates)
                    existing_ids = [p.get('scopus_id') or p.get('title', '') 
                                   for p in faculty_publications[faculty_name]['publications']]
                    if pub_id not in existing_ids:
                        faculty_publications[faculty_name]['publications'].append(pub)
                
                pub_copy = pub.copy()
                pub_copy['matched_faculty'] = [f['name'] for f in matched_faculty]
                pub_copy['matched_departments'] = list(departments_for_pub)
                matched_publications.append(pub_copy)
    
    print(f"Matched {len(matched_publications)} publications across {len(department_counts)} departments")
    print(f"Total match attempts: {match_attempts}")
    
    if match_failures and len(matched_publications) == 0:
        print(f"\nDEBUG: First 10 unmatched author names:")
        for author in match_failures[:10]:
            print(f"  - {author}")
        print(f"\nDEBUG: Sample faculty names for comparison:")
        for faculty in faculty_list[:10]:
            print(f"  - {faculty['name']} (variants: {faculty.get('name_variants', [])[:2]})")
    
    return {
        'department_counts': department_counts,
        'faculty_publications': faculty_publications,
        'matched_publications': matched_publications,
        'total_matched': len(matched_publications)
    }
