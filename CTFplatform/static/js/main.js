// ---------------------------------------------------------------------------
// Shared helpers (the CSP forbids inline handlers, so these replace them)
// ---------------------------------------------------------------------------
window.escapeHtml = function (value) {
    return String(value === null || value === undefined ? '' : value).replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
};

const CLICK_ACTIONS = {
    openBrowser() {
        const el = document.getElementById('virtual-browser');
        if (el) el.style.display = 'flex';
    },
    closeCompletionModal() {
        const el = document.getElementById('completion-modal');
        if (el) el.classList.remove('open');
    },
};

document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-click]');
    if (!el) return;
    const fn = CLICK_ACTIONS[el.dataset.click] || window[el.dataset.click];
    if (typeof fn === 'function') fn.call(el, e);
});

document.addEventListener('submit', (e) => {
    const message = e.target && e.target.dataset ? e.target.dataset.confirm : null;
    if (message && !window.confirm(message)) e.preventDefault();
});

// Global UI Interactions

document.addEventListener('DOMContentLoaded', () => {
    // Sidebar Toggle for Mobile
    const menuToggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });
    }

    // Workstation Tabs
    const tabBtns = document.querySelectorAll('.tab-btn');
    const panels = document.querySelectorAll('.panel');
    
    if (tabBtns.length > 0) {
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetId = btn.getAttribute('data-target');
                
                tabBtns.forEach(b => b.classList.remove('active'));
                panels.forEach(p => p.classList.remove('active'));
                
                btn.classList.add('active');
                const targetPanel = document.getElementById(targetId);
                if (targetPanel) {
                    targetPanel.classList.add('active');
                }
            });
        });
    }
});

// Toast Notification System
function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✓';
    if (type === 'error') icon = '✕';
    if (type === 'warning') icon = '⚠️';
    
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${message}</span>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease forwards';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3000);
}

// Fetch wrapper for JSON APIs to handle CSRF
async function apiCall(url, data, csrfToken) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify(data)
        });
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        return { success: false, message: 'Network error occurred.' };
    }
}

// Export functions to global scope
window.showToast = showToast;
window.apiCall = apiCall;
