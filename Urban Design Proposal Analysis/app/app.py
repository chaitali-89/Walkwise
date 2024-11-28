from flask import Flask, request, jsonify, render_template, send_from_directory
import geopandas as gpd
import os
import matplotlib.pyplot as plt  # Import matplotlib for plotting
import math
import numpy as np
import networkx as nx
from shapely.geometry import Point
import pandas as pd
from shapely import wkt
from shapely.geometry import Polygon, MultiPolygon

app = Flask(__name__)
uploads_dir = 'uploads'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
    
    file_path = os.path.join(uploads_dir, file.filename)
    file.save(file_path)
    
    # Process the DXF file and convert to GeoJSON
    geojson_filename = process_dxf(file_path)
    return jsonify({'geojson_filename': geojson_filename})

def process_dxf(file_path):
    cobe = gpd.read_file(file_path)
    # Add your processing logic here (scaling, translating, etc.)
    def scale_factor(coordinate):
        coordinate_rad = math.radians(coordinate)

    # Calculate the scale factor
        scale_factor_value = 1 / math.cos(coordinate_rad)

        return scale_factor_value
    
    x = 55.6588  # Latitude for scaling
    scale_x = scale_factor(x)
    geometryScaled = cobe.scale(scale_x,scale_x, origin =(0,0,0))
    
    #translate the geometry
    geometryTranslated = geometryScaled.translate(1395773.831,7489901.409,0)
    
    cobeSpatial = gpd.GeoDataFrame(cobe, geometry=geometryTranslated)
    
    # Set the CRS using the new syntax
    cobeSpatial.set_crs(epsg=3857, inplace=True)
    
    #save geojson file
    cobeSpatial.to_file(r'D:\Master in Computation design\Module 4 - Thesis\visual studio  code\new project\dxf-analyzer\app\uploads\Bcobe.geojson')
    
    #Load Geojson file
    script_dir = os.path.dirname(__file__)
    uploads_dir = os.path.join(script_dir, 'uploads')

    input_geojson_path = os.path.join(uploads_dir, 'Bcobe.geojson')
    output_geojson_path = os.path.join(uploads_dir, 'BcobeWGS84.geojson')
    
    
    if os.path.exists(input_geojson_path):
        print(f"Input GeoJSON file exists: {input_geojson_path}")
        cobe_wgs84 = gpd.read_file(input_geojson_path)
        
    else:
        print(f"Input GeoJSON file does not exist: {input_geojson_path}")
        
    
    #read geojson as geodataframe    
    gdf = gpd.read_file(input_geojson_path)
    
    print("Successfully loaded the GeoJSON file.")
    print("Current CRS:", gdf.crs)
    
    if gdf.crs is None or gdf.crs.to_epsg() != 3857:
        gdf.set_crs(epsg=3857, inplace=True)
        print("CRS was not set. Set to EPSG:3857.")
        
    #Reproject to crs 4326 (WGS84)
    gdf_wgs84 = gdf.to_crs(epsg=4326)
    print("Updated CRS:", gdf_wgs84.crs)
    
    #Save the update crs geojson
    gdf_wgs84.to_file(r'D:\Master in Computation design\Module 4 - Thesis\visual studio  code\new project\dxf-analyzer\app\uploads\BcobeWGS84.geojson')
    
    #Again load the updated geojson for further processing 
    input_geojson_path2 = r'D:\Master in Computation design\Module 4 - Thesis\visual studio  code\new project\dxf-analyzer\app\uploads\BcobeWGS84.geojson'
    
    cobe_wgs84 = gpd.read_file(input_geojson_path2)
    
    if os.path.exists(input_geojson_path2):
        print(f"File exists: {input_geojson_path2}")
    else:
        print(f"File does not exist: {input_geojson_path2}")
        

    # Extract latitude and longitude
    def extract_lat_lon(geometry):
        if geometry is not None and geometry.geom_type == 'LineString':
            coords = list(geometry.coords)
            return coords[0][1], coords[0][0]  # (latitude, longitude)
        return None, None
    
    # Apply the function to the 'geometry' column
    cobe_wgs84['latitude'], cobe_wgs84['longitude'] = zip(*cobe_wgs84['geometry'].apply(extract_lat_lon))
    
    # Split the 'Layer' column and create a new column 'Urban_Elements'
    cobe_wgs84['Urban_Elements'] = cobe_wgs84['Layer'].str.split('$').str[0].fillna(cobe_wgs84['Layer'])
    
    # Create a new column 'Function' based on the condition
    cobe_wgs84['Building_Function'] = cobe_wgs84.apply(lambda row: row['Layer'].split('$')[1] if row['Layer'].startswith('Buildings') and '$' in row['Layer'] else None, axis=1)
    
    # Create a new column 'Building_Height' based on the condition
    cobe_wgs84['Building_no_of_floors'] = np.where(cobe_wgs84['Layer'].str.startswith('Buildings'), cobe_wgs84['Linetype'], np.nan)
    
    print(cobe_wgs84['Building_no_of_floors'].unique())
    
    # Step 1: Replace None with np.nan
    cobe_wgs84['Building_no_of_floors'] = cobe_wgs84['Building_no_of_floors'].replace({None: np.nan})
    
    cobe_wgs84['Building_no_of_floors'] = cobe_wgs84['Building_no_of_floors'].fillna(0)
    
    print(cobe_wgs84['Building_no_of_floors'].unique())
    
    def convert_to_number(value):
        try:
            # Remove spaces and convert to float
            return float(str(value).replace(' ', ''))
        except ValueError:
            return 0  # Return 0 for any value that can't be converted
        
    # Apply the custom function to the column    
    cobe_wgs84['Building_no_of_floors2'] = cobe_wgs84['Building_no_of_floors'].apply(convert_to_number)
    
    # Step 2: Create the 'Building_Height' column
    cobe_wgs84['height'] = cobe_wgs84['Building_no_of_floors2'] * 3.8
    
    print(cobe_wgs84['height'].unique())
    
    # Step 2: Create the 'Building_Height' column
    cobe_wgs84['min_height'] = 0
    
    # Add 'extrude' column and set it to 'false' by default
    cobe_wgs84['extrude'] = 'false'
    
    # Set 'extrude' to 'true' for rows where 'Urban_Elements' is 'Buildings'
    cobe_wgs84.loc[cobe_wgs84['Urban_Elements'] == 'Buildings', 'extrude'] = 'true'
    
    print(cobe_wgs84['min_height'].unique())
    
    # Define the mapping from Linetype to Street Type
    linetype_to_street_type = {'DashDot': 'Pathway', 'Center': 'Thick green color', 'Dashed': 'Mediumn Thick green', None: 'Thin green', 'DOT': 'Orange color Driverless bus road', 'Hidden': 'Periphery Road'}
    
    # Apply the mapping only for rows where Layer == 'Street' and geometry type is 'LineString'
    mask = (cobe_wgs84['Layer'] == 'Street') & (cobe_wgs84['geometry'].apply(lambda x: x.geom_type == 'LineString'))
    
    # Create the new Street Type column based on the mapping
    cobe_wgs84.loc[mask, 'Street Type'] = cobe_wgs84.loc[mask, 'Linetype'].replace(linetype_to_street_type)
    
    # Specify the layer names you want to filter by
    target_layer_names = ['Pavement', 'Buildings', 'Tree', 'Cycle Park',
       'Green_Spaces', 'bus stops', 'metro', 'Playgrounds', 'Site']
    
    # Filter the GeoDataFrame to get only the linestrings from the specified layers
    mask2 = cobe_wgs84['Urban_Elements'].isin(target_layer_names) & (cobe_wgs84.geometry.type == 'LineString')
    
    # Convert linestrings to polygons using buffer() and update the original GeoDataFrame
    buffer_distance = 0.0000001  # Adjust this value as needed
    cobe_wgs84.loc[mask2, 'geometry'] = cobe_wgs84.loc[mask2, 'geometry'].buffer(buffer_distance)
    
