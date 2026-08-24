#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 13:18:28 2026

@author: inti
"""

import pandas as pd
import numpy as np
from pathlib import Path
from scipy.interpolate import RegularGridInterpolator


def load_lut(path):
    file_str = 'LUT_table.csv'
    file_lut = Path(path / file_str)
    df_lut = pd.read_csv(file_lut, index_col=0)
    return df_lut

def build_uv_interpolator(df_lut,variable_uv):
    
    columnas_atm = ["alt", "o3", "aod", "wv", "alpha", "sza"]
    lut = (
        df_lut
        .set_index(columnas_atm)
        .sort_index()
    )

    alt_grid = np.sort(df_lut["alt"].unique())
    o3_grid = np.sort(df_lut["o3"].unique())
    aod_grid = np.sort(df_lut["aod"].unique())
    wv_grid = np.sort(df_lut["wv"].unique())
    alpha_grid = np.sort(df_lut["alpha"].unique())
    sza_grid = np.sort(df_lut["sza"].unique())
    
    uv_grid = (
        lut[variable_uv]
        .values
        .reshape(
            len(alt_grid),
            len(o3_grid),
            len(aod_grid),
            len(wv_grid),
            len(alpha_grid),
            len(sza_grid)
        )
    )

    interp_uv = RegularGridInterpolator(
        (
            alt_grid,
            o3_grid,
            aod_grid,
            wv_grid,
            alpha_grid,
            sza_grid
        ),
        uv_grid,
        bounds_error=False,
        fill_value=np.nan
    )
    return interp_uv
    

def apply_interpolator(interp_uv,df_cams,station):
    X_cams = np.column_stack([
        np.full(len(df_cams), station["elevation"]/1000), #Ojo con elevation en km!!
        df_cams["tco3"],
        df_cams["aod550"],
        df_cams["tcwv"],
        np.full(len(df_cams), 1.0),  # alpha fijo
        df_cams["sza"]
    ])

    uv_lut = interp_uv(X_cams)
    return uv_lut
    
    
    