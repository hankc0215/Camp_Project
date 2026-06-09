import csv
import json
import math
import sys
from pathlib import Path
from collections import defaultdict


ROOT = Path(__file__).resolve().parents[1]
FINAL_ROOT = ROOT.parents[1]
VENDOR = FINAL_ROOT / "vendor_py"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

try:
    import shapefile
except ImportError as exc:
    raise SystemExit("Missing pyshp. Install with: python -m pip install --target ../../vendor_py pyshp") from exc


DATA_DIR = ROOT / "data"
DEMO_JS = DATA_DIR / "demo_data.js"
DEMO_PAYLOAD = DATA_DIR / "demo_payload.json"
CSV_PATH = DATA_DIR / "all_taiwan_camping_risk_demo.csv"

RIVER_LINE_SHP = FINAL_ROOT / "Data" / "RIVERLIN" / "riverlin" / "riverlin.shp"
RIVER_POLY_SHP = FINAL_ROOT / "Data" / "RIVERPOLY" / "riverpoly" / "riverpoly.shp"
DEBRIS_STREAM_SHP = FINAL_ROOT / "Data" / "2024_1753條土石流潛勢溪流圖" / "debrisstream1753_20260126_twd97.shp"


def wgs84_to_twd97_tm2(lon, lat):
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


def bbox_distance(px, py, bbox):
    minx, miny, maxx, maxy = bbox
    dx = max(minx - px, 0, px - maxx)
    dy = max(miny - py, 0, py - maxy)
    return math.hypot(dx, dy)


def point_in_ring(px, py, ring):
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def split_parts(shape):
    points = shape.points
    parts = list(shape.parts) + [len(points)]
    return [points[start:end] for start, end in zip(parts, parts[1:]) if end - start >= 2]


def clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text if text and text != "-" else None


def feature_bbox(parts):
    xs = [x for part in parts for x, _ in part]
    ys = [y for part in parts for _, y in part]
    return min(xs), min(ys), max(xs), max(ys)


def read_features(path, source, kind):
    reader = shapefile.Reader(str(path), encoding="utf-8", encodingErrors="ignore")
    features = []
    for shape_record in reader.iterShapeRecords():
        parts = split_parts(shape_record.shape)
        if not parts:
            continue
        record = shape_record.record.as_dict()
        name = clean_text(record.get("NAME") or record.get("RIVER_NAME") or record.get("Name"))
        if not name:
            name = clean_text(record.get("Debrisno"))
        features.append(
            {
                "source": source,
                "kind": kind,
                "parts": parts,
                "bbox": feature_bbox(parts),
                "name": name or None,
                "from": clean_text(record.get("FROM") or record.get("RIVER_FROM") or record.get("Basin")),
                "type": clean_text(record.get("RIVER_TYPE") or record.get("Type")),
                "risk": clean_text(record.get("Risk")),
                "debrisno": clean_text(record.get("Debrisno")),
            }
        )
    return features


def distance_to_feature(px, py, feature):
    if feature["kind"] == "polygon" and bbox_distance(px, py, feature["bbox"]) == 0:
        if any(point_in_ring(px, py, part) for part in feature["parts"]):
            return 0.0

    best = None
    for part in feature["parts"]:
        for a, b in zip(part, part[1:]):
            d = point_segment_distance(px, py, a[0], a[1], b[0], b[1])
            if best is None or d < best:
                best = d
                if best <= 0:
                    return 0.0
    return best


def nearest_feature(px, py, features):
    best = None
    candidates = sorted(
        ((bbox_distance(px, py, feature["bbox"]), feature) for feature in features),
        key=lambda item: item[0],
    )
    for box_distance, feature in candidates:
        if best and box_distance > best["distance"]:
            break
        distance = distance_to_feature(px, py, feature)
        if distance is None:
            continue
        if best is None or distance < best["distance"]:
            best = {"distance": distance, "feature": feature}
            if distance <= 0:
                return best
    return best


def cell_range(min_value, max_value, cell_size):
    return range(math.floor(min_value / cell_size), math.floor(max_value / cell_size) + 1)


def build_segment_index(features, cell_size=2000.0):
    grid = defaultdict(list)
    segments = []
    for feature in features:
        for part in feature["parts"]:
            for a, b in zip(part, part[1:]):
                minx = min(a[0], b[0])
                maxx = max(a[0], b[0])
                miny = min(a[1], b[1])
                maxy = max(a[1], b[1])
                segment = {
                    "a": a,
                    "b": b,
                    "bbox": (minx, miny, maxx, maxy),
                    "feature": feature,
                    "id": len(segments),
                }
                segments.append(segment)
                for ix in cell_range(minx, maxx, cell_size):
                    for iy in cell_range(miny, maxy, cell_size):
                        grid[(ix, iy)].append(segment)
    return {"grid": grid, "segments": segments, "cell_size": cell_size}


def evaluate_segments(px, py, candidates, best=None, seen=None):
    if seen is None:
        seen = set()
    for segment in candidates:
        if segment["id"] in seen:
            continue
        seen.add(segment["id"])
        if best and bbox_distance(px, py, segment["bbox"]) > best["distance"]:
            continue
        a = segment["a"]
        b = segment["b"]
        distance = point_segment_distance(px, py, a[0], a[1], b[0], b[1])
        if best is None or distance < best["distance"]:
            best = {"distance": distance, "feature": segment["feature"]}
            if distance <= 0:
                return best, seen
    return best, seen


