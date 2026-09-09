from pathlib import Path
import earthaccess
import time
import xarray as xr
import requests
import json
import re

#%%

earthaccess.login()

results = earthaccess.search_data(
    short_name="M2T1NXAER",
    temporal=("2024-10-01", "2024-10-31"),
)

print(f"Granules encontrados: {len(results)}")
print(results[0])


results_slv = earthaccess.search_data(
    short_name="M2T1NXSLV",
    temporal=("2024-10-01", "2024-10-31"),
)

print(f"Granules encontrados: {len(results_slv)}")


#%%

ruta = Path("/home/inti/Desktop/research/uv-project2/data/raw/merra/BON")
ruta.mkdir(parents=True, exist_ok=True)

t0 = time.time()

files = earthaccess.download(
    results[0],
    local_path=str(ruta),
)

dt = time.time() - t0

print(f"Descarga terminada en {dt/60:.2f} minutos")
print(files)

#%%

archivo = files[0]

ds = xr.open_dataset(
    archivo,
    engine="h5netcdf"
)

print(ds)
print(ds.data_vars.keys())
#%%

ds_bon = ds[["TOTEXTTAU", "TOTANGSTR"]].sel(
    lat=40.05,
    lon=-88.37,
    method="nearest",
)

print(ds_bon)
print(ds_bon.to_dataframe())

print("Latitud solicitada:", 40.05)
print("Latitud MERRA:", float(ds_bon.lat))

print("Longitud solicitada:", -88.37)
print("Longitud MERRA:", float(ds_bon.lon))

#%%


url = (
    "https://data.gesdisc.earthdata.nasa.gov/"
    "opendap/MERRA2/M2T1NXAER.5.12.4/2024/10/"
    "MERRA2_400.tavg1_2d_aer_Nx.20241001.nc4.dap.nc4"
)

r = requests.get(url)

print(r.status_code)
print(r.headers.get("content-type"))
print(r.text[:500])

#%%
earthaccess.login()


print([x for x in dir(earthaccess) if "auth" in x.lower() or "session" in x.lower()])

#%%
session = earthaccess.get_requests_https_session()

r = session.get(url)

print(r.status_code)
print(r.headers.get("content-type"))
print(r.text[:500])

#%%
url = "https://disc.gsfc.nasa.gov/service/subset"

r = session.get(url)

print(r.status_code)
print(r.headers.get("content-type"))
print(r.text[:1000])


#%%

html = r.text

scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)', html)

for s in scripts:
    print(s)
    
#%%
    
    
js_url = "https://disc.gsfc.nasa.gov/scripts/app.js"

js = requests.get(js_url).text

# for match in re.finditer(r".{0,100}(?:subset|Subset).{0,200}", js):
#     print(match.group())
    
for line in js.splitlines():
    if "subset" in line.lower() and ("http" in line or "/api" in line):
        print(line[:500])
        
for match in re.finditer(r'.{0,300}subsetServices.{0,500}', js):
    print(match.group()[:1000])
    
start = js.find("service('subsetServices'")
end = js.find("angular.module", start + 20)

print(js[start:end][:10000])

for match in re.finditer(r'postServiceRequest.{0,500}', js):
    print(match.group()[:1000])
    
start = js.find("postServiceRequest = function")
print(js[start:start+4000])

#%%



url = "https://disc.gsfc.nasa.gov/service/subset/jsonwsp"

request = {
    "methodname": "subset",
    "type": "jsonwsp/request",
    "version": "1.0",
    "args": {
        "role": "subset",
        "start": "2024-10-01T00:00:00",
        "end": "2024-10-01T23:59:59",
        "box": [-88.38, 40.04, -88.37, 40.05],
        "crop": True,
        "mapping": "nearest",
        "data": [
            {
                "datasetId": "M2T1NXAER",
                "variable": "TOTEXTTAU"
            },
            {
                "datasetId": "M2T1NXAER",
                "variable": "TOTANGSTR"
            }
        ]
    }
}

r = requests.post(url, json=request)

print(r.status_code)
print(json.dumps(r.json(), indent=2)[:5000])

#%%

