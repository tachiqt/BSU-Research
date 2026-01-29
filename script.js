const API_BASE_URL = 'http://localhost:5000/api';
const CACHE_KEY = 'bsu_research_data';
const CACHE_TIMESTAMP_KEY = 'bsu_research_data_timestamp';
const CACHE_VERSION_KEY = 'bsu_research_cache_version';
const CACHE_VERSION = 2; // Bump when backend adds colleges/department data so old cache is refetched
const CACHE_DURATION = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

window.addEventListener('DOMContentLoaded', function() {
    setCurrentDate();
    initHamburgerMenu();
    initYearFilter();
    loadAllData();
});

// Check if cached data is still valid (age and version)
function isCacheValid() {
    const version = parseInt(localStorage.getItem(CACHE_VERSION_KEY), 10);
    if (version !== CACHE_VERSION) return false;
    const timestamp = localStorage.getItem(CACHE_TIMESTAMP_KEY);
    if (!timestamp) return false;
    const age = Date.now() - parseInt(timestamp);
    return age < CACHE_DURATION;
}

// Get cached data
function getCachedData() {
    const cached = localStorage.getItem(CACHE_KEY);
    if (cached) {
        try {
            return JSON.parse(cached);
        } catch (e) {
            console.error('Error parsing cached data:', e);
            return null;
        }
    }
    return null;
}

// Store data in cache
function setCachedData(data) {
    localStorage.setItem(CACHE_KEY, JSON.stringify(data));
    localStorage.setItem(CACHE_TIMESTAMP_KEY, Date.now().toString());
    localStorage.setItem(CACHE_VERSION_KEY, String(CACHE_VERSION));
}

// Load all data from API or cache
async function loadAllData() {
    // Check cache first
    if (isCacheValid()) {
        const cachedData = getCachedData();
        if (cachedData) {
            console.log('Using cached data');
            updateDashboard(cachedData.dashboard_stats);
            return;
        }
    }
    
    // Fetch fresh data
    try {
        showLoadingState();
        const response = await fetch(`${API_BASE_URL}/all-data`);
        
        if (!response.ok) {
            throw new Error('Failed to fetch data');
        }
        
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        // Cache the data
        setCachedData(data);
        
        // Update dashboard
        updateDashboard(data.dashboard_stats);
        
    } catch (error) {
        console.error('Error loading data:', error);
        hideLoadingState();
        showErrorState();
        
        // Try to use cached data even if expired
        const cachedData = getCachedData();
        if (cachedData) {
            console.log('Using expired cached data due to fetch error');
            updateDashboard(cachedData.dashboard_stats);
        } else {
            updateDashboard({
                total_publications: 0,
                college_counts: {
                    engineering: 0,
                    informatics_computing: 0,
                    engineering_technology: 0,
                    architecture_design: 0
                },
                department_counts: {},
                quarterly_counts: {
                    q1: 0,
                    q2: 0,
                    q3: 0,
                    q4: 0
                }
            });
        }
    }
}

