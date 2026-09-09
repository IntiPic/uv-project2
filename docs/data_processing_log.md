# Bitácora técnica del procesamiento

## 2026-09-09 — UV USA y decisiones MERRA-2

### UV USA

- Loader: `src.measurements.load_usa_uv(station_id, path)`, devuelve
  `(df, resolution)` con `resolution` igual a `f01` o `f05`.
- Ubicación: `data/USA/OUT/<tag>/<tag>_UVdata_f01.csv` o
  `<tag>_UVdata_f05.csv`. Los IDs se convierten a minúscula para construir
  las rutas. Se reconoce también el sufijo `F01` presente en BRW y MSN.
- Se prefiere `f01`; `f05` es el fallback. Se conserva la resolución
  observacional original, sin interpolar `f05` a 1 minuto.
- Selección según los archivos actuales:
  - `f01`: ABQ, BIS, BRW, FPK, HNX, MSN, SEA, TBL.
  - `f05`: BON, DRA, PSU, SLC, STE, SXF.
- Los CSV están separados por comas. La primera columna, sin nombre,
  contiene timestamps `YYYY-MM-DD HH:MM:SS`, sin offset escrito.
- Según la verificación de documentación NOAA comunicada por el usuario,
  los timestamps diarios de SURFRAD y SOLRAD representan UTC. El loader
  aplica `tz_localize("UTC")`, sin cambiar las horas numéricamente ni
  convertirlas a la zona local de la estación.
- Columna medida: `UVB`. Se conserva ese nombre sin reinterpretar su
  significado espectral. Los CSV no declaran unidades; no se convierten.
- Columnas `f01`: `CZA,GHI,QCghi,UVB,QCuvb,UVT,O3`.
- Columnas `f05`: `GHI,UVB,O3,MSK,CZA,Kt,Ma`.
- Los campos vacíos se leen como `NaN`. El valor `-9.9999` todavía se
  conserva sin reinterpretar. Los flags se conservan sin aplicar filtros.
- BRW y MSN tienen actualmente `UVB` completamente igual a `-9.9999`.
  Algunas estaciones no cubren todo 2021–2023.
- En este refactor todavía no se aplicó QC ni agregación temporal.

### MERRA-2

- `process_merra()` devuelve resolución horaria nativa de los productos
  `tavg1`, con timestamps centrados en `:30`.
- Decisión de interpretación temporal: el valor de `10:30` se interpretará
  como representativo del intervalo `[10:00, 11:00)`. Esta entrada documenta
  la decisión; no implementa agregación ni cambia timestamps.
- La adquisición productiva usa bloques mensuales con fallback diario.
- Se conserva la selección espacial `nearest`.
- `process_merra_1min()` conserva la implementación interpolada anterior
  para análisis de sensibilidad.


## 2026-09-09 — Inspección QC UV USA y limpieza mínima

Esta entrada actualiza la decisión anterior de conservar `-9.9999`:
por instrucción metodológica del usuario se trata como código de dato UVB
faltante, no como una medición, y se convierte a `NaN` antes de cualquier
agregación. `load_usa_uv()` sigue conservando el CSV tal como se carga;
`clean_usa_uv(df, resolution)` aplica esta transformación explícitamente
sobre una copia y únicamente en `UVB`. No cambia otros negativos, flags,
columnas, filas, orden, índice UTC ni resolución. No interpola ni rellena.

Se inspeccionaron íntegramente los 20 CSV f01/f05 disponibles de las 14
estaciones, incluidos los f05 no seleccionados cuando existe f01. Las
frecuencias siguientes son conteos absolutos sobre todo el archivo, antes
de limpiar. No hay flags nulos ni valores distintos de `True`/`False`.

### f01 — QCuvb

