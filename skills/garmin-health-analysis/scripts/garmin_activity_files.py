#!/usr/bin/env python3
"""
Download and analyze Garmin activity FIT, GPX and TCX files.
Extract GPS, elevation, pace, heart rate, power, cadence, etc.
"""

import io
import json
import re
import sys
import os
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from garmin_auth import get_client

# Check for optional dependencies
try:
    import fitparse
    HAS_FITPARSE = True
except ImportError:
    HAS_FITPARSE = False


# An activity FIT file is KB to a few MB. This only bounds a corrupt or hostile archive.
MAX_FIT_BYTES = 100 * 1024 * 1024


class FitDataError(ValueError):
    """The data is neither a FIT file nor a ZIP archive holding exactly one."""


def _is_fit(data):
    # Every FIT file carries the ASCII signature ".FIT" at bytes 8-11 of its header.
    return len(data) >= 12 and data[8:12] == b".FIT"


def fit_bytes_from(data):
    """Raw FIT bytes from what Garmin (or a file on disk) gives us.

    Garmin's "original" activity download is a ZIP archive that *contains* the .fit file, not the FIT
    file itself, while a device or Garmin Express export is the bare FIT. Both are accepted. The archive
    member is read into memory and its own name is never used as a path, so a hostile archive cannot
    write outside the output directory.
    """
    if not data:
        raise FitDataError("Garmin returned no data for this activity")
    if _is_fit(data):
        return bytes(data)

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise FitDataError("The data is neither a FIT file nor a ZIP archive containing one")
    with archive:
        members = [m for m in archive.infolist() if not m.is_dir() and m.filename.lower().endswith(".fit")]
        if not members:
            names = ", ".join(m.filename for m in archive.infolist()[:5]) or "empty archive"
            raise FitDataError(f"The ZIP archive has no .fit file in it (contents: {names})")
        if len(members) > 1:
            names = ", ".join(m.filename for m in members[:5])
            raise FitDataError(f"The ZIP archive has more than one .fit file ({names}); not sure which to use")
        member = members[0]
        if member.file_size > MAX_FIT_BYTES:
            raise FitDataError(f"{member.filename} is {member.file_size:,} bytes, larger than the "
                               f"{MAX_FIT_BYTES:,} byte limit")
        raw = archive.read(member)

    if not _is_fit(raw):
        raise FitDataError(f"{member.filename} in the ZIP archive is not a valid FIT file")
    return raw


