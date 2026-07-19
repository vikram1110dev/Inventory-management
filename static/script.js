document.addEventListener('DOMContentLoaded', () => {
    const currentTheme = localStorage.getItem('theme');
    const themeToggle = document.getElementById('theme-toggle');

    if (currentTheme) {
        document.body.classList.add(currentTheme);
        if (themeToggle && currentTheme === 'dark-theme') {
            themeToggle.checked = true;
        }
    }

    if (themeToggle) {
        themeToggle.addEventListener('change', function() {
            if (this.checked) {
                document.body.classList.add('dark-theme');
                localStorage.setItem('theme', 'dark-theme');
            } else {
                document.body.classList.remove('dark-theme');
                localStorage.setItem('theme', '');
            }
        });
    }
});
