# import os
# import math
# import time
# from pathlib import Path
# from concurrent.futures import ThreadPoolExecutor, as_completed

# import pandas as pd
# import requests
# from tqdm import tqdm


# MAPBOX_TOKEN = "pk.eyJ1IjoiYXl1dXNoaHNoIiwiYSI6ImNtanoyd3Y4bTYzYXMzZnM1eTc4YWVwbHEifQ.CW6_GKnBSfcjvhkZVY-AvQ"
# MAPBOX_BASE = "https://api.mapbox.com/styles/v1"
# MAPBOX_OWNER = "mapbox"
# MAPBOX_STYLE = "satellite-v9"

# ZOOM = 18
# WIDTH = 512
# HEIGHT = 512

# # Tune these:
# MAX_WORKERS = 24           # increase for more concurrency (try 16/24/32)
# TIMEOUT_S = 30
# MAX_RETRIES = 6
# BACKOFF_BASE = 0.6         # exponential backoff base (seconds)
# POOL_MAXSIZE = 64          # connection pool size for requests Session


# def build_mapbox_url(lon: float, lat: float, zoom: int = ZOOM, w: int = WIDTH, h: int = HEIGHT) -> str:
#     return (
#         f"{MAPBOX_BASE}/{MAPBOX_OWNER}/{MAPBOX_STYLE}/static/"
#         f"{lon:.6f},{lat:.6f},{zoom}/{w}x{h}"
#         f"?access_token={MAPBOX_TOKEN}"
#     )


# def _safe_float(x):
#     try:
#         return float(x)
#     except Exception:
#         return math.nan


# def make_session():
#     # requests.Session enables connection pooling / keep-alive which improves performance
#     # when making many requests to the same host. [web:84][web:90]
#     s = requests.Session()
#     adapter = requests.adapters.HTTPAdapter(pool_connections=POOL_MAXSIZE, pool_maxsize=POOL_MAXSIZE)
#     s.mount("https://", adapter)
#     s.mount("http://", adapter)
#     return s


# def download_with_retries(session: requests.Session, url: str, out_path: Path):
#     out_path.parent.mkdir(parents=True, exist_ok=True)

#     for attempt in range(MAX_RETRIES):
#         try:
#             r = session.get(url, timeout=TIMEOUT_S)
#             if r.status_code == 200:
#                 out_path.write_bytes(r.content)
#                 return None
#             if r.status_code == 429:
#                 # Mapbox rate limit: throttled requests return 429; back off and retry. [web:82]
#                 sleep_s = BACKOFF_BASE * (2 ** attempt)
#                 time.sleep(sleep_s)
#                 continue
#             if 500 <= r.status_code < 600:
#                 sleep_s = BACKOFF_BASE * (2 ** attempt)
#                 time.sleep(sleep_s)
#                 continue

#             return f"HTTP {r.status_code}: {r.text[:200]}"
#         except Exception as e:
#             sleep_s = BACKOFF_BASE * (2 ** attempt)
#             time.sleep(sleep_s)

#     return "max_retries_exceeded"


# def fetch_split(df: pd.DataFrame, out_dir: str, id_col="id", lat_col="lat", lon_col="long", max_rows=None):
#     if not MAPBOX_TOKEN:
#         raise RuntimeError("Missing MAPBOX_TOKEN env var. Export it first.")

#     if max_rows is not None:
#         df = df.head(max_rows)

#     out_dir = Path(out_dir)
#     out_dir.mkdir(parents=True, exist_ok=True)

#     # Build tasks, skipping cached images
#     tasks = []
#     for _, row in df.iterrows():
#         pid = str(row[id_col])
#         lat = _safe_float(row[lat_col])
#         lon = _safe_float(row[lon_col])
#         if math.isnan(lat) or math.isnan(lon):
#             tasks.append((pid, None, None, "nan_latlon"))
#             continue

#         out_path = out_dir / f"{pid}.png"
#         if out_path.exists():
#             continue

#         url = build_mapbox_url(lon=lon, lat=lat)
#         tasks.append((pid, url, out_path, None))

#     failures = []

#     session = make_session()
#     # Threading helps because this workload is network-bound. [web:84]
#     with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
#         future_map = {}
#         for pid, url, out_path, pre_err in tasks:
#             if pre_err:
#                 failures.append((pid, pre_err))
#                 continue
#             future = ex.submit(download_with_retries, session, url, out_path)
#             future_map[future] = pid

#         for fut in tqdm(as_completed(future_map), total=len(future_map)):
#             pid = future_map[fut]
#             err = fut.result()
#             if err:
#                 failures.append((pid, err))

#     if failures:
#         pd.DataFrame(failures, columns=["id", "error"]).to_csv(out_dir / "_failures.csv", index=False)


