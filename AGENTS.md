# AGENTS.md — uv-project2

## 1. Project overview

This repository contains the code used to estimate and validate surface
ultraviolet solar irradiance using spectral radiative-transfer simulations
generated with libRadtran.

The general workflow is:

1. Obtain atmospheric variables from reanalysis / satellite products.
2. Compute solar geometry.
3. Interpolate a precomputed libRadtran lookup table (LUT).
4. Estimate spectral and integrated UV irradiance.
5. Compare modeled irradiance against ground measurements.
6. Compute validation statistics and diagnostic plots.

The project is research code associated with a scientific paper / PhD work.
Scientific correctness and traceability are more important than aggressive
software abstraction.

Do not change scientific methodology unless explicitly requested.


## 2. General coding philosophy

Keep the implementation simple and readable.

Prefer:

- small functions with clear responsibilities;
- pandas/xarray idioms;
- pathlib for filesystem paths;
- existing project conventions;
- explicit variable names;
- minimal dependencies.

Avoid:

- unnecessary classes;
- excessive abstraction;
- large architectural rewrites unless requested;
- silently changing units;
- silently changing timezone semantics;
- silently changing interpolation methods;
- coupling independent datasets/loaders.

When refactoring existing code, preserve its scientific behavior unless the
task explicitly requires changing it.

If a requested coding change requires a scientific/methodological decision
that is not specified here or in the task, do not invent one. Flag the issue
for discussion.


## 3. Main scientific quantities

The libRadtran LUT uses atmospheric/geometry inputs including:

- `alt`   : station altitude
- `o3`    : total column ozone
- `aod`   : aerosol optical depth
- `wv`    : total column water vapor
- `alpha` : Ångström exponent
- `sza`   : solar zenith angle

The exact LUT structure and interpolation implementation should be inspected
from the repository before modifying related code.


## 4. Irradiance quantities

The project works mainly with:

- UVA
- UVB
- erythemal UV / UVE

Do not assume that an observational variable named "UVB" necessarily
represents broadband physical UVB integrated over a standard wavelength
interval.

Some instruments have spectral response functions and may report an
erythemally weighted or instrument-weighted quantity.

Therefore, instrument interpretation is a scientific decision and must not
be inferred from column names alone.

Do not change wavelength integration ranges or spectral weighting functions
without explicit instructions.


## 5. Ground stations

Station metadata are stored in dictionaries such as:

- `STATIONS`
- `STATIONS_USA`

Typical station metadata include:

```python
{
    "name": ...,
    "lat": ...,
    "lon": ...,
    "elevation": ...,
    "period": ...,
    "tz": ...,
}
```

Always use station metadata rather than hardcoding coordinates, elevations,
or timezones inside loaders.

Different station networks may require different observational loaders.
Do not force all observational datasets through a single loader if their
formats or measurement definitions differ substantially.


## 6. Atmospheric datasets

The project currently uses atmospheric information from CAMS and MERRA-2.

These should remain independent data sources.

Do NOT make the MERRA implementation depend on CAMS merely to obtain dates,
indices, solar geometry, or other information unless explicitly requested.

The pipeline must be capable of operating at stations/periods where MERRA is
available but CAMS is not.


## 7. MERRA-2 variables

The relevant NASA MERRA-2 products are:

### Aerosols

Product:

`M2T1NXAER`

Variables:

- `TOTEXTTAU` -> `aod`
- `TOTANGSTR` -> `alpha`

Dataset/version currently used:

`M2T1NXAER_5.12.4`

### Surface / atmospheric column variables

Product:

`M2T1NXSLV`

Variables:

- `TO3` -> `o3`
- `TQV` -> `wv`

Dataset/version currently used:

`M2T1NXSLV_5.12.4`

Relevant units:

- `TO3`: Dobson Units (DU)
- `TQV`: kg m^-2

Do not apply additional unit conversions unless required by the LUT or
explicitly requested.


## 8. MERRA-2 acquisition

IMPORTANT:

Do not download complete global MERRA-2 granules for the normal processing
pipeline.

Full MERRA files can be hundreds of MB per day and are unnecessary because
only the grid point near each station is needed.

