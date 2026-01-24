"""
Matcha Inventory Management System - Complete Web Interface
"""

from flask import Flask, request, redirect, url_for, jsonify, send_file
import os
from datetime import datetime

from inventory_app import (
    create_database, add_raw_material, get_all_materials, get_low_stock_materials,
    increase_raw_material, decrease_raw_material, get_raw_material, add_to_batches,
    get_batches, mark_as_shipped, delete_batch, get_recipe, add_recipe,
    change_recipe, delete_recipe, delete_raw_material
)

from helper_functions import (export_to_csv, backup_database)

app = Flask(__name__)



import os
print("=" * 60)
print("🔍 DEBUG: Checking DATABASE_URL")
print(f"DATABASE_URL = {os.getenv('DATABASE_URL')}")
print("=" * 60)


if not os.path.exists('data'):
    os.makedirs('data')

try:
    from database import get_connection
    conn = get_connection()
    conn.close()
    print("✅ Database connection successful")
except:
    print("🔧 Initializing database...")
    create_database()



@app.route('/')
def index():
    return """<!DOCTYPE html><html><head><title>Matcha Inventory</title><style>
    body{font-family:Arial;max-width:1400px;margin:30px auto;padding:20px;background:linear-gradient(135deg,#f5f7fa 0%,#c3cfe2 100%)}
    .container{background:white;padding:40px;border-radius:15px;box-shadow:0 10px 30px rgba(0,0,0,0.2)}
    h1{color:#2c5f2d;border-bottom:4px solid #97bc62;padding-bottom:15px;margin-bottom:30px}
    .menu-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:25px;margin-top:30px}
    .menu-section{background:#f8f9fa;padding:20px;border-radius:10px;border-left:5px solid #97bc62}
    .menu-section h2{color:#2c5f2d;margin-top:0;font-size:20px}
    .menu-item{display:block;background:white;padding:15px;margin:10px 0;border-radius:8px;text-decoration:none;color:#2c5f2d;border:2px solid #e0e0e0;transition:all 0.3s}
    .menu-item:hover{background:#97bc62;color:white;transform:translateX(5px);border-color:#97bc62}
    .emoji{font-size:20px;margin-right:10px}
    </style></head><body><div class="container"><h1>🍵 Matcha Inventory Management System</h1>
    <p style="color:#666;">Complete inventory control at your fingertips</p>
    <div class="menu-grid">
    <div class="menu-section"><h2>📦 Inventory & Materials</h2>
    <a href="/inventory" class="menu-item"><span class="emoji">📋</span> View All Materials</a>
    <a href="/low-stock" class="menu-item"><span class="emoji">⚠️</span> Low Stock Alerts</a>
    <a href="/add-material" class="menu-item"><span class="emoji">➕</span> Add New Material</a>
    <a href="/manage-materials" class="menu-item"><span class="emoji">🔧</span> Manage Materials</a>
    </div>
    <div class="menu-section"><h2>🏭 Batch Management</h2>
    <a href="/batches" class="menu-item"><span class="emoji">📦</span> View Ready Batches</a>
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

def get_common_styles():
    return """body{font-family:Arial;margin:20px;background:linear-gradient(135deg,#f5f7fa 0%,#c3cfe2 100%);min-height:100vh}
    .container{background:white;padding:30px;border-radius:10px;max-width:1200px;margin:0 auto;box-shadow:0 4px 6px rgba(0,0,0,0.1)}
    h1{color:#2c5f2d;border-bottom:3px solid #97bc62;padding-bottom:10px}
    .back-link{display:inline-block;margin-bottom:20px;color:#2c5f2d;text-decoration:none;font-weight:bold}
    .back-link:hover{text-decoration:underline}"""

@app.route('/inventory')
def view_inventory():
    df = get_all_materials()
    table_html = '<p style="color:#666;">No materials in inventory. <a href="/add-material">Add your first material</a></p>' if df.empty else df.to_html(index=False, classes='data-table', border=0)
    return f"""<!DOCTYPE html><html><head><title>Inventory</title><style>
    {get_common_styles()}
    .data-table{{width:100%;border-collapse:collapse;margin:20px 0}}
    .data-table th,.data-table td{{padding:12px;text-align:left;border-bottom:1px solid #ddd}}
    .data-table th{{background:#97bc62;color:white;font-weight:bold}}
    .data-table tr:hover{{background:#f0f8f0}}
    </style></head><body><div class="container">
    <a href="/" class="back-link">← Back to Home</a>
    <h1>📦 Current Inventory</h1>
    <p>Total materials: {len(df)}</p>
    {table_html}</div></body></html>"""

@app.route('/add-material', methods=['GET', 'POST'])
def add_material_route():
    if request.method == 'POST':
        result = add_raw_material(
            name=request.form.get('name'), category=request.form.get('category'),
            stock_level=float(request.form.get('stock_level', 0)), unit=request.form.get('unit'),
            reorder_level=float(request.form.get('reorder_level', 0)),
            cost_per_unit=float(request.form.get('cost_per_unit', 0)),
            supplier=request.form.get('supplier') or None
        )
        return redirect(url_for('view_inventory')) if result else ("Error adding material", 500)
    
    return """<!DOCTYPE html><html><head><title>Add Material</title><style>
    """ + get_common_styles() + """
    .form-group{margin-bottom:20px}
    label{display:block;margin-bottom:5px;font-weight:bold;color:#555}
    input{width:100%;padding:10px;border:1px solid #ddd;border-radius:5px;box-sizing:border-box}
    button{background:#97bc62;color:white;padding:12px 30px;border:none;border-radius:5px;cursor:pointer;font-size:16px}
    button:hover{background:#7da34f}
    </style></head><body><div class="container">
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

@app.route('/low-stock')
def low_stock():
    df = get_low_stock_materials()
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
    <a href="/" class="back-link">← Back to Home</a>
    <h1>⚠️ Low Stock Alerts</h1>
    {message}</div></body></html>"""

@app.route('/api/health')
def health_check():
    return jsonify({'status': 'healthy', 'service': 'matcha-inventory', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
