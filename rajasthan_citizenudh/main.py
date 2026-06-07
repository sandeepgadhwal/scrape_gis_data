import pandas as pd
import geopandas as gpd
import json
from pathlib import Path
import requests
from scrape_lib import *
from tqdm import tqdm



SERVICES_URL = "https://gisprod.rajasthan.gov.in/geocode/rest/services"
OUTPUT_DIR = Path(__file__).parent / "output"
CACHE_DIR = Path(__file__).parent / "scrape_cache"

def get_token(session: requests.Session) -> dict[str, str]:
    token_url = "https://rajdharaa.rajasthan.gov.in/RajdharaaCommonWebAPI/api/GenerateGISToken"
    r = session.post(token_url)
    tokens = {}
    for service in r.json()["Messages"]:
        tokens[service["ServiceName"]] = service["Token"]
    return tokens

def get_layers_metadata(session: requests.Session, map_servers: list[tuple[str, str, bool]]) -> list[dict]:
    metadata_list = []
    for mapserver, token, count_rows in tqdm(map_servers, desc="Preparing metadata for map servers"):
        mapserver_url = f"{SERVICES_URL}/{mapserver}/MapServer"
        params = {
            "f": "json",
            "token": token
        }
        r = session.get(mapserver_url, params=params)
        mapserver_metadata = r.json()
        for layer in mapserver_metadata["layers"]:
            id = layer["id"]
            query_url = f"{mapserver_url}/{id}/query"
            metadata = {
                'query_url': query_url,
                'name': layer["name"],
                'mapserver': mapserver,
                'max_record_count': mapserver_metadata["maxRecordCount"],
                "token": token,
                'count_rows': count_rows
            }
            metadata_list.append(metadata)
    return metadata_list


def get_layer_count(session: requests.Session, query_url: str, token: str) -> int:
    params = {
        'where': '1=1',
        "f": "json",
        "token": token,
        "returnCountOnly": "true"
    }
    r = session.get(query_url, params=params)
    return r.json()["count"]


def scrape_layer(session: requests.Session, metadata: dict) -> None:
    output_layer_path = OUTPUT_DIR / metadata['mapserver'] / f"{metadata['name']}.gpkg"
    if output_layer_path.exists():
        print(f"Layer {metadata['name']} already scraped. Skipping.")
        return

    if metadata["count_rows"]:
        total_count = get_layer_count(session, metadata["query_url"], metadata["token"])
    else:
        total_count = int(1e9) # scrape all rows without counting first
    layer_cache_path = CACHE_DIR / metadata['mapserver'] / metadata['name']
    layer_cache_path.mkdir(parents=True, exist_ok=True)
    query_url = metadata["query_url"]
    result_offset = 0
    max_record_count = min(10, metadata["max_record_count"])
    params =  {
        'where': '1=1',
        "f": "json",
        "token": metadata["token"],
        "resultOffset": result_offset,
        "resultRecordCount": max_record_count,
        "returnCountOnly": "false",
        "outFields": "*"
    }
    df_store = []
    for result_offset in tqdm(range(0, total_count, max_record_count), desc=f"Scraping layer {metadata['name']}"):
        params["resultOffset"] = result_offset
        cache_path = layer_cache_path / f"{metadata['name']}_{result_offset}_{result_offset + max_record_count}.json"
        if not cache_path.exists():
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            r = session.get(query_url, params=params)
            json_response = r.json()
            with open(cache_path, "w") as f:
                json.dump(json_response, f)
    
        df = gpd.read_file(cache_path)
        if len(df) == 0:
            print(f"No more data to scrape for layer {metadata['name']}. Stopping. Total rows scraped: {len(df_store)*max_record_count}")
            break
        df_store.append(df)
    if len(df_store) == 0:
        print(f"No data scraped for layer {metadata['name']}. Skipping.")
        return
    gdf = gpd.GeoDataFrame(
        pd.concat(df_store, ignore_index=True), 
        crs=df_store[0].crs
    )
    output_layer_path.parent.mkdir(parents=True, exist_ok=True)
    _ = gdf.sindex.geometries
    # gdf.to_parquet(output_layer_path.with_suffix(".parquet"), index=False)
    gdf.to_file(output_layer_path, index=False)


def main():
    session = requests.Session()
    # home_url = "https://rajdharaa.rajasthan.gov.in/citizenudh/"
    # r = session.get(home_url)
    # with open("home.html", "wb") as f:
    #     f.write(r.content)
    tokens = get_token(session)
    # Scrape map servers
    map_servers = [
        ("JDA/CCZM", tokens["geocode"], True),
        ("JDA/InstitutionalAllotment", tokens["geocode"], True),
        ("JDA/MasterDevelopmentPlan", tokens["geocode"], True),
        ("JDA/MasterDevelopmentPlanDraft", tokens["geocode"], True),
        ("JDA/Settlement_JDA", tokens["geocode"], False),
        ("JDA/JDA_Plots", tokens["geocode"], True),
    ]
    layers_metadata = get_layers_metadata(session, map_servers)

    for layer_metdata in tqdm(layers_metadata, desc="Scrape layers"):
        scrape_layer(session, layer_metdata)   
    


if __name__ == "__main__":
    main()