Use the NASA GES DISC subset service.

Endpoint:

`https://disc.gsfc.nasa.gov/service/subset/jsonwsp`

The subset workflow uses JSON-WSP requests.

A subset request has the general form:

```python
request = {
    "methodname": "subset",
    "type": "jsonwsp/request",
    "version": "1.0",
    "args": {
        "role": "subset",
        "start": start,
        "end": end,
        "box": bbox,
        "crop": True,
        "mapping": "nearest",
        "data": [
            {
                "datasetId": dataset_id,
                "variable": variable,
            }
            for variable in variables
        ],
    },
}
```

The workflow is:

1. Submit `subset`.
2. Obtain `jobId` and `sessionId`.
3. Poll using `GetStatus`.
4. Wait until `Status == "Succeeded"`.
5. Call `GetResult`.
6. Extract the generated subset download link.
7. Download the resulting NetCDF file.

A failed/dismissed job should raise an error rather than silently continuing.


## 9. Verified MERRA subset behavior

The GES DISC subset workflow has already been manually tested successfully.

Test case:

- station: Bondville (BON)
- date: 2024-10-01
- latitude: 40.05
- longitude: -88.37

Both products were successfully retrieved:

- `M2T1NXAER_5.12.4`
- `M2T1NXSLV_5.12.4`

The resulting subsets contained:

```text
time: 24
lat: 1
lon: 1
```

The selected MERRA grid point was approximately:

```text
lat = 40.0
lon = -88.125
```

The AER subset correctly contained:

```text
TOTEXTTAU
TOTANGSTR
```

The SLV subset correctly contained:

```text
TO3
TQV
```

Therefore, do not replace this working approach with full-granule downloads
unless explicitly requested.


## 10. MERRA local storage

MERRA subsets should be cached locally.

The current directory convention is approximately:

```text
data/
    raw/
        merra/
            <station>/
```

Example:

```text
data/raw/merra/BON/
```

Daily subset files may look like:

```text
MERRA2_400.tavg1_2d_aer_Nx.20241001.SUB.nc
MERRA2_400.tavg1_2d_slv_Nx.20241001.SUB.nc
```

Before downloading a subset, check whether the required local file already
exists.

Do not repeatedly download an existing valid subset unless explicitly
requested.


## 11. MERRA processing

The high-level MERRA workflow should ultimately produce a pandas DataFrame
with columns:

```text
o3
wv
aod
alpha
```

using:

```text
TO3        -> o3
TQV        -> wv
TOTEXTTAU  -> aod
TOTANGSTR  -> alpha
```

The current high-level entry point is:

```python
process_merra(...)
```

When refactoring `merra.py`, preserve `process_merra()` as the main
high-level interface unless explicitly asked to change the API.

The desired conceptual workflow is:

```text
process_merra
    |
    +-- determine required dates
    |
    +-- obtain/cache daily AER subsets
    |
    +-- obtain/cache daily SLV subsets
    |
    +-- open daily subsets
    |
    +-- combine dates
    |
    +-- combine AER + SLV variables
    |
    +-- rename variables
    |
    +-- interpret timestamps as UTC
    |
    +-- temporal interpolation in UTC and clip to requested period
    |
    +-- convert index to station timezone
    |
    +-- return DataFrame
```

Exact function decomposition is flexible. Prefer a few reusable functions
over one very large function.


## 12. MERRA time handling

MERRA hourly timestamps are in UTC.

Typical timestamps occur at:

```text
00:30
01:30
02:30
...
23:30
```

Raw MERRA timestamps must be interpreted as UTC before conversion to local
station time.

Conceptually:

```python
index = index.tz_localize("UTC").tz_convert(station["tz"])
```

Do not treat raw MERRA timestamps as local time.


## 13. Daylight-saving time

Be careful with DST.

Some stations use timezones such as:

```text
Atlantic/Canary
America/Chicago
America/Anchorage
America/Los_Angeles
```

A local calendar month does NOT necessarily contain:

```python
days * 24 * 60
```

minutes.

DST transitions can create 23-hour or 25-hour local days.

Do not remove timestamps merely to force a fixed number of samples per
month.

