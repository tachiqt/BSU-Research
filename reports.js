/**
 * Export Report page: preview and export Excel using template.
 * Filters and preview table are user-driven.
 */

(function () {
    const API_BASE = (typeof window !== 'undefined' && window.API_BASE !== undefined && window.API_BASE !== '')
        ? window.API_BASE
        : (typeof window !== 'undefined' && window.location.protocol !== 'file:' && window.location.host)
            ? ''
            : 'http://localhost:5000';

    // Keep the exact preview rows so export matches the preview 1:1
    let lastPreviewPublications = null;
    const PREVIEW_PAGE_SIZE = 20;
    let currentPreviewPage = 1;

    function getFilters() {
        const fiscalYear = document.getElementById('fiscalYear');
        const yearFilter = document.getElementById('yearFilter');
        return {
            fiscal_year: (fiscalYear && fiscalYear.value) || String(new Date().getFullYear()),
            quarter: (document.getElementById('quarter') && document.getElementById('quarter').value) || '4th',
            campus: (document.getElementById('campus') && document.getElementById('campus').value.trim()) || 'ALANGILAN',
            year: (yearFilter && yearFilter.value) || '',
        };
    }

    function buildPreviewQuery() {
        const f = getFilters();
        const params = new URLSearchParams();
        if (f.fiscal_year) params.set('fiscal_year', f.fiscal_year);
        if (f.quarter) params.set('quarter', f.quarter);
        if (f.campus) params.set('campus', f.campus);
        if (f.year) params.set('year', f.year);
        return params.toString();
    }

    function showError(el, msg) {
        if (!el) return;
        el.textContent = msg || '';
        el.style.display = msg ? 'block' : 'none';
        if (el.classList) {
            if (msg) el.classList.add('error'); else el.classList.remove('error');
        }
    }

    function hidePagination() {
        const paginationEl = document.getElementById('previewPagination');
        if (paginationEl) paginationEl.style.display = 'none';
    }

    function renderPreviewPage(page) {
        const tbody = document.getElementById('previewTableBody');
        if (!tbody || !lastPreviewPublications) return;
        currentPreviewPage = page;
        const total = lastPreviewPublications.length;
        const start = (page - 1) * PREVIEW_PAGE_SIZE;
        const end = Math.min(start + PREVIEW_PAGE_SIZE, total);
        const pagePubs = lastPreviewPublications.slice(start, end);
        tbody.innerHTML = pagePubs.map(function (p, i) {
            const no = start + i + 1;
            return '<tr>' +
                '<td>' + no + '</td>' +
                '<td>' + escapeHtml(p.title || '') + '</td>' +
                '<td>' + escapeHtml((p.authors || '').replace(/\n/g, ', ')) + '</td>' +
                '<td>' + escapeHtml(p.college_campus || '') + '</td>' +
                '<td>' + escapeHtml(p.venue || '') + '</td>' +
                '<td>' + escapeHtml(p.pub_type || '') + '</td>' +
                '</tr>';
        }).join('');
    }

    function renderPagination() {
        const paginationEl = document.getElementById('previewPagination');
        const infoEl = document.getElementById('previewPaginationInfo');
        const controlsEl = document.getElementById('previewPageNumbers');
        const btnPrev = document.getElementById('btnPreviewPrev');
        const btnNext = document.getElementById('btnPreviewNext');
        if (!paginationEl || !lastPreviewPublications) return;
        const total = lastPreviewPublications.length;
        if (total <= PREVIEW_PAGE_SIZE) {
            paginationEl.style.display = 'none';
            return;
        }
        const totalPages = Math.ceil(total / PREVIEW_PAGE_SIZE);
        const start = (currentPreviewPage - 1) * PREVIEW_PAGE_SIZE + 1;
        const end = Math.min(currentPreviewPage * PREVIEW_PAGE_SIZE, total);
        if (infoEl) infoEl.textContent = 'Showing ' + start + '–' + end + ' of ' + total + ' entries';
        if (btnPrev) {
            btnPrev.disabled = currentPreviewPage <= 1;
        }
        if (btnNext) {
            btnNext.disabled = currentPreviewPage >= totalPages;
        }
        if (controlsEl) {
            // Progressive/sliding window: show 3 page numbers (e.g. 1,2,3 -> click 2 -> 2,3,4)
            var startPage = currentPreviewPage;
            var endPage = Math.min(currentPreviewPage + 2, totalPages);
            var html = '';
            for (var p = startPage; p <= endPage; p++) {
                var active = p === currentPreviewPage ? ' active' : '';
                html += '<button type="button" class="btn-page-num' + active + '" data-page="' + p + '">' + p + '</button>';
            }
            controlsEl.innerHTML = html;
            controlsEl.querySelectorAll('.btn-page-num').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var page = parseInt(btn.getAttribute('data-page'), 10);
                    if (page >= 1 && page <= totalPages) {
                        renderPreviewPage(page);
                        renderPagination();
                    }
                });
            });
        }
        paginationEl.style.display = 'flex';
    }

    function goPreviewPrev() {
        if (!lastPreviewPublications) return;
        const totalPages = Math.ceil(lastPreviewPublications.length / PREVIEW_PAGE_SIZE);
        if (currentPreviewPage > 1) {
            renderPreviewPage(currentPreviewPage - 1);
            renderPagination();
        }
    }

    function goPreviewNext() {
        if (!lastPreviewPublications) return;
        const totalPages = Math.ceil(lastPreviewPublications.length / PREVIEW_PAGE_SIZE);
        if (currentPreviewPage < totalPages) {
            renderPreviewPage(currentPreviewPage + 1);
            renderPagination();
        }
    }

    function loadPreview() {
        const tbody = document.getElementById('previewTableBody');
        const summary = document.getElementById('previewSummary');
        const btn = document.getElementById('btnPreview');
        if (!tbody) return;

        const qs = buildPreviewQuery();
        const url = `${API_BASE}/api/report/preview${qs ? '?' + qs : ''}`;

        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Loading...';
        }
        tbody.innerHTML = '<tr><td colspan="6"><i class="fa fa-spinner fa-spin"></i> Loading preview...</td></tr>';
        if (summary) summary.style.display = 'none';

        fetch(url)
            .then(function (res) {
                if (!res.ok) throw new Error('Preview failed: ' + res.status);
                return res.json();
            })
            .then(function (data) {
                const pubs = data.publications || [];
                const filters = data.filters || {};
                lastPreviewPublications = pubs;
                if (summary) {
                    summary.innerHTML =
                        'Fiscal Year: <strong>' + (filters.fiscal_year || '') + '</strong> | ' +
                        'Quarter: <strong>' + (filters.quarter || '') + '</strong> | ' +
                        'Campus: <strong>' + (filters.campus || '') + '</strong>' +
                        (filters.year_filter ? ' | Publication year: <strong>' + filters.year_filter + '</strong>' : '') +
                        ' — <strong>' + (data.total_count || pubs.length) + '</strong> publication(s).';
                    summary.style.display = 'block';
                }
                if (pubs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="preview-empty">No publications match the current filters.</td></tr>';
                    hidePagination();
                } else {
                    currentPreviewPage = 1;
                    renderPreviewPage(1);
                    renderPagination();
                }
            })
            .catch(function (err) {
                tbody.innerHTML = '<tr><td colspan="6" class="preview-error">Failed to load preview: ' + escapeHtml(err.message) + '</td></tr>';
                if (summary) summary.style.display = 'none';
                hidePagination();
            })
            .finally(function () {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa fa-eye"></i> Preview Report';
                }
            });
    }

    function exportReport() {
        const btn = document.getElementById('btnExport');
        const msgEl = document.getElementById('exportMessage');
        const filters = getFilters();

        if (!lastPreviewPublications) {
            showError(msgEl, 'Please click \"Preview Report\" first so the export matches the preview.');
            return;
        }

        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Generating...';
        }
        showError(msgEl, '');

        fetch(API_BASE + '/api/report/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                fiscal_year: filters.fiscal_year,
                quarter: filters.quarter,
                campus: filters.campus,
                year: filters.year,
                year_filter: filters.year,
                publications: lastPreviewPublications,
            }),
        })
            .then(function (res) {
                if (!res.ok) {
                    return res.json().then(function (j) { throw new Error(j.error || res.statusText); });
                }
                return res.blob().then(function (blob) {
                    return { blob: blob, res: res };
                });
            })
            .then(function (result) {
                var blob = result.blob;
                var res = result.res;
                var filename = 'RESEARCH_AL_Quarterly_Report.xlsx';
                var disposition = res.headers && res.headers.get && res.headers.get('Content-Disposition');
                if (disposition && disposition.indexOf('filename=') !== -1) {
                    var m = disposition.match(/filename[*]?=(?:UTF-8'')?([^;\s]+)/i);
                    if (m && m[1]) filename = m[1].replace(/^["']|["']$/g, '');
                }
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = filename;
                a.click();
                URL.revokeObjectURL(url);
                if (msgEl) {
                    msgEl.textContent = 'Report downloaded successfully.';
                    msgEl.style.display = 'block';
                    msgEl.classList.remove('error');
                }
            })
            .catch(function (err) {
                showError(msgEl, 'Export failed: ' + (err.message || 'Unknown error'));
            })
            .finally(function () {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa fa-download"></i> Export to Excel';
                }
            });
    }

    function escapeHtml(s) {
        if (s == null) return '';
        var div = document.createElement('div');
        div.textContent = s;
        return div.innerHTML;
    }

    function populateYearFilter() {
        var sel = document.getElementById('yearFilter');
        if (!sel) return;
        var year = new Date().getFullYear();
        var html = '<option value="">All years</option>';
        for (var y = year; y >= year - 10; y--) {
            html += '<option value="' + y + '">' + y + '</option>';
        }
        sel.innerHTML = html;
    }

    function initFiscalYear() {
        var el = document.getElementById('fiscalYear');
        if (el && !el.value) el.value = String(new Date().getFullYear());
    }

    function resetFilters() {
        var fy = document.getElementById('fiscalYear');
        var quarter = document.getElementById('quarter');
        var campus = document.getElementById('campus');
        var yearFilter = document.getElementById('yearFilter');
        if (fy) fy.value = String(new Date().getFullYear());
        if (quarter) quarter.value = '4th';
        if (campus) campus.value = 'ALANGILAN';
        if (yearFilter) yearFilter.value = '';
    }

    function initSidebar() {
        var menu = document.getElementById('sidebarMenu');
        var overlay = document.getElementById('sidebarOverlay');
        var openBtn = document.getElementById('menuToggle');
        var closeBtn = document.getElementById('sidebarClose');
        if (openBtn) openBtn.addEventListener('click', function () { if (menu) menu.classList.add('active'); if (overlay) overlay.classList.add('active'); });
        if (closeBtn) closeBtn.addEventListener('click', function () { if (menu) menu.classList.remove('active'); if (overlay) overlay.classList.remove('active'); });
        if (overlay) overlay.addEventListener('click', function () { if (menu) menu.classList.remove('active'); if (overlay) overlay.classList.remove('active'); });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initFiscalYear();
        populateYearFilter();
        initSidebar();
        var btnPreview = document.getElementById('btnPreview');
        var btnExport = document.getElementById('btnExport');
        if (btnPreview) btnPreview.addEventListener('click', loadPreview);
        if (btnExport) btnExport.addEventListener('click', exportReport);
        var btnReset = document.getElementById('btnResetFilters');
        if (btnReset) btnReset.addEventListener('click', resetFilters);
        var btnPreviewPrev = document.getElementById('btnPreviewPrev');
        var btnPreviewNext = document.getElementById('btnPreviewNext');
        if (btnPreviewPrev) btnPreviewPrev.addEventListener('click', goPreviewPrev);
        if (btnPreviewNext) btnPreviewNext.addEventListener('click', goPreviewNext);
    });
})();