| Estación | Filas | True | False | UVB=-9.9999 | UVB NaN | Otros UVB negativos |
|---|---:|---:|---:|---:|---:|---:|
| ABQ | 1451103 | 1450593 | 510 | 510 | 0 | 231 |
| BIS | 1237109 | 1236118 | 991 | 991 | 0 | 35 |
| BRW | 1576800 | 0 | 1576800 | 1576800 | 0 | 0 |
| FPK | 1569998 | 1533230 | 36768 | 8001 | 0 | 45 |
| HNX | 1572039 | 1571498 | 541 | 541 | 0 | 0 |
| MSN | 1573862 | 0 | 1573862 | 1573862 | 0 | 0 |
| SEA | 867573 | 324432 | 543141 | 15094 | 0 | 0 |
| TBL | 1569490 | 1566227 | 3263 | 3256 | 0 | 2 |

Todos los `-9.9999` tienen `QCuvb=False`, pero la equivalencia inversa
no se cumple: FPK tiene 28767 valores no faltantes con `False`, TBL 7 y
SEA 528047. En ABQ, BIS y HNX, los `False` coinciden exactamente con el
sentinel; en BRW y MSN toda la serie es sentinel y `False`.

Otros negativos observados: ABQ tiene 229 valores `-0.0001` y 2 `-0.0002`;
BIS, 35 valores `-0.0001`; FPK, 28 valores `-0.0001` y 17 `-0.0002`;
TBL, 2 valores `-0.0001`. No se identificó documentación que permita
clasificarlos como otros sentinels: se conservan sin reinterpretar.

### f05 — MSK

| Estación | Filas | True | False | UVB=-9.9999 | UVB NaN | UVB no faltante con False |
|---|---:|---:|---:|---:|---:|---:|
| ABQ | 291168 | 123536 | 167632 | 0 | 165061 | 2571 |
| BIS | 247968 | 98855 | 149113 | 0 | 147435 | 1678 |
| BON | 315361 | 129442 | 185919 | 0 | 182728 | 3191 |
| DRA | 315360 | 132010 | 183350 | 0 | 181081 | 2269 |
| FPK | 315360 | 122825 | 192535 | 0 | 190381 | 2154 |
| HNX | 315360 | 131370 | 183990 | 0 | 182216 | 1774 |
| PSU | 315360 | 128479 | 186881 | 0 | 184081 | 2800 |
| SEA | 206571 | 29275 | 177296 | 0 | 174840 | 2456 |
| SLC | 315360 | 129943 | 185417 | 0 | 183064 | 2353 |
| STE | 315360 | 130973 | 184387 | 0 | 181756 | 2631 |
| SXF | 315360 | 127669 | 187691 | 0 | 185718 | 1973 |
| TBL | 315360 | 128921 | 186439 | 0 | 183724 | 2715 |

No aparecen UVB negativos en f05. Todos los UVB `NaN` tienen `MSK=False`,
pero todas las estaciones también tienen valores no faltantes con
`MSK=False`. Por tanto, la máscara no equivale simplemente a presencia
o ausencia de UVB.

### Decisiones pendientes y BRW/MSN

No se aplican filtros basados en `QCuvb`, `MSK` ni `QCghi`. La inspección
del código y los documentos de texto del repositorio no encontró una
definición inequívoca de estos flags. Los archivos `QC/*QC_filter_results`
resumen etapas N1–N4 y los CSV `QC_Filters` contienen F0–F4, pero no
explican por sí solos cómo se construyeron `QCuvb` o `MSK`. Las asociaciones
observadas arriba no se toman como definición ni como criterio de filtrado.
«No faltante» tampoco implica haber superado un control de calidad.

Después de limpiar, BRW queda con 1576800 UVB NaN y MSN con 1573862:
ambas tienen **cero valores UVB no faltantes** en sus archivos disponibles.
Se mantienen en `STATIONS_USA`.

No se implementó QC por flags, agregación horaria, alineación MERRA+UV,
LUT ni validación en esta etapa.

## 2026-09-09 — Asociación temporal UV USA–MERRA

- Función: `src.measurements.match_usa_uv_merra(df_uv, df_merra)`.
- Ambos índices deben ser `DatetimeIndex` timezone-aware en UTC. Se rechazan
  índices naive, de otras zonas o con NaT; no se convierten implícitamente.
  `process_merra()` conserva la zona local de la estación: su salida debe
  convertirse explícitamente a UTC por el llamador antes de esta asociación.
