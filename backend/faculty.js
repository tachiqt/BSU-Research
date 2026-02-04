const API_BASE_URL = (typeof window !== 'undefined' && window.API_BASE_URL !== undefined && window.API_BASE_URL !== '')
    ? window.API_BASE_URL
    : (typeof window !== 'undefined' && window.location.protocol !== 'file:' && window.location.host !== '')
        ? '/api'
        : 'http://localhost:5000/api';
const ITEMS_PER_PAGE = 10;

let currentPage = 1;
let allFacultyData = [];
let filteredFacultyData = [];

const DEFAULT_DEPARTMENTS = [
    'College of Architecture Fine Arts and Design',
    'College of Informatics and Computing Sciences',
    'College of Engineering',
    'College of Engineering Technology'
];

document.addEventListener('DOMContentLoaded', function() {
    initHamburgerMenu();
    loadDepartments();
    loadFacultyCount();
    loadFacultyList();
    document.getElementById('addFacultyForm').addEventListener('submit', handleAddFaculty);
    document.getElementById('uploadExcelForm').addEventListener('submit', handleUploadExcel);
    document.getElementById('editFacultyForm').addEventListener('submit', handleEditFaculty);
    document.getElementById('searchFaculty').addEventListener('input', handleSearch);
});

function normalizeDepartmentName(name) {
    if (!name || typeof name !== 'string') return '';
    var s = name.trim();
    if (s === '' || s === 'Select department...') return '';
    if (s === 'College of Architecture, Fine Arts and Design') return 'College of Architecture Fine Arts and Design';
    return s;
}

async function loadDepartments() {
    try {
        const response = await fetch(`${API_BASE_URL}/faculty/departments`);
        const data = await response.json();
        let raw = (data.departments && data.departments.length) ? data.departments : DEFAULT_DEPARTMENTS;
        var list = [];
        var seen = {};
        raw.forEach(function(dept) {
            var norm = normalizeDepartmentName(dept);
            if (norm && !seen[norm]) {
                seen[norm] = true;
                list.push(norm);
            }
        });
        list.sort();
        
        function fillSelect(selectId) {
            const sel = document.getElementById(selectId);
            if (!sel) return;
            const currentVal = sel.value;
            sel.innerHTML = '';
            var placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = 'Select department...';
            sel.appendChild(placeholder);
            list.forEach(function(dept) {
                const opt = document.createElement('option');
                opt.value = dept;
                opt.textContent = dept;
                sel.appendChild(opt);
            });
            if (currentVal && list.indexOf(currentVal) !== -1) {
                sel.value = currentVal;
            }
        }
        fillSelect('facultyDepartment');
        fillSelect('editFacultyDepartment');
    } catch (e) {
        const list = DEFAULT_DEPARTMENTS;
        ['facultyDepartment', 'editFacultyDepartment'].forEach(function(selectId) {
            const sel = document.getElementById(selectId);
            if (!sel) return;
            sel.innerHTML = '';
            sel.appendChild(document.createElement('option')).value = '';
            sel.options[0].textContent = 'Select department...';
            list.forEach(function(dept) {
                const opt = document.createElement('option');
                opt.value = dept;
                opt.textContent = dept;
                sel.appendChild(opt);
            });
        });
    }
}

function initHamburgerMenu() {
    const menuToggle = document.getElementById('menuToggle');
    const sidebarMenu = document.getElementById('sidebarMenu');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const sidebarClose = document.getElementById('sidebarClose');

    function openMenu() {
        if (sidebarMenu) sidebarMenu.classList.add('active');
        if (sidebarOverlay) sidebarOverlay.classList.add('active');
    }

    function closeMenu() {
        if (sidebarMenu) sidebarMenu.classList.remove('active');
        if (sidebarOverlay) sidebarOverlay.classList.remove('active');
    }

    if (menuToggle) menuToggle.addEventListener('click', openMenu);
    if (sidebarClose) sidebarClose.addEventListener('click', closeMenu);
    if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeMenu);
}

function switchTab(tab) {
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    if (tab === 'add') {
        document.getElementById('addTab').classList.add('active');
        document.querySelectorAll('.tab-button')[0].classList.add('active');
    } else {
        document.getElementById('viewTab').classList.add('active');
        document.querySelectorAll('.tab-button')[1].classList.add('active');
        loadFacultyList();
    }
}

let _connectionErrorShownAt = 0;
function showFetchErrorHint(error, context) {
    const isConnectionRefused = (error && (error.message === 'Failed to fetch' || error.name === 'TypeError'));
    const isBlocked = isConnectionRefused; 
    const now = Date.now();
    if (now - _connectionErrorShownAt < 8000) return; 
    _connectionErrorShownAt = now;
    if (isBlocked || isConnectionRefused) {
        showMessage(
            'Backend unavailable. If running locally, start the server (e.g. python backend/app.py). On Replit, ensure the server is running.',
            'error'
        );
    } else if (context) {
        showMessage(context + ': ' + (error && error.message ? error.message : 'Network error'), 'error');
    }
}

