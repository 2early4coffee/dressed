(function () {
    'use strict';

    const cityInput  = document.getElementById('city-input');
    const locateBtn  = document.getElementById('locate-btn');

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

        // City input search on blur if value changed
        if (cityInput) {
            let lastLoaded = cityInput.value.trim();
            cityInput.addEventListener('blur', function () {
                const city = cityInput.value.trim();
                if (city && city !== lastLoaded) {
                    lastLoaded = city;
                    loadOutfitForCity(city);
                }
            });
        }
    }

    async function loadOutfitForCity(city) {
        showWeatherLoading();
        showOutfitLoading();

        try {
            const data = await apiFetch('/api/outfit', {
                method: 'POST',
                body:   { city },
            });

            if (cityInput) cityInput.value = data.city_name || city;
            window.renderOutfit && window.renderOutfit(data);
            window.loadForecastStrip && window.loadForecastStrip(city);

        } catch (err) {
            showWeatherError();
            console.error('Outfit load failed:', err.message);
        }
    }

    function locateAndLoad() {
        if (!navigator.geolocation) {
            // Geolocation not supported it falls back to Nairobi
            loadOutfitForCity('Nairobi');
            return;
        }

        showWeatherLoading();
        showOutfitLoading();
        setLocateBtnLoading(true);

        navigator.geolocation.getCurrentPosition(
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

                    window.renderOutfit && window.renderOutfit(data);
                    window.loadForecastStrip && window.loadForecastStrip(
                        cityInput ? cityInput.value.trim() : ''
                    );

                } catch (err) {
                    showWeatherError();
                    console.error('Outfit load failed:', err.message);
                }
            },
            function (err) {
                // Geolocation denied or unavailable it falls back to Nairobi
                setLocateBtnLoading(false);
                console.warn('Geolocation error:', err.message);
                loadOutfitForCity(cityInput && cityInput.value.trim() ? cityInput.value.trim() : 'Nairobi');
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

    function showWeatherError() {
        const skeleton = document.getElementById('weather-skeleton');
        const content  = document.getElementById('weather-content');
        const error    = document.getElementById('weather-error');
        if (skeleton) skeleton.hidden = true;
        if (content)  content.hidden  = true;
        if (error)    error.hidden    = false;
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
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();