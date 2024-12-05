from flask import Flask, request, redirect, url_for, send_from_directory, render_template
import os
import geopandas as gpd
import numpy as np
import math
from werkzeug.utils import secure_filename
import networkx as nx
from shapely.geometry import LineString, Polygon

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'dxf', 'geojson'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def scale_factor(coordinate):
    coordinate_rad = math.radians(coordinate)
    return 1 / math.cos(coordinate_rad)

def process_dxf(file_path):
    # Read the DXF file
    cobe = gpd.read_file(file_path)
    
    # Scale the geometries
    x = 55.6588  # Latitude for scaling
    scale_x = scale_factor(x)
    cobe['geometry'] = cobe['geometry'].scale(scale_x, scale_x, origin=(0, 0, 0))
    
    # Translate the geometries
    cobe['geometry'] = cobe['geometry'].translate(1395773.831, 7489901.409, 0)
    
    # Create the GeoDataFrame with CRS
    cobe_spatial = gpd.GeoDataFrame(cobe, geometry='geometry')
    cobe_spatial.set_crs(epsg=3857, inplace=True)
    
    # Save as GeoJSON
    geojson_path = os.path.join(app.config['UPLOAD_FOLDER'], 'Bcobe.geojson')
    cobe_spatial.to_file(geojson_path, driver='GeoJSON')
    
    # Process the GeoJSON
    geojson_wgs84_path = process_geojson(geojson_path)
    
    return geojson_wgs84_path

def process_geojson(file_path):
    # Load GeoDataFrame
    cobe_wgs84 = gpd.read_file(file_path)

    # Extract latitude and longitude
    def extract_lat_lon(geometry):
        if geometry is not None and geometry.geom_type == 'LineString':
            coords = list(geometry.coords)
            return coords[0][1], coords[0][0]  # (latitude, longitude)
        return None, None

    cobe_wgs84['latitude'], cobe_wgs84['longitude'] = zip(*cobe_wgs84['geometry'].apply(extract_lat_lon))

    # Create Urban_Elements column
    cobe_wgs84['Urban_Elements'] = cobe_wgs84['Layer'].str.split('$').str[0].fillna(cobe_wgs84['Layer'])

    # Building Function and Height
    cobe_wgs84['Building_Function'] = cobe_wgs84.apply(
        lambda row: row['Layer'].split('$')[1] if row['Layer'].startswith('Buildings') and '$' in row['Layer'] else None,
        axis=1
    )
    cobe_wgs84['Building_no_of_floors'] = np.where(
        cobe_wgs84['Layer'].str.startswith('Buildings'),
        cobe_wgs84['Linetype'],
        np.nan
    )

    # Street Type Mapping
    linetype_to_street_type = {
        'DashDot': 'Pathway',
        'Center': 'Thick green color',
        'Dashed': 'Medium Thick green',
        None: 'Thin green',
        'DOT': 'Orange color Driverless bus road',
        'Hidden': 'Periphery Road'
    }
    mask = (cobe_wgs84['Layer'] == 'Street') & (cobe_wgs84['geometry'].apply(lambda x: x.geom_type == 'LineString'))
    cobe_wgs84.loc[mask, 'Street Type'] = cobe_wgs84.loc[mask, 'Linetype'].replace(linetype_to_street_type)

    # Convert LineStrings to Polygons for certain layers
    target_layer_names = ['Pavement', 'Buildings', 'Tree', 'Cycle Park', 'Green_Spaces', 'bus stops', 'metro', 'Playgrounds']
    mask = cobe_wgs84['Urban_Elements'].isin(target_layer_names) & (cobe_wgs84.geometry.type == 'LineString')
    buffer_distance = 0.0000001
    cobe_wgs84.loc[mask, 'geometry'] = cobe_wgs84.loc[mask, 'geometry'].buffer(buffer_distance)

    # Initialize graph for streets
    G = nx.Graph()
    for index, row in cobe_wgs84.iterrows():
        if row['Layer'] == 'Street' and row.geometry.type == "LineString":
            start_point = (row.geometry.coords[0][0], row.geometry.coords[0][1])
            end_point = (row.geometry.coords[-1][0], row.geometry.coords[-1][1])
            if start_point not in G.nodes:
                G.add_node(start_point)
            if end_point not in G.nodes:
                G.add_node(end_point)
            if start_point != end_point:
                G.add_edge(start_point, end_point)
                
    print(cobe_wgs84)

    # Save the updated GeoDataFrame
    cobe_wgs84.to_file(file_path, driver='GeoJSON')

    return cobe_wgs84

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Process the DXF file and get the path of the GeoJSON
        geojson_path = process_dxf(file_path)
        
        # Return the path to the new GeoJSON file
        return redirect(url_for('uploaded_file', filename=os.path.basename(geojson_path)))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
