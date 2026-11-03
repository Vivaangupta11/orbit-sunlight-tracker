# app.py — Sunlight-or-Shadow Orbit Tracker (website version)

import base64
import math
import os
import io
import urllib.request
from skyfield.iokit import parse_tle_file
from datetime import date, timedelta

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import streamlit as st
import streamlit.components.v1 as components
from skyfield.api import load

st.set_page_config(page_title='Orbit Sunlight Tracker', page_icon='🛰️', layout='wide')

ISS_NUMBER = 25544

# The 10 satellite cards. Put matching photos in an "images" folder (optional).
SATELLITES = [
    {'name': 'Hubble Space Telescope', 'catnr': 20580, 'img': 'images/hubble.jpg',     'blurb': 'NASA/ESA space telescope'},
    {'name': 'Tiangong',               'catnr': 48274, 'img': 'images/tiangong.jpg',   'blurb': "China's space station"},
    {'name': 'Sentinel-1C',            'catnr': 62261, 'img': 'images/sentinel1c.jpg', 'blurb': 'ESA radar satellite, dawn-dusk orbit'},
    {'name': 'Sentinel-1A',            'catnr': 39634, 'img': 'images/sentinel1a.jpg', 'blurb': 'Same orbit as Sentinel-1C'},
    {'name': 'Sentinel-2A',            'catnr': 40697, 'img': 'images/sentinel2a.jpg', 'blurb': 'ESA colour-camera satellite'},
    {'name': 'Landsat 9',              'catnr': 49260, 'img': 'images/landsat9.jpg',   'blurb': 'NASA/USGS Earth imaging'},
    {'name': 'Terra',                  'catnr': 25994, 'img': 'images/terra.jpg',      'blurb': 'NASA climate satellite'},
    {'name': 'NOAA-20',                'catnr': 43013, 'img': 'images/noaa20.jpg',     'blurb': 'US weather satellite'},
    {'name': 'GOES-16',                'catnr': 41866, 'img': 'images/goes16.jpg',     'blurb': 'Geostationary weather satellite'},
    {'name': 'Vanguard 1',             'catnr': 5,     'img': 'images/vanguard1.jpg',  'blurb': 'Oldest satellite still in orbit (1958)'},
]


# ---------- Helper: show raw HTML ----------
def html(block):
    """Show HTML. Lines are joined so Markdown doesn't turn indented HTML into a code block."""
    st.markdown(' '.join(line.strip() for line in block.splitlines()), unsafe_allow_html=True)


# ---------- Page style ----------
html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Inter:wght@400;500;600&display=swap');
html, body, p, li, label, .stMarkdown { font-family: 'Inter', sans-serif; }
h1, h2, h3, .brand, .hero-title, .section-title { font-family: 'Space Grotesk', sans-serif !important; }
[data-testid="stHeader"], #MainMenu, footer { display: none; }
.block-container { padding-top: 5rem; max-width: 1200px; }
.topnav { position: fixed; top: 0; left: 0; right: 0; z-index: 1000; display: flex; justify-content: space-between;
          align-items: center; padding: 14px 40px; background: rgba(7,10,20,0.88); backdrop-filter: blur(8px);
          border-bottom: 1px solid rgba(255,255,255,0.08); }
