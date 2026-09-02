#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 13:18:28 2026

@author: inti
"""

import pandas as pd
import numpy as np
import xarray as xr
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
    

def apply_interpolator(interp_uv,df_cams,station,atm_source="cams"):
    if atm_source == 'cams':
        X_cams = np.column_stack([
            np.full(len(df_cams), station["elevation"]/1000), #Ojo con elevation en km!!
            df_cams["tco3"],
            df_cams["aod550"],
            df_cams["tcwv"],
            np.full(len(df_cams), 1.0),  # alpha fijo
            df_cams["sza"]
        ])
    elif atm_source == 'merra':
        X_cams = np.column_stack([
            np.full(len(df_cams), station["elevation"]/1000), #Ojo con elevation en km!!
            df_cams["o3"],
            df_cams["aod"],
            df_cams["wv"],
            df_cams["alpha"],  # Merra tiene alpha!
            df_cams["sza"]
        ])
    uv_lut = interp_uv(X_cams)
    return uv_lut
    
    
def load_lut_spectral(path):
    ds = xr.open_dataset(path / "LUT_espectral_v2.nc")
    ds['ghi_spectral'] = ds['ghi_spectral'] / 1000.0 # Convertir de mW a W (ver Kurudz!!)
    
    return ds

def erythemal_action_spectrum(wavelength):
    """
    CIE erythema action spectrum according to
    McKinlay & Diffey (1987).

    Parameters
    ----------
    wavelength : array-like
        Wavelength in nm.

    Returns
    -------
    np.ndarray
        Relative erythemal effectiveness.
    """

    wavelength = np.asarray(wavelength, dtype=float)

    action = np.zeros_like(wavelength)

    mask1 = (wavelength >= 250) & (wavelength <= 298)
    mask2 = (wavelength > 298) & (wavelength <= 328)
    mask3 = (wavelength > 328) & (wavelength <= 400)

    action[mask1] = 1.0
    action[mask2] = 10 ** (0.094 * (298 - wavelength[mask2]))
    action[mask3] = 10 ** (0.015 * (139 - wavelength[mask3]))

    return action

def integrate_lut(ds,wavelength_min,wavelength_max,erythemal=False):

    ds_uv = ds.sel(
        wavelength=slice(wavelength_min, wavelength_max)
    )

    spectral = ds_uv["ghi_spectral"]

    if erythemal:

        wavelength = ds_uv["wavelength"].values

        action = erythemal_action_spectrum(wavelength)

        spectral = spectral * xr.DataArray(
            action,
            dims=["wavelength"],
            coords={"wavelength": wavelength}
        )

    lut_integrated = spectral.integrate("wavelength")

    return lut_integrated


def build_uv_interpolator2(lut_integrated):

    columnas_atm = ["alt", "o3", "aod", "wv", "alpha", "sza"]
    
    lut_integrated = lut_integrated.transpose(*columnas_atm)

    grids = tuple(
        lut_integrated[dim].values
        for dim in columnas_atm
    )

    uv_grid = lut_integrated.values

    interp_uv = RegularGridInterpolator(
        grids,
        uv_grid,
        bounds_error=False,
        fill_value=np.nan
    )

    return interp_uv