url = "https://disc.gsfc.nasa.gov/service/datasets/jsonwsp"

request = {
    "methodname": "getServiceCatalog",
    "type": "jsonwsp/request",
    "version": "1.0",
    "args": {}
}

r = requests.post(url, json=request)

print(r.status_code)
print(json.dumps(r.json(), indent=2)[:10000])

#%%

url = "https://disc.gsfc.nasa.gov/service/datasets/jsonwsp"

request = {
    "methodname": "search",
    "type": "jsonwsp/request",
    "version": "1.0",
    "args": {
        "search": "M2T1NXAER",
        "role": "subset",
        "fields": ["dataset", "shortName", "version", "cmrConceptId"]
    }
}

r = requests.post(url, json=request)

print(r.status_code)
print(json.dumps(r.json(), indent=2)[:10000])

#%%

url = "https://disc.gsfc.nasa.gov/service/subset/jsonwsp"

request = {
    "methodname": "subset",
    "type": "jsonwsp/request",
    "version": "1.0",
    "args": {
        "role": "subset",
        "start": "2024-10-01T00:00:00",
        "end": "2024-10-01T23:59:59",
        "box": [-88.38, 40.04, -88.37, 40.05],
        "crop": True,
        "mapping": "nearest",
        "data": [
            {
                "datasetId": "M2T1NXAER_5.12.4",
                "variable": "TOTEXTTAU"
            },
            {
                "datasetId": "M2T1NXAER_5.12.4",
                "variable": "TOTANGSTR"
            }
        ]
    }
}

r = requests.post(url, json=request)

print(r.status_code)
print(json.dumps(r.json(), indent=2)[:10000])

#%%

request = {
    "methodname": "GetStatus",
    "type": "jsonwsp/request",
    "version": "1.0",
    "args": {
        "jobId": "6a99bd15cc713ad3791641df",
        "sessionId": "6a99bd15cc713ad3791641dc"
    }
}

r = requests.post(url, json=request)

print(r.status_code)
print(json.dumps(r.json(), indent=2))

#%%

request = {
    "methodname": "GetResult",
    "type": "jsonwsp/request",
    "version": "1.0",
    "args": {
        "jobId": "6a99bd15cc713ad3791641df",
        "sessionId": "6a99bd15cc713ad3791641dc"
    }
}

r = requests.post(url, json=request)

print(r.status_code)
print(json.dumps(r.json(), indent=2)[:10000])

#%%

link = r.json()["result"]["items"][1]["link"]

ruta_salida = Path(
    "/home/inti/Desktop/research/uv-project2/data/raw/merra/BON"
)
ruta_salida.mkdir(parents=True, exist_ok=True)

archivo = ruta_salida / "MERRA2_400.tavg1_2d_aer_Nx.20241001.SUB.nc"

t0 = time.time()

rr = requests.get(link, stream=True)
rr.raise_for_status()

with open(archivo, "wb") as f:
    for chunk in rr.iter_content(chunk_size=1024 * 1024):
        if chunk:
            f.write(chunk)

print(f"Descargado en {(time.time() - t0):.2f} s")
print(f"Tamaño: {archivo.stat().st_size / 1024**2:.2f} MB")
print(archivo)

ds_sub = xr.open_dataset(archivo, engine="h5netcdf")

print(ds_sub)
print(ds_sub[["TOTEXTTAU", "TOTANGSTR"]].to_dataframe())

#%%

import src.merra2 as mr

archivo_slv = mr.merra_download_subset(
    dataset_id="M2T1NXSLV_5.12.4",
    variables=["TO3", "TQV"],
    start="2024-10-01T00:00:00",
    end="2024-10-01T23:59:59",
    bbox=[-88.38, 40.04, -88.37, 40.05],
    output_file=(
        "/home/inti/Desktop/research/uv-project2/"
        "data/raw/merra/BON/"
        "MERRA2_400.tavg1_2d_slv_Nx.20241001.SUB.nc"
    ),
)

print(archivo_slv)

ds_slv = xr.open_dataset(archivo_slv, engine="h5netcdf")

print(ds_slv)
print(ds_slv[["TO3", "TQV"]].to_dataframe())