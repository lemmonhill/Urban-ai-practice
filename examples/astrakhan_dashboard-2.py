from __future__ import annotations

import json
import math
from pathlib import Path

import geopandas as gpd
import pandas as pd

TITLE = "Астрахань"
OUTPUT_NAME = "dashboard.html"


def find_data_dir() -> Path:
    candidates = []
    for base in [Path.cwd(), *Path.cwd().parents]:
        candidates.extend(
            [
                base / "examples" / "data" / "astrakhan",
                base / "data" / "astrakhan",
                base / "examples" / "data",
                base / "data",
            ]
        )
    for path in candidates:
        if (path / "blocks_indicators.geojson").exists():
            return path
    raise FileNotFoundError(
        "Не найден blocks_indicators.geojson. Запустите скрипт из корня проекта."
    )


DATA_DIR = find_data_dir()
OUTPUT_PATH = Path.cwd() / OUTPUT_NAME


def read_geojson(name: str) -> gpd.GeoDataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Отсутствует обязательный файл: {path}")
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(32639)
    return gdf.to_crs(4326)


def read_optional_geojson(name: str) -> gpd.GeoDataFrame | None:
    path = DATA_DIR / name
    if not path.exists():
        return None
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs(32639)
    return gdf.to_crs(4326)


def clean_value(value):
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "item"):
        try:
            return clean_value(value.item())
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(k): clean_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_value(v) for v in value]
    return value


def gdf_to_geojson(gdf: gpd.GeoDataFrame) -> dict:
    gdf = gdf.copy()
    for column in gdf.columns:
        if column == "geometry":
            continue
        if pd.api.types.is_datetime64_any_dtype(gdf[column]):
            gdf[column] = gdf[column].astype(str)
        elif pd.api.types.is_object_dtype(gdf[column]):
            gdf[column] = gdf[column].map(clean_value)
    return json.loads(gdf.to_json(drop_id=True))


def round_coordinates(obj, precision: int = 6):
    if isinstance(obj, (list, tuple)):
        if obj and all(isinstance(x, (int, float)) for x in obj):
            return [round(float(x), precision) for x in obj]
        return [round_coordinates(x, precision) for x in obj]
    if isinstance(obj, dict):
        return {k: round_coordinates(v, precision) for k, v in obj.items()}
    return obj


def dataframe_records(df: pd.DataFrame, max_rows: int | None = None) -> list[dict]:
    out = df.head(max_rows).copy() if max_rows is not None else df.copy()
    out = out.where(pd.notna(out), None)
    return [
        {str(k): clean_value(v) for k, v in row.items()}
        for row in out.to_dict(orient="records")
    ]


print(f"Папка с данными: {DATA_DIR.resolve()}")

blocks = read_geojson("blocks_indicators.geojson")
boundaries = read_optional_geojson("boundaries.geojson")
hospitals = read_optional_geojson("hospitals.geojson")
polyclinics = read_optional_geojson("polyclinics.geojson")

blocks["block_id"] = blocks.index.astype(str)
blocks["area_ha"] = (blocks.to_crs(32639).area / 10000.0).astype(float)

numeric_fields = [
    "population_calibrated",
    "fsi",
    "gsi",
    "mxi",
    "l",
    "osr",
    "share_living",
    "share_non_living",
    "area_accessibility",
    "hospital_count",
    "polyclinic_count",
    "hospital_provision_strong",
    "polyclinic_provision_strong",
]
categorical_fields = ["land_use", "spacematrix_morphotype", "strelka_morphotype"]

for field in numeric_fields:
    if field in blocks.columns:
        blocks[field] = pd.to_numeric(blocks[field], errors="coerce")

land_use_ru = {
    "residential": "жилая",
    "business": "деловая",
    "recreation": "рекреационная",
    "industrial": "промышленная",
    "transport": "транспортная",
    "special": "специального назначения",
    "agriculture": "сельскохозяйственная",
}
spacematrix_ru = {
    "low-rise low-density residential": "малоэтажная низкоплотная жилая",
    "mid-rise low-density residential": "среднеэтажная низкоплотная жилая",
    "low-rise low-density non-residential": "малоэтажная низкоплотная нежилая",
    "high-mid-rise residential": "жилая средней и повышенной этажности",
    "mid-rise low-density mixed-use": "среднеэтажная низкоплотная смешанная",
    "mid-rise non-residential": "среднеэтажная нежилая",
    "tower high-density non-residential": "высотная высокоплотная нежилая",
    "tower residential": "высотная жилая",
    "high-rise high-density residential": "многоэтажная высокоплотная жилая",
}
strelka_ru = {
    "central model": "плотная среднеэтажная жилая застройка",
    "high-rise modern microdistrict": "высотный современный микрорайон",
    "high-rise non-residential": "высотная нежилая застройка",
    "high-rise soviet microdistrict": "высотный советский микрорайон",
    "individual residential": "индивидуальная жилая застройка",
    "low-rise model": "малоэтажная застройка",
    "low-rise non-residential": "малоэтажная нежилая застройка",
    "mid-rise": "среднеэтажная застройка",
    "mid-rise block": "среднеэтажный квартал",
    "mid-rise microdistrict": "среднеэтажный микрорайон",
    "mid-rise non-residential": "среднеэтажная нежилая застройка",
}

blocks["land_use"] = blocks["land_use"].map(
    lambda value: land_use_ru.get(str(value), value) if pd.notna(value) else value
)
blocks["spacematrix_morphotype"] = blocks["spacematrix_morphotype"].map(
    lambda value: spacematrix_ru.get(str(value), value) if pd.notna(value) else value
)
blocks["strelka_morphotype"] = blocks["strelka_morphotype"].map(
    lambda value: strelka_ru.get(str(value), value) if pd.notna(value) else value
)

