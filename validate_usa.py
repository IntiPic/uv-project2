#!/usr/bin/env python3
"""First USA validation: provisional YES UVB-1 spectral approximation."""
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from config import STATIONS_USA
from src.measurements import load_usa_uv, clean_usa_uv, regularize_usa_uv, match_usa_uv_merra
from src.clearsky import add_usa_clearsky
from src.merra import process_merra
from src import lut
from src.validation import validation_metrics

station_id = "DRA"
start = "2021-01-01"
end = "2021-12-31"


def main():
    root = Path(__file__).resolve().parent
    station = STATIONS_USA[station_id]
    df_uv, resolution = load_usa_uv(station_id, root / 'data/USA/OUT')
    df_uv = clean_usa_uv(df_uv, resolution).loc[start:end]
    df_uv = regularize_usa_uv(df_uv, resolution)
    df_uv = add_usa_clearsky(df_uv, station)
    df_merra = process_merra(station, start, end).tz_convert('UTC')
    matched = match_usa_uv_merra(df_uv, df_merra)

    # Same mW -> W convention as load_lut_spectral, selecting wavelengths
    # first to avoid materializing the entire 250–3000 nm spectral LUT.
    with xr.open_dataset(root / 'data/lut/LUT_espectral_v2.nc') as source:
        spectral = source.sel(wavelength=slice(280, 320)).copy()
        spectral['ghi_spectral'] = spectral['ghi_spectral'] / 1000.0
        # Provisional YES UVB-1 ≈ McKinlay–Diffey erythemal integral 280–320 nm.
        # Exact instrument spectral response remains pending.
        integrated = lut.integrate_lut(spectral, wavelength_min=280,
                                       wavelength_max=320, erythemal=True)
        interpolator = lut.build_uv_interpolator2(integrated)

    variables = ['o3', 'aod', 'wv', 'alpha', 'sza']
    valid = matched.clear_sky & np.isfinite(matched.UVB)
    valid &= np.isfinite(matched[variables]).all(axis=1)
    for dimension, grid in zip(['alt', *variables], interpolator.grid):
        values = station['elevation'] / 1000. if dimension == 'alt' else matched[dimension]
        valid &= (values >= grid.min()) & (values <= grid.max())
    matched['uve_model'] = np.nan
    if valid.any():
        matched.loc[valid, 'uve_model'] = lut.apply_interpolator(
            interpolator, matched.loc[valid], station, atm_source='merra')
    valid &= np.isfinite(matched.uve_model)
    paired = matched.loc[valid, ['UVB', 'uve_model']]
    centers = paired.index.floor('h') + pd.Timedelta(minutes=30)
    hourly = paired.groupby(centers).agg(
        UVB_obs=('UVB', 'mean'), UVE_model=('uve_model', 'mean'),
        n_samples=('UVB', 'size'))
    hourly.index.name = 'Date'
    if hourly.empty:
        raise RuntimeError('No valid paired hours inside the LUT domain')
    metrics = validation_metrics(hourly.UVE_model, hourly.UVB_obs)
    output = root / 'out/validation/usa' / station_id
    output.mkdir(parents=True, exist_ok=True)
    prefix = f'{station_id}_{start}_{end}'
    hourly.to_csv(output / f'{prefix}_hourly.csv')
    metrics.to_csv(output / f'{prefix}_metrics.csv', index=False)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(hourly.UVB_obs, hourly.UVE_model, s=15, alpha=0.6)
    upper = max(hourly.UVB_obs.max(), hourly.UVE_model.max())
    ax.plot([0, upper], [0, upper], color='black', linestyle='--', label='1:1')
    ax.set(xlabel='UVB observada [W/m²]', ylabel='UVE modelo [W/m²]',
           title=f'{station_id} — {start} a {end}\nYES UVB-1: aproximación provisional 280–320 nm')
    ax.legend()
    ax.grid()
    fig.tight_layout()
    fig.savefig(output / f'{prefix}_scatter.png', dpi=150)
    # plt.close(fig)
    print(f'{station_id} ({resolution}): {len(hourly)} horas válidas')
    print(metrics.to_string(index=False))
    print(f'Resultados: {output}')
    return hourly, metrics


if __name__ == '__main__':
    main()
