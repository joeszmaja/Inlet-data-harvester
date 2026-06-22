import asyncio
import json
import csv
import os
from datetime import datetime
import websockets

# CONFIGURATION
API_KEY = "de4272bdc032841809eeab781800affe0e2f4770"

# New Topsail Inlet Box
BOUNDING_BOX = [[[34.33, -77.70], [34.38, -77.60]]]

async def connect_ais():
    url = "wss://stream.aisstream.io/v0/stream"
    async with websockets.connect(url) as websocket:
        subscribe_message = {
            "APIKey": API_KEY,
            "BoundingBoxes": BOUNDING_BOX,
            "FilterMessageTypes": ["PositionReport"]
        }
        await websocket.send(json.dumps(subscribe_message))

        filename = "vessel_tracks.csv"
        file_exists = os.path.isfile(filename)
        
        existing_points = set()
        if file_exists:
            with open(filename, mode='r') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if len(row) >= 5:
                        existing_points.add((row[3], row[4]))

        with open(filename, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(["MMSI", "Name", "Type", "Lat", "Lon", "Timestamp"])

            print("Connected to stream. Collecting tracks...")
            
            # Listen to live stream for 45 seconds per run
            start_time = datetime.now()
            async for message in websocket:
                if (datetime.now() - start_time).seconds > 45:
                    break
                    
                data = json.loads(message)
                ship_type = data.get("MetaData", {}).get("ShipType", 0)
                
                # Filters strictly for Tugs, Towboats (31,32) and Pilots (50)
                if ship_type in [31, 32, 50]:
                    mmsi = data.get("MetaData", {}).get("MMSI")
                    name = data.get("MetaData", {}).get("ShipName", "").strip()
                    lat = data.get("Message", {}).get("PositionReport", {}).get("Latitude")
                    lon = data.get("Message", {}).get("PositionReport", {}).get("Longitude")
                    timestamp = data.get("MetaData", {}).get("time_utc")
                    
                    if (str(lat), str(lon)) not in existing_points:
                        writer.writerow([mmsi, name, ship_type, lat, lon, timestamp])
                        existing_points.add((str(lat), str(lon)))

    generate_leaflet_map(filename)

def generate_leaflet_map(csv_filename):
    tracks_js = ""
    if os.path.isfile(csv_filename):
        with open(csv_filename, mode='r') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 5:
                    tracks_js += f"L.circle([{row[3]}, {row[4]}], {{color: 'red', radius: 6, fillOpacity: 0.8}}).addTo(map).bindPopup('{row[1]}');\n"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Live Inlet Tracker</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>html, body, #map {{ height: 100%; margin: 0; }}</style>
</head>
<body>
    <div id="map"></div>
    <script>
        var map = L.map('map').setView([34.35, -77.64], 14);
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: 'OpenStreetMap'
        }}).addTo(map);
        {tracks_js}
    </script>
</body>
</html>"""

    with open("index.html", "w") as f:
        f.write(html_content)

if __name__ == "__main__":
    asyncio.run(connect_ais())
