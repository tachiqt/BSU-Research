import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

OPENALEX_API_KEY = (os.getenv("OPENALEX_API_KEY") or "").strip()
OPENALEX_BASE_URL = "https://api.openalex.org"


def _make_request_with_retry(url: str, params: Dict[str, Any], max_retries: int = 3, retry_delay: int = 2):
    last_exc = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers={"Accept": "application/json"}, timeout=45)
            if resp.status_code >= 500 and attempt < max_retries - 1:
                wait_time = retry_delay * (2**attempt)
                time.sleep(wait_time)
                continue
            return resp
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2**attempt)
                time.sleep(wait_time)
                continue
            raise
    if last_exc:
        raise last_exc
    return None


def _require_api_key_error() -> Dict[str, Any]:
    return {
        "error": "OpenAlex API key is missing. Set OPENALEX_API_KEY in backend/.env (OpenAlex requires api_key for reliable access as of Feb 2026)."
    }


def _normalize_doi(doi: Optional[str]) -> str:
    if not doi:
        return ""
    s = str(doi).strip().lower()
    s = s.replace("https://doi.org/", "").replace("http://doi.org/", "")
    s = s.replace("doi:", "").strip()
    return s


_TITLE_CLEAN_RE = re.compile(r"[^a-z0-9]+")
def _normalize_title(title: Optional[str]) -> str:
    if not title:
        return ""
    s = str(title).strip().lower()
    s = _TITLE_CLEAN_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _parse_ymd(publication_date: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[str]]:
    if not publication_date:
        return None, None, None, None
    s = str(publication_date).strip()
    parts = s.split("-")
    try:
        year = int(parts[0]) if len(parts) >= 1 and parts[0] else None
    except ValueError:
        year = None
    month = None
    day = None
    try:
        if len(parts) >= 2 and parts[1]:
            month = int(parts[1])
    except ValueError:
        month = None
    try:
        if len(parts) >= 3 and parts[2]:
            day = int(parts[2])
    except ValueError:
        day = None

    date_str = None
    if year:
        if month and day:
            date_str = f"{year}/{month:02d}/{day:02d}"
        elif month:
            date_str = f"{year}/{month:02d}"
        else:
            date_str = str(year)
    return year, month, day, date_str


_SURNAME_PARTICLES = {
    "de",
    "del",
    "della",
    "di",
    "da",
    "dos",
    "das",
    "van",
    "von",
    "la",
    "le",
    "du",
    "st",
    "st.",
}


def _name_to_surname_and_initials(display_name: str) -> Tuple[str, str]:
    if not display_name:
        return "", ""
    tokens = [t for t in str(display_name).strip().split() if t]
    if not tokens:
        return "", ""

    surname_tokens = [tokens[-1]]
    i = len(tokens) - 2
    while i >= 0 and tokens[i].strip(".,").lower() in _SURNAME_PARTICLES:
        surname_tokens.insert(0, tokens[i])
        i -= 1

    surname = " ".join(surname_tokens).strip()
    given_tokens = tokens[: max(0, len(tokens) - len(surname_tokens))]
    initials = "".join([t[0].upper() for t in given_tokens if t and t[0].isalpha()])
    return surname, initials


def _extract_authors_from_work(work: Dict[str, Any]) -> Tuple[str, str]:
    authorships = work.get("authorships") or []
    display_names: List[str] = []
    matching_names: List[str] = []
    for a in authorships:
        author = (a or {}).get("author") or {}
        name = (author.get("display_name") or "").strip()
        if not name:
            continue
        display_names.append(name)
        surname, initials = _name_to_surname_and_initials(name)
        if surname:
            matching_names.append(f"{surname}, {initials}".strip().rstrip(","))
    return ", ".join(display_names), ", ".join(matching_names)


