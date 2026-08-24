#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 11:11:08 2026

@author: inti
"""

from config import STATIONS
from src.cams import load_cams
from src.measurements import load_bsrn_uv, load_bsrn_rad, load_chile_uv, load_chile_rad
from src.lut import load_lut, build_uv_interpolator, apply_interpolator
from src.clearsky import detect_clearsky, resample_csk
from src.validation import validation_metrics, msk_not_nan
from src.plotting import plot_validation, plot_atmospheric_vars
import pandas as pd
from pathlib import Path

def main():

    # Configuration
    station = STATIONS["PAR"]
    
    cwd = Path.cwd()
    ruta_cams = Path(cwd / 'data' / 'raw' / 'cams')
    ruta_uv = Path(cwd / 'data' / 'raw' / 'uv')
    ruta_rad = Path(cwd / 'data' / 'raw' / 'rad')
    ruta_lut = Path(cwd / 'data' / 'lut')
    # ruta_fig =  cwd.parent / 'FIG'
    
    # Load data
    df_cams = load_cams(station,ruta_cams)
    # print(df_cams.head())
    
    if station['name'] == 'PAR': #Chile se carga distinto!
        # start_uv = pd.Timestamp("2022-10-01").tz_localize(station["tz"])
        # end_uv = (
        #     start_uv
        #     + pd.offsets.MonthEnd(1)
        #     + pd.Timedelta(days=1)
        #     - pd.Timedelta(minutes=5)
        # )
        start = df_cams.index.min()
        end = df_cams.index.max()
        df_uv = load_chile_uv(station,ruta_uv,start,end)
        df_rad = load_chile_rad(station, ruta_rad,start,end)
    else:
        df_uv = load_bsrn_uv(station, ruta_uv)
        df_rad = load_bsrn_rad(station, ruta_rad)
    #print(df_uv.head())
    
    df_lut = load_lut(ruta_lut)
    # print(df_lut.head())
        
    #print(df_rad.head())


    # # LUT
    interp_uva = build_uv_interpolator(df_lut, "uva")
    interp_uvb = build_uv_interpolator(df_lut, "uvb")
    
    #print(interp_uva)

    
    # # Clear-sky detection & sun above 10 deg. elevation
    msk_csk = detect_clearsky(df_cams,df_rad) #incluye sza < 80
    
    if station['name'] == 'PAR':
        msk_csk = resample_csk(msk_csk, 0.8)
        df_cams["uvb_lut"] = apply_interpolator(
            interp_uvb,
            df_cams,
            station,
        )
        
        df_uv["uvb_lut"] = df_cams["uvb_lut"].resample("5min").mean()
        
        uvb_results = validation_metrics(
            df_uv.loc[msk_csk,"uvb_lut"],
            df_uv.loc[msk_csk,"uvb"]*40,
        )
        
        plot_validation(df_uv,uvb_results,msk_csk)
    else: 
        df_uv["uva_lut"] = apply_interpolator(
            interp_uva,
            df_cams,
            station,
        )
    
        df_uv["uvb_lut"] = apply_interpolator(
            interp_uvb,
            df_cams,
            station,
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
        
        plot_validation(df_uv,results,msk_csk & msk_valid)

    
    #print("Metrics:\n", results.round(2))
    # print("UVB:\n", uvb_results.round(2))

    # # Plots
    
    plot_atmospheric_vars(df_cams)
    
    

if __name__ == "__main__":
    main()

#%% Tests

# import matplotlib.pyplot as plt


# station = STATIONS["PAR"]
# day = "2022-10-15"

# start_day = pd.Timestamp(day, tz=station["tz"])
# end_day = start_day + pd.Timedelta(days=1)

# rad = df_rad.loc[start_day:end_day]
# uv = df_uv.loc[start_day:end_day]
# cams = df_cams.loc[start_day:end_day]

# fig, ax1 = plt.subplots(figsize=(14, 5))

# # GHI medido y cielo claro CAMS
# ax1.plot(rad.index, rad["ghi"], label="GHI medido")
# ax1.plot(cams.index, cams["Clear sky GHI"]*60, label="GHI cielo claro CAMS")

# ax1.set_ylabel("GHI [W/m²]")
# ax1.set_xlabel("Hora")
# ax1.legend(loc="upper left")
# ax1.grid(alpha=0.3)

# # UVB en segundo eje
# ax2 = ax1.twinx()
# ax2.plot(uv.index, uv["uvb"], label="UVB", alpha=0.8)

# ax2.set_ylabel("UVB [W/m²]")
# ax2.legend(loc="upper right")

# plt.title(f"{station['name']} — {day}")
# plt.tight_layout()
# plt.show()