#Clean the geometry of BUILDING
    def clean_geometry(geom):
        # Iterate over the geometry column, not the filtered dataframe
        if geom.geom_type == 'Polygon':
            if len(geom.interiors) > 0:
                return Polygon(geom.interiors[-1])
            else:
                return geom
        else:
            return geom
        
    target_layer = ['Pavement', 'Buildings','Tree',
       'Green_Spaces', 'Playgrounds']
    
    # Apply the function only to rows with 'Residential' in 'urban_elements'
    cobe_wgs84.loc[cobe_wgs84['Urban_Elements'].isin(target_layer), 'geometry'] = cobe_wgs84.loc[cobe_wgs84['Urban_Elements'].isin(target_layer), 'geometry'].apply(clean_geometry)
    
    
    
    print(cobe_wgs84.head(5))
    
    
    # # Initialize an empty graph for streets
    # G = nx.Graph()
    
    # # Create nodes for intersections (street endpoints)
    # for index, row in cobe_wgs84.iterrows():
    #     if row['Layer'] == 'Street' and row.geometry.type == "LineString":
    #          # Extract start and end points
    #          start_point = (row.geometry.coords[0][0], row.geometry.coords[0][1])
    #          end_point = (row.geometry.coords[-1][0], row.geometry.coords[-1][1])
             
    #          # Add nodes only if they don't already exist
    #          if start_point not in G.nodes:
    #               G.add_node(start_point)
    #          if end_point not in G.nodes:
    #              G.add_node(end_point)
                 
    #         # Add edges between start and end points
    #          if start_point != end_point:
    #              G.add_edge(start_point, end_point)
    
    
    geojson_filename = 'output.geojson'
    geojson_path = os.path.join(uploads_dir, geojson_filename)
    cobe_wgs84.to_file(geojson_path, driver='GeoJSON')
    return geojson_filename
   

@app.route('/geojson/<path:filename>', methods=['GET'])
def serve_geojson(filename):
    return send_from_directory(uploads_dir, filename)

if __name__ == '__main__':
    app.run(debug=True)