async function loadFacultyCount() {
    try {
        const response = await fetch(`${API_BASE_URL}/faculty/count`);
        const data = await response.json();
        if (data.count !== undefined) {
            const countEl = document.getElementById('facultyCount');
            if (countEl) countEl.textContent = data.count;
            const banner = document.getElementById('seedFacultyBanner');
            if (banner) banner.style.display = data.count === 0 ? 'flex' : 'none';
        }
    } catch (error) {
        console.error('Error loading faculty count:', error);
        showFetchErrorHint(error, null);
    }
}

async function seedFacultyFromDefault() {
    const btn = document.getElementById('seedFacultyBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Loading...';
    }
    try {
        const response = await fetch(`${API_BASE_URL}/faculty/seed`, { method: 'POST' });
        const data = await response.json();
        if (response.ok) {
            showMessage(data.message || `Loaded ${data.imported_count} faculty.`, 'success');
            await loadFacultyCount();
            await loadFacultyList();
            const banner = document.getElementById('seedFacultyBanner');
            if (banner) banner.style.display = 'none';
        } else {
            showMessage(data.error || 'Failed to load default faculty list', 'error');
        }
    } catch (error) {
        showFetchErrorHint(error, 'Load default faculty');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa fa-database"></i> Load default faculty list';
        }
    }
}

async function loadFacultyList() {
    const tbody = document.getElementById('facultyTableBody');
    tbody.innerHTML = '<tr><td colspan="4" class="loading-text">Loading...</td></tr>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/faculty/list`);
        const data = await response.json();
        
        if (data.faculty && Array.isArray(data.faculty) && data.faculty.length > 0) {
            allFacultyData = data.faculty.sort((a, b) => {
                const nameA = a.name.toLowerCase();
                const nameB = b.name.toLowerCase();
                return nameA.localeCompare(nameB);
            });
            
            filteredFacultyData = [...allFacultyData];
            currentPage = 1;
            displayFacultyTable();
        } else {
            allFacultyData = [];
            filteredFacultyData = [];
            tbody.innerHTML = '<tr><td colspan="4" class="no-data">No faculty members found</td></tr>';
            document.getElementById('paginationContainer').innerHTML = '';
        }
        
        if (data.count !== undefined) {
            document.getElementById('facultyCount').textContent = data.count;
        }
    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="4" class="error-text">Error loading faculty members</td></tr>';
        document.getElementById('paginationContainer').innerHTML = '';
        showFetchErrorHint(error, 'Error loading faculty list');
    }
}

function displayFacultyTable() {
    const tbody = document.getElementById('facultyTableBody');
    const searchTerm = document.getElementById('searchFaculty').value.toLowerCase();
    if (searchTerm) {
        filteredFacultyData = allFacultyData.filter(f => 
            f.name.toLowerCase().includes(searchTerm) || 
            f.department.toLowerCase().includes(searchTerm)
        );
    } else {
        filteredFacultyData = [...allFacultyData];
    }
    
    const totalPages = Math.ceil(filteredFacultyData.length / ITEMS_PER_PAGE);
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;
    const paginatedFaculty = filteredFacultyData.slice(startIndex, endIndex);
    
    if (filteredFacultyData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="no-data">No matching faculty members</td></tr>';
        document.getElementById('paginationContainer').innerHTML = '';
        return;
    }
    tbody.innerHTML = paginatedFaculty.map(faculty => `
        <tr>
            <td>${escapeHtml(faculty.name)}</td>
            <td>${escapeHtml(faculty.department)}</td>
            <td>${escapeHtml(faculty.position || '-')}</td>
            <td class="actions-cell">
                <button onclick="openEditModal(${faculty.id})" class="btn-icon" title="Edit">
                    <i class="fa fa-edit"></i>
                </button>
                <button onclick="deleteFaculty(${faculty.id}, '${escapeHtml(faculty.name)}')" class="btn-icon btn-danger" title="Delete">
                    <i class="fa fa-trash"></i>
                </button>
            </td>
        </tr>
    `).join('');
    
    displayPagination(totalPages);
}
function displayPagination(totalPages) {
    const container = document.getElementById('paginationContainer');
    
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    let paginationHTML = '<div class="pagination">';
    
    if (currentPage > 1) {
        paginationHTML += `<button onclick="goToPage(${currentPage - 1})" class="pagination-btn">
            <i class="fa fa-chevron-left"></i> Previous
        </button>`;
    } else {
        paginationHTML += '<button disabled class="pagination-btn disabled">Previous</button>';
    }
    
    paginationHTML += '<span class="pagination-info">';
    paginationHTML += `Page ${currentPage} of ${totalPages}`;
    paginationHTML += ` (${filteredFacultyData.length} total)`;
    paginationHTML += '</span>';
    if (currentPage < totalPages) {
        paginationHTML += `<button onclick="goToPage(${currentPage + 1})" class="pagination-btn">
            Next <i class="fa fa-chevron-right"></i>
        </button>`;
    } else {
        paginationHTML += '<button disabled class="pagination-btn disabled">Next</button>';
    }
    
    paginationHTML += '</div>';
    container.innerHTML = paginationHTML;
}

