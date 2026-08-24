#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 18 15:31:56 2026

@author: inti
"""

import matplotlib.pyplot as plt

def plot_validation(df_uv,df_results,msk):
    
    fig, axs = plt.subplots(1, 2, figsize=(12, 6), constrained_layout=True)

    variables = [
        ("uva", "uva_lut", "UVA"),
        ("uvb", "uvb_lut", "UVB")
    ]

    for ax, (obs_col, est_col, titulo) in zip(axs, variables):

        obs = df_uv.loc[msk, obs_col].to_numpy()
        est = df_uv.loc[msk, est_col].to_numpy()

        # Estadísticos
        nmbd = df_results.loc[obs_col,'nmbd']
        nrmsd = df_results.loc[obs_col,'nrmsd']
        N = df_results.loc[obs_col,'n']

        # Scatter
        ax.scatter(obs, est, s=8, alpha=0.5)

        lim = [0, max(obs.max(), est.max())]
        ax.plot(lim, lim, "k--", lw=1)

        ax.set_xlim(lim)
        ax.set_ylim(lim)
        ax.set_aspect("equal")

        ax.set_title(titulo)
        ax.set_xlabel(f"{titulo} medida (W m$^{{-2}}$)")
        ax.set_ylabel(f"{titulo} LUT (W m$^{{-2}}$)")

        ax.text(
            0.05,
            0.95,
            f"N = {N}\n"
            f"nMBD = {nmbd:.1f} %\n"
            f"nRMSD = {nrmsd:.1f} %",
            transform=ax.transAxes,
            va="top",
            bbox=dict(facecolor="white", alpha=0.8),
        )
        
    # plt.savefig(ruta_fig / f"dispersion_UV_{station}_2.png", dpi=300)
    plt.show()
  
    
def plot_atmospheric_vars(df,source = 'cams'):
    if source == 'cams':
        cols = ["tco3", "aod550", "tcwv"]
        titles = [
            "Ozone column (TCO3)",
            "AOD at 550 nm (AOD550)",
            "Water vapor (TCWV)"
        ]
        ylabs = [
            "DU",
            "-",
            "mm"
        ]
        
        fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
        
        for ax, col, title, ylab in zip(axes, cols, titles, ylabs):
            ax.plot(df.index, df[col], lw=0.8)
            ax.set_title(title)
            ax.set_ylabel(ylab)
            ax.grid(True, alpha=0.3)
        
        axes[-1].set_xlabel("Date")
        
        plt.tight_layout()
        # plt.savefig(ruta_fig / f"cams_variables_atmosfericas_{station}.png", dpi=300)
        plt.show()
        
    elif source == 'merra':
        cols = ['o3','aod', 'wv', 'alpha']
        titles = [
            "Ozone column (O3)",
            "AOD at 550 nm (AOD550)",
            "Water vapor (WV)",
            "Angstrom exponent (alpha)"
        ]
        ylabs = [
            "DU",
            "-",
            "mm",
            "-"
        ]
        
        fig, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
        
        for ax, col, title, ylab in zip(axes, cols, titles, ylabs):
            ax.plot(df.index, df[col], lw=0.8)
            ax.set_title(title)
            ax.set_ylabel(ylab)
            ax.grid(True, alpha=0.3)
        
        axes[-1].set_xlabel("Date")
        
        plt.tight_layout()
        # plt.savefig(ruta_fig / f"cams_variables_atmosfericas_{station}.png", dpi=300)
        plt.show()