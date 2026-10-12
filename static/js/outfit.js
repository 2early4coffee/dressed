(function () {
    'use strict';

    // Category icon emoji map
    const CATEGORY_EMOJI = {
        tops:     '👔',
        bottoms:  '👖',
        shoes:    '👟',
        layers:   '🧥',
        extras:   '🎒',
        activity: '🏃',
    };

    // Item key to emoji overrides
    const ITEM_EMOJI = {
        compact_umbrella: '☂️',
        sunglasses:       '🕶️',
        sunscreen:        '🧴',
        lip_balm:         '💋',
        moisturiser:      '🧴',
        sandals:          '🩴',
        boots:            '🥾',
        ankle_boots:      '👢',
        heels:            '👠',
        loafers:          '👞',
        oxford_shoes:     '👞',
        blazer:           '🥻',
        knit_sweater:     '🧶',
        light_jacket:     '🧥',
    };

    //Item key to icon class map
    const CATEGORY_BG = {
        extras:  'extras',
        layers:  'layer',
    };

    // Condition -> warm badge colour
    const CONDITION_CHIPS = {
        clear:            { label: 'Clear',           cls: 'chip-sun'  },
        mainly_clear:     { label: 'Mainly clear',    cls: 'chip-sun'  },
        partly_cloudy:    { label: 'Partly cloudy',   cls: ''          },
        overcast:         { label: 'Overcast',        cls: ''          },
        light_drizzle:    { label: 'Light drizzle',   cls: 'chip-blue' },
        moderate_drizzle: { label: 'Drizzle',         cls: 'chip-blue' },
        heavy_drizzle:    { label: 'Heavy drizzle',   cls: 'chip-blue' },
        light_rain:       { label: 'Light rain',      cls: 'chip-blue' },
        moderate_rain:    { label: 'Moderate rain',   cls: 'chip-blue' },
        heavy_rain:       { label: 'Heavy rain',      cls: 'chip-blue' },
        rain_showers:     { label: 'Rain showers',    cls: 'chip-warm' },
        thunderstorm:     { label: 'Thunderstorm',    cls: 'chip-warm' },
        fog:              { label: 'Foggy',           cls: ''          },
        snow:             { label: 'Snow',            cls: 'chip-blue' },
    };

    // Tier labels
    const TIER_LABELS = {
        hot:  'Hot',
        warm: 'Warm',
        mild: 'Mild',
        cool: 'Cool',
        cold: 'Cold',
    };

    // Main render function

    function renderOutfit(data) {
        renderWeatherCard(data);
        renderOutfitPanel(data);
        renderNotes(data.notes || []);
        revealAll();
    }

    // Weather card

    function renderWeatherCard(data) {
        // Temperature
        setText('temp-display', Math.round(data.temp_c));
        setText('feels-like-display', `Feels like ${Math.round(data.feels_like)}°C`);

        setText('stat-uv',    (data.uv_index || 0).toFixed(1));
        setText('stat-wind',  `${Math.round(data.wind_kph || 0)} km/h`);
        setText('stat-humid', `${Math.round(data.humidity_pct || 0)}%`);
        setText('temp-range-display', `↑ ${Math.round(data.temp_c)}°  ↓ ${Math.round(data.temp_min_c || 0)}°`);

        // Stats
        setText('stat-rain', `${Math.round((data.rain_prob || 0) * 100)}%`);

        // Location from city cookie / response
        const locName = document.getElementById('location-name');
        const cityInput = document.getElementById('city-input');
        if (locName && cityInput) {
            locName.textContent = cityInput.value || 'Your location';
        }

        // Condition badge
        const condEl   = document.getElementById('condition-badge');
        const condKey  = data.condition || 'partly_cloudy';
        const condInfo = CONDITION_CHIPS[condKey] || { label: condKey.replace(/_/g, ' '), cls: '' };
        if (condEl) {
            condEl.className  = `chip ${condInfo.cls || 'chip-green'}`;
            condEl.textContent = `${data.emoji || '🌡'} ${condInfo.label}`;
        }
    }

    // Outfit panel

    function renderOutfitPanel(data) {
        // Outfit name from outfit_key: "warm_smart_casual" -> "Warm Smart Casual"
        const outfitName = (data.outfit_key || '')
            .split('_')
            .map(w => w.charAt(0).toUpperCase() + w.slice(1))
            .join(' ');

        setText('outfit-name', outfitName || 'Today\'s Outfit');

        // Tier + rain chips
        const tagsEl = document.getElementById('outfit-tags');
        if (tagsEl) {
            tagsEl.innerHTML = '';
            if (data.tier) {
                tagsEl.insertAdjacentHTML('beforeend',
                    `<span class="chip chip-green">${TIER_LABELS[data.tier] || data.tier}</span>`
                );
            }
            if (data.is_rainy) {
                tagsEl.insertAdjacentHTML('beforeend',
                    `<span class="chip chip-blue">☂ Rainy</span>`
                );
            }
        }

        // Outfit image which check for static file, fall back to emoji
        const img         = document.getElementById('outfit-img');
        const placeholder = document.getElementById('outfit-placeholder');
        if (img && data.outfit_key) {
            img.src = `/static/img/outfits/${data.outfit_key}.jpg`;
            img.alt = outfitName;
            img.onload = function () {
                img.hidden        = false;
                if (placeholder) placeholder.hidden = true;
            };
            img.onerror = function () {
                img.hidden        = true;
                if (placeholder) {
                    placeholder.hidden    = false;
                    placeholder.textContent = data.emoji || '👕';
                }
            };
        } else if (placeholder && data.emoji) {
            placeholder.textContent = data.emoji;
        }

        // Clothing items
        const itemList  = document.getElementById('item-list');
        const itemCount = document.getElementById('items-count');
        if (!itemList) return;

        itemList.innerHTML = '';
        const items = data.items || [];

        items.forEach(function (item) {
            const emoji   = ITEM_EMOJI[item.item_key] || CATEGORY_EMOJI[item.category] || '👕';
            const bgClass = CATEGORY_BG[item.category] || '';
            const li      = document.createElement('li');
            li.className  = 'item-row';
            li.setAttribute('role', 'listitem');
            li.innerHTML  = `
        <div class="item-icon ${bgClass}" aria-hidden="true">${emoji}</div>
        <span class="item-name">${escapeHtml(item.item_name)}</span>
        <span class="item-cat">${capitalise(item.category)}</span>
      `;
            itemList.appendChild(li);
        });

        if (itemCount) {
            itemCount.textContent = `${items.length} item${items.length !== 1 ? 's' : ''}`;
        }
    }

    // Advisor notes

    function renderNotes(notes) {
        const container = document.getElementById('notes-container');
        const card      = document.getElementById('notes-card');
        if (!container || !card) return;

        if (!notes.length) {
            container.hidden = true;
            return;
        }

        card.innerHTML = notes.map(function (note) {
            return `
        <div class="note-row">
          <div class="note-dot" aria-hidden="true"></div>
          <p class="note-text">${escapeHtml(note)}</p>
        </div>
      `;
        }).join('');

        container.hidden = false;
    }

    // Reveal content, hide skeletons

    function revealAll() {
        // Weather
        hide('weather-skeleton');
        hide('weather-error');
        show('weather-content');

        // Outfit
        hide('outfit-skeleton');
        show('outfit-meta');

        // Items
        hide('items-skeleton');
        show('item-list');
    }

    // Utilities

    function setText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function show(id) {
        const el = document.getElementById(id);
        if (el) el.hidden = false;
    }

    function hide(id) {
        const el = document.getElementById(id);
        if (el) el.hidden = true;
    }

    function escapeHtml(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function capitalise(str) {
        return str ? str.charAt(0).toUpperCase() + str.slice(1) : '';
    }

    // Expose

    window.renderOutfit = renderOutfit;

})();