.topnav a { color: #cfd6e6; text-decoration: none; margin-left: 28px; font-size: 15px; }
.topnav a:hover { color: #ffd166; }
.brand { color: #ffffff; font-weight: 700; letter-spacing: 2px; font-size: 17px; }
.anchor { scroll-margin-top: 80px; }
.hero-title { font-size: 54px; line-height: 1.08; font-weight: 700; color: #ffffff; margin: 30px 0 18px; }
.hero-title span { color: #ffd166; }
.hero-sub { font-size: 18px; color: #aab4c8; line-height: 1.65; }
.btn { display: inline-block; padding: 12px 24px; border-radius: 999px; background: #ffd166; color: #0b0f1a !important;
       text-decoration: none; font-weight: 600; margin: 22px 10px 0 0; }
.btn-outline { background: transparent; color: #ffd166 !important; border: 1px solid #ffd166; }
.section-label { color: #ffd166; letter-spacing: 3px; font-size: 13px; text-transform: uppercase; margin: 70px 0 4px; }
.section-title { font-size: 38px; color: #ffffff; font-weight: 700; margin: 0 0 20px; }
.info-card { background: #121829; border: 1px solid #222b45; border-radius: 16px; padding: 24px; height: 100%; }
.info-card h4 { color: #ffffff; margin: 0 0 10px; font-family: 'Space Grotesk', sans-serif; }
.info-card p { color: #aab4c8; line-height: 1.6; margin: 0; }
.card-img { width: 100%; height: 140px; object-fit: cover; border-radius: 10px; }
.card-ph { height: 140px; border-radius: 10px; background: linear-gradient(135deg, #1b2440, #0d1324);
           display: flex; align-items: center; justify-content: center; }
.muted { color: #8a94a8; font-size: 13px; }
[data-testid="stButton"] button { width: 100%; border-radius: 999px; }
.footer { border-top: 1px solid rgba(255,255,255,0.1); margin-top: 80px; padding: 34px 0; text-align: center; color: #8a94a8; }
.footer a { color: #cfd6e6; margin: 0 16px; text-decoration: none; }
.footer a:hover { color: #ffd166; }
</style>
""")

# ---------- Top menu ----------
html("""
<div class="topnav">
<div class="brand">🛰️ ORBIT TRACKER</div>
<div><a href="#home">Home</a><a href="#about">About</a><a href="#tracker">Orbit Tracker</a></div>
</div>
""")


# ---------- Setup (cached: loaded once) ----------
@st.cache_resource
def load_basics():
    return load.timescale(), load('de421.bsp')

ts, eph = load_basics()


@st.cache_resource
def load_saved_tles():
    """Read the orbit data saved in tles.txt into a dictionary: catalog number -> satellite."""
    if not os.path.exists('tles.txt'):
        return {}
    sats = load.tle_file('tles.txt')
    return {s.model.satnum: s for s in sats}


def download_tle(catnr):
    """Try CelesTrak directly, but give up after 10 seconds."""
    url = f'https://celestrak.org/NORAD/elements/gp.php?CATNR={catnr}&FORMAT=tle'
    with urllib.request.urlopen(url, timeout=10) as response:
        data = response.read()
    sats = list(parse_tle_file(io.BytesIO(data), ts))
    return sats[0] if sats else None


@st.cache_resource(ttl=6 * 3600, show_spinner=False)
def get_satellite(catnr):
    """Use the saved file first. If the satellite isn't there, try CelesTrak."""
    saved = load_saved_tles()
    if catnr in saved:
        return saved[catnr]
    try:
        return download_tle(catnr)
    except Exception:
        return None

def orbit_period(sat):
    return 2 * math.pi / sat.model.no_kozai


def check_orbit(sat, d):
    """One orbit from midnight UTC: period, shadow minutes, % in shadow."""
    period = orbit_period(sat)
    total = round(period)
    times = ts.utc(d.year, d.month, d.day, 0, range(total))
    sunlit = sat.at(times).is_sunlit(eph)
    shadow = int(total - np.count_nonzero(sunlit))
    return period, shadow, shadow / total * 100


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def day_series(catnr, day_iso):
    """Sunlight once per minute for one day."""
    sat = get_satellite(catnr)
    d = date.fromisoformat(day_iso)
    times = ts.utc(d.year, d.month, d.day, 0, range(1440))
    sunlit = np.array(sat.at(times).is_sunlit(eph))
    return np.arange(1440) / 60, sunlit


@st.cache_data(ttl=6 * 3600, show_spinner=False, max_entries=50)
def year_series(catnr, start_iso):
    """Average minutes in shadow per orbit, for each day of a year (worked out 30 days at a time)."""
    sat = get_satellite(catnr)
    start = date.fromisoformat(start_iso)
    orbits_per_day = 1440 / orbit_period(sat)
    dates, shadow = [], []

    for first_day in range(0, 365, 30):                  # 0, 30, 60 ... one batch per 30 days
        n_days = min(30, 365 - first_day)                # the last batch is shorter
        d0 = start + timedelta(days=first_day)
        times = ts.utc(d0.year, d0.month, d0.day, 0, range(n_days * 1440))   # every minute of the batch
        sunlit = np.array(sat.at(times).is_sunlit(eph)).reshape(n_days, 1440)  # one row per day

        for k in range(n_days):
            dates.append(d0 + timedelta(days=k))
            shadow.append(float((1440 - np.count_nonzero(sunlit[k])) / orbits_per_day))

    return dates, shadow


def shadow_seasons(dates, values):
    """Find each stretch of days in a row that have some shadow."""
    runs, run_start, prev = [], None, None
    for d, v in zip(dates, values):
        if v > 0 and run_start is None:
            run_start = d
        if v == 0 and run_start is not None:
            runs.append((run_start, prev))
            run_start = None
        prev = d
    if run_start is not None:
        runs.append((run_start, prev))
    return runs


# ---------- Graph style (dark, to match the website) ----------
BG = '#0b0f1a'
RC = {'figure.facecolor': BG, 'axes.facecolor': '#121829', 'axes.edgecolor': '#2a3350',
      'axes.labelcolor': '#c9d1e0', 'xtick.color': '#c9d1e0', 'ytick.color': '#c9d1e0',
      'text.color': '#ffffff', 'grid.color': '#2a3350', 'legend.facecolor': '#121829',
      'legend.edgecolor': '#2a3350', 'font.size': 11}
ISS_COLOUR, SAT_COLOUR = '#ff9f43', '#a78bfa'


def draw_day_chart(iss, sat, iss_sun, sat_sun, hours, iss_tilt, sat_tilt, label_date):
    with plt.rc_context(RC):
        fig, axes = plt.subplots(2, 1, figsize=(12, 5.2), sharex=True)
        rows = [(axes[0], iss_sun, f'{iss.name} ({iss_tilt:.1f}° tilt)', ISS_COLOUR),
                (axes[1], sat_sun, f'{sat.name} ({sat_tilt:.1f}° tilt)', SAT_COLOUR)]
        for ax, sunlit, title, colour in rows:
            ax.step(hours, sunlit.astype(int), where='post', color=colour, linewidth=1.6)
            ax.fill_between(hours, 0, sunlit.astype(int), step='post', color=colour, alpha=0.18)
            ax.set_title(title, loc='left')
            ax.set_xlim(0, 24)
            ax.set_xticks(range(0, 25))
            ax.tick_params(labelbottom=True)
            ax.set_ylim(-0.2, 1.2)
            ax.set_yticks([0, 1])
            ax.set_yticklabels(['Shadow', 'Sunlight'])
            ax.grid(True, alpha=0.6)
        axes[1].set_xlabel('Time (hours, UTC)')
        fig.suptitle(f'Sunlight vs Earth shadow over one day: {label_date}')
        plt.tight_layout()
    return fig


def draw_year_chart(iss, sat, iss_dates, iss_year, sat_dates, sat_year, iss_tilt, sat_tilt, start, end):
    with plt.rc_context(RC):
        fig = plt.figure(figsize=(12, 5.2))
        plt.plot(iss_dates, iss_year, color=ISS_COLOUR, linewidth=1.5, label=f'{iss.name} ({iss_tilt:.1f}° tilt)')
        plt.plot(sat_dates, sat_year, color=SAT_COLOUR, linewidth=2.6, label=f'{sat.name} ({sat_tilt:.1f}° tilt)')
        ax = plt.gca()
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%b'))
        plt.xticks(rotation=45)
        plt.xlabel('Date')
        plt.ylabel('Minutes in Earth shadow per orbit')
        plt.title(f'Minutes in Earth shadow per orbit ({start:%b %Y} – {end:%b %Y})')
        plt.ylim(0, max(40, max(iss_year + sat_year) + 5))   # taller if a satellite has long eclipses
        plt.grid(True, alpha=0.6)
        plt.legend()
        plt.tight_layout()
    return fig


# ---------- Show the full results for one satellite ----------
def show_results(catnr, chosen):
    iss = get_satellite(ISS_NUMBER)
    sat = get_satellite(catnr)
    if sat is None:
        st.error('Satellite not found. Check the NORAD catalog number and try again.')
        return
    if iss is None:
        st.error('Could not download ISS data right now. Please try again in a minute.')
        return

    iss_tilt = math.degrees(iss.model.inclo)
    sat_tilt = math.degrees(sat.model.inclo)
    day_iso = chosen.isoformat()

    with st.spinner(f'Calculating a year of sunlight and shadow for {sat.name} and the ISS. '
                    f'This may take a few minutes...'):
        period, shadow, pct = check_orbit(sat, chosen)
        iss_period, iss_shadow, iss_pct = check_orbit(iss, chosen)
        hours, sat_sun = day_series(catnr, day_iso)
        _, iss_sun = day_series(ISS_NUMBER, day_iso)
        sat_dates, sat_year = year_series(catnr, day_iso)
        iss_dates, iss_year = year_series(ISS_NUMBER, day_iso)

    free_days = sum(1 for v in sat_year if v == 0)
    peak = max(sat_year)
    peak_date = sat_dates[sat_year.index(peak)]
    end = chosen + timedelta(days=364)

    html(f'<h3 style="margin-top:30px;">Results for {sat.name}</h3>'
         f'<p class="muted">Tilt {sat_tilt:.1f}° · one orbit takes {period:.1f} minutes · '
         f'compared with the ISS ({iss_tilt:.1f}° tilt) · orbit data from {sat.epoch.utc_strftime("%d %b %Y")}</p>')

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Shadow on one orbit', f'{shadow} min', delta=f'{shadow - iss_shadow:+d} min vs ISS', delta_color='inverse')
    c2.metric('Share of orbit in shadow', f'{pct:.1f}%', delta=f'{pct - iss_pct:+.1f} pts vs ISS', delta_color='inverse')
    c3.metric('Days with no shadow (next year)', f'{free_days} / 365')
    c4.metric('Longest shadow per orbit', f'{peak:.1f} min', help=f'On {peak_date:%d %b %Y}')

    st.pyplot(draw_day_chart(iss, sat, iss_sun, sat_sun, hours, iss_tilt, sat_tilt, chosen.strftime('%d %B %Y')))
    st.pyplot(draw_year_chart(iss, sat, iss_dates, iss_year, sat_dates, sat_year, iss_tilt, sat_tilt, chosen, end))

    seasons = shadow_seasons(sat_dates, sat_year)
    if free_days == 365:
        st.success(f'{sat.name} never enters Earth\'s shadow in this year: sunlight on every orbit.')
    elif len(seasons) <= 4:
        lines = '  \n'.join(f'• {a:%d %b %Y} to {b:%d %b %Y}' for a, b in seasons)
        st.info(f'**{sat.name} eclipse seasons** (days with any shadow):  \n{lines}  \n'
                f'**Peak:** {peak:.1f} min per orbit on {peak_date:%d %b %Y}')
    else:
        st.info(f'{sat.name} is in shadow on **{365 - free_days} of 365 days**. '
                f'Peak: **{peak:.1f} min per orbit** on {peak_date:%d %b %Y}.')


# ---------- Card picture (photo if you've added one, otherwise a drawn icon) ----------
def card_image(path):
    if os.path.exists(path):
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode()
        kind = 'png' if path.lower().endswith('.png') else 'jpeg'
        return f'<img class="card-img" src="data:image/{kind};base64,{data}">'
    return ('<div class="card-ph"><svg viewBox="0 0 120 70" width="62%">'
            '<rect x="8" y="27" width="36" height="16" rx="2" fill="#4ea8ff" opacity="0.85"/>'
            '<rect x="76" y="27" width="36" height="16" rx="2" fill="#4ea8ff" opacity="0.85"/>'
            '<rect x="48" y="22" width="24" height="26" rx="3" fill="#ffd166"/>'
            '<line x1="44" y1="35" x2="48" y2="35" stroke="#cfd6e6" stroke-width="2"/>'
            '<line x1="72" y1="35" x2="76" y2="35" stroke="#cfd6e6" stroke-width="2"/>'
            '<line x1="60" y1="22" x2="60" y2="10" stroke="#cfd6e6" stroke-width="2"/>'
            '<circle cx="60" cy="9" r="3" fill="#cfd6e6"/></svg></div>')

def pick(catnr):
    """Remember which satellite was picked, and that the page should scroll to the results."""
    st.session_state['selected'] = catnr
    st.session_state['scroll_now'] = True
    st.session_state['scroll_count'] = st.session_state.get('scroll_count', 0) + 1

# =====================================================================
# HOME
# =====================================================================
html('<div id="home" class="anchor"></div>')
left, right = st.columns([1.05, 1])
with left:
    html("""
    <div class="hero-title">Does your satellite live in <span>sunlight</span> or shadow?</div>
    <p class="hero-sub">Every orbit, most satellites pass through Earth's shadow, where their solar panels get no light.
    This tracker uses real orbit data to show how long any satellite spends in darkness, and why some orbits
    stay in sunlight almost all year. That matters for one big idea: putting data centers in space.</p>
    <a class="btn" href="#tracker">Try the Orbit Tracker</a>
    <a class="btn btn-outline" href="#about">Learn more</a>
    """)
with right:
    html("""
    <svg viewBox="0 0 600 420" width="100%" xmlns="http://www.w3.org/2000/svg" style="border-radius:18px;">
    <defs>
    <radialGradient id="sunglow" cx="0" cy="0.5" r="0.75"><stop offset="0" stop-color="#ffd166" stop-opacity="0.85"/><stop offset="1" stop-color="#ffd166" stop-opacity="0"/></radialGradient>
    <linearGradient id="earthfill" x1="0" x2="1"><stop offset="0" stop-color="#5fb4ff"/><stop offset="0.48" stop-color="#1f62ad"/><stop offset="0.52" stop-color="#0b2142"/><stop offset="1" stop-color="#050c1a"/></linearGradient>
    <linearGradient id="shadowfill" x1="0" x2="1"><stop offset="0" stop-color="#000000" stop-opacity="0.6"/><stop offset="1" stop-color="#000000" stop-opacity="0"/></linearGradient>
    </defs>
    <rect width="600" height="420" fill="#070a14"/>
    <g fill="#ffffff" opacity="0.7"><circle cx="420" cy="40" r="1.2"/><circle cx="520" cy="80" r="1"/><circle cx="560" cy="340" r="1.3"/>
    <circle cx="300" cy="30" r="0.9"/><circle cx="470" cy="380" r="1"/><circle cx="380" cy="360" r="0.8"/><circle cx="250" cy="390" r="1.1"/>
    <circle cx="580" cy="200" r="0.9"/><circle cx="350" cy="70" r="1"/></g>
    <rect x="0" y="0" width="300" height="420" fill="url(#sunglow)"/>
    <g stroke="#ffd166" stroke-opacity="0.35" stroke-width="1.5"><line x1="20" y1="130" x2="210" y2="130"/>
    <line x1="20" y1="170" x2="215" y2="170"/><line x1="20" y1="210" x2="215" y2="210"/>
    <line x1="20" y1="250" x2="215" y2="250"/><line x1="20" y1="290" x2="210" y2="290"/></g>
    <rect x="330" y="120" width="270" height="180" fill="url(#shadowfill)"/>
    <ellipse cx="330" cy="210" rx="170" ry="52" fill="none" stroke="#8fa3c7" stroke-opacity="0.45" stroke-dasharray="4 6" transform="rotate(-12 330 210)"/>
    <circle cx="330" cy="210" r="94" fill="none" stroke="#5fb4ff" stroke-opacity="0.3" stroke-width="4"/>
    <circle cx="330" cy="210" r="90" fill="url(#earthfill)"/>
    <path d="M 160 210 A 170 52 0 0 0 500 210" fill="none" stroke="#cfd6e6" stroke-opacity="0.85" stroke-width="1.6" transform="rotate(-12 330 210)"/>
    <g transform="translate(210 270)"><rect x="-16" y="-4" width="10" height="8" fill="#4ea8ff"/><rect x="6" y="-4" width="10" height="8" fill="#4ea8ff"/><rect x="-6" y="-6" width="12" height="12" rx="2" fill="#ffd166"/></g>
    <g transform="translate(490 194)" opacity="0.45"><rect x="-16" y="-4" width="10" height="8" fill="#6b7a99"/><rect x="6" y="-4" width="10" height="8" fill="#6b7a99"/><rect x="-6" y="-6" width="12" height="12" rx="2" fill="#8a94a8"/></g>
    <text x="36" y="70" fill="#ffd166" font-family="Space Grotesk, sans-serif" font-size="16" letter-spacing="3">SUNLIGHT</text>
    <text x="420" y="104" fill="#8fa3c7" font-family="Space Grotesk, sans-serif" font-size="14" letter-spacing="2">EARTH'S SHADOW</text>
    <text x="150" y="305" fill="#cfd6e6" font-family="Inter, sans-serif" font-size="13">In sunlight</text>
    <text x="455" y="228" fill="#8fa3c7" font-family="Inter, sans-serif" font-size="13">In shadow</text>
    </svg>
    """)

# =====================================================================
# ABOUT  (rewrite these paragraphs in your own words)
# =====================================================================
html('<div id="about" class="anchor"></div><div class="section-label">About</div>'
     '<div class="section-title">Why sunlight and shadow matter</div>')
a1, a2, a3 = st.columns(3)
with a1:
    html("""<div class="info-card"><h4>The big idea</h4><p>AI data centers use huge amounts of electricity and water.
    One proposed solution is to put them in orbit, powered by solar panels. But solar panels only work in sunlight,
    and most satellites pass through Earth's shadow on every orbit.</p></div>""")
with a2:
    html("""<div class="info-card"><h4>The question</h4><p>Companies plan to use dawn-dusk Sun-synchronous orbits,
    which ride along the line between day and night and are said to stay in sunlight for "most, or potentially all"
    of their orbit. This project tests that claim with real satellite data.</p></div>""")
with a3:
    html("""<div class="info-card"><h4>How it works</h4><p>The tracker downloads each satellite's latest orbit data
    (a TLE) from CelesTrak, predicts its position every minute with the SGP4 model in the Skyfield library,
    and checks whether Earth blocks the Sun. Counting the minutes gives the time spent in shadow.</p></div>""")

# =====================================================================
# ORBIT TRACKER
# =====================================================================
html('<div id="tracker" class="anchor"></div><div class="section-label">Orbit Tracker</div>'
     '<div class="section-title">Pick a satellite</div>'
     '<p class="muted">Click Check on any satellite to see how much of its time it spends in Earth\'s shadow, compared with the ISS.</p>')

chosen = st.date_input('Date to check (one day, and the year that follows)', value=date.today())

for row in (SATELLITES[:5], SATELLITES[5:]):
    cols = st.columns(5)
    for col, s in zip(cols, row):
        with col:
            with st.container(border=True):
                html(card_image(s['img']))
                html(f'<p style="margin:10px 0 0;"><b>{s["name"]}</b><br><span class="muted">{s["blurb"]}</span></p>')
                if st.button('Check', key=f'btn_{s["catnr"]}'):
                    pick(s['catnr'])

html('<p class="muted" style="margin-top:18px;">Or check any satellite by its NORAD catalog number:</p>')
n1, n2 = st.columns([3, 1])
with n1:
    typed = st.text_input('NORAD catalog number', placeholder='e.g. 62261', label_visibility='collapsed')
with n2:
    if st.button('Check this number'):
        if typed.strip().isdigit():
            pick(int(typed.strip()))
        else:
            st.warning('Please type numbers only.')

if 'selected' in st.session_state:
    html('<div id="results" class="anchor"></div>')     

    if st.session_state.get('scroll_now'):
        components.html(f"""
        <script>
        // click number {st.session_state['scroll_count']} (makes this script new each time, so it runs again)
        window.parent.document.getElementById('results').scrollIntoView({{behavior: 'smooth'}});
        </script>
        """, height=0)
        st.session_state['scroll_now'] = False          

    show_results(st.session_state['selected'], chosen)

# =====================================================================
# FOOTER
# =====================================================================
html("""
<div class="footer">
<div style="margin-bottom:14px;"><a href="#home">Home</a><a href="#about">About</a><a href="#tracker">Orbit Tracker</a></div>
<div>Orbit data: CelesTrak · Calculations: Skyfield (SGP4) · Sun position: NASA JPL DE421 ephemeris</div>
<div style="margin-top:6px;">Built by Vivaan Gupta</div>
</div>
""")
