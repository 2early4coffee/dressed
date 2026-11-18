(function () {
    'use strict';

    const cityInput = document.getElementById('city-input');
    const locateBtn = document.getElementById('locate-btn');

    // Autocomplete function

    let acList       = null;
    let acItems      = [];
    let acIndex      = -1;
    let acDebounce   = null;
    let acLastQuery  = '';
    let acJustSelected = false;
    let outfitInFlight = false;
    let locating       = false;
    let lastLoaded     = '';

    function buildAcList() {
        if (acList) return;
        const wrap = cityInput && cityInput.closest('.city-input-wrap');
        if (!wrap) return;

        wrap.style.position = 'relative';
        acList = document.createElement('ul');
        acList.id        = 'city-suggestions';
        acList.role      = 'listbox';
        acList.setAttribute('aria-label', 'City suggestions');
        Object.assign(acList.style, {
            position:   'absolute',
            top:        '100%',
            left:       '0',
            right:      '0',
            marginTop:  '4px',
            background: '#fff',
            border:     '1.5px solid var(--border)',
            borderRadius: 'var(--r-lg)',
            boxShadow:  '0 8px 24px rgba(0,0,0,0.10)',
            padding:    '4px 0',
            zIndex:     '999',
            listStyle:  'none',
            maxHeight:  '220px',
            overflowY:  'auto',
            display:    'none',
        });
        wrap.appendChild(acList);

        // Close on outside click
        document.addEventListener('mousedown', function (e) {
            if (!wrap.contains(e.target)) closeAc();
        });
    }

    function openAc(suggestions) {
        buildAcList();
        if (!acList) return;

        acItems = suggestions;
        acIndex = -1;
        acList.innerHTML = '';

        suggestions.forEach(function (s, i) {
            const li = document.createElement('li');
            li.setAttribute('role', 'option');
            li.setAttribute('data-index', i);
            Object.assign(li.style, {
                padding:    '0.6rem 1rem',
                cursor:     'pointer',
                fontSize:   '0.9rem',
                color:      'var(--text-primary)',
                whiteSpace: 'nowrap',
                overflow:   'hidden',
                textOverflow: 'ellipsis',
            });
            li.textContent = s.label;

            li.addEventListener('mouseenter', function () { highlightAc(i); });
            li.addEventListener('mousedown',  function (e) {
                e.preventDefault();
                selectAc(i);
            });
            acList.appendChild(li);
        });

        acList.style.display = 'block';
    }

    function closeAc() {
        if (acList) acList.style.display = 'none';
        acIndex = -1;
    }

    function highlightAc(idx) {
        acIndex = idx;
        Array.from(acList.children).forEach(function (li, i) {
            li.style.background = i === idx ? 'var(--green-50)' : '';
            li.style.color      = i === idx ? 'var(--green-700)' : 'var(--text-primary)';
        });
    }

    function selectAc(idx) {
        const s = acItems[idx];
        if (!s) return;
        acJustSelected = true;
        closeAc();
        if (cityInput) cityInput.value = s.label;
        lastLoaded = s.label;
        loadOutfitForCity(s.label, s.label);
    }

    async function fetchSuggestions(q) {
        if (q.length < 2) { closeAc(); return; }
        if (q === acLastQuery) return;
        acLastQuery = q;

        try {
            const resp = await fetch(`/api/geocode/suggest?q=${encodeURIComponent(q)}`);
            if (!resp.ok) return;
            const suggestions = await resp.json();
            if (Array.isArray(suggestions) && suggestions.length) {
                openAc(suggestions);
            } else {
                closeAc();
            }
        } catch (_) {
            // Silently ignore - autocomplete is best-effort
        }
    }

    function attachAutocomplete() {
        if (!cityInput) return;

        cityInput.setAttribute('autocomplete', 'off');
        cityInput.setAttribute('aria-autocomplete', 'list');
        cityInput.setAttribute('aria-haspopup', 'listbox');

        cityInput.addEventListener('input', function () {
            clearTimeout(acDebounce);
            const q = cityInput.value.trim();
            if (q.length < 2) { closeAc(); return; }
            acDebounce = setTimeout(function () { fetchSuggestions(q); }, 280);
        });

        cityInput.addEventListener('keydown', function (e) {
            if (!acList || acList.style.display === 'none') return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                highlightAc(Math.min(acIndex + 1, acItems.length - 1));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                highlightAc(Math.max(acIndex - 1, 0));
            } else if (e.key === 'Enter' && acIndex >= 0) {
                e.preventDefault();
                e.stopPropagation();
                selectAc(acIndex);
            } else if (e.key === 'Escape') {
                closeAc();
            }
        });
    }
    // Entry point

    function init() {
        const prefilledCity = cityInput && cityInput.value.trim();

        if (prefilledCity) {
            lastLoaded = prefilledCity;
            loadOutfitForCity(prefilledCity);
        } else {
            // First visit: no city yet. Show the welcome card instead of skeletons, and only auto-locate if permission was granted before (so the browser prompt never appears without a click).
            showWelcome();
            autoLocateIfAlreadyAllowed();
        }

        // Locate-me button in the search bar
        if (locateBtn) {
            locateBtn.addEventListener('click', locateAndLoad);
        }

        // Buttons on the first-visit welcome card
        const welcomeLocate = document.getElementById('welcome-locate-btn');
        const welcomeType   = document.getElementById('welcome-type-btn');
        if (welcomeLocate) welcomeLocate.addEventListener('click', locateAndLoad);
        if (welcomeType) {
            welcomeType.addEventListener('click', function () {
                hideLocateMsg();
                if (cityInput) cityInput.focus();
            });
        }

        // City input - search on Enter or blur if value changed
        if (cityInput) {
            cityInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' && (!acList || acList.style.display === 'none')) {
                    e.preventDefault();
                    const city = cityInput.value.trim();
                    if (city && city !== lastLoaded) {
                        lastLoaded = city;
                        loadOutfitForCity(city);
                    }
                }
            });

            cityInput.addEventListener('blur', function () {
                if (acJustSelected) { acJustSelected = false; return; }
                const city = cityInput.value.trim();
                if (city && city !== lastLoaded) {
                    lastLoaded = city;
                    loadOutfitForCity(city);
                }
            });
        }
    }

    // Load outfit by city name

    async function loadOutfitForCity(city, displayLabel) {
        if (outfitInFlight) return;
        outfitInFlight = true;
        hideLocateMsg();
        showWeatherLoading();
        showOutfitLoading();

        try {
            const data = await apiFetch('/api/outfit', {
                method: 'POST',
                body:   { city },
            });

            const label = displayLabel || data.city_name || city;
            if (cityInput) cityInput.value = label;
            lastLoaded = label;
            window.renderOutfit      && window.renderOutfit(data);
            window.loadForecastStrip && window.loadForecastStrip(label);

        } catch (err) {
            showWeatherError(err.code);
            console.error('Outfit load failed:', err.message);
        } finally {
            outfitInFlight = false;
        }
    }

    // Load outfit by coordinates (after geolocation succeeds)

    async function loadOutfitForCoords(lat, lng) {
        if (outfitInFlight) return;
        outfitInFlight = true;
        hideLocateMsg();
        showWeatherLoading();
        showOutfitLoading();

        try {
            const data = await apiFetch('/api/outfit', {
                method: 'POST',
                body:   { lat, lng },
            });

            if (data.city_name) {
                if (cityInput) cityInput.value = data.city_name;
                lastLoaded = data.city_name;
            }
            window.renderOutfit && window.renderOutfit(data);
            if (data.city_name) {
                window.loadForecastStrip && window.loadForecastStrip(data.city_name);
            }

        } catch (err) {
            showWeatherError(err.code);
            console.error('Outfit load failed:', err.message);
        } finally {
            outfitInFlight = false;
        }
    }

    // Browser geolocation

    function autoLocateIfAlreadyAllowed() {
        if (!navigator.geolocation || !navigator.permissions) return;
        navigator.permissions.query({ name: 'geolocation' })
            .then(function (status) {
                if (status.state === 'granted') locateAndLoad();
            })
            .catch(function () { /* Permissions API unsupported: wait for a click */ });
    }

    function locateAndLoad() {
        if (locating || outfitInFlight) return;

        if (!navigator.geolocation) {
            showLocateMsg('Your browser cannot share your location. Type your city instead.');
            return;
        }

        locating = true;
        setLocateBtnLoading(true);

        // Safety net: if the permission prompt is ignored or dismissed, the browser never calls either callback. Don't leave the button stuck.
        let gaveUp = false;
        const guard = setTimeout(function () {
            gaveUp   = true;
            locating = false;
            setLocateBtnLoading(false);
            showLocateMsg('Still waiting for your location. Check the prompt by the address bar, or type your city.');
        }, 20000);

        navigator.geolocation.getCurrentPosition(
            function (position) {
                clearTimeout(guard);
                locating = false;
                setLocateBtnLoading(false);
                // Load even if the safety net fired: the user allowed it late.
                loadOutfitForCoords(position.coords.latitude, position.coords.longitude);
            },
            function (err) {
                clearTimeout(guard);
                locating = false;
                setLocateBtnLoading(false);
                console.warn('Geolocation error', err.code, err.message);
                if (!gaveUp) showLocateMsg(geoErrorMessage(err));
            },
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 }
        );
    }

    function geoErrorMessage(err) {
        if (err.code === 1) {
            return 'Location is blocked for this site. Allow it from the icon in the address bar, or type your city.';
        }
        if (err.code === 2) {
            return "Your device couldn't work out where you are. Check that location services are on, or type your city.";
        }
        return 'Finding your location took too long. Try again, or type your city.';
    }

    // UI helpers

    function setHidden(id, hidden) {
        const el = document.getElementById(id);
        if (el) el.hidden = hidden;
    }

    function showWelcome() {
        setHidden('weather-skeleton', true);
        setHidden('weather-content',  true);
        setHidden('weather-error',    true);
        setHidden('weather-welcome',  false);
        setHidden('outfit-skeleton',  true);
        setHidden('items-skeleton',   true);
        setHidden('items-idle',       false);
    }

    function showLocateMsg(text) {
        const el = document.getElementById('locate-msg');
        if (el) {
            el.textContent = text;
            el.hidden = false;
        }
        if (cityInput) cityInput.focus();
    }

    function hideLocateMsg() {
        setHidden('locate-msg', true);
    }

    function showWeatherLoading() {
        setHidden('weather-welcome',  true);
        setHidden('weather-skeleton', false);
        setHidden('weather-content',  true);
        setHidden('weather-error',    true);
    }

    function showOutfitLoading() {
        setHidden('items-idle',      true);
        setHidden('outfit-skeleton', false);
        setHidden('outfit-meta',     true);
        setHidden('items-skeleton',  false);
        setHidden('item-list',       true);
        setHidden('notes-container', true);
    }

    function showWeatherError(code) {
        setHidden('weather-welcome',  true);
        setHidden('weather-skeleton', true);
        setHidden('weather-content',  true);
        setHidden('weather-error',    false);

        const errorMsg = document.getElementById('weather-error-msg');
        if (errorMsg) {
            if (code === 'rate_limited') {
                errorMsg.textContent = 'Weather service is busy, please try again in a moment.';
            } else {
                errorMsg.textContent = 'Check your connection or try a different city.';
            }
        }
    }

    function setLocateBtnLoading(loading) {
        const buttons = [locateBtn, document.getElementById('welcome-locate-btn')];
        buttons.forEach(function (btn) {
            if (!btn) return;
            if (loading) {
                if (!btn.dataset.label) btn.dataset.label = btn.innerHTML;
                btn.innerHTML = '<span class="spinner spinner-sm" aria-hidden="true"></span> Locating...';
                btn.disabled  = true;
            } else {
                if (btn.dataset.label) btn.innerHTML = btn.dataset.label;
                btn.disabled  = false;
            }
        });
    }

    // Expose globals

    window.loadOutfitForCity = loadOutfitForCity;
    window.locateAndLoad     = locateAndLoad;

    // Boot

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            attachAutocomplete();
            init();
        });
    } else {
        attachAutocomplete();
        init();
    }
})();