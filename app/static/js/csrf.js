(function () {
    'use strict';

    function getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    async function apiFetch(url, options = {}) {
        const method = (options.method || 'GET').toUpperCase();

        const headers = {
            'Content-Type': 'application/json',
            'Accept':       'application/json',
            ...(options.headers || {}),
        };

        // Attach CSRF token on mutating methods
        if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
            headers['X-CSRFToken'] = getCSRFToken();
        }

        // JSON-encode body if it is a plain object
        let body = options.body;
        if (body && typeof body === 'object' && !(body instanceof FormData)) {
            body = JSON.stringify(body);
        }

        const response = await fetch(url, {
            ...options,
            method,
            headers,
            body,
        });

        // Parse JSON regardless of status so we can read the error message
        let data;
        try {
            data = await response.json();
        } catch {
            data = null;
        }

        if (!response.ok) {
            const message =
                (data && data.error) ||
                `Request failed: ${response.status} ${response.statusText}`;
            throw new Error(message);
        }

        return data;
    }

    function showToast(message, type = 'info') {
        const container = getOrCreateToastContainer();

        const toast = document.createElement('div');
        toast.className = `flash flash-${type}`;
        toast.setAttribute('role', 'status');
        toast.setAttribute('aria-live', 'polite');

        const icons = { success: 'circle-check', error: 'alert-circle', info: 'info-circle' };
        toast.innerHTML = `
      <i class="ti ti-${icons[type] || icons.info}" aria-hidden="true"></i>
      <span>${escapeHtml(message)}</span>
      <button class="flash-close" aria-label="Dismiss">
        <i class="ti ti-x" aria-hidden="true"></i>
      </button>
    `;

        // Dismiss button
        toast.querySelector('.flash-close').addEventListener('click', () => dismissToast(toast));

        container.appendChild(toast);

        // Auto-dismiss after 4 seconds
        setTimeout(() => dismissToast(toast), 4000);
    }

    function dismissToast(toast) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-8px)';
        toast.style.transition = 'opacity 0.18s ease, transform 0.18s ease';
        setTimeout(() => toast.remove(), 200);
    }

    function getOrCreateToastContainer() {
        let container = document.querySelector('.flash-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'flash-container';
            document.body.appendChild(container);
        }
        return container;
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // Expose globally so all other JS modules can use them
    window.apiFetch  = apiFetch;
    window.showToast = showToast;

})();