async function loadDashboardData(year = '') {
    // Get cached data
    const cachedData = getCachedData();
    if (!cachedData) {
        await loadAllData();
        return;
    }
    
    let dashboardStats = cachedData.dashboard_stats;
    
    // Apply year filter if specified
    if (year) {
        try {
            const filterYear = parseInt(year, 10);
            if (isNaN(filterYear)) {
                updateDashboard(dashboardStats);
                return;
            }
            const allPublications = cachedData.publications || [];
            
            // Normalize publication year to number for comparison
            function getPubYear(pub) {
                const pubYear = pub.year;
                if (pubYear == null || pubYear === '') return null;
                if (typeof pubYear === 'number' && !isNaN(pubYear)) return Math.floor(pubYear);
                if (typeof pubYear === 'string') {
                    const y = parseInt(pubYear.split('/')[0].trim(), 10) || parseInt(pubYear.trim(), 10);
                    return isNaN(y) ? null : y;
                }
                const y = parseInt(pubYear, 10);
                return isNaN(y) ? null : y;
            }
            
            // Filter publications by year
            const filteredPublications = allPublications.filter(pub => {
                const yearValue = getPubYear(pub);
                return yearValue !== null && yearValue === filterYear;
            });
            
            // Recalculate quarterly counts
            // If filtering by current year, only count quarters up to current quarter
            const currentDate = new Date();
            const currentYear = currentDate.getFullYear();
            const currentMonth = currentDate.getMonth() + 1; // JavaScript months are 0-indexed
            const isCurrentYear = filterYear === currentYear;
            
            // Determine current quarter (1-4)
            let currentQuarter = 1;
            if (currentMonth >= 1 && currentMonth <= 3) currentQuarter = 1;
            else if (currentMonth >= 4 && currentMonth <= 6) currentQuarter = 2;
            else if (currentMonth >= 7 && currentMonth <= 9) currentQuarter = 3;
            else if (currentMonth >= 10 && currentMonth <= 12) currentQuarter = 4;
            
            const quarterly_counts = {'q1': 0, 'q2': 0, 'q3': 0, 'q4': 0};
            let publicationsWithoutMonth = 0;
            let publicationsCountedInTotal = 0;
            
            filteredPublications.forEach(pub => {
                const month = pub.month;
                if (month !== null && month !== undefined && month !== '') {
                    try {
                        const monthInt = parseInt(month);
                        if (!isNaN(monthInt) && monthInt >= 1 && monthInt <= 12) {
                            let pubQuarter = 0;
                            if (1 <= monthInt && monthInt <= 3) pubQuarter = 1;
                            else if (4 <= monthInt && monthInt <= 6) pubQuarter = 2;
                            else if (7 <= monthInt && monthInt <= 9) pubQuarter = 3;
                            else if (10 <= monthInt && monthInt <= 12) pubQuarter = 4;
                            
                            // Only count if it's not current year, or if it's current year and quarter <= current quarter
                            if (pubQuarter > 0 && (!isCurrentYear || pubQuarter <= currentQuarter)) {
                                if (pubQuarter === 1) quarterly_counts.q1++;
                                else if (pubQuarter === 2) quarterly_counts.q2++;
                                else if (pubQuarter === 3) quarterly_counts.q3++;
                                else if (pubQuarter === 4) quarterly_counts.q4++;
                                publicationsCountedInTotal++;
                            }
                        } else {
                            publicationsWithoutMonth++;
                            // Count publications with invalid months in total only if not current year
                            if (!isCurrentYear) {
                                publicationsCountedInTotal++;
                            }
                            console.warn(`Publication has invalid month: ${month}`, pub);
                        }
                    } catch (e) {
                        publicationsWithoutMonth++;
                        // Count publications with parsing errors in total only if not current year
                        if (!isCurrentYear) {
                            publicationsCountedInTotal++;
                        }
                        console.warn(`Error parsing month for publication:`, pub, e);
                    }
                } else {
                    publicationsWithoutMonth++;
                    // Count publications without months in total only if not current year
                    if (!isCurrentYear) {
                        publicationsCountedInTotal++;
                    }
                    console.warn(`Publication missing month:`, pub);
                }
            });
            
            // Total should match the sum of quarters displayed (for current year, only up to current quarter)
            const total_publications = isCurrentYear ? publicationsCountedInTotal : filteredPublications.length;
            
            // Log if there's a discrepancy
            const quarterlySum = quarterly_counts.q1 + quarterly_counts.q2 + quarterly_counts.q3 + quarterly_counts.q4;
            if (quarterlySum + publicationsWithoutMonth !== total_publications && !isCurrentYear) {
                console.warn(`Quarterly count mismatch: Total=${total_publications}, Quarters=${quarterlySum}, WithoutMonth=${publicationsWithoutMonth}`);
            }
            
            // Recalculate college counts from filtered publications (each pub has colleges[] from backend)
            const college_counts = {
                engineering: 0,
                informatics_computing: 0,
                engineering_technology: 0,
                architecture_design: 0
            };
            filteredPublications.forEach(pub => {
                const colleges = pub.colleges || [];
                colleges.forEach(c => {
                    if (college_counts.hasOwnProperty(c)) {
                        college_counts[c]++;
                    }
                });
            });
            
            dashboardStats = {
                ...dashboardStats,
                total_publications: total_publications,
                quarterly_counts: quarterly_counts,
                college_counts: college_counts
            };
        } catch (e) {
            console.error('Error filtering by year:', e);
        }
    }
    
    updateDashboard(dashboardStats);
}

