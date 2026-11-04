# Dressed

Oct 31, 2026 · @Walter Roy

Live at <https://dressed-cl21.onrender.com> · [GitHub](https://github.com/2early4coffee/dressed)

## Overview

Dressed is a weather-aware outfit advisor and travel packing assistant built as the final project for Harvard's CS50x Introduction to Computer Science. The application takes a user's location, fetches live weather data from the Open-Meteo API, and recommends a complete outfit appropriate for the current conditions and the user's preferred style. Beyond the daily recommendation, Dressed provides a five-day forecast, a trip packing list generator for multiple destinations, and a preference system that remembers each user's style and default location.

The project was developed to explore how a web application can combine multiple external data sources — weather, geocoding, and user-stored preferences — into a coherent, opinionated product. Rather than presenting raw weather data, Dressed makes a concrete decision for the user: given today's temperature, precipitation, and the style they prefer, here is what to wear. That decision is communicated through a curated outfit image, the outfit name, and a set of descriptive tags, all loaded dynamically without a page refresh.

Dressed is built with Python and Flask, stores user accounts and preferences in a PostgreSQL database hosted on Supabase, and is designed to be deployed on Render using Gunicorn as the production WSGI server. The application follows the application-factory pattern, uses SQLAlchemy for all database access, and serves static files through WhiteNoise middleware so no separate object-storage bucket is required.

## Features

**Outfit Advisor.** The core feature of Dressed is a single-page outfit recommendation. After a user enters their location and selects a style preference (casual, smart casual, or formal), the application fetches the current temperature and checks for precipitation. It maps those conditions to one of 18 outfit combinations — six temperature tiers crossed with three style levels, with a rainy-day override — and displays the matching outfit image, name, and descriptive tags. All of this happens via a single AJAX call; the page does not reload.

**Five-Day Forecast.** Below the daily recommendation, a forecast strip shows the next five days. Each day displays the high and low temperature, a weather condition icon, and the outfit name for that day, allowing users to plan their wardrobe for the week ahead.

**Trip Packing List.** Users can enter up to five destinations and travel dates to generate a consolidated packing list. The application fetches forecast data for each destination, determines the outfit category for each day of travel, and collapses the results into a deduplicated list of clothing items. The list is presented in a printable format.

**User Preferences.** Registered users can save a default location and a default style preference. On return visits, the outfit advisor pre-populates with their saved settings, reducing the number of fields to fill in. Preferences are stored per user in the database and updated through a dedicated settings page.

**Geocoding Cache.** To avoid repeated calls to the Nominatim API for the same place name, the application stores resolved coordinates in a database table keyed by a normalised version of the search string. Subsequent lookups for the same location return instantly from the cache rather than making a new outbound request.

## How It Works

**Outfit selection logic.** The application maps weather conditions to outfit recommendations using a two-part key: a temperature tier and a style level. Temperature is divided into six tiers — hot (above 30 °C), warm (25–30 °C), mild (18–25 °C), cool (10–18 °C), cold (0–10 °C), and freezing (below 0 °C). Each tier is crossed with three style levels — casual, smart casual, and formal — producing 18 base combinations. A rainy-day override applies when the current weather code from Open-Meteo indicates precipitation: the tier stays the same but the outfit switches to a rain-appropriate variant regardless of the selected style. The selected key is used to look up both an image filename and a set of descriptive tags from a static mapping dictionary.

**Geocoding flow.** When a user submits a location string, the application first normalises the string (lowercased, stripped of extra whitespace) and checks the geocoding cache table. On a cache miss, it calls the Nominatim API with a structured query and stores the returned latitude, longitude, and canonical place name in the cache before returning them to the caller. All subsequent weather API calls for that location use the cached coordinates.

**Weather data.** Coordinates are passed to the Open-Meteo API, which returns hourly temperature, precipitation probability, and weather condition codes. The application extracts the value for the current hour for the daily recommendation, and aggregates daily highs, lows, and dominant conditions for the five-day forecast. No API key is required for Open-Meteo, which operates under a free-tier agreement for non-commercial use.

## Design Decisions

**Application factory pattern.** Flask's `create_app()` factory function is used rather than a module-level app instance. This makes the application easier to test in isolation and is a requirement for Gunicorn's multi-worker mode, where each worker process calls the factory to create its own app instance.

