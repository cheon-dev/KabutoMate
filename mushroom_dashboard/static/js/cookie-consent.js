(function () {
    'use strict';

    const storageKey = 'kabutomate-cookie-consent';
    const banner = document.getElementById('cookie-consent');
    const acceptButton = banner?.querySelector('[data-cookie-consent-accept]');
    const rejectButton = banner?.querySelector('[data-cookie-consent-reject]');

    if (!banner || !acceptButton || !rejectButton) return;

    let consent = null;
    try {
        consent = window.localStorage.getItem(storageKey);
    } catch (error) {
        // Show the banner when browser storage is unavailable.
    }

    if (consent !== 'accepted' && consent !== 'rejected') {
        banner.hidden = false;
        document.body.classList.add('cookie-consent-visible');
    }

    function dismissBanner(choice) {
        try {
            window.localStorage.setItem(storageKey, choice);
        } catch (error) {
            // The banner can still be dismissed for this page.
        }
        banner.hidden = true;
        document.body.classList.remove('cookie-consent-visible');
    }

    acceptButton.addEventListener('click', function () {
        dismissBanner('accepted');
    });

    rejectButton.addEventListener('click', function () {
        dismissBanner('rejected');
    });
}());