- MERRA `tavg1` en `HH:30` representa `[HH:00, HH+1:00)`. Cada observación
  UV se asocia exactamente a `df_uv.index.floor("h") + 30 minutos`.
  La regla es la misma para f01 y f05, incluido el cruce de día.
- Se agregan `o3`, `wv`, `aod`, `alpha`, repetidas dentro de cada hora,
  sin interpolación ni búsqueda temporal nearest. Se exigen registros MERRA
  únicos centrados exactamente en `HH:30:00`.
- Se conservan todas las filas, timestamps, columnas y flags UV, también
  las observaciones con UVB NaN. Las colisiones de nombres se rechazan
  para no sobrescribir columnas UV existentes.
- Una hora MERRA ausente deja sus cuatro variables como NaN. Se imprime el
  número de observaciones sin registro asociado y se conserva en
  `result.attrs["merra_unmatched_count"]`. Se cuenta ausencia de registro,
  no NaN en un registro MERRA existente.
- Esta asociación precede a SZA/LUT y a la agregación horaria. Ninguna de
  esas etapas se implementa en este cambio.

## 2026-09-09 — Cielo claro USA a resolución observacional

- Función: `src.clearsky.add_usa_clearsky(df, station)`. Entorno comprobado:
  pvlib **0.15.1** (`/home/inti/anaconda3/envs/spyder-env/bin/python`).
- Conserva columnas originales, UVB, GHI, flags, filas e índice UTC; agrega
  únicamente `sza`, `ghi_clear`, `clear_sky` (booleana). No usa CAMS,
  no aplica filtro SZA y no evalúa LUT ni agrega horas.
- Posición solar: `pvlib.solarposition.get_solarposition`, usando latitud,
  longitud y elevación de la estación en cada timestamp observacional.
  `sza` es `zenith` (geométrico), la misma columna usada en `src/merra.py`,
  no `apparent_zenith`. Se conservan los demás defaults de posición solar.
- Referencia: `Location.get_clearsky(model="ineichen", solar_position=solar)`.
  El modelo estándar usa internamente `apparent_zenith`, masa de aire y
  presión estimada a partir de la elevación; esto no redefine `sza`.
- Linke turbidity: búsqueda estándar en `pvlib/data/LinkeTurbidities.h5`,
  climatología de promedios mensuales, seleccionada por latitud/longitud.
  pvlib divide los valores almacenados por 20 y, por defecto
  `interp_turbidity=True`, interpola los valores mensuales a valores diarios
  según el día del año UTC. No es turbidez observada ni tomada de CAMS.
  Esta interpolación interna de climatología no interpola GHI observada.

### Metodologías diferenciadas por cadencia

Se usa `pvlib.clearsky.detect_clearsky`, con `times=df.index`.

| Parámetro | f01: Reno–Hansen defaults | f05: Jordan–Hansen, inferidos por pvlib |
|---|---:|---:|
| `infer_limits` | False | True |
| `window_length` (min) | 10 | 60 |
| `mean_diff` | 75 | 75 |
| `max_diff` | 75 | 65 |
| `lower_line_length` | -5 | -45 |
| `upper_line_length` | 10 | 80 |
| `var_diff` | 0.005 | 0.01 |
| `slope_dev` | 8 | 60 |
| `max_iterations` | 20 | 20 |
| `return_components` | False | False |

Los defaults originales son adecuados para ventanas de 10 min con datos
minutales. En f05 sólo darían 2 muestras y pvlib exige al menos 3.
El usuario autorizó explícitamente `infer_limits=True` para f05: pvlib
sustituye ventana y umbrales por los derivados de Jordan–Hansen (2023),
Tabla 1. Los valores de la tabla corresponden a la versión instalada;
f05 permanece en intervalos de 5 min, sin conversión a f01. Para f01 los
parámetros originales se pasan explícitamente. El algoritmo puede escalar
internamente la referencia para la clasificación; `ghi_clear` conserva la
GHI original de Ineichen, sin ese escalado.