def search_institution_id(institution_name: str, prefer_country_code: str = "PH") -> Optional[str]:
    if not institution_name:
        return None
    if not OPENALEX_API_KEY:
        return None

    url = f"{OPENALEX_BASE_URL}/institutions"
    params = {"search": institution_name, "per-page": 10, "api_key": OPENALEX_API_KEY}
    resp = _make_request_with_retry(url, params=params)
    if resp is None or resp.status_code != 200:
        return None
    data = resp.json() or {}
    results = data.get("results") or []
    if not results:
        return None

    norm_target = _normalize_title(institution_name)
    best = None
    best_score = -1
    for inst in results:
        dn = (inst.get("display_name") or "").strip()
        inst_id = (inst.get("id") or "").strip()
        country = (inst.get("country_code") or "").strip().upper()
        if not inst_id:
            continue

        score = 0
        if prefer_country_code and country == prefer_country_code.upper():
            score += 10
        if _normalize_title(dn) == norm_target:
            score += 20
        elif norm_target and norm_target in _normalize_title(dn):
            score += 5

        if score > best_score:
            best_score = score
            best = inst_id

    if not best:
        return None
    m = re.search(r"/I(\d+)$", best)
    return f"I{m.group(1)}" if m else (best.replace("https://openalex.org/", "") if best.startswith("https://openalex.org/") else best)


def fetch_openalex_works_for_institution(
    institution_id: str,
    max_results: int = 20000,
) -> Dict[str, Any]:
    if not OPENALEX_API_KEY:
        return {"works": [], "total": 0, "processed": 0, **_require_api_key_error()}
    if not institution_id:
        return {"works": [], "total": 0, "processed": 0, "error": "OpenAlex institution_id is required (e.g. I123456789)."}

    inst = institution_id.strip()
    if inst.startswith("https://openalex.org/"):
        inst = inst.replace("https://openalex.org/", "", 1).strip()
    if inst and inst[0].lower() == "i":
        inst = "I" + inst[1:]

    url = f"{OPENALEX_BASE_URL}/works"
    per_page = 200
    cursor = "*"
    works: List[Dict[str, Any]] = []
    total = 0

    select = ",".join(
        [
            "id",
            "ids",
            "doi",
            "display_name",
            "publication_year",
            "publication_date",
            "type",
            "type_crossref",
            "cited_by_count",
            "authorships",
            "primary_location",
            "locations",
        ]
    )

    while cursor and len(works) < max_results:
        params = {
            "filter": f"institutions.id:{inst}",
            "per-page": per_page,
            "cursor": cursor,
            "select": select,
            "api_key": OPENALEX_API_KEY,
        }
        resp = _make_request_with_retry(url, params=params)
        if resp.status_code != 200:
            detail = (resp.text or "")[:200]
            return {
                "works": works,
                "total": total or len(works),
                "processed": len(works),
                "error": f"Error fetching OpenAlex works: {resp.status_code} - {detail}",
            }

        data = resp.json() or {}
        meta = data.get("meta") or {}
        if not total:
            try:
                total = int(meta.get("count") or 0)
            except (ValueError, TypeError):
                total = 0

        batch = data.get("results") or []
        if not batch:
            break
        works.extend(batch)
        cursor = meta.get("next_cursor")

        if len(batch) < per_page:
            break

    return {"works": works[:max_results], "total": total or len(works), "processed": len(works[:max_results])}


def fetch_openalex_works_by_dois(dois: List[str]) -> Dict[str, Any]:
    if not OPENALEX_API_KEY:
        return {"works": [], "processed": 0, **_require_api_key_error()}

    norm_dois = []
    for d in dois or []:
        nd = _normalize_doi(d)
        if nd:
            norm_dois.append(nd)

    seen = set()
    unique = []
    for d in norm_dois:
        if d in seen:
            continue
        seen.add(d)
        unique.append(d)

    if not unique:
        return {"works": [], "processed": 0}

    url = f"{OPENALEX_BASE_URL}/works"
    select = ",".join(
        [
            "id",
            "ids",
            "doi",
            "display_name",
            "publication_year",
            "publication_date",
            "type",
            "type_crossref",
            "cited_by_count",
            "authorships",
            "primary_location",
            "locations",
        ]
    )

    works: List[Dict[str, Any]] = []
    batch_size = 100
    for i in range(0, len(unique), batch_size):
        batch = unique[i : i + batch_size]
        values = "|".join([f"https://doi.org/{d}" for d in batch])
        params = {
            "filter": f"doi:{values}",
            "per-page": 100,
            "select": select,
            "api_key": OPENALEX_API_KEY,
        }
        resp = _make_request_with_retry(url, params=params)
        if resp.status_code != 200:
            detail = (resp.text or "")[:200]
            return {"works": works, "processed": len(works), "error": f"Error fetching OpenAlex works by DOI: {resp.status_code} - {detail}"}

        data = resp.json() or {}
        results = data.get("results") or []
        works.extend(results)

    return {"works": works, "processed": len(works)}


