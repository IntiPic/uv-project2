#!/usr/bin/env python3
"""Visual check of native ABQ f01 and BON f05 observations; no validation statistics."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from config import STATIONS_USA
from src.measurements import load_usa_uv, clean_usa_uv
from src.clearsky import add_usa_clearsky


def plot_station(station_id):
    root = Path(__file__).resolve().parent
    df, resolution = load_usa_uv(station_id, root / 'data/USA/OUT')
    df = clean_usa_uv(df, resolution).loc['2021-06-01':'2021-06-03']
    result = add_usa_clearsky(df, STATIONS_USA[station_id])
    fig, ax = plt.subplots(figsize=(12, 4))
    observed = result.GHI.mask(result.GHI.eq(-9999.9))
    ax.plot(result.index, observed, label='GHI observada', linewidth=0.7)
    ax.plot(result.index, result.ghi_clear, label='GHI Ineichen', linewidth=1)
    mask = result.clear_sky
    ax.scatter(result.index[mask], observed[mask], s=5, color='green', label=('Reno–Hansen' if resolution == 'f01' else 'Jordan–Hansen') + ': clear-sky')
    ax.set(title=f'{station_id} — 1–3 junio 2021 — {resolution}', xlabel='Fecha y hora UTC', ylabel='GHI [W/m²]')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M', tz=result.index.tz))
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    output = root / f'out/fig/usa_clearsky_{station_id}_20210601_20210603.png'
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    print(output)


if __name__ == '__main__':
    for station_id in ('ABQ', 'BON'):
        plot_station(station_id)
