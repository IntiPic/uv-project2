# Current task

Refactor MERRA loader.

1. Add generic GES DISC subset request/download functions.
2. Cache daily files under data/raw/merra/<station>/.
3. Download AER + SLV for each required day.
4. Open subsets with xarray.
5. Merge:
   TO3 -> o3
   TQV -> wv
   TOTEXTTAU -> aod
   TOTANGSTR -> alpha
6. Preserve timezone conversion.
7. Preserve minute interpolation.
8. process_merra() should remain the main high-level entry point.