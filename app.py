"""
Matcha Inventory Management System - Complete Web Interface
This is the main Flask app that runs the web interface
"""

# Flask is what lets us make a web app with routes and pages
from flask import Flask, request, redirect, url_for, jsonify, send_file
import os
from datetime import datetime
from functools import wraps
#from flask_limiter import Limiter
#from flask_limiter.util import get_remote_address

# Import all our inventory functions from inventory_app.py
from inventory_app import (
    create_database, add_raw_material, get_all_materials, get_low_stock_materials,
    increase_raw_material, decrease_raw_material, get_raw_material, add_to_batches,
    get_batches, mark_as_shipped, delete_batch, get_recipe, add_recipe,
    change_recipe, delete_recipe, delete_raw_material
)

# Import helper functions for exporting data
from helper_functions import (export_to_csv, backup_database)

# Create the Flask app instance - this is the web server
app = Flask(__name__)



# =======================
# DATABASE SETUP & CHECKS
# ========================


# Debug output to check if we're using PostgreSQL (Railway) or SQLite (local)
print("=" * 60)
print("🔍 DEBUG: Checking DATABASE_URL")
print(f"DATABASE_URL = {os.getenv('DATABASE_URL')}")
print("=" * 60)

# Make sure we have a 'data' folder for local SQLite database
if not os.path.exists('data'):
    os.makedirs('data')

# Try to connect to the database - if it fails, create one
try:
    from database import get_connection
    conn = get_connection()
    conn.close()
    print("✅ Database connection successful")
except:
    # If connection fails, initialize a new database
    print("🔧 Initializing database...")
    create_database()



#################
#CHECK AUTHURIZATION
###################

# ======================== 
# RATE LIMITING SETUP

#limiter = Limiter(
#    app=app,
 ##   default_limits=["200 per day", "50 per hour"] 
    # Limit each IP to 200 requests per day and 100 per hour
#)
# ========================




# os.environ.get() reads environment variables
# Second parameter is fallback for local testing
AUTH_USERNAME = os.environ.get('AUTH_USERNAME', 'botanik_admin')
AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD', 'matcha_220')

# In production (Railway): Reads from environment variable
# Locally (your laptop): Uses fallback value



#use "@requires_auth" above any route to require authentication
def requires_auth(f):
    @wraps(f) # Decorator to require authentication for a route
    
    def decorated(*args, **kwargs): # The actual decorator function
        auth = request.authorization # Get auth info from request
         # If no auth or incorrect auth, send 401 response
        if not auth or not check_auth(auth.username, auth.password): #calls check auth, if False
            return authenticate()# Send 401 response to prompt for login
         # If auth is correct, proceed to the actual route function

        return f(*args, **kwargs)# Call the original route function which is the 
    return decorated


def check_auth(username, password):
    """Check if a username/password combination is valid."""
    return username == AUTH_USERNAME and password == AUTH_PASSWORD



def authenticate(): 
    
    """Sends a 401 response that enables basic auth"""
    return jsonify({'message': 'Authentication required.'}), 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}
# 




# ========================
# WEB ROUTES (PAGES)
# ========================