def _write_private(path, data):
    """Write owner-only (0600), without following a symlink planted at the destination: the default
    output directory, /tmp, is shared, and these files hold GPS tracks."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as f:
        if hasattr(os, "fchmod"):
            os.fchmod(f.fileno(), 0o600)  # the mode above only applies when the file is new
        f.write(data)


def download_activity_file(client, activity_id, file_format="fit", output_dir="/tmp"):
    """Download an activity as FIT, GPX or TCX into output_dir (created if missing, mode 700)."""
    try:
        fmt = file_format.lower()
        formats = {
            "fit": client.ActivityDownloadFormat.ORIGINAL,
            "gpx": client.ActivityDownloadFormat.GPX,
            "tcx": client.ActivityDownloadFormat.TCX,
        }
        if fmt not in formats:
            return {"error": f"Unsupported format: {file_format}"}

        data = client.download_activity(activity_id, dl_fmt=formats[fmt])
        if fmt == "fit":
            data = fit_bytes_from(data)

        # mode applies only to a directory created here, not to parents or an existing directory
        out_dir = Path(output_dir)
        out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        output_path = out_dir / f"activity_{activity_id}.{fmt}"
        _write_private(output_path, data)

        return {"file": str(output_path), "activity_id": activity_id, "format": file_format}

    except Exception as e:
        return {"error": str(e), "activity_id": activity_id}


def parse_fit_file(file_path):
    """Parse FIT file and extract all data points."""
    if not HAS_FITPARSE:
        return {"error": "fitparse library not installed. Run: pip install -r requirements.txt in the Kai repo root"}
    
    try:
        # Accept a bare FIT or a ZIP holding one (what earlier versions saved for `download --format fit`)
        with open(file_path, "rb") as f:
            raw = fit_bytes_from(f.read())
        fitfile = fitparse.FitFile(io.BytesIO(raw))
        
        # Extract different record types
        records = []
        laps = []
        sessions = []
        
        for record in fitfile.get_messages('record'):
            data_point = {}
            for field in record:
                if field.value is not None:
                    data_point[field.name] = field.value
            if data_point:
                records.append(data_point)
        
        for record in fitfile.get_messages('lap'):
            lap_data = {}
            for field in record:
                if field.value is not None:
                    lap_data[field.name] = field.value
            if lap_data:
                laps.append(lap_data)
        
        for record in fitfile.get_messages('session'):
            session_data = {}
            for field in record:
                if field.value is not None:
                    session_data[field.name] = field.value
            if session_data:
                sessions.append(session_data)
        
        return {
            "records": records,
            "laps": laps,
            "sessions": sessions,
            "total_records": len(records)
        }
    
    except fitparse.utils.FitParseError as e:
        return {"error": f"Could not read this FIT file: {e}. It may be damaged, or written by an app the "
                         "FIT parser can't decode (seen with indoor rides uploaded from third-party apps). "
                         "Try the same activity as TCX: download it with --format tcx and parse that file, "
                         "which also carries per-second data such as heart rate, distance and power. "
                         "The activity summary is available from garmin_data.py."}
    except Exception as e:
        return {"error": str(e)}


# TCX files are a few MB at most. This only bounds a corrupt or hostile one.
MAX_TCX_BYTES = 100 * 1024 * 1024


def _tcx_text(parent, name):
    """Text of a child element, whatever its XML namespace (TCX versions and Garmin's extensions differ)."""
    child = parent.find(f"{{*}}{name}")
    if child is None or child.text is None or not child.text.strip():
        return None
    return child.text.strip()


def _tcx_number(parent, name):
    try:
        return float(_tcx_text(parent, name))
    except (TypeError, ValueError):
        return None


def _tcx_time(text):
    # TCX times look like 2026-09-25T09:00:00.000Z; the result is timezone-aware (UTC)
    try:
        return datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def _tcx_trackpoint(tp):
    """One <Trackpoint> as a record with the field names the FIT parser uses. A field the file doesn't
    have for this point is left out, as the FIT parser does: pool swims carry only time and heart rate,
    and any point can lack position or speed."""
    point = {}
    timestamp = _tcx_time(_tcx_text(tp, "Time"))
    if timestamp:
        point["timestamp"] = timestamp
    position = tp.find("{*}Position")
    if position is not None:
        lat, lon = _tcx_number(position, "LatitudeDegrees"), _tcx_number(position, "LongitudeDegrees")
        if lat is not None and lon is not None:
            point["latitude"], point["longitude"] = lat, lon
    for name, key in (("AltitudeMeters", "altitude"), ("DistanceMeters", "distance")):
        value = _tcx_number(tp, name)
        if value is not None:
            point[key] = value
    heart_rate = tp.find("{*}HeartRateBpm")
    if heart_rate is not None and _tcx_number(heart_rate, "Value") is not None:
        point["heart_rate"] = int(_tcx_number(heart_rate, "Value"))
    cadence = _tcx_number(tp, "Cadence")            # bike cadence is a plain child...
    extensions = tp.find("{*}Extensions")
    for tpx in (extensions if extensions is not None else []):
        for name, key in (("Speed", "speed"), ("Watts", "power")):
            value = _tcx_number(tpx, name)
            if value is not None:
                point[key] = int(value) if key == "power" else value
        if cadence is None:                         # ...run cadence lives in the extension
            cadence = _tcx_number(tpx, "RunCadence")
    if cadence is not None:
        point["cadence"] = int(cadence)
    return point


def _tcx_lap(lap):
    """One <Lap> as a summary with the field names the FIT parser uses for laps."""
    summary = {}
    start = _tcx_time(lap.get("StartTime"))
    if start:
        summary["start_time"] = start
    for name, key in (("TotalTimeSeconds", "total_elapsed_time"), ("DistanceMeters", "total_distance"),
                      ("MaximumSpeed", "max_speed"), ("Calories", "total_calories"), ("Cadence", "avg_cadence")):
        value = _tcx_number(lap, name)
        if value is not None:
            summary[key] = value
    for name, key in (("AverageHeartRateBpm", "avg_heart_rate"), ("MaximumHeartRateBpm", "max_heart_rate")):
        holder = lap.find(f"{{*}}{name}")
        if holder is not None and _tcx_number(holder, "Value") is not None:
            summary[key] = int(_tcx_number(holder, "Value"))
    if _tcx_text(lap, "Intensity"):
        summary["intensity"] = _tcx_text(lap, "Intensity")
    extensions = lap.find("{*}Extensions")
    for lx in (extensions if extensions is not None else []):
        for name, key in (("AvgSpeed", "avg_speed"), ("AvgWatts", "avg_power"), ("MaxWatts", "max_power"),
                          ("AvgRunCadence", "avg_cadence"), ("MaxRunCadence", "max_cadence"),
                          ("MaxBikeCadence", "max_cadence")):
            value = _tcx_number(lx, name)
            if value is not None:
                summary.setdefault(key, value)
    return summary


def _load_xml_root(file_path, label, root_name, max_bytes):
    """Read an activity XML file (TCX or GPX) and return (root element, None), or (None, error dict).

    Shared guards: a size limit, a refusal of DTDs and entity declarations, and a check that the root
    element is the one the format uses, so a file handed over under the wrong extension gets a clear error.
    """
    try:
        path = Path(file_path)
        if path.stat().st_size > max_bytes:
            return None, {"error": f"{path.name} is larger than the {max_bytes:,} byte limit for {label} files"}
        data = path.read_bytes()
        # Neither format ever has a DTD or entity declarations. Refusing them closes the usual XML
        # entity-expansion trick, which the standard library parser doesn't fully guard against.
        if re.search(rb"<!(?:DOCTYPE|ENTITY)", data, re.IGNORECASE):
            return None, {"error": f"This file declares a DTD or XML entities, which a {label} file never does; "
                                   "not parsing it"}
        root = ET.fromstring(data)
        found = root.tag.rsplit("}", 1)[-1]
        if found != root_name:
            return None, {"error": f"Not a {label} file (its root element is <{found}>)"}
        return root, None
    except ET.ParseError as e:
        return None, {"error": f"Could not read this {label} file: {e}"}
    except Exception as e:
        return None, {"error": str(e)}


def parse_tcx_file(file_path):
    """Parse a TCX file into the same shape the FIT parser returns (records, laps, total_records).

    TCX is the export that still carries per-second data (heart rate, distance, power, cadence, speed,
    altitude) for activities whose FIT file the FIT parser can't decode. It has no session summary, so
    `sessions` is always empty. Uses only the standard library.
    """
    root, error = _load_xml_root(file_path, "TCX", "TrainingCenterDatabase", MAX_TCX_BYTES)
    if error:
        return error
    records = [point for point in map(_tcx_trackpoint, root.findall(".//{*}Trackpoint")) if point]
    laps = [_tcx_lap(lap) for lap in root.findall(".//{*}Lap")]
    return {"records": records, "laps": laps, "sessions": [], "total_records": len(records)}


# GPX files are a few MB at most. This only bounds a corrupt or hostile one.
MAX_GPX_BYTES = 100 * 1024 * 1024


# Garmin's GPX export only holds points that have a GPS position, so treadmill, pool and other indoor
# activities come out as a valid GPX with no track points at all.
EMPTY_GPX_NOTE = ("This GPX file has no track points. Garmin leaves them out for activities recorded "
                  "without GPS (treadmill, pool swims, some indoor rides): download the TCX instead")


def _gpx_trackpoint(trkpt):
    """One <trkpt> as a record with the field names the FIT and TCX parsers use. A field the point
    doesn't have is left out. Heart rate and cadence sit in Garmin's TrackPointExtension (any version,
    any namespace prefix), so they are matched by their local names `hr` and `cad`."""
    point = {}
    timestamp = _tcx_time(_tcx_text(trkpt, "time"))
    if timestamp:
        point["timestamp"] = timestamp
    try:
        lat, lon = float(trkpt.get("lat")), float(trkpt.get("lon"))
    except (TypeError, ValueError):
        lat = lon = None
    if lat is not None and lon is not None:
        point["latitude"], point["longitude"] = lat, lon
    altitude = _tcx_number(trkpt, "ele")
    if altitude is not None:
        point["altitude"] = altitude
    extensions = trkpt.find("{*}extensions")
    for element in (extensions.iter() if extensions is not None else []):
        key = {"hr": "heart_rate", "cad": "cadence"}.get(element.tag.rsplit("}", 1)[-1])
        if key and key not in point:
            try:
                point[key] = int(float(element.text))
            except (TypeError, ValueError):
                pass
    return point


def parse_gpx_file(file_path):
    """Parse a GPX file into the same shape the FIT and TCX parsers return (records, laps, total_records).

    GPX carries time, position, elevation and, in Garmin's extension, heart rate and cadence. It has no
    distance, power or speed (use the TCX or FIT file for those), and no laps or session summary, so
    `laps` and `sessions` are empty. Only track points count: waypoints and routes are ignored. Uses
    only the standard library.
    """
    root, error = _load_xml_root(file_path, "GPX", "gpx", MAX_GPX_BYTES)
    if error:
        return error
    records = [point for point in map(_gpx_trackpoint, root.findall(".//{*}trk//{*}trkpt")) if point]
    result = {"records": records, "laps": [], "sessions": [], "total_records": len(records)}
    if not records:
        result["note"] = EMPTY_GPX_NOTE
    return result


def parse_activity_file(file_path):
    """Parse a FIT, GPX or TCX file chosen by its extension (any case); None if it's none of those."""
    parser = {".fit": parse_fit_file, ".gpx": parse_gpx_file, ".tcx": parse_tcx_file}.get(
        Path(file_path).suffix.lower())
    return parser(file_path) if parser else None


def query_data_at_distance(data, distance_meters):
    """Find data point closest to a specific distance."""
    if "records" not in data:
        return {"error": "No data records found"}
    records = data["records"]
    if not any("distance" in record for record in records):
        return {"error": "This activity file has no distance values to search (GPX files don't record "
                         "distance). Query by --time instead, or use the TCX or FIT file of the same activity"}

    # Find closest by distance
    closest = None
    min_diff = float('inf')
    
    for record in records:
        if "distance" in record:
            diff = abs(record["distance"] - distance_meters)
            if diff < min_diff:
                min_diff = diff
                closest = record
    
    return closest


def query_data_at_time(data, target_time):
    """Find data point at a specific time."""
    if "records" not in data:
        return {"error": "No data records found"}
    records = data["records"]

    # Parse target time
    if isinstance(target_time, str):
        try:
            target_dt = datetime.fromisoformat(target_time.replace("Z", "+00:00"))
        except:
            return {"error": f"Invalid time format: {target_time}"}
    else:
        target_dt = target_time
    
    target_ts = target_dt.timestamp()
    
    closest = None
    min_diff = float('inf')
    
    for record in records:
        if "timestamp" in record:
            if isinstance(record["timestamp"], datetime):
                rec_ts = record["timestamp"].timestamp()
            else:
                continue
            
            diff = abs(rec_ts - target_ts)
            if diff < min_diff:
                min_diff = diff
                closest = record
    
    return closest


def analyze_activity(data):
    """Analyze activity data and provide insights."""
    if "error" in data:
        return data
    
    records = data.get("records", [])
    if not records:
        return {"error": "No data records to analyze" + (f". {data['note']}" if data.get("note") else "")}
    
    # Calculate statistics
    hr_values = [r.get("heart_rate") for r in records if r.get("heart_rate")]
    elevation_values = [r.get("altitude") or r.get("elevation") for r in records if r.get("altitude") or r.get("elevation")]
    speed_values = [r.get("speed") for r in records if r.get("speed")]
    cadence_values = [r.get("cadence") for r in records if r.get("cadence")]
    power_values = [r.get("power") for r in records if r.get("power")]
    
    analysis = {
        "total_points": len(records),
        "duration_seconds": None,
        "distance_meters": None,
        "heart_rate": {
            "avg": sum(hr_values) / len(hr_values) if hr_values else None,
            "max": max(hr_values) if hr_values else None,
            "min": min(hr_values) if hr_values else None
        },
        "elevation": {
            "max": max(elevation_values) if elevation_values else None,
            "min": min(elevation_values) if elevation_values else None,
            "gain": None  # Would need to calculate from sequential points
        },
        "speed": {
            "avg": sum(speed_values) / len(speed_values) if speed_values else None,
            "max": max(speed_values) if speed_values else None
        },
        "cadence": {
            "avg": sum(cadence_values) / len(cadence_values) if cadence_values else None
        } if cadence_values else None,
        "power": {
            "avg": sum(power_values) / len(power_values) if power_values else None,
            "max": max(power_values) if power_values else None
        } if power_values else None
    }
    
    # Get duration and distance from first/last records
    if records:
        if "timestamp" in records[0] and "timestamp" in records[-1]:
            if isinstance(records[0]["timestamp"], datetime):
                duration = (records[-1]["timestamp"] - records[0]["timestamp"]).total_seconds()
                analysis["duration_seconds"] = duration
        
        if "distance" in records[-1]:
            analysis["distance_meters"] = records[-1]["distance"]
    
    return analysis


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze Garmin activity files")
    parser.add_argument("action", choices=["download", "parse", "query", "analyze"],
                       help="Action to perform")
    parser.add_argument("--activity-id", type=int, help="Activity ID")
    parser.add_argument("--format", choices=["fit", "gpx", "tcx"], default="fit",
                       help="File format for download")
    parser.add_argument("--file", help="Path to a local FIT, GPX or TCX file")
    parser.add_argument("--distance", type=float, help="Query data at distance (meters)")
    parser.add_argument("--time", help="Query data at time (ISO format)")
    parser.add_argument("--output-dir", default="/tmp", help="Output directory")
    
    args = parser.parse_args()
    
    if args.action == "download":
        if not args.activity_id:
            print('{"error": "activity-id required for download"}')
            sys.exit(1)
        
        client = get_client()
        if not client:
            print('{"error": "Not authenticated. Ask the account owner to run this in their own terminal: .venv/bin/python3 skills/garmin-health-analysis/scripts/garmin_auth.py login"}')
            sys.exit(1)
        
        result = download_activity_file(client, args.activity_id, args.format, args.output_dir)
        print(json.dumps(result, indent=2))
    
    elif args.action == "parse":
        if not args.file:
            print('{"error": "file path required for parse"}')
            sys.exit(1)
        
        result = parse_activity_file(args.file)
        if result is None:
            result = {"error": "Unsupported file type. Use .fit, .gpx or .tcx"}
        
        print(json.dumps(result, indent=2, default=str))
    
    elif args.action == "query":
        if not args.file:
            print('{"error": "file path required for query"}')
            sys.exit(1)
        
        # First parse the file
        data = parse_activity_file(args.file)
        if data is None:
            print('{"error": "Unsupported file type"}')
            sys.exit(1)
        
        if "error" in data:
            print(json.dumps(data, indent=2))
            sys.exit(1)
        
        # Query
        if args.distance is not None:
            result = query_data_at_distance(data, args.distance)
        elif args.time:
            result = query_data_at_time(data, args.time)
        else:
            result = {"error": "Specify --distance or --time for query"}
        
        print(json.dumps(result, indent=2, default=str))
    
    elif args.action == "analyze":
        if not args.file:
            print('{"error": "file path required for analyze"}')
            sys.exit(1)
        
        # Parse and analyze
        data = parse_activity_file(args.file)
        if data is None:
            print('{"error": "Unsupported file type"}')
            sys.exit(1)
        
        result = analyze_activity(data)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