population_total = float(blocks.get("population", pd.Series(dtype=float)).sum())
blocks_total = int(len(blocks))
living_blocks = int((blocks["population_calibrated"].fillna(0) > 0).sum())
hospital_blocks = int((blocks["hospital_count"].fillna(0) > 0).sum())
polyclinic_blocks = int((blocks["polyclinic_count"].fillna(0) > 0).sum())
service_blocks = int(
    ((blocks["hospital_count"].fillna(0) > 0) | (blocks["polyclinic_count"].fillna(0) > 0)).sum()
)
city_area_ha = (
    float(boundaries.to_crs(32639).area.sum() / 10000.0)
    if boundaries is not None
    else float(blocks["area_ha"].sum())
)
accessibility_mean = float(blocks["area_accessibility"].mean())

hospital_provision_share = float(
    (pd.to_numeric(blocks["hospital_provision_strong"], errors="coerce").dropna() > 0).mean() * 100
)
polyclinic_provision_share = float(
    (pd.to_numeric(blocks["polyclinic_provision_strong"], errors="coerce").dropna() > 0).mean() * 100
)

landuse_counts = blocks["land_use"].fillna("нет данных").value_counts(dropna=False).head(20)
spacematrix_counts = (
    blocks["spacematrix_morphotype"].fillna("нет застройки").value_counts(dropna=False).head(12)
)
strelka_counts = (
    blocks["strelka_morphotype"].fillna("нет застройки").value_counts(dropna=False).head(12)
)

map_columns = [
    c
    for c in [
        "block_id",
        "area_ha",
        "land_use",
        "population_calibrated",
        "fsi",
        "gsi",
        "mxi",
        "l",
        "osr",
        "share_living",
        "area_accessibility",
        "hospital_count",
        "polyclinic_count",
        "hospital_provision_strong",
        "polyclinic_provision_strong",
        "spacematrix_morphotype",
        "strelka_morphotype",
    ]
    if c in blocks.columns
]

blocks_map = blocks[["geometry", *map_columns]].copy()
try:
    blocks_map["geometry"] = blocks_map.geometry.simplify(0.00005, preserve_topology=True)
except Exception as exc:
    print(f"Не удалось упростить геометрию кварталов: {exc}")

blocks_geojson = round_coordinates(gdf_to_geojson(blocks_map))
boundaries_geojson = (
    round_coordinates(gdf_to_geojson(boundaries[["geometry"]])) if boundaries is not None else None
)
hospitals_geojson = (
    round_coordinates(gdf_to_geojson(hospitals)) if hospitals is not None else None
)
polyclinics_geojson = (
    round_coordinates(gdf_to_geojson(polyclinics)) if polyclinics is not None else None
)

table_columns = [
    c
    for c in [
        "block_id",
        "population_calibrated",
        "area_ha",
        "land_use",
        "spacematrix_morphotype",
        "strelka_morphotype",
        "fsi",
        "gsi",
        "mxi",
        "l",
        "osr",
        "area_accessibility",
        "hospital_count",
        "polyclinic_count",
        "hospital_provision_strong",
        "polyclinic_provision_strong",
    ]
    if c in blocks.columns
]
block_table = dataframe_records(blocks[table_columns], max_rows=len(blocks))

labels = {
    "block_id": "ID квартала",
    "area_ha": "Площадь, га",
    "population_calibrated": "Расчётное население, чел.",
    "fsi": "Плотность застройки, коэф.",
    "gsi": "Доля застроенной территории, коэф.",
    "mxi": "Доля жилой площади, коэф.",
    "l": "Средняя этажность, эт.",
    "osr": "Открытые пространства, коэф.",
    "share_living": "Доля жилой площади",
    "share_non_living": "Доля нежилой площади",
    "area_accessibility": "Средняя пешеходная доступность, мин",
    "hospital_count": "Количество больниц",
    "polyclinic_count": "Количество поликлиник",
    "hospital_provision_strong": "Обеспеченность больницами",
    "polyclinic_provision_strong": "Обеспеченность поликлиниками",
    "land_use": "Функциональное назначение",
    "spacematrix_morphotype": "Морфотип пространственной матрицы",
    "strelka_morphotype": "Морфотип «Стрелка»",
}

payload = {
    "title": TITLE,
    "center": [
        float(blocks.to_crs(4326).geometry.representative_point().y.mean()),
        float(blocks.to_crs(4326).geometry.representative_point().x.mean()),
    ],
    "kpis": {
        "populationTotal": round(population_total),
        "areaHa": round(city_area_ha, 1),
        "blocksTotal": blocks_total,
        "livingBlocks": living_blocks,
        "serviceBlocks": service_blocks,
        "hospitalBlocks": hospital_blocks,
        "polyclinicBlocks": polyclinic_blocks,
        "accessibilityMean": accessibility_mean,
        "hospitalProvisionShare": hospital_provision_share,
        "polyclinicProvisionShare": polyclinic_provision_share,
    },
    "fields": {
        "numeric": [f for f in numeric_fields if f in blocks.columns],
        "categorical": [f for f in categorical_fields if f in blocks.columns],
    },
    "labels": labels,
    "blocks": blocks_geojson,
    "boundaries": boundaries_geojson,
    "hospitals": hospitals_geojson,
    "polyclinics": polyclinics_geojson,
    "landuseCounts": dataframe_records(
        landuse_counts.rename_axis("value").rename("count").reset_index()
    ),
    "spacematrixCounts": dataframe_records(
        spacematrix_counts.rename_axis("value").rename("count").reset_index()
    ),
    "strelkaCounts": dataframe_records(
        strelka_counts.rename_axis("value").rename("count").reset_index()
    ),
    "histograms": {},
    "blockTable": block_table,
}

