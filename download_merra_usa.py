#!/usr/bin/env python3
"""Adquirir MERRA-2 horario nativo para todas las estaciones de STATIONS_USA."""

from pathlib import Path
from time import perf_counter

from config import STATIONS_USA
import src.merra as mr

start = "2021-01-01"
end = "2023-12-31"


def _duration(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours} h {minutes} min {seconds} s"


def main():
    root = Path(__file__).resolve().parent
    started = perf_counter()
    completed, failed = [], []
    for station_id, station in STATIONS_USA.items():
        print(f"\n=== {station_id} ({station['name']}) ===", flush=True)
        station_started = perf_counter()
        try:
            df = mr.process_merra(station, start, end)
            output_file = (root / "data/processed/merra" / station_id
                           / f"{station_id}_MERRA_{start}_{end}.csv")
            output_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_file)
        except Exception as exc:
            failed.append(station_id)
            print(f"ERROR en {station_id}: {exc}", flush=True)
        else:
            completed.append(station_id)
            print(f"{station_id} completada: {output_file.relative_to(root)}", flush=True)
            print(f"{station_id} completada en {_duration(perf_counter() - station_started)}", flush=True)

    print(f"\nEstaciones completadas ({len(completed)}): {', '.join(completed) or 'ninguna'}")
    print(f"Estaciones fallidas ({len(failed)}): {', '.join(failed) or 'ninguna'}")
    print(f"Tiempo total de ejecución: {_duration(perf_counter() - started)}")


if __name__ == "__main__":
    main()
