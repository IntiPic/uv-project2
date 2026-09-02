#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 11:11:08 2026

@author: inti
"""

from config import STATIONS
from src.cams import load_cams
from src.clearsky import detect_clearsky
from src.validation import validation_metrics, msk_not_nan
from src.plotting import plot_validation_chile, plot_atmospheric_vars
import src.measurements as ms
import src.merra as mr
import src.lut as lt
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt


#%% TEST MERRA-2

# station_label = "PAR"
# station = STATIONS[station_label]

# auth = mr.login_merra()


# df_merra = mr.process_merra(
#     STATIONS[station_label],
#     "2022-10-01",
#     "2022-10-31",
# )

# plot_atmospheric_vars(df_merra,"merra")

# cwd = Path.cwd()
# ruta_merra = Path(cwd / 'data' / 'raw' / 'merra')

# df_merra.to_csv(ruta_merra / f"{station_label}_MERRA.csv")

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
    ruta_fig =  Path(cwd / 'out' / 'fig')
    
    # Load data
    df_cams = load_cams(station,ruta_cams)
    df_merra = mr.load_merra(station,ruta_merra)
    # df_merra = df_merra.iloc[60:] # CAMBIAR LUEGO!!
    # print(df_cams.head())
    
    df_uv = ms.load_chile_uv(station, ruta_uv)
    df_rad = ms.load_chile_rad(station, ruta_rad)
    #print(df_uv.head())
    #print(df_rad.head())
    
    # df_lut = load_lut(ruta_lut)
    ds_lut = lt.load_lut_spectral(ruta_lut)
    # wavelength_min = 280
    # wavelength_max = 315
    lut_uve = lt.integrate_lut(
        ds_lut,
        wavelength_min=280,
        wavelength_max=320,
        erythemal=True
    )
    
    interp_uve = lt.build_uv_interpolator2(lut_uve)
    
    #print(interp_uva)

    
    # # Clear-sky detection & sun above 10 deg. elevation
    msk_csk = detect_clearsky(df_cams,df_rad) #incluye sza < 80
    
    # df_uv["uva_lut"] = apply_interpolator(
    #     interp_uva,
    #     df_merra,
    #     station,
    #     "merra",
    # )

    df_uv["uvb_lut"] = lt.apply_interpolator(
        interp_uve,
        df_merra,
        station,
        "merra",
    )
    
    msk_valid = msk_not_nan(df_rad, df_uv)
    
    # uva_results = validation_metrics(
    #     df_uv.loc[msk_csk & msk_valid,"uva_lut"],
    #     df_uv.loc[msk_csk & msk_valid,"uva"],
    # )
    
    uvb_results = validation_metrics(
        df_uv.loc[msk_csk,"uvb_lut"],
        df_uv.loc[msk_csk,"uvb"],
    )
    
    results = uvb_results
    # results = pd.concat(
    #     [uva_results, uvb_results],
    #     keys=["uva", "uvb"]
    # ).reset_index(level=1, drop=True)
    
    # results.index.name = "variable"

    
    print("Metrics:\n", results.round(2))
    # print("UVB:\n", uvb_results.round(2))

    # # Plots
    
    # plot_atmospheric_vars(df_cams)
    plot_atmospheric_vars(df_merra,"merra")
    plt.savefig(ruta_fig / f"{station_label}_atmosphere.png") 
    plot_validation_chile(df_uv,results,msk_csk & msk_valid,station["name"])
    plt.savefig(ruta_fig / f"{station_label}_validation.png")    
    
if __name__ == "__main__":
    main()


#%%
#Busco productos de Ozono y wv



