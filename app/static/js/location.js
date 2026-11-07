(function () {
    'use strict';

    const cityInput = document.getElementById('city-input');
    const locateBtn = document.getElementById('locate-btn');

    // Autocomplete

    let acList       = null;   // the dropdown <ul>
    let acItems      = [];     // current suggestion objects
    let acIndex      = -1;     // keyboard-highlighted index
    let acDebounce   = null;
    let acLastQuery  = '';
    let acJustSelected = false;

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
        closeAc();
        if (cityInput) cityInput.value = s.label;
        acJustSelected = true;
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
            loadOutfitForCity(prefilledCity);
        } else {
            locateAndLoad();
        }

        // Locate-me button
        if (locateBtn) {
            locateBtn.addEventListener('click', function () {
                locateAndLoad();
            });
        }

        // City input - search on Enter or blur if value changed
        if (cityInput) {
            let lastLoaded = cityInput.value.trim();

            cityInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const city = cityInput.value.trim();
                    if (city) {
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
        showWeatherLoading();
        showOutfitLoading();

        try {
            const data = await apiFetch('/api/outfit', {
                method: 'POST',
                body:   { city },
            });

            if (cityInput) cityInput.value = displayLabel || data.city_name || city;
            window.renderOutfit      && window.renderOutfit(data);
            window.loadForecastStrip && window.loadForecastStrip(data.city_name || city);

        } catch (err) {
            showWeatherError(err.code);
            console.error('Outfit load failed:', err.message);
        }
    }

    // Load outfit by browser geolocation

    function locateAndLoad() {
        if (!navigator.geolocation) {
            // No geolocation support - prompt user to type a city
            showWeatherError();
            if (cityInput) {
                cityInput.value       = '';
                cityInput.placeholder = 'Enter your city to get started';
                cityInput.focus();
            }
            return;
        }

        showWeatherLoading();
        showOutfitLoading();
        setLocateBtnLoading(true);

        navigator.geolocation.getCurrentPosition(
            // Success
            async function (position) {
                setLocateBtnLoading(false);
                const { latitude: lat, longitude: lng } = position.coords;

                try {
                    const data = await apiFetch('/api/outfit', {
                        method: 'POST',
                        body:   { lat, lng },
                    });

                    if (cityInput && data.city_name) {
                        cityInput.value = data.city_name;
                    }

                    window.renderOutfit      && window.renderOutfit(data);
                    window.loadForecastStrip && window.loadForecastStrip(
                        cityInput ? cityInput.value.trim() : ''
                    );

                } catch (err) {
                    showWeatherError(err.code);
                    console.error('Outfit load failed:', err.message);
                }
            },
            // Denied / error - do not assume any city
            function (err) {
                setLocateBtnLoading(false);
                console.warn('Geolocation error:', err.message);
                showWeatherError(null);
                if (cityInput) {
                    cityInput.value       = '';
                    cityInput.placeholder = 'Enter your city to get started';
                    cityInput.focus();
                }
            },
            { timeout: 8000, maximumAge: 300000 }
        );
    }

    // UI helpers

    function showWeatherLoading() {
        const skeleton = document.getElementById('weather-skeleton');
        const content  = document.getElementById('weather-content');
        const error    = document.getElementById('weather-error');
        if (skeleton) skeleton.hidden = false;
        if (content)  content.hidden  = true;
        if (error)    error.hidden    = true;
    }

    function showOutfitLoading() {
        const outfitSkeleton = document.getElementById('outfit-skeleton');
        const outfitMeta     = document.getElementById('outfit-meta');
        const itemsSkeleton  = document.getElementById('items-skeleton');
        const itemList       = document.getElementById('item-list');
        const notes          = document.getElementById('notes-container');

        if (outfitSkeleton) outfitSkeleton.hidden = false;
        if (outfitMeta)     outfitMeta.hidden     = true;
        if (itemsSkeleton)  itemsSkeleton.hidden  = false;
        if (itemList)       itemList.hidden       = true;
        if (notes)          notes.hidden          = true;
    }

    function showWeatherError(code) {
        const skeleton   = document.getElementById('weather-skeleton');
        const content    = document.getElementById('weather-content');
        const error      = document.getElementById('weather-error');
        const errorMsg   = document.getElementById('weather-error-msg');
        if (skeleton) skeleton.hidden = true;
        if (content)  content.hidden  = true;
        if (error)    error.hidden    = false;

        if (errorMsg) {
            if (code === 'rate_limited') {
                errorMsg.textContent = 'Weather service is busy, please try again in a moment.';
            } else {
                errorMsg.textContent = 'Check your connection or try a different city.';
            }
        }
    }

    function setLocateBtnLoading(loading) {
        if (!locateBtn) return;
        if (loading) {
            locateBtn.innerHTML = '<span class="spinner spinner-sm" aria-hidden="true"></span> Locating...';
            locateBtn.disabled  = true;
        } else {
            locateBtn.innerHTML = '<i class="ti ti-current-location" aria-hidden="true"></i> Locate me';
            locateBtn.disabled  = false;
        }
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