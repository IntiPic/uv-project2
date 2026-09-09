#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 13:48:26 2026

@author: inti
"""

import pvlib as pv
import pandas as pd


def add_usa_clearsky(df, station):
    """Add zenith SZA, Ineichen GHI and clear-sky flags at native cadence.

    Requires regular UTC observations and GHI in W/m². Uses Reno–Hansen
    defaults at 1 minute, Jordan–Hansen inferred limits at 5 minutes. No input columns
    are modified; only GHI=-9999.9 is masked in the detection input.
    """
    if not isinstance(df.index, pd.DatetimeIndex) or str(df.index.tz) != "UTC":
        raise ValueError("USA clear-sky: index must be timezone-aware in UTC")
    if df.index.hasnans or not df.index.is_unique or not df.index.is_monotonic_increasing:
        raise ValueError("USA clear-sky: timestamps must be valid, unique and ordered")
    if len(df) < 2:
        raise ValueError("USA clear-sky: insufficient samples to determine cadence")
    steps = df.index[1:] - df.index[:-1]
    infer_limits = bool((steps == pd.Timedelta(minutes=5)).all())
    if not infer_limits and not (steps == pd.Timedelta(minutes=1)).all():
        raise ValueError("USA clear-sky: requires regular 1- or 5-minute samples; no gap filling is applied")
    if len(df) < (12 if infer_limits else 10):
        raise ValueError("USA clear-sky: insufficient samples for the detection window")
    if "GHI" not in df.columns:
        raise ValueError("USA clear-sky: missing GHI column (expected W/m²)")
    if any(column in df.columns for column in ("sza", "ghi_clear", "clear_sky")):
        raise ValueError("USA clear-sky: output columns already exist")
    solar = pv.solarposition.get_solarposition(
        time=df.index, latitude=station["lat"], longitude=station["lon"],
        altitude=station["elevation"])
    location = pv.location.Location(station["lat"], station["lon"],
                                    tz="UTC", altitude=station["elevation"])
    reference = location.get_clearsky(df.index, model="ineichen", solar_position=solar)
    measured = df["GHI"].mask(df["GHI"].eq(-9999.9))
    result = df.copy()
    result["sza"] = solar["zenith"]
    result["ghi_clear"] = reference["ghi"]
    result["clear_sky"] = pv.clearsky.detect_clearsky(
        measured, reference["ghi"], times=df.index, infer_limits=infer_limits,
        window_length=10, mean_diff=75, max_diff=75,
        lower_line_length=-5, upper_line_length=10,
        var_diff=0.005, slope_dev=8, max_iterations=20, return_components=False)
    return result

def detect_clearsky(df_cams, df_rad):
    
    # Intersecto indices por las dudass
    idx = df_cams.index.intersection(df_rad.index)
    df_cams = df_cams.loc[idx]
    df_rad = df_rad.loc[idx]
    
    GHI_csk_cams = df_cams['Clear sky GHI'] * 60

    msk_csk = pv.clearsky.detect_clearsky(
        df_rad.ghi,
        GHI_csk_cams
    )

    msk_dia = (df_cams.sza > 0) & (df_cams.sza < 80)

    return msk_csk & msk_dia


def resample_csk(mask_1min, tol=0.8, min_fraction_data=1.0):
    """Los datos de chile son con cadencia 5-min mientras que la máscara de
    cielo claro es minutal. Esto crea la máscara a nivel 5-min con tolerancia
    dada por tol (0.8 = 80% de los minutos deben ser claros para que el intervalo
    5-min sea claro).    
    """
    
    grouped = mask_1min.resample("5min")

    fraction_clear = grouped.mean()
    fraction_data = grouped.count() / 5

    mask_5min = (
        (fraction_clear >= tol)
        & (fraction_data >= min_fraction_data)
    )

    return mask_5min