Do not strip timezone information to make indices align.

Any change to timezone/index semantics should be treated as a scientific
data-processing decision and discussed before implementation.


## 14. Temporal interpolation

Atmospheric MERRA variables are hourly and are interpolated to the temporal
resolution required by the irradiance pipeline, currently generally
1 minute.

Preserve the existing interpolation method unless explicitly requested to
change it.

Do not interpolate across large missing-data gaps without explicit
instructions.

Do not invent values outside the available temporal range through
uncontrolled extrapolation.


## 15. CAMS

CAMS is another source of atmospheric information and/or clear-sky
irradiance used in the project.

There is existing CAMS-specific code.

Do not modify CAMS code while working on MERRA unless the task explicitly
requires it.

Do not use CAMS timestamps as the definition of the MERRA processing period.
MERRA should be independently processable.


## 16. Solar geometry

Solar zenith angle (`sza`) is required by the LUT.

Inspect the existing repository implementation before modifying solar
geometry calculations.

Do not independently introduce a different solar-position algorithm merely
because a library provides one.

Consistency with the existing validation pipeline is important.


## 17. Clear-sky filtering

The validation pipeline uses clear-sky filtering.

There is existing logic based on comparison between measured irradiance and
clear-sky estimates, including work using a Reno/Hansen-type algorithm.

Clear-sky classification is part of the scientific methodology.

Do not modify clear-sky filtering thresholds or algorithms as part of an
unrelated refactor.


## 18. Validation metrics

Validation uses quantities including:

- mean observed irradiance
- MBD
- normalized MBD
- RMSD
- normalized RMSD
- number of samples

Existing metric implementations should be reused.

Do not redefine normalization conventions without explicit instructions.


## 19. Observational datasets

The project includes data from multiple networks/sites.

Examples include:

- Izaña
- Punta Arenas
- Payerne
- US stations such as Bondville, Barrow, Desert Rock, etc.

These datasets are not necessarily homogeneous.

For example, Chile/Punta Arenas data require different loading/time handling
from BSRN-style datasets.

Keep station/network-specific preprocessing isolated when appropriate.


## 20. Instrument-specific UV interpretation

Instrument spectral response is important.

Known examples investigated in this project include:

- Yankee Environmental Systems UV instruments
- Solar Light 501A UV Biometer

A measured quantity must not automatically be interpreted as physical UVB
simply because a source labels it UVB.

Instrument spectral response, erythemal weighting, and integration wavelength
range may need to be considered.

This interpretation is handled at the scientific-methodology level, not by
guessing inside loaders.


## 21. Data integrity rules

When joining observational/model datasets:

- preserve timezone-aware DatetimeIndex objects;
- inspect cadence differences;
- avoid silent row dropping;
- avoid positional alignment when timestamp alignment is intended;
- do not fill observational NaNs unless explicitly required;
- distinguish missing observations from missing model inputs.

Do not use operations such as arbitrary `.iloc[...]` trimming as a permanent
solution to index alignment problems.


## 22. Working with existing code

Before editing a module:

1. Read the complete relevant module.
2. Search the repository for calls to the functions being modified.
3. Understand expected inputs and outputs.
4. Preserve public behavior where possible.
5. Make the smallest coherent change needed.
6. Run the relevant code/tests after modification.

Do not assume a function is unused without searching the repository.


## 23. Testing research code

There may not yet be comprehensive automated tests.

When implementing or refactoring loaders, perform lightweight sanity checks
where appropriate.

For MERRA subsets, useful checks include:

```text
expected variables exist
time dimension is non-empty
lat/lon dimensions correspond to the requested nearest-point subset
timestamps parse correctly
resulting DataFrame index is monotonic
expected columns exist
```

Avoid embedding overly restrictive assumptions such as exactly 1440 local
timestamps per day because of DST.


## 24. Performance

Avoid downloading or loading unnecessary data.

In particular:

BAD:

```text
download ~500 MB global MERRA granule
-> open entire file
-> select one grid point
```

GOOD:

```text
request station subset
-> download small NetCDF
-> process only required variables
```

When processing many stations/months, reuse cached subset files.


