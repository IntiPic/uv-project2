#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 11:11:08 2026

@author: inti
"""

from config import STATIONS
from src.cams import load_cams
from src.measurements import load_bsrn_uv, load_bsrn_rad
from src.lut import load_lut, build_uv_interpolator, apply_interpolator
from src.clearsky import detect_clearsky
from src.validation import validation_metrics, msk_not_nan
from src.plotting import plot_validation, plot_atmospheric_vars
import src.merra as mr
import pandas as pd
from pathlib import Path


#%% TEST MERRA-2

station_label = "PAR"
station = STATIONS[station_label]

auth = mr.login_merra()


df_merra = mr.process_merra(
    STATIONS[station_label],
    "2022-10-01",
    "2022-10-31",
)

plot_atmospheric_vars(df_merra,"merra")

cwd = Path.cwd()
ruta_merra = Path(cwd / 'data' / 'raw' / 'merra')

df_merra.to_csv(ruta_merra / f"{station_label}_MERRA.csv")

#%%
def main():

    # Configuration
    station_label = "PAR"
    station = STATIONS[station_label]
    
    cwd = Path.cwd()
    ruta_cams = Path(cwd / 'data' / 'raw' / 'cams')
    ruta_merra = Path(cwd / 'data' / 'raw' / 'merra')
    ruta_uv = Path(cwd / 'data' / 'raw' / 'uv')
    ruta_rad = Path(cwd / 'data' / 'raw' / 'rad')
    ruta_lut = Path(cwd / 'data' / 'lut')
    # ruta_fig =  cwd.parent / 'FIG'
    
    # Load data
    df_cams = load_cams(station,ruta_cams)
    df_merra = mr.load_merra(station,ruta_merra)
    df_merra = df_merra.iloc[60:] # CAMBIAR LUEGO!!
    # print(df_cams.head())
    
    df_uv = load_bsrn_uv(station, ruta_uv)
    df_rad = load_bsrn_rad(station, ruta_rad)
    #print(df_uv.head())
    #print(df_rad.head())
    
    df_lut = load_lut(ruta_lut)
    # print(df_lut.head())
        

    # # LUT
    interp_uva = build_uv_interpolator(df_lut, "uva")
    interp_uvb = build_uv_interpolator(df_lut, "uvb")
    
    #print(interp_uva)

    
    # # Clear-sky detection & sun above 10 deg. elevation
    msk_csk = detect_clearsky(df_cams,df_rad) #incluye sza < 80
    
    df_uv["uva_lut"] = apply_interpolator(
        interp_uva,
        df_merra,
        station,
        "merra",
    )

    df_uv["uvb_lut"] = apply_interpolator(
        interp_uvb,
        df_merra,
        station,
        "merra",
    )
    
    msk_valid = msk_not_nan(df_rad, df_uv)
    
    uva_results = validation_metrics(
        df_uv.loc[msk_csk & msk_valid,"uva_lut"],
        df_uv.loc[msk_csk & msk_valid,"uva"],
    )
    
    uvb_results = validation_metrics(
        df_uv.loc[msk_csk,"uvb_lut"],
        df_uv.loc[msk_csk,"uvb"],
    )
    
    results = pd.concat(
        [uva_results, uvb_results],
        keys=["uva", "uvb"]
    ).reset_index(level=1, drop=True)
    
    results.index.name = "variable"

    
    print("Metrics:\n", results.round(2))
    print("UVB:\n", uvb_results.round(2))

    # # Plots
    
    # plot_atmospheric_vars(df_cams)
    # plot_atmospheric_vars(df_merra,"merra")
    plot_validation(df_uv,results,msk_csk & msk_valid,station["name"])
    

if __name__ == "__main__":
    main()


#%%
#Busco productos de Ozono y wv