function updateDashboard(data) {
    const publicationsValue = document.querySelector('.publications-box .box-value');
    if (publicationsValue) {
        publicationsValue.textContent = String(data.total_publications || 0).padStart(2, '0');
    }
    
    // Update college boxes with department counts from Excel
    const collegeBoxes = document.querySelectorAll('.college-box .box-value');
    if (collegeBoxes.length >= 4 && data.college_counts) {
        // Use department-based counts from Excel faculty matching
        collegeBoxes[0].textContent = String(data.college_counts.engineering || 0).padStart(2, '0');
        collegeBoxes[1].textContent = String(data.college_counts.informatics_computing || 0).padStart(2, '0');
        collegeBoxes[2].textContent = String(data.college_counts.engineering_technology || 0).padStart(2, '0');
        collegeBoxes[3].textContent = String(data.college_counts.architecture_design || 0).padStart(2, '0');
    }
    
    // Update quarterly counts (based on faculty-filtered publications)
    if (data.quarterly_counts) {
        const quarterValues = document.querySelectorAll('.quarter-value');
        if (quarterValues.length >= 4) {
            quarterValues[0].textContent = String(data.quarterly_counts.q1 || 0).padStart(2, '0');
            quarterValues[1].textContent = String(data.quarterly_counts.q2 || 0).padStart(2, '0');
            quarterValues[2].textContent = String(data.quarterly_counts.q3 || 0).padStart(2, '0');
            quarterValues[3].textContent = String(data.quarterly_counts.q4 || 0).padStart(2, '0');
        }
    }
    
    // Log department breakdown if available
    if (data.department_counts && Object.keys(data.department_counts).length > 0) {
        console.log('Department Publication Counts (from Excel):');
        for (const [dept, count] of Object.entries(data.department_counts)) {
            console.log(`  ${dept}: ${count}`);
        }
    }
    
    // Log department quarterly counts if available
    if (data.department_quarterly_counts && Object.keys(data.department_quarterly_counts).length > 0) {
        console.log('Department Quarterly Counts (from Excel):');
        for (const [dept, quarters] of Object.entries(data.department_quarterly_counts)) {
            console.log(`  ${dept}: Q1=${quarters.q1}, Q2=${quarters.q2}, Q3=${quarters.q3}, Q4=${quarters.q4}`);
        }
    }
    
    if (data.quarterly_counts) {
        const quarterValues = document.querySelectorAll('.quarter-value');
        if (quarterValues.length >= 4) {
            quarterValues[0].textContent = String(data.quarterly_counts.q1 || 0).padStart(2, '0');
            quarterValues[1].textContent = String(data.quarterly_counts.q2 || 0).padStart(2, '0');
            quarterValues[2].textContent = String(data.quarterly_counts.q3 || 0).padStart(2, '0');
            quarterValues[3].textContent = String(data.quarterly_counts.q4 || 0).padStart(2, '0');
        }
    }
    
    const yearFilter = document.getElementById('yearFilter');
    if (yearFilter) {
        const currentValue = yearFilter.value;
        yearFilter.innerHTML = '<option value="">All Years</option>';
        
        // Generate complete year range from earliest to current year
        const currentYear = new Date().getFullYear();
        let startYear = currentYear;
        
        // Use earliest year from data if available, otherwise default to 10 years ago
        if (data.earliest_year && data.earliest_year < currentYear) {
            startYear = data.earliest_year;
        } else if (!data.earliest_year) {
            // Default to 10 years ago if no data available
            startYear = currentYear - 10;
        }
        
        // Generate year options from earliest to current (newest first)
        for (let year = currentYear; year >= startYear; year--) {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            yearFilter.appendChild(option);
        }
        
        // Restore previous selection if it still exists
        if (currentValue) {
            yearFilter.value = currentValue;
        }
    }
    
    hideLoadingState();
}

function showLoadingState() {
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.classList.add('active');
    }
    const boxes = document.querySelectorAll('.box-value');
    boxes.forEach(box => {
        box.style.opacity = '0.5';
    });
}

function hideLoadingState() {
    const loadingOverlay = document.getElementById('loadingOverlay');
    if (loadingOverlay) {
        loadingOverlay.classList.remove('active');
    }
    const boxes = document.querySelectorAll('.box-value');
    boxes.forEach(box => {
        box.style.opacity = '1';
    });
}

function showErrorState() {
    console.error('Failed to load dashboard data');
}

function setCurrentDate() {
    const today = new Date();
    const options = { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    };
    const formattedDate = today.toLocaleDateString('en-US', options);
    const dateElement = document.getElementById('currentDate');
    if (dateElement) {
        dateElement.textContent = formattedDate.toUpperCase();
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

    if (menuToggle) {
        menuToggle.addEventListener('click', openMenu);
    }
    if (sidebarClose) {
        sidebarClose.addEventListener('click', closeMenu);
    }
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', closeMenu);
    }
}

// Removed sign-out functionality - no authentication needed

function initYearFilter() {
    const yearFilter = document.getElementById('yearFilter');
    if (yearFilter) {
        yearFilter.addEventListener('change', function() {
            const selectedYear = this.value;
            loadDashboardData(selectedYear);
        });
    }
}