## 25. Error handling

Network/data-access functions should fail clearly.

Use exceptions for:

- HTTP errors;
- failed GES DISC jobs;
- missing expected variables;
- invalid downloaded files.

Do not silently substitute atmospheric values when a download fails.

Keep retry/polling logic simple and bounded where appropriate.


## 26. Scope of agent decisions

Codex is encouraged to independently handle:

- implementation details;
- function decomposition;
- filesystem operations;
- straightforward refactors;
- removal of clearly obsolete code after checking usage;
- testing;
- debugging;
- improving readability;
- avoiding duplicated code.

Codex should NOT independently decide:

- UV wavelength integration limits;
- instrument spectral interpretation;
- erythemal weighting definitions;
- clear-sky methodology;
- atmospheric-variable substitutions;
- unit conversions affecting the LUT;
- interpolation methodology;
- timezone semantics;
- validation metric definitions;
- scientific filtering thresholds.

When such a decision is required, stop and report the specific question.


## 27. Current priority

The current development priority is refactoring the MERRA implementation.

The old implementation downloaded complete global MERRA granules using
Earthaccess and then selected the nearest station grid point.

That approach should be replaced by the already verified GES DISC subset
workflow.

The intended result is that a call conceptually similar to:

```python
df_merra = process_merra(
    station,
    start,
    end,
)
```

can:

1. determine the required days;
2. obtain missing daily AER subsets;
3. obtain missing daily SLV subsets;
4. reuse cached files;
5. open and concatenate them;
6. extract `o3`, `wv`, `aod`, `alpha`;
7. correctly handle UTC/local time;
8. interpolate to the required cadence;
9. return the processed DataFrame.

Do not require CAMS for this workflow.


## 28. Communication

For implementation tasks:

- make the requested changes directly;
- explain briefly what changed;
- report files modified;
- report tests/checks executed;
- mention unresolved scientific questions separately.

Avoid giving long tutorials unless requested.

When a scientific ambiguity prevents a correct implementation, formulate the
question precisely so it can be discussed outside the coding task.


## 29. Approved MERRA period and interpolation contract (2026-09-08)

These explicit user decisions supersede the legacy 59-minute tail and lack of
period clipping. Preserve `process_merra(station, start, end)`.

- Naive `start`/`end` mean UTC. A timezone-aware bound preserves its instant
  and is converted to UTC.
- ISO date-only `start` means 00:00 UTC. ISO date-only `end` includes that whole
  UTC day: next midnight is the exclusive upper bound. A `datetime.date` has
  the same date-only meaning. Datetimes, including midnight, are explicit
  instants; an end with a time is inclusive and is never extended.
- Build a one-minute UTC grid starting at the requested start; return only grid
  ticks inside the requested bounds (do not append an off-cadence end).
- Determine the actual hourly :30 UTC records bracketing that grid. Acquire
  only their daily AER/SLV subsets, reusing valid station caches. A complete
  UTC day can require subsets from the preceding and following UTC dates.
- Align products by timestamp. Interpolate in UTC with `method="time"` only
  between valid hourly inputs exactly one hour apart. Missing required hourly
  data, nonfinite values or missing edge coverage must raise an explicit error
  identifying the variable and affected UTC period. Never extrapolate or fill
  such gaps. Missing values outside the required records are not interpolated.
- Convert the final index to `station["tz"]`, retaining timezone awareness and
  DST. Do not change cadence, units, or observational timestamp interpretation.
- BON metadata: name BON, latitude 40.05, longitude -88.37,
  `tz="America/Chicago"`. This timezone defines the MERRA output index only.
  No station elevation has been supplied; do not invent one for LUT use.
- Existing `df_merra.iloc[60:]` in main.py and main_chile.py is incompatible
  with newly clipped outputs: it removes valid requested data. Do not use
  positional trimming to align data. Review observational/model coverage by
  timestamp before changing the downstream validation scripts.

Acquisition uses src/merra2.py with bounded HTTP waits and job polling. Invalid
cache files are reported; replacements are published only after NetCDF
validation. Keep the experimental pruebas_merra.py out of normal execution.
