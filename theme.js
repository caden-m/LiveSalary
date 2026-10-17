// Applies a saved theme before first paint so there is no flash of the wrong colours.
// Loaded as a blocking script in <head>; kept out of index.html so the page can use a strict CSP.
try {
    var savedTheme = JSON.parse(localStorage.getItem('mls.v2') || '{}').theme;
    if (savedTheme === 'dark' || savedTheme === 'light') document.documentElement.dataset.theme = savedTheme;
} catch (e) { /* storage unavailable */ }
