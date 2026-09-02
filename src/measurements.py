#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 13:04:18 2026

@author: inti
"""

import numpy as np
import pandas as pd 
from pathlib import Path

def filenames(station, path):
    label = station["name"]
    period = station["period"]
    if label == 'PAR':
        file_str_uv = f"{label}_Ultra-violet.csv"
        file_str_rad = f"{label}_radiation_{period}.csv"
    else:
        file_str_uv = f"{label}_Ultra-violet_{period}.tab"
        file_str_rad = f"{label}_radiation_{period}.tab"
    file_uv = Path(path / file_str_uv)
    file_rad = Path(path / file_str_rad)
    return file_uv, file_rad


def load_bsrn_uv(station, path, start=None, end=None):
    
    filename = filenames(station, path)
    filename = filename[0]
    tz_local = station["tz"]
    
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


def load_bsrn_rad(station, path, start=None, end=None):
    
    filename = filenames(station, path)
    filename = filename[1]
    tz_local = station["tz"]

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

def load_chile_uv(station, path, start=None, end=None):

    filename = filenames(station, path)[0]
    tz_local = station["tz"]

    df = pd.read_csv(
        filename,
        parse_dates=[0],
        index_col=0
    )

    df.index = pd.to_datetime(df.index).tz_localize(tz_local)
    df.index.name = "Date"

    df = df.rename(columns={df.columns[0]: "uvb"})

    if start is None:
        period = pd.Period(station["period"], freq="M")
        start = period.start_time.tz_localize(tz_local)
        end = period.end_time.floor("min").tz_localize(tz_local)

    # Índice final a 1 minuto
    idx = pd.date_range(start=start, end=end, freq="1min")

    # Interpolar desde los datos originales de 5 min
    df = (
        df.reindex(idx)
          .interpolate(method="time")
    )

    # Completar los minutos finales posteriores a la última medición
    df = df.ffill()

    return df

def load_chile_rad(station, path, start=None, end=None):

    filename = filenames(station, path)
    filename = filename[1]
    tz_local = station["tz"]
    
    df = pd.read_csv(filename, sep=";")

    df["Date"] = (
        pd.to_datetime(df["momento"])
        .dt.tz_localize("UTC")
        .dt.tz_convert(tz_local)
    )

    df = (
        df[["Date", "radiacionGlobalInst"]]
        .rename(columns={"radiacionGlobalInst": "ghi"})
        .set_index("Date")
    )

    df["ghi"] = pd.to_numeric(df["ghi"], errors="coerce")

    start = pd.Period(station["period"], freq="M").start_time
    end = pd.Period(station["period"], freq="M").end_time.floor("min")
    
    start = start.tz_localize(station["tz"])
    end = end.tz_localize(station["tz"])

    # Completar minutos faltantes con NaN
    idx = pd.date_range(
        start=start,
        end=end,
        freq="1min",
        tz=station["tz"]
    )
    
    df = df.reindex(idx)

    

    return df