# The '@app.route' decorator tells Flask what URL should trigger this function
# '/' means the home page (like http://localhost:8000/)
@app.route('/')
@requires_auth
def index():
    # Return HTML for the home page - it's all inline here as one big string
    return """<!DOCTYPE html><html><head><title>Matcha Inventory</title><style>
    body{font-family:Arial;max-width:1400px;margin:30px auto;padding:20px;background:linear-gradient(135deg,#f5f7fa 0%,#c3cfe2 100%)}
    .container{background:white;padding:40px;border-radius:15px;box-shadow:0 10px 30px rgba(0,0,0,0.2);position:relative}
    .logo{position:absolute;top:20px;left:20px;z-index:100}
    .logo img{width:60px;height:60px;object-fit:contain;transition:opacity 0.3s}
    .logo img:hover{opacity:0.8}
    h1{color:#2c5f2d;border-bottom:4px solid #97bc62;padding-bottom:15px;margin-bottom:30px}
    .menu-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:25px;margin-top:30px}
    .menu-section{background:#f8f9fa;padding:20px;border-radius:10px;border-left:5px solid #97bc62}
    .menu-section h2{color:#2c5f2d;margin-top:0;font-size:20px}
    .menu-item{display:block;background:white;padding:15px;margin:10px 0;border-radius:8px;text-decoration:none;color:#2c5f2d;border:2px solid #e0e0e0;transition:all 0.3s}
    .menu-item:hover{background:#97bc62;color:white;transform:translateX(5px);border-color:#97bc62}
    .emoji{font-size:20px;margin-right:10px}
    </style></head><body><div class="container">
    <a href="/" class="logo"><img src="/static/images/logo.png" alt="Botanik Logo"></a>
    <h1>         Botanik Inventory Management System</h1>
    <p style="color:#666;">Inventory control and managment</p>
    <div class="menu-grid">
    <div class="menu-section"><h2>📦 Inventory & Materials</h2>
    <a href="/inventory" class="menu-item"><span class="emoji">📋</span> View All Materials</a>
    <a href="/low-stock" class="menu-item"><span class="emoji">⚠️</span> Low Stock Alerts</a>
    <a href="/add-material" class="menu-item"><span class="emoji">➕</span> Add New Material</a>
    <a href="/manage-materials" class="menu-item"><span class="emoji">🔧</span> Manage Materials</a>
    </div>
    <div class="menu-section"><h2>🏭 Batch Management</h2>
    <a href="/batches" class="menu-item"><span class="emoji">📋</span> View Ready Batches</a>
    <a href="/create-batch" class="menu-item"><span class="emoji">➕</span> Create New Batch</a>
    <a href="/manage-batches" class="menu-item"><span class="emoji">🔧</span> Manage Batches</a>
    </div>
    <div class="menu-section"><h2>📖 Recipes</h2>
    <a href="/recipes" class="menu-item"><span class="emoji">📋</span> View All Recipes</a>
    <a href="/add-recipe" class="menu-item"><span class="emoji">➕</span> Add New Recipe</a>
    <a href="/manage-recipes" class="menu-item"><span class="emoji">🔧</span> Manage Recipes</a>
    </div>
    <div class="menu-section"><h2>📊 Reports & System</h2>
    <a href="/export-inventory" class="menu-item"><span class="emoji">📥</span> Export Inventory</a>
    <a href="/export-low-stock" class="menu-item"><span class="emoji">📥</span> Export Low Stock</a>
    <a href="/backup" class="menu-item"><span class="emoji">💾</span> Create Backup</a>
    </div></div></div></body></html>"""

# Helper function to keep CSS consistent across pages
def get_common_styles():
    # Returns CSS that's used on multiple pages - keeps styling consistent
    return """body{font-family:Arial;margin:20px;background:linear-gradient(135deg,#f5f7fa 0%,#c3cfe2 100%);min-height:100vh}
    .container{background:white;padding:30px;border-radius:10px;max-width:1200px;margin:0 auto;box-shadow:0 4px 6px rgba(0,0,0,0.1);position:relative}
    .logo{position:absolute;top:20px;left:20px;z-index:100}
    .logo img{width:60px;height:60px;object-fit:contain;transition:opacity 0.3s}
    .logo img:hover{opacity:0.8}
    h1{color:#2c5f2d;border-bottom:3px solid #97bc62;padding-bottom:10px}
    .back-link{display:inline-block;margin-bottom:20px;color:#2c5f2d;text-decoration:none;font-weight:bold}
    .back-link:hover{text-decoration:underline}"""

# Helper function to generate logo HTML
def get_logo_html():
    # Returns HTML for the logo in the top-left corner
    return """<a href="/" class="logo"><img src="/static/images/logo.png" alt="Botanik Logo"></a>"""

# ========================
# INVENTORY PAGES
# ========================

@app.route('/inventory')

def view_inventory():
    # Get all materials from database as a pandas dataframe
    df = get_all_materials()

    # If there's no materials, show a message, otherwise convert dataframe to HTML table
    table_html = '<p style="color:#666;">No materials in inventory. <a href="/add-material">Add your first material</a></p>' if df.empty else df.to_html(index=False, classes='data-table', border=0)

    # Return the full HTML page with the table embedded using an f-string
    return f"""<!DOCTYPE html><html><head><title>Inventory</title><style>
    {get_common_styles()}
    .data-table{{width:100%;border-collapse:collapse;margin:20px 0}}
    .data-table th,.data-table td{{padding:12px;text-align:left;border-bottom:1px solid #ddd}}
    .data-table th{{background:#97bc62;color:white;font-weight:bold}}
    .data-table tr:hover{{background:#f0f8f0}}
    </style></head><body><div class="container">
    {get_logo_html()}
    <a href="/" class="back-link">← Back to Home</a>
    <h1>📦 Current Inventory</h1>
    <p>Total materials: {len(df)}</p>
    {table_html}</div></body></html>"""

