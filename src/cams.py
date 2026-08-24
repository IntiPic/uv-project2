#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 11:13:15 2026

@author: inti


This module loads and processes CAMS atmospherical data
"""

import pandas as pd
from pathlib import Path


def filename_cams(station, path):
    label = station["name"]
    file_str_cams = f'{label}_CAMS.csv'
    file_cams = Path(path / file_str_cams)
    return file_cams

def load_cams(station, path):
    
    filename = filename_cams(station,path)
    tz_local = station["tz"]
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

