"""Portal JavaScript - progressive enhancement only.

No credentials, tokens, or user data in this script.
"""
document.addEventListener("DOMContentLoaded", function () {
    // Wire up any confirm-dialog forms via onsubmit attributes in HTML
    document.querySelectorAll("form[onsubmit]").forEach(function (form) {
        // handled by onsubmit attribute in HTML
    });
});