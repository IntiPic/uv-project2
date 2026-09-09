#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 11:11:08 2026

@author: inti
"""

from config import STATIONS, STATIONS_USA
from src.cams import load_cams
from src.clearsky import detect_clearsky
from src.validation import validation_metrics, msk_not_nan
from src.plotting import plot_validation, plot_atmospheric_vars
import src.measurements as ms
import src.merra as mr
import src.lut as lt
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

#%% TEST MERRA-2
# station = STATIONS["IZA"]

# cwd = Path.cwd()

# station_id = "BRW"
# station = STATIONS_USA[station_id]
# start = "2024-01-01"
# end = "2024-01-02"

# df = mr.process_merra(station, start, end)

# carpeta = (
#     Path(cwd)
#     / "data/processed/merra"
#     / station_id
# )
# carpeta.mkdir(parents=True, exist_ok=True)

# archivo = carpeta / f"{station_id}_MERRA_{start}_{end}.csv"
# df.to_csv(archivo)
# print(archivo)

#%%
def main():

    # Configuration
    station_label = "IZA"
    station = STATIONS[station_label]
    
    cwd = Path.cwd()
    ruta_cams = Path(cwd / 'data' / 'raw' / 'cams')
    ruta_merra = Path(cwd / 'data' / 'raw' / 'merra')
    ruta_uv = Path(cwd / 'data' / 'raw' / 'uv')
    ruta_rad = Path(cwd / 'data' / 'raw' / 'rad')
    ruta_lut = Path(cwd / 'data' / 'lut')
    ruta_fig =  Path(cwd / 'out' / 'fig')
    
    # --------------------------------------------------
    # Load data
    # --------------------------------------------------
    
    df_cams = load_cams(station, ruta_cams)
    df_merra = mr.load_merra(station, ruta_merra)
    
    df_uv = ms.load_bsrn_uv(station, ruta_uv)
    df_rad = ms.load_bsrn_rad(station, ruta_rad)
    
    
    # --------------------------------------------------
    # Align datasets temporally
    # --------------------------------------------------
    
    idx = (
        df_cams.index
        .intersection(df_merra.index)
        .intersection(df_uv.index)
        .intersection(df_rad.index)
    )
    
    df_cams = df_cams.loc[idx]
    df_merra = df_merra.loc[idx]
    df_uv = df_uv.loc[idx]
    df_rad = df_rad.loc[idx]
    
    
    # --------------------------------------------------
    # LUT
    # --------------------------------------------------
    
    ds_lut = lt.load_lut_spectral(ruta_lut)
    
    
    # UVA: 320–400 nm, sin weighting eritemático
    lut_uva = lt.integrate_lut(
        ds_lut,
        wavelength_min=315,
        wavelength_max=400,
        erythemal=False
    )
    
    interp_uva = lt.build_uv_interpolator2(lut_uva)
    
    
    # UVB: 280–320 nm, sin weighting eritemático
    lut_uvb = lt.integrate_lut(
        ds_lut,
        wavelength_min=280,
        wavelength_max=315,
        erythemal=False
    )
    
    interp_uvb = lt.build_uv_interpolator2(lut_uvb)
    
    
    # --------------------------------------------------
    # Clear-sky detection & sun above 10 deg elevation
    # --------------------------------------------------
    
    msk_csk = detect_clearsky(df_cams, df_rad)
    
    
    # --------------------------------------------------
    # LUT estimation using MERRA
    # --------------------------------------------------
    
    df_uv["uva_lut"] = lt.apply_interpolator(
        interp_uva,
        df_merra,
        station,
        "merra",
    )
    
    df_uv["uvb_lut"] = lt.apply_interpolator(
        interp_uvb,
        df_merra,
        station,
        "merra",
    )
    
    
    # --------------------------------------------------
    # Valid data mask
    # --------------------------------------------------
    
    msk_valid = msk_not_nan(df_rad, df_uv)
    
    
    # --------------------------------------------------
    # Validation
    # --------------------------------------------------
    
    msk = msk_csk & msk_valid
    
    uva_results = validation_metrics(
        df_uv.loc[msk, "uva_lut"],
        df_uv.loc[msk, "uva"],
    )
    
    uvb_results = validation_metrics(
        df_uv.loc[msk, "uvb_lut"],
        df_uv.loc[msk, "uvb"],
    )
    
    
    results = pd.concat(
        [uva_results, uvb_results],
        keys=["uva", "uvb"]
    ).reset_index(level=1, drop=True)
    
    results.index.name = "variable"
    
    
    print("Metrics:\n", results.round(2))
    print("UVB:\n", uvb_results.round(2))
    
    
    # --------------------------------------------------
    # Plots
    # --------------------------------------------------
    
    plot_atmospheric_vars(df_merra,"merra")
    plt.savefig(ruta_fig / f"{station_label}_atmosphere.png") 
    plot_validation(df_uv,results,msk_csk & msk_valid,station["name"])
    plt.savefig(ruta_fig / f"{station_label}_validation.png")  
if __name__ == "__main__":
    main()


#%%
#Busco productos de Ozono y wv