def nearest_polygon_containment(px, py, polygon_features):
    for feature in polygon_features:
        if bbox_distance(px, py, feature["bbox"]) != 0:
            continue
        if any(point_in_ring(px, py, part) for part in feature["parts"]):
            return {"distance": 0.0, "feature": feature}
    return None


def nearest_feature_indexed(px, py, index, polygon_features):
    inside = nearest_polygon_containment(px, py, polygon_features)
    if inside:
        return inside

    grid = index["grid"]
    cell_size = index["cell_size"]
    cx = math.floor(px / cell_size)
    cy = math.floor(py / cell_size)
    best = None
    seen = set()

    for radius in range(0, 80):
        cells = []
        for ix in range(cx - radius, cx + radius + 1):
            cells.append((ix, cy - radius))
            cells.append((ix, cy + radius))
        for iy in range(cy - radius + 1, cy + radius):
            cells.append((cx - radius, iy))
            cells.append((cx + radius, iy))
        for cell in cells:
            best, seen = evaluate_segments(px, py, grid.get(cell, []), best, seen)
        if best is not None:
            break

    if best is None:
        return None

    exact_seen = set()
    for ix in cell_range(px - best["distance"], px + best["distance"], cell_size):
        for iy in cell_range(py - best["distance"], py + best["distance"], cell_size):
            best, exact_seen = evaluate_segments(px, py, grid.get((ix, iy), []), best, exact_seen)
    return best


def river_score(distance_m):
    if distance_m is None:
        return 0
    if distance_m < 50:
        return 100
    if distance_m < 100:
        return 50
    return 0


def load_demo_data():
    text = DEMO_JS.read_text(encoding="utf-8")
    prefix = "window.DEMO_DATA = "
    if not text.startswith(prefix):
        raise ValueError(f"{DEMO_JS} does not start with {prefix!r}")
    return json.loads(text[len(prefix) :].rstrip(";\n"))


def update_summary(payload, features):
    camps = payload.get("campsites", [])
    summary = payload.setdefault("summary", {})
    near50 = sum(1 for camp in camps if isinstance(camp.get("river_dist_m"), (int, float)) and camp["river_dist_m"] < 50)
    near100 = sum(1 for camp in camps if isinstance(camp.get("river_dist_m"), (int, float)) and camp["river_dist_m"] < 100)
    summary["scope"] = "全台灣露營區風險監測 Demo｜全河川與土石流潛勢溪流距離版"
    summary["river_recalculation_note"] = (
        "river_dist_m is the minimum distance from each campsite point to riverlin.shp, "
        "riverpoly.shp, or debrisstream1753_20260126_twd97.shp after projecting campsite "
        "coordinates from EPSG:4326 to EPSG:3826. river_score: <50m=100, <100m=50, otherwise 0."
    )
    summary["river_source"] = {
        "line": "riverlin.shp",
        "polygon": "riverpoly.shp",
        "debris_stream": "debrisstream1753_20260126_twd97.shp",
        "crs": "EPSG:3826",
    }
    summary["river_feature_count"] = len(features)
    summary["near_river_50m"] = near50
    summary["near_river_100m"] = near100


def write_csv(payload):
    camps = payload.get("campsites", [])
    existing_fields = []
    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            existing_fields = reader.fieldnames or []

    new_fields = []
    for camp in camps:
        for key in camp:
            if key not in existing_fields and key not in new_fields and key != "score_parts":
                new_fields.append(key)

    fieldnames = existing_fields + new_fields
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for camp in camps:
            writer.writerow(camp)


def main():
    payload = load_demo_data()
    features = []
    features.extend(read_features(RIVER_LINE_SHP, "riverlin.shp", "line"))
    features.extend(read_features(RIVER_POLY_SHP, "riverpoly.shp", "polygon"))
    features.extend(read_features(DEBRIS_STREAM_SHP, "debrisstream1753_20260126_twd97.shp", "line"))
    polygon_features = [feature for feature in features if feature["kind"] == "polygon"]
    segment_index = build_segment_index(features)

    for camp in payload.get("campsites", []):
        px, py = wgs84_to_twd97_tm2(float(camp["lon"]), float(camp["lat"]))
        nearest = nearest_feature_indexed(px, py, segment_index, polygon_features)
        if not nearest:
            continue

        distance = nearest["distance"]
        feature = nearest["feature"]
        camp["river_dist_m"] = round(distance, 2)
        camp["river_score"] = river_score(distance)
        camp["river_source"] = feature["source"]
        camp["nearest_river_name"] = feature["name"]
        camp["nearest_river_from"] = feature["from"]
        camp["nearest_river_type"] = feature["type"]
        camp["nearest_river_risk"] = feature["risk"]
        camp["nearest_debris_stream_no"] = feature["debrisno"]
        camp["river_recalc_note"] = "nearest_of_riverlin_riverpoly_debrisstream_2026-06-09"

    update_summary(payload, features)
    DEMO_PAYLOAD.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    DEMO_JS.write_text("window.DEMO_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    write_csv(payload)
    print(
        f"Updated {len(payload.get('campsites', []))} campsites with {len(features)} river/debris stream features. "
        f"near50={payload['summary']['near_river_50m']} near100={payload['summary']['near_river_100m']}"
    )


if __name__ == "__main__":
    main()