# def main():
#     train_df = pd.read_csv("data/train(1).csv", dtype={"id": "string"})
#     test_df  = pd.read_csv("data/test2.csv",   dtype={"id": "string"})

#     fetch_split(train_df, "data/images/train")
#     fetch_split(test_df,  "data/images/test")


# if __name__ == "__main__":
#     main()


import os
import math
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from tqdm import tqdm


# ---------- Config ----------
MAPBOX_TOKEN = "pk.eyJ1IjoiYXl1dXNoaHNoIiwiYSI6ImNtanoyd3Y4bTYzYXMzZnM1eTc4YWVwbHEifQ.CW6_GKnBSfcjvhkZVY-AvQ"
MAPBOX_BASE = "https://api.mapbox.com/styles/v1"
MAPBOX_OWNER = "mapbox"
MAPBOX_STYLE = "satellite-v9"

ZOOM = 18
WIDTH = 256
HEIGHT = 256

MAX_WORKERS = 24
TIMEOUT_S = 30
MAX_RETRIES = 6
BACKOFF_BASE = 0.6
POOL_MAXSIZE = 64

SAVE_SAMPLE_URLS = True
SAMPLE_N = 50


# ---------- Mapbox URL ----------
def build_mapbox_url(lon: float, lat: float) -> str:
    # Many Mapbox web APIs use longitude,latitude ordering. [web:105]
    return (
        f"{MAPBOX_BASE}/{MAPBOX_OWNER}/{MAPBOX_STYLE}/static/"
        f"{lon:.6f},{lat:.6f},{ZOOM}/{WIDTH}x{HEIGHT}"
        f"?access_token={MAPBOX_TOKEN}"
    )


# ---------- Helpers ----------
def make_session():
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=POOL_MAXSIZE, pool_maxsize=POOL_MAXSIZE)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def _to_float(x):
    try:
        return float(str(x).strip())
    except Exception:
        return math.nan


def _valid_lat(lat):  # [-90, 90]
    return not math.isnan(lat) and (-90.0 <= lat <= 90.0)


def _valid_lon(lon):  # [-180, 180]
    return not math.isnan(lon) and (-180.0 <= lon <= 180.0)


def download_with_retries(session: requests.Session, url: str, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, timeout=TIMEOUT_S)
            if r.status_code == 200:
                out_path.write_bytes(r.content)
                return None

            # 429 => backoff
            if r.status_code == 429:
                time.sleep(BACKOFF_BASE * (2 ** attempt))
                continue

            # 5xx => backoff
            if 500 <= r.status_code < 600:
                time.sleep(BACKOFF_BASE * (2 ** attempt))
                continue

            return f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            time.sleep(BACKOFF_BASE * (2 ** attempt))

    return "max_retries_exceeded"


def read_minimal_csv(path: str):
    # Only read exactly what we need: id, lat, long (prevents “messing up”). [web:112]
    return pd.read_csv(
        path,
        usecols=["id", "lat", "long"],
        dtype={"id": "string"},  # avoid 12345 -> 12345.0 filenames
    )


def fetch_from_csv(csv_path: str, out_dir: str):
    if not MAPBOX_TOKEN:
        raise RuntimeError("Missing MAPBOX_TOKEN env var. Export it first.")

    df = read_minimal_csv(csv_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = []
    failures = []
    sample_rows = []

    for _, row in df.iterrows():
        pid = str(row["id"])
        lat = _to_float(row["lat"])
        lon = _to_float(row["long"])

        if not _valid_lat(lat) or not _valid_lon(lon):
            failures.append((pid, f"bad_range lat={row['lat']} long={row['long']}"))
            continue

        out_path = out_dir / f"{pid}.png"
        if out_path.exists():
            continue

        url = build_mapbox_url(lon=lon, lat=lat)
        tasks.append((pid, url, out_path))

        if SAVE_SAMPLE_URLS and len(sample_rows) < SAMPLE_N:
            sample_rows.append({"id": pid, "lat": lat, "lon": lon, "url": url})

    if SAVE_SAMPLE_URLS and sample_rows:
        pd.DataFrame(sample_rows).to_csv(out_dir / "sample_urls.csv", index=False)

    session = make_session()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        fut_map = {ex.submit(download_with_retries, session, url, out_path): pid for pid, url, out_path in tasks}
        for fut in tqdm(as_completed(fut_map), total=len(fut_map)):
            pid = fut_map[fut]
            err = fut.result()
            if err:
                failures.append((pid, err))

    if failures:
        pd.DataFrame(failures, columns=["id", "error"]).to_csv(out_dir / "_failures.csv", index=False)


def main():
    fetch_from_csv("data/train(1).csv", "data/images/train")
    fetch_from_csv("data/test2.csv", "data/images/test")


if __name__ == "__main__":
    main()
