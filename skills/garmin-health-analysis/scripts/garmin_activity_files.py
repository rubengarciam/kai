#!/usr/bin/env python3
"""
Download and analyze Garmin activity FIT/GPX files.
Extract GPS, elevation, pace, heart rate, power, cadence, etc.
"""

import io
import json
import sys
import os
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

try:
    import gpxpy
    import gpxpy.gpx
    HAS_GPXPY = True
except ImportError:
    HAS_GPXPY = False


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
                         "The activity summary is still available from garmin_data.py, and per-second data "
                         "from the Strava skill."}
    except Exception as e:
        return {"error": str(e)}


def parse_gpx_file(file_path):
    """Parse GPX file and extract track points."""
    if not HAS_GPXPY:
        return {"error": "gpxpy library not installed. Run: pip install -r requirements.txt in the Kai repo root"}
    
    try:
        with open(file_path, 'r') as f:
            gpx = gpxpy.parse(f)
        
        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    points.append({
                        "latitude": point.latitude,
                        "longitude": point.longitude,
                        "elevation": point.elevation,
                        "time": point.time.isoformat() if point.time else None,
                        "speed": point.speed,
                        "hr": point.extensions.get("hr") if point.extensions else None
                    })
        
        return {
            "points": points,
            "total_points": len(points),
            "bounds": {
                "min_lat": gpx.get_bounds().min_latitude,
                "max_lat": gpx.get_bounds().max_latitude,
                "min_lon": gpx.get_bounds().min_longitude,
                "max_lon": gpx.get_bounds().max_longitude
            } if gpx.get_bounds() else None
        }
    
    except Exception as e:
        return {"error": str(e)}


def query_data_at_distance(data, distance_meters):
    """Find data point closest to a specific distance."""
    if "records" in data:
        records = data["records"]
    elif "points" in data:
        records = data["points"]
    else:
        return {"error": "No data records found"}
    
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
    if "records" in data:
        records = data["records"]
    elif "points" in data:
        records = data["points"]
    else:
        return {"error": "No data records found"}
    
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
        return {"error": "No data records to analyze"}
    
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
    parser.add_argument("--file", help="Path to local FIT/GPX file")
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
        
        if args.file.lower().endswith('.fit'):
            result = parse_fit_file(args.file)
        elif args.file.lower().endswith('.gpx'):
            result = parse_gpx_file(args.file)
        else:
            result = {"error": "Unsupported file type. Use .fit or .gpx"}
        
        print(json.dumps(result, indent=2, default=str))
    
    elif args.action == "query":
        if not args.file:
            print('{"error": "file path required for query"}')
            sys.exit(1)
        
        # First parse the file
        if args.file.lower().endswith('.fit'):
            data = parse_fit_file(args.file)
        elif args.file.lower().endswith('.gpx'):
            data = parse_gpx_file(args.file)
        else:
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
        if args.file.lower().endswith('.fit'):
            data = parse_fit_file(args.file)
        elif args.file.lower().endswith('.gpx'):
            data = parse_gpx_file(args.file)
        else:
            print('{"error": "Unsupported file type"}')
            sys.exit(1)
        
        result = analyze_activity(data)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
