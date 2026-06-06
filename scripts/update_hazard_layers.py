import json
import math
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINAL_ROOT = ROOT.parents[1]
DATA_DIR = ROOT / "data"
DEMO_PAYLOAD = DATA_DIR / "demo_payload.json"
FAULT_SHP = FINAL_ROOT / "Data" / "Fault" / "TaiwanFault.shp"
RIVER_SHP = FINAL_ROOT / "Data" / "2024_1753條土石流潛勢溪流圖" / "debrisstream1753_20260126_twd97.shp"
JSON_OUT = DATA_DIR / "hazard_layers.json"
JS_OUT = DATA_DIR / "hazard_layers.js"


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


def read_shape_lines(path):
    data = path.read_bytes()
    offset = 100
    lines = []
    while offset + 8 <= len(data):
        _record_number, content_words = struct.unpack(">2i", data[offset : offset + 8])
        offset += 8
        content_len = content_words * 2
        content = data[offset : offset + content_len]
        offset += content_len
        if len(content) < 44:
            continue

        shape_type = struct.unpack("<i", content[:4])[0]
        if shape_type not in (3, 5, 13, 15):
            continue

        num_parts = struct.unpack("<i", content[36:40])[0]
        num_points = struct.unpack("<i", content[40:44])[0]
        parts_start = 44
        points_start = parts_start + 4 * num_parts
        if len(content) < points_start + 16 * num_points:
            continue

        parts = list(struct.unpack(f"<{num_parts}i", content[parts_start:points_start]))
        parts.append(num_points)
        points = [
            struct.unpack("<2d", content[points_start + i * 16 : points_start + (i + 1) * 16])
            for i in range(num_points)
        ]

        for start, end in zip(parts, parts[1:]):
            coords = points[start:end]
            if len(coords) < 2:
                continue
            xs = [p[0] for p in coords]
            ys = [p[1] for p in coords]
            lines.append({"coords": coords, "bbox": (min(xs), min(ys), max(xs), max(ys))})
    return lines


def nearest_distance(px, py, lines):
    best = None
    for line in lines:
        if best is not None and bbox_distance(px, py, line["bbox"]) > best:
            continue
        coords = line["coords"]
        for a, b in zip(coords, coords[1:]):
            d = point_segment_distance(px, py, a[0], a[1], b[0], b[1])
            if best is None or d < best:
                best = d
                if best <= 0:
                    return 0.0
    return best


def fault_score(distance_m):
    if distance_m is None:
        return 0
    if distance_m <= 250:
        return 100
    if distance_m <= 500:
        return 75
    if distance_m < 1000:
        return 25
    return 0


def river_score(distance_m):
    if distance_m is None:
        return 0
    if distance_m < 50:
        return 100
    if distance_m < 100:
        return 50
    return 0


def main():
    payload = json.loads(DEMO_PAYLOAD.read_text(encoding="utf-8"))
    fault_lines = read_shape_lines(FAULT_SHP)
    river_lines = read_shape_lines(RIVER_SHP)

    by_rank = {}
    for camp in payload["campsites"]:
        px, py = wgs84_to_twd97_tm2(float(camp["lon"]), float(camp["lat"]))
        fault_dist = nearest_distance(px, py, fault_lines)
        river_dist = nearest_distance(px, py, river_lines)
        by_rank[str(camp["priority_rank"])] = {
            "fault_dist_m": round(fault_dist, 1) if fault_dist is not None else None,
            "fault_score": fault_score(fault_dist),
            "river_dist_m": round(river_dist, 1) if river_dist is not None else None,
            "river_score": river_score(river_dist),
        }

    output = {
        "source": {
            "fault": str(FAULT_SHP.relative_to(FINAL_ROOT)),
            "river": str(RIVER_SHP.relative_to(FINAL_ROOT)),
        },
        "method": "TWD97 TM2 nearest segment distance",
        "fault_line_count": len(fault_lines),
        "river_line_count": len(river_lines),
        "campsite_count": len(by_rank),
        "by_priority_rank": by_rank,
    }
    JSON_OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    JS_OUT.write_text("window.HAZARD_LAYERS = " + json.dumps(output, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    print(f"Wrote {JSON_OUT} and {JS_OUT}; campsites={len(by_rank)}")


if __name__ == "__main__":
    main()
