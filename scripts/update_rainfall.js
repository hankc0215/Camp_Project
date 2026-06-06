const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const ENV_PATHS = [
  path.join(ROOT, ".env"),
  path.resolve(ROOT, "..", ".env"),
  path.resolve(ROOT, "..", "..", ".env"),
];
const DATA_PATH = path.join(ROOT, "demo_payload.json");
const OUT_PATH = path.join(ROOT, "real_rainfall.json");
const JS_OUT_PATH = path.join(ROOT, "real_rainfall.js");
const CWA_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001";

function loadEnv() {
  for (const envPath of ENV_PATHS) {
    if (!fs.existsSync(envPath)) continue;
    const lines = fs.readFileSync(envPath, "utf8").split(/\r?\n/);
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const match = trimmed.match(/^([\w.-]+)\s*=\s*(.*)$/);
      if (!match) continue;
      const key = match[1];
      let value = match[2].trim();
      if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
        value = value.slice(1, -1);
      }
      if (!process.env[key]) process.env[key] = value;
    }
  }
}

function toNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const text = String(value).trim();
  if (["-99", "-999", "-999.0", "null", "NaN"].includes(text)) return null;
  const n = Number(text);
  return Number.isFinite(n) ? n : null;
}

function getNested(obj, keys) {
  let cur = obj;
  for (const key of keys) {
    if (cur === null || cur === undefined) return undefined;
    cur = cur[key];
  }
  return cur;
}

function readRain(station) {
  const element = station.RainfallElement || station.WeatherElement || {};
  const candidates = [
    ["Past24hr", "Precipitation"],
    ["Past24hr", "Accumulation"],
    ["Past24hr"],
    ["Past12hr", "Precipitation"],
    ["Past6hr", "Precipitation"],
    ["Past3hr", "Precipitation"],
    ["Past1hr", "Precipitation"],
    ["Now", "Precipitation"],
  ];
  for (const keys of candidates) {
    const value = toNumber(getNested(element, keys));
    if (value !== null) {
      return { rain24hMm: value, field: keys.join(".") };
    }
  }
  return { rain24hMm: null, field: null };
}

function readStationPosition(station) {
  const lon = toNumber(
    getNested(station, ["GeoInfo", "Coordinates", 0, "StationLongitude"]) ??
      getNested(station, ["GeoInfo", "Coordinates", 0, "Longitude"]) ??
      getNested(station, ["StationPosition", "StationLongitude"]) ??
      station.StationLongitude
  );
  const lat = toNumber(
    getNested(station, ["GeoInfo", "Coordinates", 0, "StationLatitude"]) ??
      getNested(station, ["GeoInfo", "Coordinates", 0, "Latitude"]) ??
      getNested(station, ["StationPosition", "StationLatitude"]) ??
      station.StationLatitude
  );
  return { lat, lon };
}

function distanceKm(a, b) {
  const radius = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLon = ((b.lon - a.lon) * Math.PI) / 180;
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * radius * Math.asin(Math.sqrt(h));
}

function nearestStation(camp, stations) {
  let best = null;
  for (const station of stations) {
    const distKm = distanceKm(camp, station);
    if (!best || distKm < best.distanceKm) best = { station, distanceKm: distKm };
  }
  return best;
}

async function fetchCwaRainfall(apiKey) {
  const url = new URL(CWA_URL);
  url.searchParams.set("Authorization", apiKey);
  url.searchParams.set("format", "JSON");
  const res = await fetch(url);
  if (!res.ok) throw new Error(`CWA API failed: ${res.status} ${res.statusText}`);
  const json = await res.json();
  const rawStations = json.records?.Station || json.records?.location || [];
  const stations = rawStations
    .map((station) => {
      const pos = readStationPosition(station);
      const rain = readRain(station);
      return {
        id: station.StationId || station.StationID || station.stationId || "",
        name: station.StationName || station.stationName || "",
        county: station.GeoInfo?.CountyName || station.CountyName || "",
        town: station.GeoInfo?.TownName || station.TownName || "",
        obsTime: station.ObsTime?.DateTime || station.ObsTime || station.obsTime || "",
        lat: pos.lat,
        lon: pos.lon,
        rain24hMm: rain.rain24hMm,
        rainField: rain.field,
      };
    })
    .filter((station) => station.lat !== null && station.lon !== null && station.rain24hMm !== null);

  if (!stations.length) throw new Error("CWA response did not include usable rainfall stations.");
  return stations;
}

async function main() {
  loadEnv();
  const apiKey = process.env.CWA_API_KEY || process.env.CWA_AUTHORIZATION_KEY || process.env.CWB_API_KEY;
  if (!apiKey) {
    throw new Error("Missing CWA_API_KEY. Create .env from .env.example and fill in your CWA API key.");
  }

  const payload = JSON.parse(fs.readFileSync(DATA_PATH, "utf8"));
  const camps = (payload.campsites || []).filter((camp) => Number.isFinite(Number(camp.lat)) && Number.isFinite(Number(camp.lon)));
  const stations = await fetchCwaRainfall(apiKey);
  const byPriorityRank = {};

  for (const camp of camps) {
    const match = nearestStation({ lat: Number(camp.lat), lon: Number(camp.lon) }, stations);
    if (!match) continue;
    byPriorityRank[String(camp.priority_rank)] = {
      rain_24h_mm_real: Number(match.station.rain24hMm.toFixed(1)),
      rain_station_id: match.station.id,
      rain_station_name: match.station.name,
      rain_station_county: match.station.county,
      rain_station_town: match.station.town,
      rain_station_distance_km: Number(match.distanceKm.toFixed(2)),
      rain_observed_at: match.station.obsTime,
      rain_source_field: match.station.rainField,
    };
  }

  const output = {
    source: "CWA O-A0002-001",
    generated_at: new Date().toISOString(),
    station_count: stations.length,
    campsite_count: Object.keys(byPriorityRank).length,
    by_priority_rank: byPriorityRank,
  };
  fs.writeFileSync(OUT_PATH, JSON.stringify(output, null, 2), "utf8");
  fs.writeFileSync(
    JS_OUT_PATH,
    `window.REAL_RAINFALL = ${JSON.stringify(output, null, 2)};\n`,
    "utf8"
  );
  console.log(`Wrote ${OUT_PATH}`);
  console.log(`Wrote ${JS_OUT_PATH}`);
  console.log(`Matched ${output.campsite_count} campsites using ${output.station_count} CWA rainfall stations.`);
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