### GHI y limitaciones

- Se inspeccionaron los 20 CSV f01/f05 disponibles. Los f01 contienen
  `GHI=-9999.9` y otros valores negativos pequeños. No se encontraron
  `GHI=-9.9999`, `-9999`, `-999` ni `-99.99`. Los f05 contienen campos
  vacíos/NaN y no muestran GHI negativa en los archivos inspeccionados.
- `-9999.9` es un código faltante reconocido por el lector SURFRAD de pvlib;
  se trata como NaN sólo en la serie entregada al detector. No se modifica
  la GHI original, no se recortan otros negativos ni se usan `QCghi`,
  `QCuvb` o `MSK` para filtrar.
- Ineichen y el detector trabajan en W/m²: la función requiere GHI en esas
  unidades y no aplica conversiones. Los CSV procesados no declaran unidades
  en sus cabeceras; no se infiere una conversión a partir de su magnitud.
- El detector requiere una serie equiespaciada: se rechazan índices con
  huecos, duplicados, desorden o zona distinta de UTC. No se rellenan huecos
  ni se elige una política de segmentación. Se requieren al menos 10 muestras
  f01 o 12 muestras f05 para cubrir una ventana. Algunas series f01 completas
  tienen huecos; su tratamiento sigue pendiente.
- `clear_sky=False` expresa ausencia de identificación como cielo claro,
  no una afirmación de nubosidad cuando falta GHI.
- No se decide ninguna proporción de muestras claras por hora.

Prueba visual: `plot_usa_clearsky.py`, ABQ f01 y BON f05 del 1 al 3 de junio
2021, con GHI observada, referencia Ineichen y puntos clasificados claros.
Salidas: `out/fig/usa_clearsky_ABQ_20210601_20210603.png` y
`out/fig/usa_clearsky_BON_20210601_20210603.png`.

Fuentes de implementación:
[pvlib detect_clearsky y umbrales](https://pvlib-python.readthedocs.io/en/latest/_modules/pvlib/clearsky.html),
[modelos de cielo claro y turbidez](https://pvlib-python.readthedocs.io/en/latest/user_guide/modeling_topics/clearsky.html),
[lector SURFRAD y sentinel](https://pvlib-python.readthedocs.io/en/v0.10.5/_modules/pvlib/iotools/surfrad.html).
La firma y los valores numéricos se comprobaron también en el código local 0.15.1.

## 2026-09-09 — Primera validación USA: aproximación instrumental provisional

`validate_usa.py` usa provisionalmente **YES UVB-1 ≈ irradiancia eritémica
McKinlay–Diffey integrada entre 280 y 320 nm**. Reutiliza `integrate_lut`
con `erythemal=True` y límites explícitos; no usa una variable UVE previamente
integrada ni una integral UVB sin ponderación. Conserva la conversión espectral
mW→W (/1000) de `load_lut_spectral`, aplicada después de seleccionar la banda
para evitar cargar toda la LUT. La integral final se expresa en W/m² según
la convención existente del proyecto. La respuesta espectral instrumental
exacta queda pendiente.

## 2026-09-09 — Regularización explícita de gaps UV USA

`regularize_usa_uv(df, resolution)` reindexa entre el primer y último
registro sobre una grilla UTC continua: 1 min para f01, 5 min para f05.
Conserva los valores existentes y crea filas NaN en todas las columnas
(incluidos flags) donde faltan timestamps. No interpola, rellena valores
ni segmenta por gaps. Rechaza duplicados y timestamps fuera de la grilla
para evitar pérdida silenciosa de observaciones.

`validate_usa.py` la aplica tras limpiar y recortar el período, antes de
`add_usa_clearsky()`. Esta última ya admite GHI NaN en una grilla regular:
no necesitó cambios. Se mantienen Reno–Hansen original para f01 e
`infer_limits=True` para f05. Esto resuelve la limitación de gaps descrita
anteriormente sin cambiar LUT, MERRA ni agregación horaria.
