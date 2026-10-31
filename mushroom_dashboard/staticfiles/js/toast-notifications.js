(function () {
    'use strict';

    const MAX_VISIBLE_TOASTS = 3;
    const DEFAULT_DURATION = 4500;
    let activeConfirmation = null;

    function getContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            container.setAttribute('aria-live', 'polite');
            container.setAttribute('aria-atomic', 'true');
            document.body.appendChild(container);
        }
        return container;
    }

    function normalizeType(type) {
        return ['success', 'error', 'warning', 'info'].includes(type) ? type : 'info';
    }

    function iconFor(type) {
        return {
            success: 'fa-circle-check',
            error: 'fa-circle-exclamation',
            warning: 'fa-triangle-exclamation',
            info: 'fa-circle-info'
        }[type];
    }

    function removeToast(toast) {
        if (!toast || toast.classList.contains('toast-leaving')) return;
        toast.classList.add('toast-leaving');
        window.setTimeout(() => toast.remove(), 220);
    }

    window.showToast = function (message, type, options) {
        if (!message) return;
        const normalizedType = normalizeType(type);
        const settings = options || {};
        const container = getContainer();

        while (container.children.length >= MAX_VISIBLE_TOASTS) {
            removeToast(container.firstElementChild);
        }

        const toast = document.createElement('div');
        toast.className = `toast toast-${normalizedType}`;
        toast.setAttribute('role', normalizedType === 'error' ? 'alert' : 'status');

        const icon = document.createElement('i');
        icon.className = `toast-icon fa-solid ${iconFor(normalizedType)}`;
        icon.setAttribute('aria-hidden', 'true');

        const text = document.createElement('div');
        text.className = 'toast-message';
        text.textContent = String(message);

        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'toast-close';
        close.setAttribute('aria-label', 'Dismiss notification');
        close.innerHTML = '&times;';
        close.addEventListener('click', () => removeToast(toast));

        toast.append(icon, text, close);
        container.appendChild(toast);

        const duration = Number(settings.duration) || DEFAULT_DURATION;
        if (duration > 0) window.setTimeout(() => removeToast(toast), duration);
    };

    window.showConfirm = function (message) {
        return new Promise((resolve) => {
            if (activeConfirmation) activeConfirmation(false);

            const overlay = document.createElement('div');
            overlay.className = 'toast-confirm-overlay';
            overlay.setAttribute('role', 'presentation');

            const dialog = document.createElement('div');
            dialog.className = 'toast-confirm-dialog';
            dialog.setAttribute('role', 'alertdialog');
            dialog.setAttribute('aria-modal', 'true');

            const text = document.createElement('p');
            text.textContent = String(message || 'Are you sure?');

            const actions = document.createElement('div');
            actions.className = 'toast-confirm-actions';
            const cancel = document.createElement('button');
            cancel.type = 'button';
            cancel.className = 'toast-confirm-cancel';
            cancel.textContent = 'Cancel';
            const confirm = document.createElement('button');
            confirm.type = 'button';
            confirm.className = 'toast-confirm-ok';
            confirm.textContent = 'Continue';
            actions.append(cancel, confirm);
            dialog.append(text, actions);
            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            const finish = (result) => {
                if (!overlay.isConnected) return;
                activeConfirmation = null;
                overlay.remove();
                resolve(result);
            };
            activeConfirmation = finish;
            cancel.addEventListener('click', () => finish(false));
            confirm.addEventListener('click', () => finish(true));
            overlay.addEventListener('click', (event) => {
                if (event.target === overlay) finish(false);
            });
            dialog.addEventListener('keydown', (event) => {
                if (event.key === 'Escape') finish(false);
            });
            confirm.focus();
        });
    };

    function initializeServerMessages() {
        document.querySelectorAll('[data-toast-message]').forEach((messageElement) => {
            const type = messageElement.dataset.toastType || 'info';
            showToast(messageElement.dataset.toastMessage, type);
            messageElement.remove();
        });
    }

    function initializeExistingToasts() {
        document.querySelectorAll('#toast-container .toast').forEach((toast) => {
            const close = toast.querySelector('.toast-close');
            if (close) close.addEventListener('click', () => removeToast(toast));
            window.setTimeout(() => removeToast(toast), DEFAULT_DURATION);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initializeExistingToasts();
            initializeServerMessages();
        });
    } else {
        initializeExistingToasts();
        initializeServerMessages();
    }
}());
