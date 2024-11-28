import json

def remove_duplicates(geojson_data):
    seen = set()
    unique_features = []

    for feature in geojson_data['features']:
        # Create a tuple of the coordinates to use as a unique identifier
        coords_tuple = tuple(feature['geometry']['coordinates'])
        
        if coords_tuple not in seen:
            seen.add(coords_tuple)
            unique_features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": unique_features
    }

# Load GeoJSON data from a file
input_file = '/static/Diversity.geojson'
output_file = '/static/Diversity2.geojson'

with open(input_file, 'r') as f:
    geojson_data = json.load(f)

# Remove duplicates
cleaned_geojson = remove_duplicates(geojson_data)

# Save the cleaned GeoJSON to a new file
with open(output_file, 'w') as f:
    json.dump(cleaned_geojson, f, indent=4)

print(f"Removed duplicates. Cleaned GeoJSON saved to {output_file}.")