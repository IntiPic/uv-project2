#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 14:36:46 2026

@author: inti
"""
import numpy as np
import pandas as pd

def msk_not_nan(df_rad,df_uv):
    msk1 = df_rad.ghi.notna()
    msk2 = ~df_uv.isna().any(axis=1)
    return msk1 & msk2


def validation_metrics(est, obs):

    mbd = np.mean(est - obs)
    rmsd = np.sqrt(np.mean((est - obs) ** 2))

    mean_obs = np.mean(obs)

    nmbd = 100 * mbd / mean_obs
    nrmsd = 100 * rmsd / mean_obs

    return pd.DataFrame({
        "mean_obs": [mean_obs],
        "mbd": [mbd],
        "nmbd": [nmbd],
        "rmsd": [rmsd],
        "nrmsd": [nrmsd],
        "n": [len(obs)]
    })