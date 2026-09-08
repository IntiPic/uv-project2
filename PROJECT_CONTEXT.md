# UV Project Context

## Scientific goal

Validation of UV irradiance estimated with a libRadtran LUT against
ground observations.

LUT atmospheric inputs:
- alt
- o3
- aod
- wv
- alpha
- sza

## Atmospheric datasets

CAMS:
- existing implementation

MERRA-2:
- M2T1NXAER
    - TOTEXTTAU -> aod
    - TOTANGSTR -> alpha

- M2T1NXSLV
    - TO3 -> o3
    - TQV -> wv

MERRA subset service:
NASA GES DISC subset JSON-WSP API.
Use spatial crop around station and mapping="nearest".
Do NOT download complete global MERRA granules.

## Time handling

Raw MERRA timestamps are UTC.
Convert to station["tz"] after loading.
Atmospheric variables are interpolated to 1-minute cadence.

Be careful with DST. Do not assume every local month has
number_of_days * 1440 timestamps.

## Stations

Station metadata live in STATIONS / STATIONS_USA dictionaries.

## Code philosophy

Keep data loaders independent.
Do not make MERRA depend on CAMS.
Functions should be reusable for stations for which only MERRA is available.

Avoid unnecessary abstractions.
Prefer pandas/xarray idioms already used in the project.

## Current work

Refactor merra.py so process_merra() obtains daily MERRA AER and SLV
subsets using GES DISC instead of downloading complete global granules.

Already tested successfully:
- BON
- 2024-10-01
- M2T1NXAER
- M2T1NXSLV
- resulting subsets contain time=24, lat=1, lon=1