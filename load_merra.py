#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep  3 10:41:26 2026

@author: inti
"""
from pathlib import Path
import pandas as pd

from config import STATIONS_USA
from src.merra import login_merra, process_merra
#%%
cwd = Path.cwd()

ruta_USA = cwd / "data" / "USA" / "OUT"
ruta_processed = cwd / "data" / "processed"


# Login NASA
login_merra()


# Año a descargar
start = "2021-01-01"
end = "2021-02-01"


for label, station in STATIONS_USA.items():

    label = label.lower()

    # ---------------------------------------------------------
    # Determinar resolución UV
    # ---------------------------------------------------------

    carpeta_uv = ruta_USA / label

    archivo_f01 = carpeta_uv / f"{label}_UVdata_f01.csv"
    archivo_f05 = carpeta_uv / f"{label}_UVdata_f05.csv"

    if archivo_f01.exists():
        freq = "f01"

    elif archivo_f05.exists():
        freq = "f05"

    else:
        print(f"{label}: no se encontró archivo UV")
        continue

    print(f"\nProcesando {label} ({freq})")

    # ---------------------------------------------------------
    # Procesar MERRA
    # ---------------------------------------------------------

    df = process_merra(
        station,
        start,
        end,
    )

    # ---------------------------------------------------------
    # Adaptar resolución
    # ---------------------------------------------------------

    if freq == "f05":
        df = df.resample("5min").asfreq()

    # ---------------------------------------------------------
    # Guardar
    # ---------------------------------------------------------

    output_dir = ruta_processed / label
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{label}_MERRA_{freq}.csv"

    df.to_csv(output_file)

    print(f"Guardado: {output_file}")