function goToPage(page) {
    currentPage = page;
    displayFacultyTable();
    window.scrollTo({ top: document.getElementById('facultyTableContainer').offsetTop - 20, behavior: 'smooth' });
}

async function handleAddFaculty(e) {
    e.preventDefault();
    
    const formData = {
        name: document.getElementById('facultyName').value.trim(),
        department: document.getElementById('facultyDepartment').value ? document.getElementById('facultyDepartment').value.trim() : '',
        position: document.getElementById('facultyPosition').value.trim()
    };
    
    if (!formData.name || !formData.department) {
        showMessage('Name and Department are required', 'error');
        return;
    }
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn.innerHTML;
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Adding...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/faculty/add`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage(data.message || 'Faculty member added successfully!', 'success');
            document.getElementById('addFacultyForm').reset();
            await loadDepartments();
            loadFacultyCount();
            switchTab('view');
            await loadFacultyList();
        } else {
            if (response.status === 409 || data.duplicate) {
                showMessage(data.error || 'This faculty member already exists', 'error');
            } else {
                showMessage(data.error || 'Error adding faculty member', 'error');
            }
        }
    } catch (error) {
        showMessage('Error adding faculty member: ' + error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    }
}

async function handleUploadExcel(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('excelFile');
    if (!fileInput.files || fileInput.files.length === 0) {
        showMessage('Please select an Excel file', 'error');
        return;
    }
    
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        const sheetName = document.getElementById('sheetName').value.trim();
        if (sheetName) {
            formData.append('sheet_name', sheetName);
        }
        formData.append('clear_existing', document.getElementById('clearExisting').checked);
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Uploading...';
    
    try {
        const response = await fetch(`${API_BASE_URL}/faculty/upload-excel`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            let message = data.message || `Successfully imported ${data.imported_count} faculty members!`;
            if (data.skipped_count > 0) {
                message += ` (${data.skipped_count} duplicates skipped)`;
            }
            showMessage(message, 'success');
            document.getElementById('uploadExcelForm').reset();
            loadFacultyCount();
            switchTab('view');
            await loadFacultyList();
        } else {
            if (data.duplicate) {
                showMessage(data.error || 'This faculty member already exists', 'error');
            } else {
                showMessage(data.error || 'Error uploading Excel file', 'error');
            }
        }
    } catch (error) {
        showMessage('Error uploading Excel file: ' + error.message, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    }
}

async function openEditModal(facultyId) {
    try {
        const response = await fetch(`${API_BASE_URL}/faculty/${facultyId}`);
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Faculty member not found');
        }
        
        const faculty = await response.json();
        
        document.getElementById('editFacultyId').value = faculty.id;
        document.getElementById('editFacultyName').value = faculty.name;
        var deptNorm = normalizeDepartmentName(faculty.department) || faculty.department;
        if (deptNorm && Array.from(document.getElementById('editFacultyDepartment').options).some(function(o) { return o.value === deptNorm; })) {
            document.getElementById('editFacultyDepartment').value = deptNorm;
        }
        document.getElementById('editFacultyPosition').value = faculty.position || '';
        
        document.getElementById('editModal').classList.add('active');
    } catch (error) {
        showMessage('Error loading faculty member: ' + error.message, 'error');
    }
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
    document.getElementById('editFacultyForm').reset();
}

async function handleEditFaculty(e) {
    e.preventDefault();
    
    const facultyId = document.getElementById('editFacultyId').value;
    const formData = {
        name: document.getElementById('editFacultyName').value.trim(),
        department: document.getElementById('editFacultyDepartment').value ? document.getElementById('editFacultyDepartment').value.trim() : '',
        position: document.getElementById('editFacultyPosition').value.trim()
    };
    
    if (!formData.name || !formData.department) {
        showMessage('Name and Department are required', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/faculty/${facultyId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage('Faculty member updated successfully!', 'success');
            closeEditModal();
            await loadFacultyList();
        } else {
            showMessage(data.error || 'Error updating faculty member', 'error');
        }
    } catch (error) {
        showMessage('Error updating faculty member: ' + error.message, 'error');
    }
}

async function deleteFaculty(facultyId, facultyName) {
    if (!confirm(`Are you sure you want to delete "${facultyName}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/faculty/${facultyId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showMessage('Faculty member deleted successfully!', 'success');
            loadFacultyCount();
            await loadFacultyList();
        } else {
            showMessage(data.error || 'Error deleting faculty member', 'error');
        }
    } catch (error) {
        showMessage('Error deleting faculty member: ' + error.message, 'error');
    }
}

function handleSearch() {
    currentPage = 1; 
    displayFacultyTable();
}

function showMessage(message, type = 'info') {
    const container = document.getElementById('messageContainer');
    if (!container) return;
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${type}`;
    messageDiv.textContent = message;
    
    container.innerHTML = '';
    container.appendChild(messageDiv);
    
    setTimeout(() => {
        messageDiv.classList.add('show');
    }, 10);
    
    setTimeout(() => {
        messageDiv.classList.remove('show');
        setTimeout(() => {
            if (messageDiv.parentNode === container) {
                container.removeChild(messageDiv);
            }
        }, 300);
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
