import argparse
import json
from scopus import fetch_scopus_data, search_organization_id

def analyze_document_types(publications):
    doc_types = {}
    missing_ids = []
    
    for pub in publications:
        doc_type = pub.get('document_type', 'Unknown')
        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        
        if not pub.get('scopus_id'):
            missing_ids.append(pub.get('title', 'Untitled')[:50])
    
    return doc_types, missing_ids

def verify_api_results(organization_name=None, organization_id=None):
    if organization_name and not organization_id:
        orgs = search_organization_id(organization_name)
        if orgs:
            for i, org in enumerate(orgs[:5], 1):
                print(f"  {i}. {org['name']} (ID: {org['id']}, {org.get('city', 'N/A')}, {org.get('country', 'N/A')})")
            if orgs:
                print(f"\nUsing first match: {orgs[0]['name']} (ID: {orgs[0]['id']})")
                organization_id = orgs[0]['id']
                organization_name = orgs[0]['name']
        else:
            print(f"  No exact match found. Using name-based query.")
    print(f"\nFetching data for: {organization_name or 'Batangas State University'}")
    if organization_id:
        print(f"Using Affiliation ID: {organization_id}")
    
    result = fetch_scopus_data(
        organization_name=organization_name,
        organization_id=organization_id,
        include_all_doctypes=True
    )
    
    if result.get('error'):
        print(f"\nERROR: {result['error']}")
        return
    
    publications = result.get('publications', [])
    api_total = result.get('statistics', {}).get('api_total_results', 0)
    final_total = result.get('total_publications', 0)
    processed = result.get('processed_publications', 0)
    
    print("\n" + "-"*80)
    print("RESULTS SUMMARY")
    print("-"*80)
    print(f"API Reported Total:     {api_total}")
    print(f"Records Processed:     {processed}")
    print(f"Final Total:           {final_total}")
    print(f"Unique Publications:   {len(publications)}")
    doc_types, missing_ids = analyze_document_types(publications)
    
    print("\n" + "-"*80)
    print("DOCUMENT TYPE DISTRIBUTION")
    print("-"*80)
    for doc_type, count in sorted(doc_types.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(publications) * 100) if publications else 0
        print(f"  {doc_type:30s}: {count:4d} ({percentage:5.1f}%)")
    
    if missing_ids:
        print(f"\nWARNING: {len(missing_ids)} records without Scopus ID")
        print("  This may indicate incomplete data or API issues")
        if len(missing_ids) <= 5:
            for title in missing_ids:
                print(f"    - {title}...")
    export_file = "scopus_api_results.json"
    export_data = {
        'organization_name': organization_name,
        'organization_id': organization_id,
        'api_total': api_total,
        'final_total': final_total,
        'processed': processed,
        'unique_count': len(publications),
        'document_types': doc_types,
        'sample_titles': [p.get('title', '')[:100] for p in publications[:10]]
    }
    
    with open(export_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults exported to: {export_file}")
    print("="*80 + "\n")
    
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Verify Scopus API results')
    parser.add_argument('--organization', '-o', help='Organization name')
    parser.add_argument('--org-id', '-i', help='Scopus Affiliation ID')
    
    args = parser.parse_args()
    
    verify_api_results(
        organization_name=args.organization,
        organization_id=args.org_id
    )
