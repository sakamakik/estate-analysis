from flask import Flask, render_template, request, jsonify, send_from_directory
from condo_extractor import extract_listing_data, get_centris_id_from_url, get_cached_data
import re
import os
import json

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chart')
def chart():
    return render_template('chart.html')

@app.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory('data', filename)

@app.route('/api/property-data')
def property_data():
    data_points = []
    data_dir = 'data'
    
    # Read all JSON files in the data directory
    for filename in os.listdir(data_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(data_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    property_data = json.load(f)
                    
                    # Only include if we have price
                    price = property_data.get('price')
                    terrain = property_data.get('municipal_terrain')
                    building = property_data.get('municipal_building')
                    sqft = property_data.get('sqft')
                    
                    if price:
                        total_assessment = None
                        if terrain and building:
                            total_assessment = int(terrain) + int(building)
                            
                        centris_id = property_data.get('centris_id', '')
                        
                        # Check if photo exists in data directory
                        photo_path = None
                        if centris_id:
                            if os.path.exists(os.path.join('data', f'{centris_id}.jpeg')):
                                photo_path = f'{centris_id}.jpeg'
                        
                        data_points.append({
                            'price': int(price),
                            'assessment': total_assessment,
                            'sqft': sqft,
                            'price_per_sqft': round(int(price) / int(sqft)) if sqft else None,
                            'address': property_data.get('address', 'Unknown'),
                            'centris_id': centris_id,
                            'photo_path': photo_path
                        })
            except Exception as e:
                print(f"Error reading {filename}: {str(e)}")
    
    return jsonify(data_points)

@app.route('/extract', methods=['POST'])
def extract():
    url = request.form.get('url', '').strip()
    
    # Validate URL
    if not url:
        return jsonify({'error': 'URL is required'}), 400
        
    if not re.match(r'^https?://(?:www\.)?centris\.ca/fr/', url):
        return jsonify({'error': 'Invalid Centris URL. Please enter a valid Centris listing URL.'}), 400
    
    try:
        # Check if data is already cached
        centris_id = get_centris_id_from_url(url)
        cached_data = get_cached_data(centris_id) if centris_id else None
        
        # Get data (either from cache or web)
        data = extract_listing_data(url)
        
        return jsonify({
            'success': True,
            'data': data,
            'fromCache': cached_data is not None
        })
    except Exception as e:
        return jsonify({'error': f'Failed to extract data: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
