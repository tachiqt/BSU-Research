// API Base URL - use relative /api when served from same host (avoids some ad-blocker blocks), else localhost
const API_BASE_URL = (typeof window !== 'undefined' && window.API_BASE_URL !== undefined && window.API_BASE_URL !== '')
    ? window.API_BASE_URL
    : (typeof window !== 'undefined' && window.location.protocol !== 'file:' && window.location.host !== '')
        ? '/api'
        : 'http://localhost:5000/api';
const ITEMS_PER_PAGE = 10;

let currentPage = 1;
let allFacultyData = [];
let filteredFacultyData = [];

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    initHamburgerMenu();
    loadFacultyCount();
    loadFacultyList();
    
    // Form handlers
    document.getElementById('addFacultyForm').addEventListener('submit', handleAddFaculty);
    document.getElementById('uploadExcelForm').addEventListener('submit', handleUploadExcel);
    document.getElementById('editFacultyForm').addEventListener('submit', handleEditFaculty);
    document.getElementById('searchFaculty').addEventListener('input', handleSearch);
});

// Hamburger menu
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

// Tab switching
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

// Show hint when fetch fails (e.g. ERR_BLOCKED_BY_CLIENT from ad blocker)
function showFetchErrorHint(error, context) {
    const isBlocked = (error && (error.message === 'Failed to fetch' || error.name === 'TypeError'));
    if (isBlocked) {
        showMessage(
            'Request was blocked. Disable ad blocker or privacy extensions for this site, or open the page from http://localhost:5000',
            'error'
        );
    } else if (context) {
        showMessage(context + ': ' + (error && error.message ? error.message : 'Network error'), 'error');
    }
}

// Load faculty count
async function loadFacultyCount() {
    try {
        const response = await fetch(`${API_BASE_URL}/faculty/count`);
        const data = await response.json();
        if (data.count !== undefined) {
            document.getElementById('facultyCount').textContent = data.count;
        }
    } catch (error) {
        console.error('Error loading faculty count:', error);
        showFetchErrorHint(error, null);
    }
}

// Load faculty list
async function loadFacultyList() {
    const tbody = document.getElementById('facultyTableBody');
    tbody.innerHTML = '<tr><td colspan="4" class="loading-text">Loading...</td></tr>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/faculty/list`);
        const data = await response.json();
        
        if (data.faculty && Array.isArray(data.faculty) && data.faculty.length > 0) {
            // Sort alphabetically by name
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
        
        // Update count
        if (data.count !== undefined) {
            document.getElementById('facultyCount').textContent = data.count;
        }
    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="4" class="error-text">Error loading faculty members</td></tr>';
        document.getElementById('paginationContainer').innerHTML = '';
        showFetchErrorHint(error, 'Error loading faculty list');
    }
}

// Display faculty table with pagination
function displayFacultyTable() {
    const tbody = document.getElementById('facultyTableBody');
    const searchTerm = document.getElementById('searchFaculty').value.toLowerCase();
    
    // Filter by search term
    if (searchTerm) {
        filteredFacultyData = allFacultyData.filter(f => 
            f.name.toLowerCase().includes(searchTerm) || 
            f.department.toLowerCase().includes(searchTerm)
        );
    } else {
        filteredFacultyData = [...allFacultyData];
    }
    
    // Calculate pagination
    const totalPages = Math.ceil(filteredFacultyData.length / ITEMS_PER_PAGE);
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;
    const paginatedFaculty = filteredFacultyData.slice(startIndex, endIndex);
    
    if (filteredFacultyData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="no-data">No matching faculty members</td></tr>';
        document.getElementById('paginationContainer').innerHTML = '';
        return;
    }
    
    // Display paginated data
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
    
    // Display pagination
    displayPagination(totalPages);
}

// Display pagination controls
function displayPagination(totalPages) {
    const container = document.getElementById('paginationContainer');
    
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    let paginationHTML = '<div class="pagination">';
    
    // Previous button
    if (currentPage > 1) {
        paginationHTML += `<button onclick="goToPage(${currentPage - 1})" class="pagination-btn">
            <i class="fa fa-chevron-left"></i> Previous
        </button>`;
    } else {
        paginationHTML += '<button disabled class="pagination-btn disabled">Previous</button>';
    }
    
    // Page numbers
    paginationHTML += '<span class="pagination-info">';
    paginationHTML += `Page ${currentPage} of ${totalPages}`;
    paginationHTML += ` (${filteredFacultyData.length} total)`;
    paginationHTML += '</span>';
    
    // Next button
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

// Go to specific page
function goToPage(page) {
    currentPage = page;
    displayFacultyTable();
    // Scroll to top of table
    window.scrollTo({ top: document.getElementById('facultyTableContainer').offsetTop - 20, behavior: 'smooth' });
}

// Handle add faculty form
async function handleAddFaculty(e) {
    e.preventDefault();
    
    const formData = {
        name: document.getElementById('facultyName').value.trim(),
        department: document.getElementById('facultyDepartment').value.trim(),
        position: document.getElementById('facultyPosition').value.trim()
    };
    
    if (!formData.name || !formData.department) {
        showMessage('Name and Department are required', 'error');
        return;
    }
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn.innerHTML;
    
    // Show loading state
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
            showMessage('Faculty member added successfully!', 'success');
            document.getElementById('addFacultyForm').reset();
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
        // Hide loading state
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    }
}

// Handle Excel upload
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
    
    // Show loading state
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
        // Hide loading state
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    }
}

// Open edit modal
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
        document.getElementById('editFacultyDepartment').value = faculty.department;
        document.getElementById('editFacultyPosition').value = faculty.position || '';
        
        document.getElementById('editModal').classList.add('active');
    } catch (error) {
        showMessage('Error loading faculty member: ' + error.message, 'error');
    }
}

// Close edit modal
function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
    document.getElementById('editFacultyForm').reset();
}

// Handle edit form
async function handleEditFaculty(e) {
    e.preventDefault();
    
    const facultyId = document.getElementById('editFacultyId').value;
    const formData = {
        name: document.getElementById('editFacultyName').value.trim(),
        department: document.getElementById('editFacultyDepartment').value.trim(),
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

// Delete faculty
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

// Search handler
function handleSearch() {
    currentPage = 1; // Reset to first page on search
    displayFacultyTable();
}

// Show message
function showMessage(message, type = 'info') {
    const container = document.getElementById('messageContainer');
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
        setTimeout(() => container.removeChild(messageDiv), 300);
    }, 3000);
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
