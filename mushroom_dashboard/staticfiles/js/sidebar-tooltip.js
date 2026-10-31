// Sidebar Tooltip for Collapsed State
(function() {
    document.addEventListener('DOMContentLoaded', function() {
        const sidebar = document.querySelector('.sidebar');
        if (!sidebar) return;
        
        // Create tooltip element
        const tooltipEl = document.createElement('div');
        tooltipEl.id = 'sidebar-tooltip';
        tooltipEl.style.cssText = 'position:fixed;background:#0c4b33;color:#fff;padding:8px 12px;border-radius:6px;font-size:0.85rem;white-space:nowrap;z-index:9999;pointer-events:none;opacity:0;transition:opacity 0.2s;box-shadow:0 4px 12px rgba(0,0,0,0.2);';
        document.body.appendChild(tooltipEl);
        
        // Add event listeners to all sidebar links
        document.querySelectorAll('.sidebar-nav a[data-tooltip]').forEach(function(link) {
            link.addEventListener('mouseenter', function(e) {
                if (sidebar.classList.contains('collapsed')) {
                    const rect = this.getBoundingClientRect();
                    tooltipEl.textContent = this.getAttribute('data-tooltip');
                    tooltipEl.style.left = (rect.right + 10) + 'px';
                    tooltipEl.style.top = (rect.top + rect.height / 2) + 'px';
                    tooltipEl.style.transform = 'translateY(-50%)';
                    tooltipEl.style.opacity = '1';
                }
            });
            link.addEventListener('mouseleave', function() {
                tooltipEl.style.opacity = '0';
            });
        });
    });
})();