**SQLAlchemy over raw SQL.** CS50's problem sets use the `cs50` library's raw SQL helpers. Dressed deliberately adopts SQLAlchemy to explore a production-grade ORM. Model definitions, relationships, and queries are expressed through the ORM layer, which also handles connection pooling and session lifecycle through Flask-SQLAlchemy.

**WhiteNoise for static files.** Rather than configuring a separate CDN or object-storage bucket to serve images and CSS, WhiteNoise middleware is mounted directly on the Flask application. This keeps deployment simple — static files are committed to the repository and served from the same Gunicorn process — while still adding cache headers and gzip compression in production.

**No JavaScript framework.** The frontend relies on the Fetch API and vanilla DOM manipulation rather than React or another framework. This was a deliberate choice to keep the project within the scope of what was taught in CS50's Week 8 (HTML, CSS, JavaScript) without introducing build tooling. The result is a single HTML template with a small, readable script block.

**Free-tier APIs.** Both Open-Meteo (weather) and Nominatim (geocoding) are free services that require no API key for reasonable usage. This keeps the project fully deployable without billing credentials, which matters for a CS50 submission and for anyone who wants to run a fork locally.

## Project Structure

```
dressed/
  app/
    __init__.py          # create_app() factory, registers blueprints and WhiteNoise
    models.py            # SQLAlchemy models: User, UserPreference, GeoCache
    routes/
      auth.py            # /login, /register, /logout
      main.py            # / (index), /outfit, /forecast, /packing-list, /settings
    services/
      weather.py         # Open-Meteo API calls and condition parsing
      geocoding.py       # Nominatim calls and GeoCache read/write
      outfits.py         # Tier/style mapping, rainy override, image and tag lookup
    static/
      css/main.css       # Design tokens and component styles
      img/outfits/       # 18 outfit images (hot/warm/mild/cool/cold/rainy x casual/smart/formal)
      js/
    templates/
      base.html          # Layout shell: nav, footer, CSS/JS links
      index.html         # Main page: outfit advisor, forecast strip
      auth/              # login.html, register.html
      packing.html       # Trip packing list form and results
      settings.html      # Preference editing form
  config.py              # Config classes (Development, Production) reading .env
  requirements.txt
  Procfile               # web: gunicorn "app:create_app()" --workers 2 --threads 4 --timeout 60
  .env.example
```

## Setup and Installation

**Prerequisites:** Python 3.11 or later, a Supabase project (free tier is sufficient), and Git.

1. Clone the repository and create a virtual environment:

   ```
   git clone https://github.com/<username>/dressed.git
   cd dressed
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in the values:

   ```
   DATABASE_URL=postgresql+psycopg2://<user>:<password>@<host>:6543/postgres
   SECRET_KEY=<long random string>
   FLASK_ENV=development
   ```

   The `DATABASE_URL` should point to Supabase's session pooler endpoint (port 6543), not the direct connection (port 5432), to avoid IPv6 routing issues on most local networks.
3. Initialise the database:

   ```
   flask db upgrade
   ```

   If Flask-Migrate is not configured, the models can be created directly with `flask shell` and `db.create_all()`.
4. Run the development server:

   ```
   flask run
   ```

   The application is available at `http://127.0.0.1:5000`.

**Production deployment (Render).** Set the same environment variables in Render's dashboard under Environment. Use the start command:

```
gunicorn "app:create_app()" --workers 2 --threads 4 --timeout 60
```

Render's free tier puts the service to sleep after inactivity; a paid instance type keeps it awake.

## Acknowledgements

Dressed was created as the final project for [CS50x: Introduction to Computer Science](https://cs50.harvard.edu/x/), Harvard University's open-enrollment introductory programming course. The project structure, tooling choices, and ambition to ship something real were all shaped by the course's emphasis on building things that work, not just things that compile.

Weather data is provided by [Open-Meteo](https://open-meteo.com/), an open-source weather API that offers free access for non-commercial use. Geocoding (place name to coordinates) is provided by [Nominatim](https://nominatim.org/) and the OpenStreetMap community. Neither service requires an API key for reasonable usage.

The application is hosted on [Supabase](https://supabase.com/) (PostgreSQL) and deployed via [Render](https://render.com/).