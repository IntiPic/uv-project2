#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 13:48:26 2026

@author: inti
"""

import pvlib as pv

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