def _work_to_publication(work: Dict[str, Any]) -> Dict[str, Any]:
    title = (work.get("display_name") or "").strip()
    doi = work.get("doi") or (work.get("ids") or {}).get("doi") or ""
    doi_norm = _normalize_doi(doi)
    year = work.get("publication_year")
    pub_date = work.get("publication_date")
    y, m, d, date_str = _parse_ymd(pub_date)
    if not year and y:
        year = y

    authors_display, authors_matching = _extract_authors_from_work(work)

    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    venue = (source.get("display_name") or "").strip()

    landing_page_url = (primary_location.get("landing_page_url") or "").strip()
    link = landing_page_url
    if doi_norm:
        link = f"https://doi.org/{doi_norm}"

    citations = work.get("cited_by_count") or 0
    try:
        citations = int(citations)
    except (ValueError, TypeError):
        citations = 0

    openalex_id = (work.get("id") or (work.get("ids") or {}).get("openalex") or "").strip()

    publisher = ""

    return {
        "title": title,
        "authors": authors_display,
        "authors_matching": authors_matching,
        "year": year,
        "month": m,
        "day": d,
        "date": date_str,
        "venue": venue,
        "publisher": publisher,
        "citations": citations,
        "link": link,
        "doi": doi_norm,
        "affiliation": "",
        "document_type": (work.get("type_crossref") or work.get("type") or ""),
        "openalex_id": openalex_id,
        "source": "openalex",
    }


def filter_openalex_publications_by_scopus(
    openalex_works: List[Dict[str, Any]],
    scopus_publications: List[Dict[str, Any]],
) -> Dict[str, Any]:
    doi_to_scopus: Dict[str, Dict[str, Any]] = {}
    title_year_to_scopus: Dict[Tuple[str, Optional[int]], Dict[str, Any]] = {}
    title_counts: Dict[str, int] = {}
    title_only_to_scopus: Dict[str, Dict[str, Any]] = {}

    for sp in scopus_publications or []:
        sdoi = _normalize_doi(sp.get("doi"))
        if sdoi and sdoi not in doi_to_scopus:
            doi_to_scopus[sdoi] = sp

        st = _normalize_title(sp.get("title"))
        if st:
            title_counts[st] = title_counts.get(st, 0) + 1
            if st not in title_only_to_scopus:
                title_only_to_scopus[st] = sp

            sy = sp.get("year")
            try:
                sy_int = int(sy) if sy is not None and sy != "" else None
            except (ValueError, TypeError):
                sy_int = None
            key = (st, sy_int)
            if key not in title_year_to_scopus:
                title_year_to_scopus[key] = sp

    filtered: List[Dict[str, Any]] = []
    matched_by = {"doi": 0, "title_year": 0, "title_only": 0}

    for w in openalex_works or []:
        pub = _work_to_publication(w)

        odoi = _normalize_doi(pub.get("doi"))
        if odoi and odoi in doi_to_scopus:
            sp = doi_to_scopus[odoi]
            pub["scopus_id"] = sp.get("scopus_id", "")
            pub["matched_by"] = "doi"
            pub["indexing"] = "Scopus"
            filtered.append(pub)
            matched_by["doi"] += 1
            continue

        ot = _normalize_title(pub.get("title"))
        oy = pub.get("year")
        try:
            oy_int = int(oy) if oy is not None and oy != "" else None
        except (ValueError, TypeError):
            oy_int = None

        if ot and (ot, oy_int) in title_year_to_scopus:
            sp = title_year_to_scopus[(ot, oy_int)]
            pub["scopus_id"] = sp.get("scopus_id", "")
            pub["matched_by"] = "title_year"
            pub["indexing"] = "Scopus"
            filtered.append(pub)
            matched_by["title_year"] += 1
            continue

        if ot and title_counts.get(ot, 0) == 1 and ot in title_only_to_scopus:
            sp = title_only_to_scopus[ot]
            pub["scopus_id"] = sp.get("scopus_id", "")
            pub["matched_by"] = "title_only"
            pub["indexing"] = "Scopus"
            filtered.append(pub)
            matched_by["title_only"] += 1
            continue

    return {
        "publications": filtered,
        "processed_openalex": len(openalex_works or []),
        "matched_total": len(filtered),
        "matched_by": matched_by,
    }


