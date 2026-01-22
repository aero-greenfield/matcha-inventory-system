"""
Matcha Inventory Management System - Complete Web Interface
Full-featured Flask app with ALL CLI features

FEATURES INCLUDED (matches cli.py):
✅ View inventory
✅ Add material
✅ Restock material (increase)
✅ Decrease material stock
✅ Delete material
✅ View low stock alerts
✅ Create batch
✅ View batches
✅ Mark batch as shipped
✅ Delete batch
✅ View recipe
✅ Add recipe
✅ Modify recipe
✅ Delete recipe
✅ Export to CSV
✅ Database backups
"""

from flask import Flask, request, redirect, url_for, jsonify, send_file
import os
from datetime import datetime

# Import ALL functions from inventory_app.py
from inventory_app import (
    create_database,
    add_raw_material,
    get_all_materials,
    get_low_stock_materials,
    increase_raw_material,
    decrease_raw_material,
    get_raw_material,
    add_to_batches,
    get_batches,
    mark_as_shipped,
    delete_batch,
    get_recipe,
    add_recipe,
    change_recipe,
    delete_recipe,
    delete_raw_material
)

# Import helper functions
from helper_functions import (
    export_to_csv,
    backup_database
)

app = Flask(__name__)

# ============================================================
# DATABASE INITIALIZATION
# ============================================================

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


# ============================================================
# HOME PAGE
# ============================================================

@app.route('/')
def index():
    """Main navigation page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Matcha Inventory System</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 1400px;
                margin: 30px auto;
                padding: 20px;
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            h1 {
                color: #2c5f2d;
                border-bottom: 4px solid #97bc62;
                padding-bottom: 15px;
                margin-bottom: 30px;
            }
            .menu-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 25px;
                margin-top: 30px;
            }
            .menu-section {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                border-left: 5px solid #97bc62;
            }
            .menu-section h2 {
                color: #2c5f2d;
                margin-top: 0;
                font-size: 20px;
            }
            .menu-item {
                display: block;
                background: white;
                padding: 15px;
                margin: 10px 0;
                border-radius: 8px;
                text-decoration: none;
                color: #2c5f2d;
                border: 2px solid #e0e0e0;
                transition: all 0.3s;
            }
            .menu-item:hover {
                background: #97bc62;
                color: white;
                transform: translateX(5px);
                border-color: #97bc62;
            }
            .emoji { font-size: 20px; margin-right: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🍵 Matcha Inventory Management System</h1>
            <p style="color: #666;">Complete inventory control at your fingertips</p>
            
            <div class="menu-grid">
                <!-- INVENTORY & MATERIALS -->
                <div class="menu-section">
                    <h2>📦 Inventory & Materials</h2>
                    <a href="/inventory" class="menu-item">
                        <span class="emoji">📋</span> View All Materials
                    </a>
                    <a href="/low-stock" class="menu-item">
                        <span class="emoji">⚠️</span> Low Stock Alerts
                    </a>
                    <a href="/add-material" class="menu-item">
                        <span class="emoji">➕</span> Add New Material
                    </a>
                    <a href="/manage-materials" class="menu-item">
                        <span class="emoji">🔧</span> Manage Materials
                    </a>
                </div>
                
                <!-- BATCH MANAGEMENT -->
                <div class="menu-section">
                    <h2>🏭 Batch Management</h2>
                    <a href="/batches" class="menu-item">
                        <span class="emoji">📦</span> View Ready Batches
                    </a>
                    <a href="/create-batch" class="menu-item">
                        <span class="emoji">➕</span> Create New Batch
                    </a>
                    <a href="/manage-batches" class="menu-item">
                        <span class="emoji">🔧</span> Manage Batches
                    </a>
                </div>
                
                <!-- RECIPES -->
                <div class="menu-section">
                    <h2>📖 Recipes</h2>
                    <a href="/recipes" class="menu-item">
                        <span class="emoji">📋</span> View All Recipes
                    </a>
                    <a href="/add-recipe" class="menu-item">
                        <span class="emoji">➕</span> Add New Recipe
                    </a>
                    <a href="/manage-recipes" class="menu-item">
                        <span class="emoji">🔧</span> Manage Recipes
                    </a>
                </div>
                
                <!-- REPORTS & SYSTEM -->
                <div class="menu-section">
                    <h2>📊 Reports & System</h2>
                    <a href="/export-inventory" class="menu-item">
                        <span class="emoji">📥</span> Export Inventory
                    </a>
                    <a href="/export-low-stock" class="menu-item">
                        <span class="emoji">📥</span> Export Low Stock
                    </a>
                    <a href="/backup" class="menu-item">
                        <span class="emoji">💾</span> Create Backup
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


# ============================================================
# INVENTORY FUNCTIONS
# ============================================================

@app.route('/inventory')
def view_inventory():
    """Display all materials"""
    df = get_all_materials()
    
    if df.empty:
        table_html = '<p style="color: #666;">No materials in inventory. <a href="/add-material">Add your first material</a></p>'
    else:
        table_html = df.to_html(index=False, classes='data-table', border=0)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Inventory</title>
        <style>
            {get_common_styles()}
            .data-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .data-table th, .data-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            .data-table th {{ background: #97bc62; color: white; font-weight: bold; }}
            .data-table tr:hover {{ background: #f0f8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Home</a>
            <h1>📦 Current Inventory</h1>
            <p>Total materials: {len(df)}</p>
            {table_html}
        </div>
    </body>
    </html>
    """


