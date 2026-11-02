
(function () {
    'use strict';

    const DAY_NAMES = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

    async function loadForecastStrip(city) {
        if (!city) return;

        const strip = document.getElementById('forecast-strip');
        if (!strip) return;

        try {
            const data = await apiFetch(`/api/forecast?city=${encodeURIComponent(city)}`);
            const signals = data.signals || [];

            strip.innerHTML = '';

            signals.slice(0, 6).forEach(function (signal, index) {
                const date     = new Date(signal.date + 'T12:00:00');
                const dayName  = index === 0 ? 'Today' : DAY_NAMES[date.getDay()];
                const rainPct  = Math.round((signal.rain_prob || 0) * 100);
                const temp     = Math.round(signal.temp_c);

                const div = document.createElement('div');
                div.className  = 'forecast-day' + (index === 0 ? ' active' : '');
                div.setAttribute('role', 'listitem');
                div.setAttribute('tabindex', '0');
                div.setAttribute('aria-label',
                    `${dayName}: ${signal.condition_emoji || ''} ${temp}°C, ${rainPct}% rain`
                );

                div.innerHTML = `
          <span class="day-name">${dayName}</span>
          <span class="day-emoji" aria-hidden="true">${signal.condition_emoji || '🌡'}</span>
          <span class="day-temp">${temp}°</span>
          ${rainPct > 10 ? `<span class="day-rain">${rainPct}%</span>` : ''}
        `;

                // Click to switch active state (future: load that day's outfit)
                div.addEventListener('click', function () {
                    strip.querySelectorAll('.forecast-day').forEach(function (d) {
                        d.classList.remove('active');
                    });
                    div.classList.add('active');
                });

                div.addEventListener('keydown', function (e) {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        div.click();
                    }
                });

                strip.appendChild(div);
            });

        } catch (err) {
            // Non-fatal strip just stays empty
            console.warn('Forecast strip failed:', err.message);
        }
    }

    window.loadForecastStrip = loadForecastStrip;

})();