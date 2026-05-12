from flask import Blueprint, jsonify, request
from datetime import datetime
import logging
import json

from auth import requires_auth
from database import get_db_connection
from services.materials import get_all_materials
from services.lots import get_all_lots_for_material, get_lots_for_material
from services.recipes import get_all_recipes, get_recipe

api_bp = Blueprint('api', __name__, url_prefix='/api')


# checks db connection and returns service status
@api_bp.route('/health')
def health_check():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        db.execute(cursor, "SELECT 1")
        db.close()
        db_status = 'connected'
    except Exception as e:
        logging.error(f"health_check: {e}", exc_info=True)
        db_status = 'error'
    return jsonify({'status': 'healthy', 'db': db_status, 'service': 'matcha-inventory', 'timestamp': datetime.now().isoformat()})


# autocomplete dropdown for material search (requires JS on frontend)
@api_bp.route('/materials')
@requires_auth
def api_materials():
    df = get_all_materials()
    if df.empty:
        return jsonify([])
    return jsonify(df['name'].dropna().sort_values().tolist())


# autocomplete dropdown for recipe search when making a batch (requires JS on frontend)
@api_bp.route('/recipes')
@requires_auth
def api_recipes():
    df = get_all_recipes()
    if df.empty:
        return jsonify([])
    return jsonify(df['recipe_product_name'].dropna().drop_duplicates().sort_values().tolist())


# returns all lots for a given material (used to populate lot selection dropdowns)
@api_bp.route('/lots/<material_id>')
@requires_auth
def api_lots(material_id):
    df = get_all_lots_for_material(material_id=material_id)
    if df is None or df.empty:
        return jsonify([])
    return jsonify(json.loads(df.to_json(orient='records')))


# looks up a material's unit by name (used to auto-fill unit field on forms)
@api_bp.route('/material-unit')
@requires_auth
def api_material_unit():
    name = request.args.get('name', '').strip()
    if not name:
        return jsonify({'exists': False})
    df = get_all_materials()
    if df is None or df.empty:
        return jsonify({'exists': False})
    match = df[df['name'].str.lower() == name.lower()]
    if match.empty:
        return jsonify({'exists': False})
    return jsonify({'exists': True, 'unit': match.iloc[0]['unit']})



#will return all AVAILABLE lots for batch creation drop down. 
@api_bp.route('/available-lots/<material_id>')
@requires_auth
def api_available_lots(material_id):
    df = get_lots_for_material(material_id=material_id)
    if df is None or df.empty:
        return jsonify([])
    return jsonify(json.loads(df.to_json(orient='records')))
# json.loads(df.to_json(orient='records')) converts the DataFrame to a list of dictionaries, 
# which can be easily consumed by the frontend JavaScript code.

#will return recipe given a name, for frontend of batch creation. needs to know which lots to ask user about. 
@api_bp.route('/recipe-materials/<path:product_name>')
@requires_auth
def api_recipe_materials(product_name):
    df = get_recipe(product_name)
    if df is None or df.empty:
        return jsonify([])
    return jsonify(df.to_dict(orient='records'))