@app.route('/add-material', methods=['GET', 'POST'])
def add_material_route():
    """Add new material"""
    if request.method == 'POST':
        result = add_raw_material(
            name=request.form.get('name'),
            category=request.form.get('category'),
            stock_level=float(request.form.get('stock_level', 0)),
            unit=request.form.get('unit'),
            reorder_level=float(request.form.get('reorder_level', 0)),
            cost_per_unit=float(request.form.get('cost_per_unit', 0)),
            supplier=request.form.get('supplier') or None
        )
        
        if result:
            return redirect(url_for('view_inventory'))
        else:
            return "Error adding material", 500
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Add Material</title>
        <style>
            """ + get_common_styles() + """
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
            input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            button { background: #97bc62; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
            button:hover { background: #7da34f; }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Home</a>
            <h1>➕ Add New Material</h1>
            <form method="POST">
                <div class="form-group">
                    <label>Material Name *</label>
                    <input type="text" name="name" required>
                </div>
                <div class="form-group">
                    <label>Category *</label>
                    <input type="text" name="category" placeholder="e.g., Powder, Liquid, Packaging" required>
                </div>
                <div class="form-group">
                    <label>Initial Stock Level *</label>
                    <input type="number" step="0.01" name="stock_level" required>
                </div>
                <div class="form-group">
                    <label>Unit *</label>
                    <input type="text" name="unit" placeholder="e.g., kg, L, units" required>
                </div>
                <div class="form-group">
                    <label>Reorder Level *</label>
                    <input type="number" step="0.01" name="reorder_level" required>
                </div>
                <div class="form-group">
                    <label>Cost per Unit *</label>
                    <input type="number" step="0.01" name="cost_per_unit" required>
                </div>
                <div class="form-group">
                    <label>Supplier (optional)</label>
                    <input type="text" name="supplier">
                </div>
                <button type="submit">Add Material</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.route('/manage-materials')
def manage_materials():
    """Manage materials - restock, decrease, delete"""
    df = get_all_materials()
    
    if df.empty:
        return redirect(url_for('add_material_route'))
    
    rows_html = ""
    for _, row in df.iterrows():
        rows_html += f"""
        <tr>
            <td><strong>{row['name']}</strong></td>
            <td>{row['category']}</td>
            <td>{row['stock_level']} {row['unit']}</td>
            <td>
                <a href="/restock/{row['name']}" class="action-btn restock">↑ Restock</a>
                <a href="/decrease/{row['name']}" class="action-btn decrease">↓ Decrease</a>
                <a href="/delete-material/{row['name']}" class="action-btn delete" onclick="return confirm('Delete {row['name']}?')">🗑 Delete</a>
            </td>
        </tr>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Manage Materials</title>
        <style>
            {get_common_styles()}
            .data-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .data-table th, .data-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            .data-table th {{ background: #97bc62; color: white; }}
            .action-btn {{
                display: inline-block;
                padding: 6px 12px;
                margin: 2px;
                border-radius: 4px;
                text-decoration: none;
                font-size: 14px;
                color: white;
            }}
            .restock {{ background: #28a745; }}
            .decrease {{ background: #ffc107; color: #333; }}
            .delete {{ background: #dc3545; }}
            .action-btn:hover {{ opacity: 0.8; }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Home</a>
            <h1>🔧 Manage Materials</h1>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Material</th>
                        <th>Category</th>
                        <th>Stock</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """


@app.route('/restock/<material_name>', methods=['GET', 'POST'])
def restock_material(material_name):
    """Increase material stock"""
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        result = increase_raw_material(material_name, amount)
        
        if result is not None:
            return redirect(url_for('manage_materials'))
        else:
            return "Error restocking material", 500
    
    material_info = get_raw_material(material_name)
    if not material_info:
        return "Material not found", 404
    
    _, name, current_stock, reorder_level, cost = material_info
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Restock {material_name}</title>
        <style>
            {get_common_styles()}
            .info-box {{ background: #f0f8f0; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            input {{ width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; }}
            button {{ background: #28a745; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/manage-materials" class="back-link">← Back to Manage Materials</a>
            <h1>📈 Restock: {material_name}</h1>
            <div class="info-box">
                <p><strong>Current Stock:</strong> {current_stock} units</p>
                <p><strong>Reorder Level:</strong> {reorder_level} units</p>
            </div>
            <form method="POST">
                <label>Amount to Add:</label>
                <input type="number" step="0.01" name="amount" required min="0.01">
                <button type="submit">Add Stock</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.route('/decrease/<material_name>', methods=['GET', 'POST'])
def decrease_material_route(material_name):
    """Decrease material stock"""
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        result = decrease_raw_material(material_name, amount)
        
        if result is not None:
            return redirect(url_for('manage_materials'))
        else:
            return "Error: Insufficient stock or material not found", 400
    
    material_info = get_raw_material(material_name)
    if not material_info:
        return "Material not found", 404
    
    _, name, current_stock, reorder_level, cost = material_info
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Decrease {material_name}</title>
        <style>
            {get_common_styles()}
            .info-box {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #ffc107; }}
            input {{ width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; }}
            button {{ background: #ffc107; color: #333; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/manage-materials" class="back-link">← Back to Manage Materials</a>
            <h1>📉 Decrease Stock: {material_name}</h1>
            <div class="info-box">
                <p><strong>Current Stock:</strong> {current_stock} units</p>
                <p><strong>Maximum you can remove:</strong> {current_stock} units</p>
            </div>
            <form method="POST">
                <label>Amount to Remove:</label>
                <input type="number" step="0.01" name="amount" required min="0.01" max="{current_stock}">
                <button type="submit">Remove Stock</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.route('/delete-material/<material_name>')
def delete_material_route(material_name):
    """Delete material"""
    delete_raw_material(material_name)
    return redirect(url_for('manage_materials'))


@app.route('/low-stock')
def low_stock():
    """Display low stock materials"""
    df = get_low_stock_materials()
    
    if df.empty:
        message = '<p style="color: green; font-size: 18px;">✅ All materials are adequately stocked!</p>'
    else:
        message = f'<p style="color: red; font-size: 18px;">⚠️ {len(df)} material(s) need reordering:</p>'
        message += df.to_html(index=False, classes='data-table', border=0)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Low Stock Alerts</title>
        <style>
            {get_common_styles()}
            .data-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .data-table th, .data-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            .data-table th {{ background: #dc3545; color: white; }}
            .data-table tr:hover {{ background: #fff3cd; }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Home</a>
            <h1>⚠️ Low Stock Alerts</h1>
            {message}
        </div>
    </body>
    </html>
    """


# ============================================================
# BATCH MANAGEMENT
# ============================================================

@app.route('/batches')
def view_batches_route():
    """View ready batches"""
    df = get_batches()
    
    if df.empty:
        table_html = '<p style="color: #666;">No batches ready for shipment.</p>'
    else:
        table_html = df.to_html(index=False, classes='data-table', border=0)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ready Batches</title>
        <style>
            {get_common_styles()}
            .data-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .data-table th, .data-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            .data-table th {{ background: #97bc62; color: white; }}
            .data-table tr:hover {{ background: #f0f8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Home</a>
            <h1>📋 Ready to Ship Batches</h1>
            {table_html}
        </div>
    </body>
    </html>
    """


@app.route('/create-batch', methods=['GET', 'POST'])
def create_batch_route():
    """Create new batch"""
    if request.method == 'POST':
        product_name = request.form.get('product_name')
        quantity = int(request.form.get('quantity'))
        batch_id = request.form.get('batch_id')
        
        # Convert empty string to None for auto-generate
        if not batch_id:
            batch_id = None
        else:
            batch_id = int(batch_id)
        
        # Create backup before batch creation
        backup_database(reason="before_batch")
        
        result = add_to_batches(
            product_name=product_name,
            quantity=quantity,
            batch_id=batch_id,
            deduct_resources=True
        )
        
        if result:
            return redirect(url_for('view_batches_route'))
        else:
            return "Error creating batch. Check if recipe exists and materials are sufficient.", 400
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Create Batch</title>
        <style>
            """ + get_common_styles() + """
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
            input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            button { background: #97bc62; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; }
            .info { background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Home</a>
            <h1>➕ Create New Batch</h1>
            <div class="info">
                <p><strong>Note:</strong> Recipe must exist for this product. Materials will be automatically deducted from inventory.</p>
            </div>
            <form method="POST">
                <div class="form-group">
                    <label>Product Name *</label>
                    <input type="text" name="product_name" required>
                </div>
                <div class="form-group">
                    <label>Quantity *</label>
                    <input type="number" name="quantity" required min="1">
                </div>
                <div class="form-group">
                    <label>Batch ID (optional - leave empty for auto-generate)</label>
                    <input type="number" name="batch_id">
                </div>
                <button type="submit">Create Batch</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.route('/manage-batches')
def manage_batches():
    """Manage batches - ship or delete"""
    df = get_batches()
    
    if df.empty:
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Manage Batches</title><style>{get_common_styles()}</style></head>
        <body>
            <div class="container">
                <a href="/" class="back-link">← Back to Home</a>
                <h1>🔧 Manage Batches</h1>
                <p>No batches available. <a href="/create-batch">Create a batch</a></p>
            </div>
        </body>
        </html>
        """
    
    rows_html = ""
    for _, row in df.iterrows():
        rows_html += f"""
        <tr>
            <td><strong>{row['batch_id']}</strong></td>
            <td>{row['product_name']}</td>
            <td>{row['quantity']}</td>
            <td>{row['date_completed']}</td>
            <td>
                <a href="/ship-batch/{row['batch_id']}" class="action-btn ship">📦 Ship</a>
                <a href="/delete-batch/{row['batch_id']}" class="action-btn delete" onclick="return confirm('Delete batch {row['batch_id']}?')">🗑 Delete</a>
            </td>
        </tr>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Manage Batches</title>
        <style>
            {get_common_styles()}
            .data-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .data-table th, .data-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            .data-table th {{ background: #97bc62; color: white; }}
            .action-btn {{
                display: inline-block;
                padding: 6px 12px;
                margin: 2px;
                border-radius: 4px;
                text-decoration: none;
                font-size: 14px;
                color: white;
            }}
            .ship {{ background: #28a745; }}
            .delete {{ background: #dc3545; }}
            .action-btn:hover {{ opacity: 0.8; }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Home</a>
            <h1>🔧 Manage Batches</h1>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Batch ID</th>
                        <th>Product</th>
                        <th>Quantity</th>
                        <th>Date Completed</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """


@app.route('/ship-batch/<int:batch_id>')
def ship_batch(batch_id):
    """Mark batch as shipped"""
    result = mark_as_shipped(batch_id)
    return redirect(url_for('manage_batches'))


@app.route('/delete-batch/<int:batch_id>')
def delete_batch_route(batch_id):
    """Delete batch (materials reallocated)"""
    backup_database(reason="before_delete")
    delete_batch(batch_id, reallocate=True)
    return redirect(url_for('manage_batches'))


# ============================================================
# RECIPE MANAGEMENT
# ============================================================

@app.route('/recipes')
def view_recipes():
    """View all recipes (simplified - just product names)"""
    # Note: get_recipe only works with product_name, so we can't easily list all
    # This would need a new function get_all_recipes() in inventory_app.py
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Recipes</title>
        <style>{get_common_styles()}</style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Home</a>
            <h1>📖 Recipes</h1>
            <p>Enter product name to view recipe details:</p>
            <form action="/view-recipe" method="GET" style="margin: 20px 0;">
                <input type="text" name="product_name" placeholder="Product name..." style="padding: 10px; width: 300px;">
                <button type="submit" style="padding: 10px 20px; background: #97bc62; color: white; border: none; cursor: pointer;">View Recipe</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.route('/view-recipe')
def view_recipe_route():
    """View specific recipe"""
    product_name = request.args.get('product_name')
    
    if not product_name:
        return redirect(url_for('view_recipes'))
    
    df = get_recipe(product_name)
    
    if df is None or df.empty:
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Recipe Not Found</title><style>{get_common_styles()}</style></head>
        <body>
            <div class="container">
                <a href="/recipes" class="back-link">← Back to Recipes</a>
                <h1>❌ Recipe Not Found</h1>
                <p>No recipe found for "{product_name}"</p>
            </div>
        </body>
        </html>
        """
    
    table_html = df[['material_name', 'quantity_needed']].to_html(index=False, classes='data-table', border=0)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Recipe: {product_name}</title>
        <style>
            {get_common_styles()}
            .data-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            .data-table th, .data-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            .data-table th {{ background: #97bc62; color: white; }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/recipes" class="back-link">← Back to Recipes</a>
            <h1>📋 Recipe: {product_name}</h1>
            {table_html}
        </div>
    </body>
    </html>
    """


@app.route('/add-recipe', methods=['GET', 'POST'])
def add_recipe_route():
    """Add new recipe"""
    if request.method == 'POST':
        product_name = request.form.get('product_name')
        notes = request.form.get('notes') or None
        
        # Parse materials (expecting format: "material1:qty1,material2:qty2")
        materials_str = request.form.get('materials')
        materials = []
        
        for item in materials_str.split(','):
            if ':' in item:
                mat_name, qty = item.strip().split(':')
                materials.append({
                    'material_name': mat_name.strip(),
                    'quantity_needed': float(qty.strip())
                })
        
        result = add_recipe(product_name, materials, notes)
        
        if result:
            return redirect(url_for('view_recipes'))
        else:
            return "Error adding recipe", 500
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Add Recipe</title>
        <style>
            """ + get_common_styles() + """
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
            input, textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
            button { background: #97bc62; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; }
            .help { background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Home</a>
            <h1>➕ Add New Recipe</h1>
            <div class="help">
                <p><strong>Materials Format:</strong> material_name:quantity, material_name:quantity</p>
                <p><strong>Example:</strong> Matcha Powder:10, Milk:200, Sugar:50</p>
            </div>
            <form method="POST">
                <div class="form-group">
                    <label>Product Name *</label>
                    <input type="text" name="product_name" required>
                </div>
                <div class="form-group">
                    <label>Materials (format: name:qty, name:qty) *</label>
                    <textarea name="materials" rows="4" required placeholder="Matcha Powder:10, Milk:200"></textarea>
                </div>
                <div class="form-group">
                    <label>Notes (optional)</label>
                    <input type="text" name="notes">
                </div>
                <button type="submit">Add Recipe</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.route('/manage-recipes')
def manage_recipes():
    """Manage recipes - modify or delete"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Manage Recipes</title>
        <style>{get_common_styles()}</style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Home</a>
            <h1>🔧 Manage Recipes</h1>
            <p>Enter product name to modify or delete recipe:</p>
            <form action="/modify-recipe" method="GET" style="margin: 20px 0;">
                <input type="text" name="product_name" placeholder="Product name..." style="padding: 10px; width: 300px;">
                <button type="submit" style="padding: 10px 20px; background: #ffc107; color: #333; border: none; cursor: pointer;">Modify</button>
            </form>
            <form action="/delete-recipe" method="GET" style="margin: 20px 0;">
                <input type="text" name="product_name" placeholder="Product name..." style="padding: 10px; width: 300px;">
                <button type="submit" style="padding: 10px 20px; background: #dc3545; color: white; border: none; cursor: pointer;" onclick="return confirm('Delete this recipe?')">Delete</button>
            </form>
        </div>
    </body>
    </html>
    """


@app.route('/delete-recipe')
def delete_recipe_route():
    """Delete recipe"""
    product_name = request.args.get('product_name')
    if product_name:
        delete_recipe(product_name)
    return redirect(url_for('manage_recipes'))


# ============================================================
# EXPORT & BACKUP
# ============================================================

@app.route('/export-inventory')
def export_inventory():
    """Export inventory to CSV"""
    df = get_all_materials()
    
    if df.empty:
        return "No data to export", 404
    
    filepath = export_to_csv(df, "inventory")
    
    return send_file(
        filepath,
        as_attachment=True,
        download_name=f"inventory_{datetime.now().strftime('%Y%m%d')}.csv"
    )


@app.route('/export-low-stock')
def export_low_stock():
    """Export low stock report to CSV"""
    df = get_low_stock_materials()
    
    if df.empty:
        return "No low stock items to export", 404
    
    filepath = export_to_csv(df, "low_stock")
    
    return send_file(
        filepath,
        as_attachment=True,
        download_name=f"low_stock_{datetime.now().strftime('%Y%m%d')}.csv"
    )


@app.route('/backup')
def create_backup():
    """Create manual backup"""
    backup_path = backup_database(reason="manual_web")
    
    if backup_path:
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Backup Created</title><style>{get_common_styles()}</style></head>
        <body>
            <div class="container">
                <a href="/" class="back-link">← Back to Home</a>
                <h1>✅ Backup Created Successfully</h1>
                <p>Backup saved to: {backup_path}</p>
            </div>
        </body>
        </html>
        """
    else:
        return "Backup failed", 500


# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/api/health')
def health_check():
    """Health check for Railway"""
    return jsonify({
        'status': 'healthy',
        'service': 'matcha-inventory',
        'timestamp': datetime.now().isoformat()
    })


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_common_styles():
    """Common CSS styles for all pages"""
    return """
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            min-height: 100vh;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            max-width: 1200px;
            margin: 0 auto;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c5f2d;
            border-bottom: 3px solid #97bc62;
            padding-bottom: 10px;
        }
        .back-link {
            display: inline-block;
            margin-bottom: 20px;
            color: #2c5f2d;
            text-decoration: none;
            font-weight: bold;
        }
        .back-link:hover {
            text-decoration: underline;
        }
    """


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)