def mix_scopus_with_openalex_when_available(
    openalex_works: List[Dict[str, Any]],
    scopus_publications: List[Dict[str, Any]],
) -> Dict[str, Any]:
    openalex_pubs = [_work_to_publication(w) for w in (openalex_works or [])]

    doi_to_oa: Dict[str, Dict[str, Any]] = {}
    title_year_to_oa: Dict[Tuple[str, Optional[int]], Dict[str, Any]] = {}
    title_counts_oa: Dict[str, int] = {}
    title_only_to_oa: Dict[str, Dict[str, Any]] = {}

    for op in openalex_pubs:
        od = _normalize_doi(op.get("doi"))
        if od and od not in doi_to_oa:
            doi_to_oa[od] = op

        ot = _normalize_title(op.get("title"))
        if ot:
            title_counts_oa[ot] = title_counts_oa.get(ot, 0) + 1
            if ot not in title_only_to_oa:
                title_only_to_oa[ot] = op

            oy = op.get("year")
            try:
                oy_int = int(oy) if oy is not None and oy != "" else None
            except (ValueError, TypeError):
                oy_int = None
            key = (ot, oy_int)
            if key not in title_year_to_oa:
                title_year_to_oa[key] = op

    mixed: List[Dict[str, Any]] = []
    used_openalex = 0
    used_scopus = 0
    used_by = {"doi": 0, "title_year": 0, "title_only": 0}

    for sp in scopus_publications or []:
        sdoi = _normalize_doi(sp.get("doi"))
        st = _normalize_title(sp.get("title"))
        sy = sp.get("year")
        try:
            sy_int = int(sy) if sy is not None and sy != "" else None
        except (ValueError, TypeError):
            sy_int = None

        match = None
        match_kind = None
        if sdoi and sdoi in doi_to_oa:
            match = doi_to_oa[sdoi]
            match_kind = "doi"
        elif st and (st, sy_int) in title_year_to_oa:
            match = title_year_to_oa[(st, sy_int)]
            match_kind = "title_year"
        elif st and title_counts_oa.get(st, 0) == 1 and st in title_only_to_oa:
            match = title_only_to_oa[st]
            match_kind = "title_only"

        if not match:
            pub = dict(sp)
            pub["source"] = pub.get("source") or "scopus"
            pub["indexing"] = pub.get("indexing") or "Scopus"
            pub["matched_by"] = "scopus_only"
            mixed.append(pub)
            used_scopus += 1
            continue

        pub = dict(match)
        pub["source"] = "openalex"
        pub["indexing"] = "Scopus"
        pub["matched_by"] = match_kind
        pub["scopus_id"] = sp.get("scopus_id", pub.get("scopus_id", ""))
        pub["subtype"] = sp.get("subtype", pub.get("subtype", ""))
        pub["subtype_code"] = sp.get("subtype_code", pub.get("subtype_code", ""))
        pub["aggregation_type"] = sp.get("aggregation_type", pub.get("aggregation_type", ""))
        pub["document_type"] = sp.get("document_type", pub.get("document_type", ""))
        pub["subject_areas"] = sp.get("subject_areas", pub.get("subject_areas", []))
        pub["affiliation"] = sp.get("affiliation", pub.get("affiliation", ""))
        pub["title"] = pub.get("title") or sp.get("title") or ""
        pub["doi"] = _normalize_doi(pub.get("doi") or sp.get("doi"))
        pub["year"] = sp.get("year") if sp.get("year") not in (None, "") else pub.get("year")
        pub["month"] = sp.get("month") if sp.get("month") not in (None, "") else pub.get("month")
        pub["day"] = sp.get("day") if sp.get("day") not in (None, "") else pub.get("day")
        pub["date"] = sp.get("date") or pub.get("date")
        pub["venue"] = pub.get("venue") or sp.get("venue") or ""
        pub["publisher"] = pub.get("publisher") or sp.get("publisher") or ""
        pub["link"] = pub.get("link") or sp.get("link") or ""
        pub["authors"] = pub.get("authors") or sp.get("authors") or ""
        pub["authors_matching"] = pub.get("authors_matching") or sp.get("authors_matching") or ""
        pub["citations"] = sp.get("citations", pub.get("citations", 0))

        mixed.append(pub)
        used_openalex += 1
        if match_kind in used_by:
            used_by[match_kind] += 1

    return {
        "publications": mixed,
        "total": len(mixed),
        "openalex_used": used_openalex,
        "scopus_used": used_scopus,
        "openalex_match_by": used_by,
        "processed_openalex": len(openalex_works or []),
        "processed_scopus": len(scopus_publications or []),
    }

