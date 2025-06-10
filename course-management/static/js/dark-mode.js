function applyDarkMode() {
    const preference = localStorage.getItem('dark-mode');
    const shouldEnable = preference === 'true' ||
        (preference === null && window.matchMedia('(prefers-color-scheme: dark)').matches);
    if (shouldEnable) {
        document.body.classList.add('dark-mode');
        adjustNavbar(true);
    }
}

function adjustNavbar(enable) {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;
    if (enable) {
        navbar.classList.remove('navbar-light', 'bg-light');
        navbar.classList.add('navbar-dark', 'bg-dark');
    } else {
        navbar.classList.remove('navbar-dark', 'bg-dark');
        navbar.classList.add('navbar-light', 'bg-light');
    }
}

function toggleDarkMode() {
    const enabled = document.body.classList.toggle('dark-mode');
    adjustNavbar(enabled);
    localStorage.setItem('dark-mode', enabled);
}

document.addEventListener('DOMContentLoaded', applyDarkMode);
