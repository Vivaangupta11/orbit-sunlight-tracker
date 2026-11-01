# app.py — Sunlight-or-Shadow Orbit Tracker (web version)

import math
from datetime import date, timedelta

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import streamlit as st
from skyfield.api import load

# ---------- Page heading ----------
st.set_page_config(page_title='Orbit Sunlight Tracker', layout='wide')
st.title('Sunlight-or-Shadow Orbit Tracker')
st.write("Enter a satellite's NORAD catalog number to see how much time it spends "
         "in Earth's shadow, compared with the International Space Station.")

# ---------- Setup (cached so it only loads once, not every click) ----------
@st.cache_resource
def load_basics():
    ts = load.timescale()
    eph = load('de421.bsp')   # positions of the Sun and planets
    return ts, eph

ts, eph = load_basics()

def load_satellite_by_number(catnr):
    url = f'https://celestrak.org/NORAD/elements/gp.php?CATNR={catnr}&FORMAT=tle'
    sats = load.tle_file(url, filename=f'sat_{catnr}.tle', reload=True)
    if len(sats) == 0:
        return None
    return sats[0]

# ---------- Your functions (same maths as before) ----------
def check_orbit(satellite, year, month, day):
    """Check one orbit and return a summary line."""
    period = 2 * math.pi / satellite.model.no_kozai
    total = round(period)
    times = ts.utc(year, month, day, 0, range(total))
    sunlit = satellite.at(times).is_sunlit(eph)
    sunlit_mins = sum(sunlit)
    shadow_mins = total - sunlit_mins
    shadow_percent = (shadow_mins / total) * 100
    return (f'**{satellite.name}**: period {period:.1f} min | sunlit {sunlit_mins} min | '
            f'shadow {shadow_mins} min | {shadow_percent:.1f}% in shadow')

def day_timeline(satellite, year, month, day):
    """Check sunlight once per minute for a whole day."""
    minutes_in_day = 1440
    times = ts.utc(year, month, day, 0, range(minutes_in_day))
    sunlit = satellite.at(times).is_sunlit(eph)
    hours = np.arange(minutes_in_day) / 60
    return hours, sunlit

def draw_line(ax, hours, sunlit, title, colour):
    """Draw one satellite's day as a line: up = sunlight, down = shadow."""
    ax.step(hours, sunlit.astype(int), where='post', color=colour, linewidth=1.5)
    ax.set_title(title)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25))
    ax.tick_params(labelbottom=True)
    ax.set_ylim(-0.2, 1.2)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(['Shadow', 'Sunlight'])
    ax.grid(True, alpha=0.3)

def shadow_per_orbit_over_year(satellite, start_date, number_of_days):
    """For each day, work out the average minutes in shadow per orbit."""
    period = 2 * math.pi / satellite.model.no_kozai
    orbits_per_day = 1440 / period
    dates = []
    shadow_per_orbit = []
    for i in range(number_of_days):
        d = start_date + timedelta(days=i)
        hours, sunlit = day_timeline(satellite, d.year, d.month, d.day)
        shadow_today = len(sunlit) - sum(sunlit)
        dates.append(d)
        shadow_per_orbit.append(shadow_today / orbits_per_day)
    return dates, shadow_per_orbit

# ---------- What the visitor sees and types ----------
catnr = st.text_input('NORAD catalog number', value='62261',
                      help='Examples: 62261 = Sentinel-1C, 39634 = Sentinel-1A, 20580 = Hubble')
chosen_date = st.date_input('Date', value=date.today())

if st.button('Run'):
    iss = load_satellite_by_number(25544)
    sat = load_satellite_by_number(catnr.strip())

    if sat is None:
        st.error('Satellite not found. Check the catalog number and try again.')
        st.stop()

    iss_tilt = math.degrees(iss.model.inclo)
    sat_tilt = math.degrees(sat.model.inclo)
    year, month, day = chosen_date.year, chosen_date.month, chosen_date.day
    date_label = chosen_date.strftime('%d %B %Y')

    # --- One-orbit summary ---
    st.subheader(f'One orbit starting 00:00 UTC on {date_label}')
    st.markdown(check_orbit(iss, year, month, day))
    st.markdown(check_orbit(sat, year, month, day))

    # --- Day graph ---
    st.subheader('Sunlight and shadow over one day')
    iss_hours, iss_sunlit = day_timeline(iss, year, month, day)
    sat_hours, sat_sunlit = day_timeline(sat, year, month, day)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 5), sharex=True)
    draw_line(ax1, iss_hours, iss_sunlit, f'{iss.name} ({iss_tilt:.1f}° tilt)', 'tab:orange')
    draw_line(ax2, sat_hours, sat_sunlit, f'{sat.name} ({sat_tilt:.1f}° tilt)', 'tab:purple')
    ax2.set_xlabel('Time (hours, UTC)')
    fig.suptitle(f'Sunlight vs Earth shadow over one day: {date_label}')
    plt.tight_layout()
    st.pyplot(fig)

    # --- Year chart ---
    st.subheader('Minutes in shadow per orbit over one year')
    with st.spinner('Checking 365 days for both satellites... this takes about a minute'):
        iss_dates, iss_shadow = shadow_per_orbit_over_year(iss, chosen_date, 365)
        sat_dates, sat_shadow = shadow_per_orbit_over_year(sat, chosen_date, 365)

    end_date = chosen_date + timedelta(days=364)
    fig = plt.figure(figsize=(12, 5))
    plt.plot(iss_dates, iss_shadow, color='tab:orange', label=f'{iss.name} ({iss_tilt:.1f}° tilt)')
    plt.plot(sat_dates, sat_shadow, color='tab:purple', linewidth=2.5, label=f'{sat.name} ({sat_tilt:.1f}° tilt)')
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%b'))
    plt.xticks(rotation=45)
    plt.xlabel('Date')
    plt.ylabel('Minutes in Earth shadow per orbit')
    plt.title(f'Minutes in Earth shadow per orbit ({chosen_date:%b %Y} – {end_date:%b %Y})')
    plt.ylim(0, 40)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    st.pyplot(fig)

    # --- Eclipse season ---
    first_eclipse = None
    last_eclipse = None
    for i in range(len(sat_shadow)):
        if sat_shadow[i] > 0:
            if first_eclipse is None:
                first_eclipse = sat_dates[i]
            last_eclipse = sat_dates[i]
    peak = max(sat_shadow)
    peak_date = sat_dates[sat_shadow.index(peak)]

    if first_eclipse is None:
        st.success(f'{sat.name} never enters Earth\'s shadow in this year.')
    else:
        st.info(f'**{sat.name} eclipse season:** {first_eclipse} to {last_eclipse}  \n'
                f'**Peak:** {peak:.1f} min per orbit on {peak_date}')
