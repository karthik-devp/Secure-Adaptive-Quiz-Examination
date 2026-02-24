/**
 * theme.js - Dark/Light mode toggle with localStorage persistence
 */
(function() {
    // Load saved theme or default to dark
    const savedTheme = localStorage.getItem('quizEngineTheme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateIcons(savedTheme);
})();

function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';

    html.setAttribute('data-theme', next);
    localStorage.setItem('quizEngineTheme', next);
    updateIcons(next);
}

function updateIcons(theme) {
    const icons = document.querySelectorAll('#theme-icon, #theme-icon-auth');
    icons.forEach(icon => {
        if (icon) {
            icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
        }
    });
}
