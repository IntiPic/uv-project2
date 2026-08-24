#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 29 15:00:51 2026

@author: inti
"""
import numpy as np
import pandas as pd 
import re


def load_bsrn_info(filename):
    with open(filename) as f:
        texto = f.read()

    metadata = texto.split("*/")[0]
    
    info = {}
    # Estación
    m = re.search(r'Event\(s\):\s*([A-Z0-9_-]+)', metadata)
    if m:
        info["station"] = m.group(1)

    # Latitud
    m = re.search(r'LATITUDE:\s*([-\d.]+)', metadata)
    if m:
        info["lat"] = float(m.group(1))

    # Longitud
    m = re.search(r'LONGITUDE:\s*([-\d.]+)', metadata)
    if m:
        info["lon"] = float(m.group(1))

    # Elevación
    m = re.search(r'ELEVATION:\s*([-\d.]+)\s*m', metadata)
    if m:
        info["elevation"] = float(m.group(1))
        
    return info
        
#%%        

def load_bsrn_uv(filename,tz_local,start=None,end=None):
    
    with open(filename, "r") as f:
        for i, line in enumerate(f):
            if line.strip() == "*/":
                skiprows = i + 1
                break

    df = pd.read_csv(filename,sep="\t", skiprows=skiprows, parse_dates=["Date/Time"])

    df["Date"] = (
    pd.to_datetime(df["Date/Time"])
      .dt.tz_localize("UTC")
      .dt.tz_convert(tz_local)
      )
    
    columnas = {
        "Date": "Date",
        "UV-a global [W/m**2]": "uva",
        "UV-b global [W/m**2]": "uvb"
    }

    presentes = [c for c in columnas if c in df.columns]

    df = df[presentes].rename(columns=columnas).set_index("Date")

    for col in ["uva", "uvb"]:
        if col not in df.columns:
            df[col] = np.nan

    # Opcional: mantener un orden fijo
    df = df[["uva", "uvb"]]
    
    if start is None:
        start = df.index.min()
    else:
        start = (
            pd.Timestamp(start)
            .tz_localize("UTC")
            .tz_convert(tz_local)
        )
    
    if end is None:
        end = df.index.max()
    else:
        end = (
            pd.Timestamp(end)
            .tz_localize("UTC")
            .tz_convert(tz_local)
        )
    
    idx = pd.date_range(start, end, freq="1min")
    
    df = df.reindex(idx)
    df.index.name = "Date"
    
    return df
#%%
def load_bsrn_radiation(filename, tz_local, start=None, end=None):

    with open(filename, "r") as f:
        for i, line in enumerate(f):
            if line.strip() == "*/":
                skiprows = i + 1
                break

    df = pd.read_csv(
        filename,
        sep="\t",
        skiprows=skiprows,
        parse_dates=["Date/Time"]
    )

    df["Date"] = (
        pd.to_datetime(df["Date/Time"])
        .dt.tz_localize("UTC")
        .dt.tz_convert(tz_local)
    )

    columnas = {
        "Date": "Date",
        "SWD [W/m**2]": "ghi",
        "DIR [W/m**2]": "dni",
        "DIF [W/m**2]": "dhi",
    }

    presentes = [c for c in columnas if c in df.columns]

    df = (
        df[presentes]
        .rename(columns=columnas)
        .set_index("Date")
    )

    # Reemplazar códigos de dato faltante de BSRN
    df = df.replace(-1, np.nan)

    # Asegurar que siempre existan las columnas
    for col in ["ghi", "dni", "dhi"]:
        if col not in df.columns:
            df[col] = np.nan

    df = df[["ghi", "dni", "dhi"]]

    if start is None:
        start = df.index.min()
    else:
        start = (
            pd.Timestamp(start)
            .tz_localize("UTC")
            .tz_convert(tz_local)
        )

    if end is None:
        end = df.index.max()
    else:
        end = (
            pd.Timestamp(end)
            .tz_localize("UTC")
            .tz_convert(tz_local)
        )

    idx = pd.date_range(start, end, freq="1min")

    df = df.reindex(idx)
    df.index.name = "Date"

    return df
#%%
def load_cams(filename, tz_local):

    with open(filename) as f:
        lines = f.readlines()

    header_line = next(
        line for line in lines
        if line.startswith("# Observation period;")
    )

    columns = header_line[2:].strip().split(";")

    df = pd.read_csv(filename,sep=";",comment="#",header=None,names=columns)

    df["Date"] = (pd.to_datetime(df["Observation period"].str.split("/").str[0],
            utc=True
        ).dt.tz_convert(tz_local))

    df = df.set_index("Date").drop(columns="Observation period")

    df["aod550"] = (df["AOD BC"]+ df["AOD DU"]+ df["AOD SS"]+ df["AOD OR"]+ df["AOD SU"]
        + df["AOD NI"]+ df["AOD AM"] + df["AOD SO"])

    df = df.rename(columns={
        "TO3": "tco3",
        "TCWV": "tcwv",
        "Solar zenith angle": "sza",
        "Angstrom exponent": "alpha",
        "GHI": "ghi"
    })

    return df