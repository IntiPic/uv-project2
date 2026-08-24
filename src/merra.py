#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug 21 13:56:16 2026

@author: inti

user: intipiccioli
pass: jovnef-jasgiv-cedcY9

"""

MERRA_PRODUCTS = {
    "slv": {
        "short_name": "M2T1NXSLV",
        "variables": {
            "o3": "TO3",
            "wv": "TQV",
        },
    },
    "aer": {
        "short_name": "M2T1NXAER",
        "variables": {
            "aod": "TOTEXTTAU",
            "alpha": "TOTANGSTR",
        },
    },
}

import pandas as pd
import earthaccess
import xarray as xr


def login_merra():
    """
    Authenticate against NASA Earthdata and return an authenticated session.
    """

    auth = earthaccess.login(
        strategy="interactive",
        persist=True,
    )

    return auth

def search_merra(product, start, end):
    """
    Search MERRA-2 granules for a given product and period.
    """
    results = earthaccess.search_data(
        short_name=product,
        temporal=(start, end),
    )

    return results

def open_merra(granule):
    """
    Open a MERRA-2 granule remotely.
    """
    files = earthaccess.open([granule])
    return files[0]

def open_merra_dataset(granule):
    """
    Open a MERRA-2 granule remotely with xarray.
    """
    f = earthaccess.open([granule])[0]

    ds = xr.open_dataset(
        f,
        engine="h5netcdf",
    )

    return ds

def load_merra(station, start, end):
    """
    Load MERRA-2 atmospheric data for a station.

    Returns hourly data for:
        o3
        wv
        aod
        alpha

    The index is localized to the station timezone.
    """

    # ---------------------------------------------------------
    # Ozono + vapor de agua
    # ---------------------------------------------------------

    results_slv = search_merra(
        "M2T1NXSLV",
        start,
        end,
    )

    dfs_slv = []

    for granule in results_slv:

        ds_slv = open_merra_dataset(granule)

        df_slv = (
            ds_slv[["TO3", "TQV"]]
            .sel(
                lat=station["lat"],
                lon=station["lon"],
                method="nearest",
            )
            .to_dataframe()
        )

        df_slv = df_slv[["TO3", "TQV"]]

        df_slv = df_slv.rename(
            columns={
                "TO3": "o3",
                "TQV": "wv",
            }
        )

        dfs_slv.append(df_slv)

    df_slv = pd.concat(dfs_slv)


    # ---------------------------------------------------------
    # AOD + Angstrom
    # ---------------------------------------------------------

    results_aer = search_merra(
        "M2T1NXAER",
        start,
        end,
    )

    dfs_aer = []

    for granule in results_aer:

        ds_aer = open_merra_dataset(granule)

        df_aer = (
            ds_aer[["TOTEXTTAU", "TOTANGSTR"]]
            .sel(
                lat=station["lat"],
                lon=station["lon"],
                method="nearest",
            )
            .to_dataframe()
        )

        df_aer = df_aer[["TOTEXTTAU", "TOTANGSTR"]]

        df_aer = df_aer.rename(
            columns={
                "TOTEXTTAU": "aod",
                "TOTANGSTR": "alpha",
            }
        )

        dfs_aer.append(df_aer)

    df_aer = pd.concat(dfs_aer)


    # ---------------------------------------------------------
    # Combinar los dos productos
    # ---------------------------------------------------------

    df = df_slv.join(
        df_aer,
        how="inner",
    )


    # ---------------------------------------------------------
    # Timezone local
    # ---------------------------------------------------------

    df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(station["tz"])

    return df