@app.route('/add-material', methods=['GET', 'POST'])

def add_material_route():
    # This route handles both GET (showing the form) and POST (submitting the form)

    if request.method == 'POST':
        # When form is submitted, get all the form data and add to database
        result = add_raw_material(
            name=request.form.get('name'),
            category=request.form.get('category'),
            stock_level=float(request.form.get('stock_level', 0)),
            unit=request.form.get('unit'),
            reorder_level=float(request.form.get('reorder_level', 0)),
            cost_per_unit=float(request.form.get('cost_per_unit', 0)),
            supplier=request.form.get('supplier') or None  # Supplier is optional
        )
        # If successful, redirect to inventory page, otherwise show error
        return redirect(url_for('view_inventory')) if result else ("Error adding material", 500)

    # If it's a GET request, show the form to add a new material
    return """<!DOCTYPE html><html><head><title>Add Material</title><style>
    """ + get_common_styles() + """
    .form-group{margin-bottom:20px}
    label{display:block;margin-bottom:5px;font-weight:bold;color:#555}
    input{width:100%;padding:10px;border:1px solid #ddd;border-radius:5px;box-sizing:border-box}
    button{background:#97bc62;color:white;padding:12px 30px;border:none;border-radius:5px;cursor:pointer;font-size:16px}
    button:hover{background:#7da34f}
    </style></head><body><div class="container">
    """ + get_logo_html() + """
    <a href="/" class="back-link">← Back to Home</a>
    <h1>➕ Add New Material</h1>
    <form method="POST">
    <div class="form-group"><label>Material Name *</label><input type="text" name="name" required></div>
    <div class="form-group"><label>Category *</label><input type="text" name="category" required></div>
    <div class="form-group"><label>Initial Stock Level *</label><input type="number" step="0.01" name="stock_level" required></div>
    <div class="form-group"><label>Unit *</label><input type="text" name="unit" required></div>
    <div class="form-group"><label>Reorder Level *</label><input type="number" step="0.01" name="reorder_level" required></div>
    <div class="form-group"><label>Cost per Unit *</label><input type="number" step="0.01" name="cost_per_unit" required></div>
    <div class="form-group"><label>Supplier (optional)</label><input type="text" name="supplier"></div>
    <button type="submit">Add Material</button>
    </form></div></body></html>"""

# ========================
# LOW STOCK ALERTS
# ========================

@app.route('/low-stock')

def low_stock():
    # Get all materials where stock is below reorder level
    df = get_low_stock_materials()

    # Show success message if everything is stocked, or show the low stock table
    if df.empty:
        message = '<p style="color:green;font-size:18px;">✅ All materials are adequately stocked!</p>'
    else:
        message = f'<p style="color:red;font-size:18px;">⚠️ {len(df)} material(s) need reordering:</p>'
        message += df.to_html(index=False, classes='data-table', border=0)

    return f"""<!DOCTYPE html><html><head><title>Low Stock</title><style>
    {get_common_styles()}
    .data-table{{width:100%;border-collapse:collapse;margin:20px 0}}
    .data-table th,.data-table td{{padding:12px;text-align:left;border-bottom:1px solid #ddd}}
    .data-table th{{background:#dc3545;color:white}}
    .data-table tr:hover{{background:#fff3cd}}
    </style></head><body><div class="container">
    {get_logo_html()}
    <a href="/" class="back-link">← Back to Home</a>
    <h1>⚠️ Low Stock Alerts</h1>
    {message}</div></body></html>"""

# ========================
# API ENDPOINTS
# ========================

@app.route('/api/health')
def health_check():
    # Simple health check endpoint - returns JSON to confirm the app is running
    # Useful for Railway or other hosting platforms to check if app is alive
    return jsonify({'status': 'healthy', 'service': 'matcha-inventory', 'timestamp': datetime.now().isoformat()})

# ========================
# START THE APP
# ========================

if __name__ == '__main__':
    # Get port from environment variable (Railway sets this) or default to 8000
    port = int(os.environ.get('PORT', 8000))

    # Run the Flask app
    # host='0.0.0.0' means it's accessible from any IP (needed for Railway)
    # debug=False for production (debug=True shows detailed errors but is unsafe in production)
    app.run(host='0.0.0.0', port=port, debug=False)
