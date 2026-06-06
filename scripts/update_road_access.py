import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO_PAYLOAD = ROOT / "demo_payload.json"
ROAD_GEOJSON = ROOT.parents[1] / "eRoad_MapDataDownload" / "_merged" / "eroad_line_data_merged_latest.geojson"
JSON_OUT = ROOT / "road_access.json"
JS_OUT = ROOT / "road_access.js"

ROAD_RADIUS_M = 1000.0


def wgs84_to_twd97_tm2(lon, lat):
    # EPSG:3826-style TWD97 / TM2 zone 121 forward projection.
    a = 6378137.0
    b = 6356752.314245
    lon0 = math.radians(121.0)
    k0 = 0.9999
    dx = 250000.0
    e = math.sqrt(1 - (b * b) / (a * a))
    e2 = e * e / (1 - e * e)

    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    n = a / math.sqrt(1 - e * e * math.sin(lat_r) ** 2)
    t = math.tan(lat_r) ** 2
    c = e2 * math.cos(lat_r) ** 2
    A = math.cos(lat_r) * (lon_r - lon0)
    m = a * (
        (1 - e * e / 4 - 3 * e**4 / 64 - 5 * e**6 / 256) * lat_r
        - (3 * e * e / 8 + 3 * e**4 / 32 + 45 * e**6 / 1024) * math.sin(2 * lat_r)
        + (15 * e**4 / 256 + 45 * e**6 / 1024) * math.sin(4 * lat_r)
        - (35 * e**6 / 3072) * math.sin(6 * lat_r)
    )

    x = dx + k0 * n * (
        A
        + (1 - t + c) * A**3 / 6
        + (5 - 18 * t + t * t + 72 * c - 58 * e2) * A**5 / 120
    )
    y = k0 * (
        m
        + n
        * math.tan(lat_r)
        * (
            A * A / 2
            + (5 - t + 9 * c + 4 * c * c) * A**4 / 24
            + (61 - 58 * t + t * t + 600 * c - 330 * e2) * A**6 / 720
        )
    )
    return x, y


def point_segment_distance(px, py, ax, ay, bx, by):
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def iter_lines(geometry):
    coords = geometry.get("coordinates") or []
    if geometry.get("type") == "LineString":
        yield coords
    elif geometry.get("type") == "MultiLineString":
        yield from coords


def load_roads():
    with ROAD_GEOJSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    roads = []
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        name = props.get("編號") or props.get("編碼") or props.get("source_category") or "未命名道路"
        road_id = props.get("編碼") or name
        for coords in iter_lines(feature.get("geometry") or {}):
            if len(coords) < 2:
                continue
            xs = [p[0] for p in coords]
            ys = [p[1] for p in coords]
            roads.append(
                {
                    "id": str(road_id),
                    "name": str(name),
                    "category": props.get("source_category") or "",
                    "coords": coords,
                    "bbox": (min(xs), min(ys), max(xs), max(ys)),
                }
            )
    return roads


def score_road_count(count):
    if count <= 1:
        return 100
    if count == 2:
        return 50
    return 0


def nearest_and_count(camp, roads):
    px, py = wgs84_to_twd97_tm2(float(camp["lon"]), float(camp["lat"]))
    unique = set()
    nearest = None

    for road in roads:
        minx, miny, maxx, maxy = road["bbox"]
        if px < minx - ROAD_RADIUS_M or px > maxx + ROAD_RADIUS_M or py < miny - ROAD_RADIUS_M or py > maxy + ROAD_RADIUS_M:
            continue

        best = None
        coords = road["coords"]
        for a, b in zip(coords, coords[1:]):
            d = point_segment_distance(px, py, a[0], a[1], b[0], b[1])
            if best is None or d < best:
                best = d
                if best <= 5:
                    break

        if best is None:
            continue
        if nearest is None or best < nearest["distance_m"]:
            nearest = {"name": road["name"], "category": road["category"], "distance_m": best}
        if best <= ROAD_RADIUS_M:
            unique.add(road["id"])

    count = len(unique)
    return {
        "road_count_1km": count,
        "road_score": score_road_count(count),
        "nearest_road_name": nearest["name"] if nearest else None,
        "nearest_road_category": nearest["category"] if nearest else None,
        "nearest_road_distance_m": round(nearest["distance_m"], 1) if nearest else None,
    }


def main():
    with DEMO_PAYLOAD.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    roads = load_roads()
    by_rank = {}
    for camp in payload["campsites"]:
        by_rank[str(camp["priority_rank"])] = nearest_and_count(camp, roads)

    output = {
        "source": "eRoad MapDataDownload merged latest",
        "method": "TWD97 TM2 distance; unique road ids within 1km",
        "road_radius_m": ROAD_RADIUS_M,
        "road_feature_count": len(roads),
        "campsite_count": len(by_rank),
        "by_priority_rank": by_rank,
    }
    JSON_OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    JS_OUT.write_text("window.ROAD_ACCESS = " + json.dumps(output, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    print(f"Wrote {JSON_OUT} and {JS_OUT}; campsites={len(by_rank)}, road lines={len(roads)}")


if __name__ == "__main__":
    main()
