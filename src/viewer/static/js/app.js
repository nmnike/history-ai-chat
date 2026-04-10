/**
 * Chat Viewer Application
 * Theme toggle, search, and UI interactions
 */

(function() {
    'use strict';

    // DOM Elements
    const themeToggle = document.getElementById('theme-toggle');
    const searchInput = document.getElementById('search-input');
    const chatContainer = document.querySelector('.chat-container');

    // Theme Management
    const THEME_KEY = 'chat-viewer-theme';

    function getStoredTheme() {
        return localStorage.getItem(THEME_KEY);
    }

    function setStoredTheme(theme) {
        localStorage.setItem(THEME_KEY, theme);
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        updateThemeIcon(theme);
    }

    function updateThemeIcon(theme) {
        if (!themeToggle) return;
        themeToggle.textContent = theme === 'light' ? '🌙' : '☀️';
        themeToggle.setAttribute('aria-label', theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme');
    }

    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
        setStoredTheme(newTheme);
    }

    function initTheme() {
        const storedTheme = getStoredTheme();
        const theme = storedTheme || 'light';
        applyTheme(theme);
    }

    // Search functionality
    let searchTimeout = null;
    const SEARCH_DEBOUNCE_MS = 300;

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function debounce(func, wait) {
        return function executedFunction(...args) {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    function highlightText(element, query) {
        if (!query) {
            element.innerHTML = element.textContent;
            return;
        }

        const text = element.textContent;
        const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
        element.innerHTML = text.replace(regex, '<mark class="highlight">$1</mark>');
    }

    function escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function performSearch(query) {
        if (!chatContainer) return;

        const messages = chatContainer.querySelectorAll('.message-content');
        const normalizedQuery = query.trim().toLowerCase();

        if (!normalizedQuery) {
            // Reset all messages
            messages.forEach(msg => {
                msg.innerHTML = msg.textContent;
                msg.closest('.message').classList.remove('hidden');
            });
            return;
        }

        messages.forEach(msg => {
            const text = msg.textContent.toLowerCase();
            const messageEl = msg.closest('.message');

            if (text.includes(normalizedQuery)) {
                messageEl.classList.remove('hidden');
                highlightText(msg, normalizedQuery);
            } else {
                messageEl.classList.add('hidden');
            }
        });
    }

    const debouncedSearch = debounce(performSearch, SEARCH_DEBOUNCE_MS);

    // Collapsible blocks
    function initCollapsibleBlocks() {
        document.addEventListener('click', (e) => {
            const header = e.target.closest('.thinking-header, .tool-header');
            if (!header) return;

            const block = header.closest('.thinking-block, .tool-block');
            if (!block) return;

            toggleBlock(block);
        });
    }

    function toggleBlock(block) {
        const isCollapsed = block.classList.contains('collapsed');
        block.classList.toggle('collapsed');

        const toggle = block.querySelector('.thinking-toggle, .tool-toggle');
        if (toggle) {
            toggle.textContent = isCollapsed ? '▼' : '▶';
        }
    }

    function collapseAllBlocks() {
        document.querySelectorAll('.thinking-block, .tool-block').forEach(block => {
            block.classList.add('collapsed');
            const toggle = block.querySelector('.thinking-toggle, .tool-toggle');
            if (toggle) {
                toggle.textContent = '▶';
            }
        });
    }

    function expandAllBlocks() {
        document.querySelectorAll('.thinking-block, .tool-block').forEach(block => {
            block.classList.remove('collapsed');
            const toggle = block.querySelector('.thinking-toggle, .tool-toggle');
            if (toggle) {
                toggle.textContent = '▼';
            }
        });
    }

    // Keyboard shortcuts
    function initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K to focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }

            // Escape to clear search
            if (e.key === 'Escape' && document.activeElement === searchInput) {
                searchInput.value = '';
                performSearch('');
                searchInput.blur();
            }
        });
    }

    // Initialize
    function init() {
        initTheme();
        initCollapsibleBlocks();
        initKeyboardShortcuts();

        // Theme toggle
        if (themeToggle) {
            themeToggle.addEventListener('click', toggleTheme);
        }

        // Search
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                debouncedSearch(e.target.value);
            });
        }

        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            if (!getStoredTheme()) {
                applyTheme('light');
            }
        });
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose utility functions globally
    window.ChatViewer = {
        escapeHtml,
        toggleTheme,
        collapseAllBlocks,
        expandAllBlocks,
        performSearch
    };

})();