for field in [
    "population_calibrated",
    "fsi",
    "area_accessibility",
    "hospital_provision_strong",
    "polyclinic_provision_strong",
]:
    series = pd.to_numeric(blocks[field], errors="coerce").dropna()
    payload["histograms"][field] = {
        "values": [round(float(v), 5) for v in series.tolist()],
        "label": labels.get(field, field),
    }

html = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  :root {
    --bg: #eef2f4;
    --surface: #ffffff;
    --surface-soft: #f8fafc;
    --ink: #102a29;
    --muted: #64748b;
    --muted-light: #94a3b8;
    --border: #dde5e7;
    --accent: #0f766e;
    --accent-dark: #0b3b38;
    --shadow: 0 8px 24px rgba(15, 42, 41, .06);
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    margin: 0;
    font-family: Inter, "Segoe UI", Arial, sans-serif;
    background: var(--bg);
    color: var(--ink);
  }
  .topbar { background: var(--accent-dark); color: #fff; }
  .topbar-inner { max-width: 1440px; margin: 0 auto; padding: 22px 28px; }
  .topbar h1 { margin: 0; font-size: 32px; line-height: 1.1; letter-spacing: -.7px; }
  .credit { margin: 8px 0 0; font-size: 12px; line-height: 1.4; font-weight: 400; color: rgba(255,255,255,.72); }
  .container { max-width: 1440px; margin: 0 auto; padding: 24px 28px 12px; }
  .block { margin-top: 28px; }
  .section-head {
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 16px; margin-bottom: 12px;
  }
  .section-head h2 { margin: 0; font-size: 21px; letter-spacing: -.3px; }
  .subtitle { margin: 4px 0 0; color: var(--muted); font-size: 13px; line-height: 1.35; }
  .badge {
    display: inline-flex; align-items: center; white-space: nowrap;
    border: 1px solid var(--border); background: var(--surface);
    color: var(--muted); border-radius: 999px; padding: 7px 11px; font-size: 12px;
  }
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 18px; box-shadow: var(--shadow);
  }
  .kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; }
  .kpi { min-height: 112px; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; }
  .kpi-label { color: var(--muted); font-size: 13px; line-height: 1.25; min-height: 34px; }
  .kpi-value { font-size: 30px; line-height: 1.1; font-weight: 750; color: var(--ink); margin: 8px 0 0; letter-spacing: -.6px; }
  .map-layout { display: grid; grid-template-columns: minmax(0, 1fr) 344px; gap: 16px; align-items: start; }
  .map-card { padding: 14px; min-width: 0; }
  .map-toolbar { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 12px; }
  .chip {
    border: 1px solid var(--border); background: var(--surface-soft); color: #334155;
    border-radius: 999px; padding: 8px 11px; font: inherit; font-size: 12px;
    cursor: pointer; transition: .15s ease;
  }
  .chip:hover { border-color: #a7c7c3; background: #f0fdfa; }
  .chip.active { background: var(--accent); border-color: var(--accent); color: #fff; }
  #mapCanvas { height: 700px; border-radius: 13px; overflow: hidden; z-index: 1; background: #fff; }
  .leaflet-container { background: #fff; }
  .map-side { display: grid; gap: 14px; position: sticky; top: 16px; }
  .info-card { padding: 17px; }
  .card-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
  .card-head h3 { margin: 0; font-size: 15px; }
  .selection-empty { padding: 24px 6px 20px; text-align: center; color: var(--muted); }
  .selection-empty strong { display: block; color: var(--ink); font-size: 14px; margin-bottom: 7px; }
  .selection-empty p { margin: 0; font-size: 12px; line-height: 1.5; }
  .selected-title { font-size: 18px; font-weight: 700; margin-bottom: 12px; }
  .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 12px; }
  .info-item span { display: block; color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .04em; }
  .info-item b { display: block; margin-top: 2px; font-size: 13px; font-weight: 650; overflow-wrap: anywhere; }
  .legend-title { font-size: 13px; font-weight: 650; margin-bottom: 10px; }
  .legend-gradient { height: 10px; border-radius: 999px; }
  .legend-labels { display: flex; justify-content: space-between; color: var(--muted); font-size: 10px; margin-top: 5px; }
  .legend-list { display: grid; gap: 6px; }
  .legend-row { display: flex; align-items: center; gap: 7px; font-size: 11px; color: #475569; }
  .legend-swatch { width: 10px; height: 10px; border-radius: 3px; flex: 0 0 auto; }
  .legend-note { color: var(--muted-light); font-size: 10px; line-height: 1.4; margin: 10px 0 0; }
  .service-key { display: grid; gap: 9px; }
  .service-key-row { display: flex; align-items: center; gap: 9px; color: #475569; font-size: 12px; }
  .service-symbols { display: inline-flex; align-items: center; gap: 5px; min-width: 43px; }
  .service-sep { color: #94a3b8; font-size: 13px; line-height: 1; }
  .service-dot {
    width: 12px; height: 12px; border-radius: 50%; flex: 0 0 auto;
    border: 2px solid #fff; box-shadow: 0 0 0 1px #cbd5e1;
  }
  .service-area {
    width: 14px; height: 11px; flex: 0 0 auto; border-radius: 2px;
    border: 2px solid #fff; box-shadow: 0 0 0 1px #cbd5e1;
  }
  .service-dot.hospital { background: #dc2626; }
  .service-dot.polyclinic { background: #2563eb; }
  .service-area.hospital { background: #fecaca; border-color: #991b1b; box-shadow: none; }
  .service-area.polyclinic { background: #bfdbfe; border-color: #1e3a8a; box-shadow: none; }
  .charts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
  .chart-card { padding: 8px 8px 2px; min-width: 0; min-height: 380px; }
  .chart { height: 366px; width: 100%; }
  .table-card { padding: 18px; }
  .table-head { align-items: center; }
  .button {
    border: 1px solid var(--border); background: var(--surface); color: var(--ink);
    border-radius: 10px; padding: 9px 12px; font: inherit; font-size: 12px; cursor: pointer;
  }
  .button:hover { background: var(--surface-soft); }
  .filters { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0; }
  .filters input, .filters select {
    border: 1px solid var(--border); background: var(--surface); color: var(--ink);
    border-radius: 9px; padding: 9px 10px; font: inherit; font-size: 12px;
  }
  .filters input { min-width: 280px; flex: 1 1 280px; }
  .table-wrap { max-height: 620px; overflow: auto; border: 1px solid var(--border); border-radius: 12px; }
  table { width: 100%; min-width: 1420px; border-collapse: collapse; font-size: 12px; }
  th, td { border-bottom: 1px solid #edf2f3; padding: 9px 11px; text-align: left; white-space: nowrap; }
  th {
    position: sticky; top: 0; z-index: 2; background: #f6f9fa; color: #475569;
    font-size: 10px; text-transform: uppercase; letter-spacing: .035em; font-weight: 700;
  }
  tbody tr { cursor: pointer; }
  tbody tr:hover { background: #f4fbfa; }
  tbody tr.selected { background: #dff5f1; }
  .pager { display: flex; align-items: center; justify-content: flex-end; gap: 10px; margin-top: 12px; color: var(--muted); font-size: 12px; }
  .pager button {
    border: 1px solid var(--border); background: var(--surface); border-radius: 8px;
    width: 32px; height: 30px; cursor: pointer; font: inherit;
  }
  .pager button:disabled { opacity: .4; cursor: default; }
  .page-footer {
    max-width: 1440px; margin: 0 auto; padding: 4px 28px 26px;
    color: var(--muted-light); font-size: 10.5px; line-height: 1.55;
  }
  @media (max-width: 1180px) {
    .kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .charts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .map-layout { grid-template-columns: minmax(0, 1fr) 310px; }
  }
  @media (max-width: 980px) {
    .map-layout { grid-template-columns: 1fr; }
    .map-side { position: static; grid-template-columns: 1fr 1fr; }
    #mapCanvas { height: 520px; }
  }
  @media (max-width: 700px) {
    .container { padding: 16px 14px 8px; }
    .topbar-inner { padding: 18px 14px; }
    .topbar h1 { font-size: 27px; }
    .kpis, .charts, .map-side { grid-template-columns: 1fr; }
    .kpi { min-height: 110px; }
    .chart-card { min-height: 330px; }
    .chart { height: 316px; }
    #mapCanvas { height: 430px; }
    .filters input { min-width: 0; }
  }
</style>
</head>
<body>
<header class="topbar">
  <div class="topbar-inner">
    <h1>__TITLE__</h1>
    <p class="credit">Выполнила Косолапкина Варвара, C4206</p>
  </div>
</header>

<main class="container">
  <section class="kpis" id="kpis"></section>

  <section class="block" id="mapSection">
    <div class="section-head">
      <div>
        <h2>Карта кварталов</h2>
        <p class="subtitle">Выберите показатель, затем нажмите на квартал, чтобы увидеть его характеристики.</p>
      </div>
      <span class="badge" id="activeLayer">Население квартала, чел.</span>
    </div>
    <div class="map-layout">
      <div class="card map-card">
        <div class="map-toolbar" id="layerChips"></div>
        <div id="mapCanvas"></div>
      </div>
      <aside class="map-side">
        <div class="card info-card">
          <div class="card-head"><h3>Выбранный квартал</h3></div>
          <div id="selectionBody" class="selection-empty">
            <strong>Выберите квартал на карте</strong>
            <p>Или нажмите на строку в таблице ниже.<br>Здесь появятся основные показатели.</p>
          </div>
        </div>
        <div class="card info-card">
          <div class="legend-title" id="legendTitle">Легенда</div>
          <div id="legendBody"></div>
        </div>
        <div class="card info-card" id="serviceKeyCard" hidden>
          <div class="legend-title">Условные обозначения</div>
          <div class="service-key">
            <div class="service-key-row">
              <span class="service-symbols">
                <span class="service-dot hospital"></span>
                <span class="service-sep">/</span>
                <span class="service-area hospital"></span>
              </span>
              <span>Больницы</span>
            </div>
            <div class="service-key-row">
              <span class="service-symbols">
                <span class="service-dot polyclinic"></span>
                <span class="service-sep">/</span>
                <span class="service-area polyclinic"></span>
              </span>
              <span>Поликлиники</span>
            </div>
          </div>
        </div>
      </aside>
    </div>
  </section>

  <section class="block">
    <div class="section-head">
      <div>
        <h2>Показатели</h2>
        <p class="subtitle">Распределение кварталов по функциональному назначению, морфотипам, населению и пешеходной доступности (мин).</p>
      </div>
    </div>
    <div class="charts" id="charts"></div>
  </section>

  <section class="block" id="tableSection">
    <div class="card table-card">
      <div class="section-head table-head">
        <div>
          <h2>Таблица кварталов</h2>
          <p class="subtitle" id="tableCount"></p>
        </div>
        <button class="button" id="downloadBtn" type="button">Скачать CSV</button>
      </div>
      <div class="filters">
        <input id="tableSearch" type="search" placeholder="Поиск по ID, функциональному назначению или морфотипу">
        <select id="landUseFilter"></select>
        <select id="pageSize">
          <option value="25">25 строк</option>
          <option value="50" selected>50 строк</option>
          <option value="100">100 строк</option>
          <option value="250">250 строк</option>
        </select>
      </div>
      <div class="table-wrap">
        <table>
          <thead id="tableHead"></thead>
          <tbody id="tableBody"></tbody>
        </table>
      </div>
      <div class="pager" id="pager"></div>
    </div>
  </section>
</main>

<footer class="page-footer">
  <div>Дата создания: 24.10.2026</div>
  <div>OSM / BlocksNet</div>
</footer>

<script>
const DATA = __PAYLOAD__;

const fmtInt = v => v == null ? '—' : Number(v).toLocaleString('ru-RU', {maximumFractionDigits: 0});
const fmtNum = (v, d = 2) => v == null ? '—' : Number(v).toLocaleString('ru-RU', {maximumFractionDigits: d});
const fmtText = v => v == null || v === '' ? '—' : String(v);
const escapeHtml = v => fmtText(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const kpis = [
  {label: 'Расчётное население', value: fmtInt(DATA.kpis.populationTotal)},
  {label: 'Площадь, га', value: fmtNum(DATA.kpis.areaHa, 1)},
  {label: 'Кварталы', value: fmtInt(DATA.kpis.blocksTotal)},
  {label: 'Кварталов с больницами или поликлиниками', value: fmtInt(DATA.kpis.serviceBlocks)},
  {label: 'Средняя пешеходная доступность, мин', value: fmtNum(DATA.kpis.accessibilityMean, 1)}
];

document.getElementById('kpis').innerHTML = kpis.map(item => `
  <article class="card kpi">
    <div class="kpi-label">${escapeHtml(item.label)}</div>
    <div class="kpi-value">${item.value}</div>
  </article>
`).join('');

const blockFeatures = {};
DATA.blocks.features.forEach(feature => {
  blockFeatures[String(feature.properties?.block_id)] = feature;
});

const map = L.map('mapCanvas', {preferCanvas: true, zoomSnap: .25, zoomDelta: .5}).setView(DATA.center, 11);
map.attributionControl.setPrefix('');
L.control.scale({imperial: false}).addTo(map);

const boundaryPane = map.createPane('boundary');
boundaryPane.style.zIndex = 450;
const servicePane = map.createPane('services');
servicePane.style.zIndex = 625;

const boundaryRenderer = L.svg({pane: 'boundary'});
const serviceRenderer = L.svg({pane: 'services'});

if (DATA.boundaries) {
  L.geoJSON(DATA.boundaries, {
    renderer: boundaryRenderer,
    pane: 'boundary',
    interactive: false,
    style: {color: '#0b3b38', weight: 2.2, fillOpacity: 0}
  }).addTo(map);
}

const initialBounds = DATA.boundaries
  ? L.geoJSON(DATA.boundaries).getBounds()
  : L.geoJSON(DATA.blocks).getBounds();
map.fitBounds(initialBounds, {padding: [24, 24]});
map.setZoom(map.getZoom() + 0.25);

const sequential = ['#cffafe', '#67e8f9', '#22d3ee', '#06b6d4', '#0891b2', '#0e7490'];
const redGreen = ['#dc2626', '#f97316', '#facc15', '#84cc16', '#16a34a'];
const categorical = ['#2563eb', '#0d9488', '#f59e0b', '#8b5cf6', '#ec4899', '#ef4444', '#14b8a6', '#84cc16', '#f97316'];

const layerDefs = [
  {field: 'population_calibrated', label: 'Население, чел.', fullLabel: 'Население квартала, чел.', kind: 'num', palette: sequential, digits: 0},
  {field: 'fsi', label: 'Плотность, коэф.', fullLabel: 'Плотность застройки, коэф.', kind: 'num', palette: sequential, digits: 2},
  {field: 'gsi', label: 'Застройка, коэф.', fullLabel: 'Доля застроенной территории, коэф.', kind: 'num', palette: sequential, digits: 2},
  {field: 'mxi', label: 'Доля жилой площади, коэф.', fullLabel: 'Доля жилой площади, коэф.', kind: 'num', palette: sequential, digits: 2},
  {field: 'area_accessibility', label: 'Пешеходная доступность, мин', fullLabel: 'Средняя пешеходная доступность, мин', kind: 'num', palette: sequential, digits: 1},
  {field: 'hospital_provision_strong', label: 'Обеспеченность больницами', fullLabel: 'Обеспеченность больницами', kind: 'num', palette: redGreen, digits: 2},
  {field: 'polyclinic_provision_strong', label: 'Обеспеченность поликлиниками', fullLabel: 'Обеспеченность поликлиниками', kind: 'num', palette: redGreen, digits: 2},
  {field: 'land_use', label: 'Функциональное назначение', fullLabel: 'Функциональное назначение', kind: 'cat'},
  {field: 'spacematrix_morphotype', label: 'Морфотип', fullLabel: 'Морфотип', kind: 'cat'},
  {field: 'strelka_morphotype', label: 'Стрелка', fullLabel: 'Морфотип «Стрелка»', kind: 'cat'}
];

const availableFields = new Set([...(DATA.fields.numeric || []), ...(DATA.fields.categorical || [])]);
const serviceFields = new Set(['hospital_provision_strong', 'polyclinic_provision_strong']);
const layers = {};
const layerIndex = {};
let currentDef = null;
let selectedLayer = null;
let selectedDef = null;
let hospitalLayer = null;
let polyclinicLayer = null;

function valuesFor(def) {
  return DATA.blocks.features
    .map(f => f.properties?.[def.field])
    .filter(v => v != null && Number.isFinite(Number(v)))
    .map(Number);
}

function prepareDef(def) {
  if (def.kind === 'cat') {
    const values = DATA.blocks.features.map(f => f.properties?.[def.field]);
    def.categories = [...new Set(values.map(v => v == null ? 'нет данных' : String(v)))];
    return;
  }
  const values = valuesFor(def);
  def.min = values.length ? Math.min(...values) : 0;
  def.max = values.length ? Math.max(...values) : 1;
}

function colorAt(palette, t) {
  const idx = Math.max(0, Math.min(palette.length - 1, Math.floor(t * palette.length)));
  return palette[idx];
}

function styleFor(def, properties) {
  const base = {color: '#ffffff', weight: .45, fillOpacity: .78};
  const value = properties?.[def.field];
  if (def.kind === 'cat') {
    const key = value == null ? 'нет данных' : String(value);
    const idx = def.categories.indexOf(key);
    return {...base, fillColor: key === 'нет данных' ? '#cbd5e1' : categorical[idx % categorical.length]};
  }
  const number = Number(value);
  if (!Number.isFinite(number)) return {...base, fillColor: '#e2e8f0'};
  const t = def.max === def.min ? 0.5 : (number - def.min) / (def.max - def.min);
  return {...base, fillColor: colorAt(def.palette, Math.max(0, Math.min(1, t)))};
}

function makeLayer(def) {
  layerIndex[def.field] = {};
  return L.geoJSON(DATA.blocks, {
    style: feature => styleFor(def, feature.properties),
    onEachFeature: (feature, layer) => {
      layerIndex[def.field][String(feature.properties?.block_id)] = layer;
      layer.on('click', () => selectFeature(feature, layer, def));
    }
  });
}

function renderLegend(def) {
  document.getElementById('legendTitle').textContent = `Легенда: ${def.fullLabel}`;
  const body = document.getElementById('legendBody');
  if (def.kind === 'cat') {
    body.innerHTML = `
      <div class="legend-list">
        ${def.categories.map((value, i) => `
          <div class="legend-row">
            <span class="legend-swatch" style="background:${value === 'нет данных' ? '#cbd5e1' : categorical[i % categorical.length]}"></span>
            <span>${escapeHtml(value)}</span>
          </div>
        `).join('')}
      </div>
      <p class="legend-note">Серый цвет — нет данных.</p>
    `;
    return;
  }
  body.innerHTML = `
    <div class="legend-gradient" style="background:linear-gradient(90deg,${def.palette.join(',')})"></div>
    <div class="legend-labels"><span>${fmtNum(def.min, def.digits)}</span><span>${fmtNum(def.max, def.digits)}</span></div>
    <p class="legend-note">Серый цвет — нет данных. Наведите на квартал для подсказки.</p>
  `;
}

function emptySelection() {
  document.getElementById('selectionBody').className = 'selection-empty';
  document.getElementById('selectionBody').innerHTML = `
    <strong>Выберите квартал на карте</strong>
    <p>Или нажмите на строку в таблице ниже.<br>Здесь появятся основные показатели.</p>
  `;
}

function clearSelection() {
  if (selectedLayer && selectedDef) {
    selectedLayer.setStyle(styleFor(selectedDef, selectedLayer.feature.properties));
  }
  selectedLayer = null;
  selectedDef = null;
  emptySelection();
}

function renderSelection(properties) {
  const body = document.getElementById('selectionBody');
  body.className = '';
  const rows = [
    ['Население, чел.', fmtInt(properties.population_calibrated)],
    ['Площадь, га', fmtNum(properties.area_ha, 1)],
    ['Функциональное назначение', fmtText(properties.land_use)],
    ['Морфотип пространственной матрицы', fmtText(properties.spacematrix_morphotype)],
    ['Плотность застройки, коэф.', fmtNum(properties.fsi, 3)],
    ['Доля застройки, коэф.', fmtNum(properties.gsi, 3)],
    ['Доля жилой площади, коэф.', fmtNum(properties.mxi, 3)],
    ['Этажность, эт.', fmtNum(properties.l, 2)],
    ['Пешеходная доступность, мин', fmtNum(properties.area_accessibility, 1)],
    ['Количество больниц', fmtInt(properties.hospital_count)],
    ['Количество поликлиник', fmtInt(properties.polyclinic_count)],
    ['Морфотип «Стрелка»', fmtText(properties.strelka_morphotype)]
  ];
  body.innerHTML = `
    <div class="selected-title">Квартал ${escapeHtml(properties.block_id)}</div>
    <div class="info-grid">
      ${rows.map(([label, value]) => `
        <div class="info-item"><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>
      `).join('')}
    </div>
  `;
  document.querySelectorAll('#tableBody tr[data-id]').forEach(row => {
    row.classList.toggle('selected', row.dataset.id === String(properties.block_id));
  });
}

function selectFeature(feature, layer, def) {
  if (selectedLayer && selectedLayer !== layer && selectedDef) {
    selectedLayer.setStyle(styleFor(selectedDef, selectedLayer.feature.properties));
  }
  selectedLayer = layer;
  selectedDef = def;
  layer.setStyle({color: '#0f172a', weight: 2.4, fillOpacity: .94});
  layer.bringToFront();
  renderSelection(feature.properties);
}

function syncServiceVisibility() {
  const shouldShow = Boolean(currentDef && serviceFields.has(currentDef.field));
  [hospitalLayer, polyclinicLayer].forEach(layer => {
    if (!layer) return;
    if (shouldShow && !map.hasLayer(layer)) layer.addTo(map);
    if (!shouldShow && map.hasLayer(layer)) map.removeLayer(layer);
  });
  const card = document.getElementById('serviceKeyCard');
  if (card) card.hidden = !shouldShow;
}

function showLayer(def) {
  clearSelection();
  if (currentDef && layers[currentDef.field]) map.removeLayer(layers[currentDef.field]);
  if (!layers[def.field]) layers[def.field] = makeLayer(def);
  layers[def.field].addTo(map);
  currentDef = def;
  layerDefs.forEach(item => item.button?.classList.toggle('active', item === def));
  document.getElementById('activeLayer').textContent = def.fullLabel;
  renderLegend(def);
  syncServiceVisibility();
}

const chips = document.getElementById('layerChips');
layerDefs.filter(def => availableFields.has(def.field)).forEach(def => {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'chip';
  button.textContent = def.label;
  button.onclick = () => showLayer(def);
  def.button = button;
  chips.appendChild(button);
});

layerDefs.filter(def => availableFields.has(def.field)).forEach(prepareDef);
const firstAvailable = layerDefs.find(def => availableFields.has(def.field));
if (firstAvailable) showLayer(firstAvailable);

if (DATA.hospitals) {
  hospitalLayer = L.geoJSON(DATA.hospitals, {
    renderer: serviceRenderer,
    pane: 'services',
    style: {color: '#991b1b', weight: 2, opacity: 1, fillColor: '#fecaca', fillOpacity: .65},
    pointToLayer: (f, latlng) => L.circleMarker(latlng, {renderer: serviceRenderer, pane: 'services', radius: 4.5, color: '#ffffff', weight: 2, opacity: 1, fillColor: '#dc2626', fillOpacity: 1}),
    onEachFeature: (f, layer) => layer.bindPopup(`<b>Больница</b><br>Ёмкость: ${f.properties?.capacity ?? '—'}`)
  }).addTo(map);
}

if (DATA.polyclinics) {
  polyclinicLayer = L.geoJSON(DATA.polyclinics, {
    renderer: serviceRenderer,
    pane: 'services',
    style: {color: '#1e3a8a', weight: 2, opacity: 1, fillColor: '#bfdbfe', fillOpacity: .65},
    pointToLayer: (f, latlng) => L.circleMarker(latlng, {renderer: serviceRenderer, pane: 'services', radius: 4.5, color: '#ffffff', weight: 2, opacity: 1, fillColor: '#2563eb', fillOpacity: 1}),
    onEachFeature: (f, layer) => layer.bindPopup(`<b>Поликлиника</b><br>Ёмкость: ${f.properties?.capacity ?? '—'}`)
  }).addTo(map);
}

syncServiceVisibility();

function chartLayout(title, xTitle, yTitle) {
  return {
    title: {text: title, font: {size: 13, color: '#334155'}, x: .02, xanchor: 'left'},
    margin: {l: 70, r: 18, t: 44, b: 60},
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: {family: 'Inter, Segoe UI, Arial, sans-serif', size: 10, color: '#64748b'},
    xaxis: {
      gridcolor: '#edf2f3', zeroline: false,
      title: {text: xTitle, font: {size: 10}, standoff: 8}
    },
    yaxis: {
      gridcolor: '#edf2f3', zeroline: false,
      title: {text: yTitle, font: {size: 10}, standoff: 8}
    },
    height: 366,
    showlegend: false
  };
}

function addChartCard() {
  const card = document.createElement('div');
  card.className = 'card chart-card';
  const plot = document.createElement('div');
  plot.className = 'chart';
  card.appendChild(plot);
  document.getElementById('charts').appendChild(card);
  return plot;
}

function barChart(title, records, yTitle, color = '#0f766e') {
  const plot = addChartCard();
  const labels = records.map(r => String(r.value ?? 'Нет данных'));
  const values = records.map(r => Number(r.count || 0));
  const layout = chartLayout(title, 'Количество кварталов, шт.', yTitle);
  layout.margin = {l: 250, r: 18, t: 44, b: 60};
  layout.yaxis = {
    automargin: true, gridcolor: '#edf2f3', zeroline: false,
    title: {text: yTitle, font: {size: 10}, standoff: 8}
  };
  layout.xaxis.range = [0, Math.max(1, Math.max(...values) * 1.06)];
  Plotly.newPlot(plot, [{
    type: 'bar',
    orientation: 'h',
    x: values,
    y: labels,
    marker: {color},
    hovertemplate: '%{y}: %{x}<extra></extra>'
  }], layout, {displayModeBar: false, responsive: true});
}

function histogram(title, values, xTitle, color = '#0f766e') {
  const plot = addChartCard();
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const padding = (maxValue - minValue) * .04 || 1;
  const layout = chartLayout(title, xTitle, 'Количество кварталов, шт.');
  layout.xaxis.range = [minValue - padding, maxValue + padding];
  Plotly.newPlot(plot, [{
    type: 'histogram',
    x: values,
    marker: {color},
    hovertemplate: '%{x}: %{y}<extra></extra>'
  }], {...layout, bargap: .1}, {displayModeBar: false, responsive: true});
}

if (window.Plotly) {
  const landuse = (DATA.landuseCounts || []).filter(r => r.value !== 'нет данных');
  if (landuse.length) barChart('Функциональное назначение кварталов', landuse.slice(0, 8), 'Функциональное назначение');

  const spacematrix = (DATA.spacematrixCounts || []).filter(r => r.value !== 'нет застройки');
  if (spacematrix.length) barChart('Морфотипы пространственной матрицы', spacematrix.slice(0, 8), 'Морфотип');

  const populationValues = DATA.histograms?.population_calibrated?.values || [];
  const sortedPopulation = [...populationValues].sort((a, b) => a - b);
  const cutoff = sortedPopulation[Math.floor(sortedPopulation.length * .99)] ?? null;
  const populationShown = cutoff == null ? populationValues : populationValues.filter(v => v <= cutoff);
  histogram('Распределение населения (до 99-го перцентиля)', populationShown, 'Население, чел.');

  const accessibilityValues = DATA.histograms?.area_accessibility?.values || [];
  if (accessibilityValues.length) histogram('Средняя пешеходная доступность, мин', accessibilityValues, 'Пешеходная доступность, мин', '#2563eb');

  const hospitalValues = DATA.histograms?.hospital_provision_strong?.values || [];
  if (hospitalValues.length) histogram('Обеспеченность больницами', hospitalValues, 'Обеспеченность больницами, коэф.', '#dc2626');

  const polyclinicValues = DATA.histograms?.polyclinic_provision_strong?.values || [];
  if (polyclinicValues.length) histogram('Обеспеченность поликлиниками', polyclinicValues, 'Обеспеченность поликлиниками, коэф.', '#2563eb');
}

const columns = [
  ['block_id', 'ID'],
  ['population_calibrated', 'Население, чел.'],
  ['area_ha', 'Площадь, га'],
  ['land_use', 'Функциональное назначение'],
  ['spacematrix_morphotype', 'Морфотип пространственной матрицы'],
  ['strelka_morphotype', 'Морфотип «Стрелка»'],
  ['fsi', 'Плотность застройки, коэф.'],
  ['gsi', 'Доля застройки, коэф.'],
  ['mxi', 'Доля жилой площади, коэф.'],
  ['l', 'Этажность, эт.'],
  ['area_accessibility', 'Пешеходная доступность, мин'],
  ['hospital_count', 'Количество больниц'],
  ['polyclinic_count', 'Количество поликлиник']
];

const tableHead = document.getElementById('tableHead');
const tableBody = document.getElementById('tableBody');
const tableCount = document.getElementById('tableCount');
const searchInput = document.getElementById('tableSearch');
const landUseFilter = document.getElementById('landUseFilter');
const pageSize = document.getElementById('pageSize');
const pager = document.getElementById('pager');
let page = 1;

tableHead.innerHTML = `<tr>${columns.map(([, label]) => `<th>${escapeHtml(label)}</th>`).join('')}</tr>`;

const landUses = [...new Set(DATA.blockTable.map(row => row.land_use ?? 'нет данных'))]
  .sort((a, b) => String(a).localeCompare(String(b), 'ru'));
landUseFilter.innerHTML = '<option value="__all__">Все назначения</option>' +
  landUses.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');

function tableValue(row, key) {
  if (key === 'population_calibrated' || key === 'hospital_count' || key === 'polyclinic_count') {
    return fmtInt(row[key]);
  }
  if (key === 'area_ha') return fmtNum(row[key], 1);
  if (key === 'fsi' || key === 'gsi' || key === 'mxi' || key === 'l') return fmtNum(row[key], 3);
  if (key === 'area_accessibility') return fmtNum(row[key], 1);
  return fmtText(row[key]);
}

function filteredRows() {
  const query = searchInput.value.trim().toLowerCase();
  const landUse = landUseFilter.value;
  return DATA.blockTable.filter(row => {
    if (landUse !== '__all__' && (row.land_use ?? 'нет данных') !== landUse) return false;
    if (!query) return true;
    return [row.block_id, row.land_use, row.spacematrix_morphotype, row.strelka_morphotype]
      .map(value => String(value ?? '').toLowerCase())
      .some(value => value.includes(query));
  });
}

function renderTable() {
  const rows = filteredRows();
  const size = Number(pageSize.value) || 50;
  const pages = Math.max(1, Math.ceil(rows.length / size));
  page = Math.min(page, pages);
  const start = (page - 1) * size;
  const visible = rows.slice(start, start + size);
  tableBody.innerHTML = visible.length ? visible.map(row => `
    <tr data-id="${escapeHtml(row.block_id)}">
      ${columns.map(([key]) => `<td>${escapeHtml(tableValue(row, key))}</td>`).join('')}
    </tr>
  `).join('') : `<tr><td colspan="${columns.length}">Ничего не найдено</td></tr>`;
  tableCount.textContent = rows.length
    ? `${fmtInt(rows.length)} кварталов · показаны ${fmtInt(start + 1)}–${fmtInt(Math.min(start + size, rows.length))}`
    : '0 кварталов';
  pager.innerHTML = `
    <button type="button" id="prevPage" ${page <= 1 ? 'disabled' : ''}>←</button>
    <span>Страница ${fmtInt(page)} из ${fmtInt(pages)}</span>
    <button type="button" id="nextPage" ${page >= pages ? 'disabled' : ''}>→</button>
  `;
  document.getElementById('prevPage').onclick = () => { if (page > 1) { page -= 1; renderTable(); } };
  document.getElementById('nextPage').onclick = () => { if (page < pages) { page += 1; renderTable(); } };
  tableBody.querySelectorAll('tr[data-id]').forEach(row => {
    row.onclick = () => focusBlock(row.dataset.id);
  });
}

function focusBlock(blockId) {
  const feature = blockFeatures[String(blockId)];
  if (!feature) return;
  if (!layers[currentDef.field]) showLayer(currentDef);
  const layer = layerIndex[currentDef.field]?.[String(blockId)];
  if (layer) {
    selectFeature(feature, layer, currentDef);
  } else {
    renderSelection(feature.properties);
  }
  document.getElementById('mapSection').scrollIntoView({behavior: 'smooth', block: 'start'});
}

searchInput.addEventListener('input', () => { page = 1; renderTable(); });
landUseFilter.addEventListener('change', () => { page = 1; renderTable(); });
pageSize.addEventListener('change', () => { page = 1; renderTable(); });

document.getElementById('downloadBtn').onclick = () => {
  const csvEscape = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
  const lines = [
    columns.map(([, label]) => csvEscape(label)).join(';'),
    ...DATA.blockTable.map(row => columns.map(([key]) => csvEscape(tableValue(row, key))).join(';'))
  ];
  const blob = new Blob(['\ufeff' + lines.join('\r\n')], {type: 'text/csv;charset=utf-8;'});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'astrakhan_blocks.csv';
  link.click();
  URL.revokeObjectURL(link.href);
};

renderTable();
window.addEventListener('resize', () => map.invalidateSize());
</script>
</body>
</html>
"""

html = html.replace("__TITLE__", TITLE).replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
OUTPUT_PATH.write_text(html, encoding="utf-8")
print(f"Дашборд сохранён: {OUTPUT_PATH.resolve()}")
print(f"Размер файла: {OUTPUT_PATH.stat().st_size / 1024 / 1024:.1f} МБ")
