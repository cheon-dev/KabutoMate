(function () {
    'use strict';

    var STORAGE_KEY = 'kabutomate:navigation-start';
    var SHOW_DELAY = 250;
    var MAX_PENDING_AGE = 120000;
    var navigationStart = null;
    var showTimer = null;

    function readNavigationStart() {
        try {
            var storedValue = window.sessionStorage.getItem(STORAGE_KEY);
            var timestamp = Number(storedValue);

            if (!timestamp || Date.now() - timestamp > MAX_PENDING_AGE) {
                window.sessionStorage.removeItem(STORAGE_KEY);
                return null;
            }

            return timestamp;
        } catch (error) {
            return null;
        }
    }

    function storeNavigationStart(timestamp) {
        try {
            window.sessionStorage.setItem(STORAGE_KEY, String(timestamp));
        } catch (error) {
            // Storage can be unavailable in private browsing; navigation still works.
        }
    }

    function showLoader() {
        document.documentElement.classList.add('page-loading-pending');
    }

    function finishNavigation() {
        if (showTimer) {
            window.clearTimeout(showTimer);
            showTimer = null;
        }

        document.documentElement.classList.remove('page-loading-pending');

        try {
            if (navigationStart && window.sessionStorage.getItem(STORAGE_KEY) === String(navigationStart)) {
                window.sessionStorage.removeItem(STORAGE_KEY);
            }
        } catch (error) {
            // Ignore unavailable session storage.
        }
    }

    function armNavigation(timestamp) {
        navigationStart = timestamp || Date.now();
        storeNavigationStart(navigationStart);

        var remaining = SHOW_DELAY - (Date.now() - navigationStart);
        if (remaining <= 0) {
            showLoader();
        } else {
            if (showTimer) {
                window.clearTimeout(showTimer);
            }
            showTimer = window.setTimeout(showLoader, remaining);
        }
    }

    function shouldTrackLink(event, link) {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return false;
        }

        if (!link || link.target === '_blank' || link.hasAttribute('download') || link.dataset.noPageLoader !== undefined) {
            return false;
        }

        var href = link.getAttribute('href');
        if (!href || href.charAt(0) === '#' || /^(javascript:|mailto:|tel:|data:)/i.test(href)) {
            return false;
        }

        try {
            var destination = new URL(href, window.location.href);
            var current = new URL(window.location.href);
            return destination.origin === current.origin &&
                (destination.pathname !== current.pathname || destination.search !== current.search);
        } catch (error) {
            return false;
        }
    }

    navigationStart = readNavigationStart();
    if (navigationStart) {
        armNavigation(navigationStart);
    }

    document.addEventListener('click', function (event) {
        var clickedElement = event.target;
        var link = clickedElement && clickedElement.closest ? clickedElement.closest('a') : null;
        if (shouldTrackLink(event, link)) {
            armNavigation();
        }
    });

    // Covers normal form submits and location changes that do not originate from a link click.
    window.addEventListener('beforeunload', function () {
        if (!navigationStart) {
            storeNavigationStart(Date.now());
        }
    });

    window.addEventListener('pagehide', function () {
        if (!navigationStart) {
            storeNavigationStart(Date.now());
        }
    });

    window.addEventListener('load', finishNavigation, { once: true });
    window.addEventListener('pageshow', function (event) {
        if (event.persisted) {
            finishNavigation();
        }
    });
    if (document.readyState === 'complete') {
        finishNavigation();
    }
})();
