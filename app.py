"""
Matcha Inventory Management System - Complete Web Interface

╔════════════════════════════════════════════════════════════════════════╗
║                    PROJECT ARCHITECTURE OVERVIEW                       ║
╚════════════════════════════════════════════════════════════════════════╝

HOW ALL THE FILES WORK TOGETHER:
=================================

    USER (Browser)
         ↓ HTTP Request (GET /inventory)
         ↓
    [app.py] Flask Web Framework)
         │
         ├─→ Handles URLs (@app.route)
         ├─→ Checks authentication (@requires_auth)
         ├─→ Processes forms (request.form)
         └─→ Returns HTML to browser
         ↓
    [inventory_app.py] (Business Logic)
         │
         ├─→ get_all_materials()
         ├─→ add_raw_material()
         └─→ All database operations
         ↓
    [database.py] (Database Wrapper)
         │
         └─→ Handles PostgreSQL OR SQLite connection
         ↓
    [DATABASE] (PostgreSQL/SQLite)
         └─→ Stores all your data

    DATA FLOW: User Request → Flask → Business Logic → Database → Back to User

╔════════════════════════════════════════════════════════════════════════╗
║                        FLASK FRAMEWORK BASICS                          ║
╚════════════════════════════════════════════════════════════════════════╝

WHAT IS FLASK?
==============
Flask is a "micro web framework" for Python. It's a toolkit that makes it easy
to create web applications by handling the complicated parts of HTTP for you.

Think of Flask as a translator between:
  - HTTP requests (what your browser sends) → Python functions
  - Python functions → HTML pages (what your browser displays)

KEY FLASK CONCEPTS YOU'LL SEE IN THIS FILE:
============================================

1. Routes (@app.route('/path'))
   - Map URLs to Python functions
   - Example: @app.route('/inventory') → def view_inventory()
   - When user visits /inventory, Flask runs view_inventory()

2. HTTP Methods (GET vs POST)
   - GET: Viewing/retrieving data (show a page)
   - POST: Sending/submitting data (submit a form)
   - Routes can handle one or both

3. Request Object (request.form, request.authorization)
   - Access data from the browser
   - request.form = form data from POST
   - request.authorization = login credentials

4. Response Types
   - HTML string: Return webpage to display
   - redirect(): Send user to different URL
   - send_file(): Download a file
   - jsonify(): Return JSON data (for APIs)

5. Decorators (@app.route, @requires_auth)
   - Functions that modify other functions
   - @app.route: Tells Flask which URL triggers this function
   - @requires_auth: Adds login requirement

╔════════════════════════════════════════════════════════════════════════╗
║                    REQUEST/RESPONSE CYCLE                              ║
╚════════════════════════════════════════════════════════════════════════╝

Example: User wants to view inventory

1. USER: Types http://localhost:8000/inventory in browser
2. BROWSER: Sends "GET /inventory" request to Flask server
3. FLASK: Finds @app.route('/inventory')
4. FLASK: Checks @requires_auth (prompts login if needed)
5. FLASK: Calls view_inventory() function
6. PYTHON: Queries database with get_all_materials()
7. PYTHON: Converts data to HTML table
8. FLASK: Sends HTML back to browser
9. BROWSER: Displays the inventory page

This cycle repeats for EVERY page load, form submission, export, etc.
"""

# =======================
# LOAD ENVIRONMENT VARIABLES
# =======================
# Load .env file for local development (must be BEFORE other imports that use env vars)
try:
    from dotenv import load_dotenv
    load_dotenv()
    
except ImportError:
   
    pass

# =======================
# IMPORTS
# =======================

# Flask core imports - these are the building blocks of our web app
from unicodedata import category

from flask import Flask, request, redirect, url_for, jsonify, send_file, render_template
# - Flask: The main application class
# - request: Access data from browser (form data, URL parameters, etc.)
# - redirect: Send user to a different page
# - url_for: Generate URLs for routes by function name
# - jsonify: Convert Python data to JSON format (for API endpoints)
# - send_file: Send files to browser (used for Excel exports)

import os  # Operating system functions (file paths, environment variables)
from datetime import datetime  # For timestamps in exports
from functools import wraps  # Used for creating decorators (like @requires_auth)



# Import all our inventory functions from inventory_app.py
from inventory_app import (
    create_database, add_raw_material, get_all_materials, get_all_recipes, get_batches_shipped, get_low_stock_materials,
    increase_raw_material, decrease_raw_material, get_raw_material, add_to_batches,
    get_batches, mark_as_shipped, delete_batch, get_recipe, add_recipe,
    change_recipe, delete_recipe, delete_raw_material, get_material_by_id, get_all_materials_with_id, update_raw_material)


# Import helper functions for exporting data
# - export_to_csv: Exports DataFrames to CSV files (original functionality)
# - export_to_excel: NEW - Exports DataFrames to Excel files (.xlsx format)
# - backup_database: Creates timestamped backups of the database
from helper_functions import (export_to_csv, export_to_excel, backup_database)

# =======================
# CREATE FLASK APP
# =======================
# This creates the Flask application instance - the core of your web server
# __name__ tells Flask where to look for templates and static files
app = Flask(__name__)

# WHAT IS 'app'?
# Think of 'app' as your web server. When you do @app.route('/inventory'),
# you're telling this server "when someone visits /inventory, run this function"



# =======================
# DATABASE SETUP & CHECKS
# ========================




# Make sure we have a 'data' folder for local SQLite database
if not os.path.exists('data'):
    os.makedirs('data')

# Try to connect to the database - if it fails, create one
try:
    from database import get_connection
    conn = get_connection()
    conn.close()
    print("[SUCCESS] Database connection successful")
except:
    # If connection fails, initialize a new database
    print("[INIT] Initializing database...")
    create_database()



# =======================
# AUTHENTICATION SYSTEM
# =======================




# ========================
# RATE LIMITING (Currently Disabled)
# ========================
# Rate limiting prevents abuse by limiting how many requests one IP can make
# Example: Limit to 200 requests per day, 50 per hour
# Currently commented out, but you can enable it if needed

#limiter = Limiter(
#    app=app,
#    default_limits=["200 per day", "50 per hour"]
#)
# ========================


# AUTHENTICATION CREDENTIALS
# os.environ.get() checks for environment variables (set in Railway/production)
# If not found, uses the fallback value (for local development)

AUTH_USERNAME = os.environ.get('AUTH_USERNAME')
AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD')

assert(AUTH_USERNAME and AUTH_PASSWORD), "Error: AUTH_USERNAME and AUTH_PASSWORD must be set in environment variables or .env file"

# How this works:
# - Production (Railway): Reads from environment variables (secure, not in code)
# - Local development: Uses fallback values (convenient for testing)


# AUTHENTICATION DECORATOR
# This is a "decorator factory" - a function that creates a decorator
def requires_auth(f):
    """
    Decorator to protect routes with authentication

    Usage: Put @requires_auth above any route that should require login

    Example:
        @app.route('/inventory')
        @requires_auth
        def view_inventory():
            return "Secret inventory!"

    How it works:
    1. @wraps(f) preserves the original function's name and docstring
    2. decorated() is the wrapper function that adds auth checking
    3. Returns the wrapped function
    """
    @wraps(f)  # Preserves metadata from original function

    def decorated(*args, **kwargs):
        """
        This wrapper function runs BEFORE the actual route function

        Flow:
        1. Get auth credentials from request
        2. Validate credentials
        3. If valid → run the original function
           If invalid → return 401 error
        """
        # request.authorization contains username/password from browser's login popup
        auth = request.authorization

        # Check if auth exists AND is valid
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()  # Show login prompt

        # Authentication successful! Run the original function
        return f(*args, **kwargs)

    return decorated  # Return the wrapped function


def check_auth(username, password):
    """
    Validates username and password

    Returns:
        True if credentials match
        False if credentials don't match
    """
    return username == AUTH_USERNAME and password == AUTH_PASSWORD


def authenticate():
    """
    Sends HTTP 401 response that triggers browser's login popup

    HTTP Status Codes:
    - 200: Success
    - 401: Unauthorized (need to login)
    - 404: Not found
    - 500: Server error

    The 'WWW-Authenticate' header tells the browser to show a login popup
    """
    return jsonify({'message': 'Authentication required.'}), 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}




# ========================
# WEB ROUTES (PAGES)
# ========================

"""
UNDERSTANDING ROUTES
====================
A "route" is a mapping between a URL and a Python function.

HOW ROUTES WORK:
1. User types URL in browser (e.g., http://localhost:8000/inventory)
2. Browser sends HTTP request to Flask server
3. Flask looks at the URL path (/inventory)
4. Flask finds the function with @app.route('/inventory')
5. Flask runs that function
6. Function returns HTML
7. Flask sends HTML back to browser
8. Browser displays the page

ROUTE DECORATORS:
@app.route('/path') - Defines which URL triggers this function
@requires_auth - Requires login before allowing access

DECORATOR ORDER MATTERS:
@app.route('/')      ← Must be first (tells Flask about the route)
@requires_auth       ← Then add authentication
def my_function():   ← The actual function that handles the request
    ...
"""

# =======================
# HOME PAGE ROUTE
# =======================
# This is the main landing page of your app

@app.route('/')  # '/' means root URL (e.g., http://localhost:8000/)
@requires_auth   # User must login to see this page
def index():
    """
    Home page with navigation menu

    HTTP Method: GET (default)
    - GET is for viewing/retrieving data
    - No data is being submitted, just showing the page

    Returns: HTML string (the entire home page)
    """
    # Return HTML for the home page - it's all inline here as one big string
    return render_template("index.html")



# ========================
# INVENTORY PAGES
# ========================

"""
DATA FLOW: DATABASE → PYTHON → HTML → BROWSER
==============================================

1. DATABASE: Data is stored (PostgreSQL or SQLite)
   └→ get_all_materials() queries database

2. PYTHON: Data is processed
   └→ Returns pandas DataFrame 

3. HTML: Data is converted to HTML
   └→ df.to_html() converts DataFrame to <table> HTML
   └→ Wrapped in styled HTML page

4. BROWSER: User sees the result
   └→ Flask sends HTML to browser
   └→ Browser renders it as a webpage

"""

@app.route('/inventory')  # URL path: http://localhost:8000/inventory
# Note: No methods= parameter means GET only (can't submit data to this route)
@requires_auth
def view_inventory():
    """
    View All Inventory Page

    STEP-BY-STEP FLOW:
    1. User visits /inventory
    2. Flask calls this function
    3. Function queries database for all materials
    4. Converts data to HTML table
    5. Wraps table in styled HTML page
    6. Returns HTML to browser
    """

    # STEP 1: Get data from database
    # get_all_materials() returns a pandas DataFrame
    df = get_all_materials()
    materials = df.to_dict(orient='records') if not df.empty else []
    return render_template("inventory.html",
        materials=materials,
        count=len(df),
        back_link=True,
        back_link_url="/",
        back_link_label="Back to Home"
)


# NEW: Excel export route for inventory
@app.route('/export/inventory-excel')
@requires_auth
def export_inventory_excel():
    """
    Export inventory data to Excel file and trigger download

    How it works:
    1. Gets all materials from database
    2. Checks if there's data (returns error if empty)
    3. Calls export_to_excel() to create timestamped .xlsx file
    4. Uses send_file() to trigger browser download
    """
    df = get_all_materials() # Get fresh data from database

    # Return error if no data to export
    if df.empty:
        return "No data to export", 400

    # Create Excel file with timestamp (e.g., inventory_20260203_143022.xlsx)
    filepath = export_to_excel(df, 'inventory')

    # Send file to browser as download
    # - as_attachment=True: Forces download instead of opening in browser
    # - download_name: Sets the filename shown in download dialog
    return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))

"""
HTTP METHODS: GET vs POST
==========================
Routes can handle different HTTP methods. The two most common are:

GET - Retrieve/View Data
- Used when you just want to SEE something
- Data appears in URL (?param=value)
- Safe to bookmark or refresh
- Examples: Viewing inventory, loading a form

POST - Submit/Send Data
- Used when you want to SEND data to the server
- Data is hidden in request body (not in URL)
- NOT safe to refresh (might duplicate submission)
- Examples: Submitting a form, adding an item

HANDLING BOTH METHODS IN ONE ROUTE:
Some routes need to handle both GET and POST:
- GET: Show the form (e.g., "Add Material" page)
- POST: Process the form submission (e.g., actually add the material)
"""

@app.route('/add-material', methods=['GET', 'POST'])
# methods=['GET', 'POST'] tells Flask this route handles both GET and POST requests
@requires_auth
def add_material_route():
    """
    Add Material Route - Handles both showing form and processing submission

    This is a common pattern in web development:
    1. User visits /add-material (GET) → Show empty form
    2. User fills form and clicks submit → Browser sends POST request
    3. Server processes POST → Adds material to database
    4. Server redirects to inventory page to show the new material
    """

    # Check which HTTP method was used
    if request.method == 'POST':
        """
        POST REQUEST HANDLING
        =====================
        When the user submits the form, browser sends a POST request
        with all the form data.

        request.form is a dictionary containing all form fields:
        - request.form.get('name') → Value from input with name="name"
        - request.form.get('category') → Value from input with name="category"
        - etc.

        Note: HTML form sends everything as strings, so we convert:
        - float() for decimal numbers (stock_level, cost_per_unit)
        - int() for whole numbers (if needed)
        """

        # Extract all form data and call the database function
        result = add_raw_material(
            name=request.form.get('name'),  # Get value from <input name="name">
            category=request.form.get('category'),
            stock_level=float(request.form.get('stock_level', 0)),  # Convert to number
            unit=request.form.get('unit'),
            reorder_level=float(request.form.get('reorder_level', 0)),
            cost_per_unit=float(request.form.get('cost_per_unit', 0)),
            supplier=request.form.get('supplier') or None  # Optional field
        )

        # After processing, REDIRECT to another page
        # This prevents duplicate submissions if user refreshes
        # This is called the "Post/Redirect/Get" pattern
        if result:
            # Success! Redirect to inventory page
            # url_for('view_inventory') generates the URL for the view_inventory function
            return redirect(url_for('view_inventory'))
        else:
            # Failed! Return error message with 500 status code
            return ("Error adding material", 500)

   
    return render_template("add_material.html",
    back_link=True,
    back_link_url="/",
    back_link_label="Back to Home"
)






# ========================
# LOW STOCK ALERTS
# ========================

@app.route('/low-stock')
@requires_auth
def low_stock():
    # Get all materials where stock is below reorder level
    df = get_low_stock_materials()
    materials = df.to_dict(orient='records') if not df.empty else []
    return render_template("low_stock.html",
        materials=materials,
        count=len(df),
        back_link=True,
        back_link_url="/",
        back_link_label="Back to Home"
)


# NEW: Excel export route for low stock alerts
@app.route('/export/low-stock-excel')
@requires_auth
def export_low_stock_excel():
    """
    Export low stock materials to Excel file

    Useful for:
    - Sending reorder lists to suppliers
    - Keeping records of stock alerts
    - Sharing stock status with team members
    """
    df = get_low_stock_materials()  # Get materials below reorder level

    if df.empty:
        return "No data to export", 400  # No low stock items to export

    # Create Excel file (e.g., low_stock_20260203_143022.xlsx)
    filepath = export_to_excel(df, 'low_stock')

    # Trigger browser download
    return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))



#=============
#inventory MANAGEMENT PAGES (edit/delete materials)
#=============

@app.route('/manage-materials') # Page to view all materials with edit/delete options 
@requires_auth
def manage_materials():
    df = get_all_materials_with_id()
    materials = df.to_dict(orient='records') if (df is not None and not df.empty) else []
    return render_template("manage_materials.html",
        materials=materials,
        count=len(materials),
        back_link=True,
        back_link_url="/",
        back_link_label="Back to Home"
)



# edit material page
@app.route('/edit-material/<int:material_id>')
@requires_auth

def edit_material(material_id):
    material = get_material_by_id(material_id)
    if not material:
        return f"<h1>Material not found</h1><a href='/manage-materials'>← Back</a>", 404

    mat_id, name, category, stock_level, unit, reorder_level, cost_per_unit, supplier = material
    msg = request.args.get('msg', '')
    err = request.args.get('err', '')
    return render_template("edit_material.html",
        mat_id=mat_id, name=name, category=category,
        stock_level=stock_level, unit=unit, reorder_level=reorder_level,
        cost_per_unit=cost_per_unit, supplier=supplier,
        msg=msg, err=err,
        back_link=True,
        back_link_url="/manage-materials",
        back_link_label="Back to Manage Materials"
)


@app.route('/edit-material/<int:material_id>/adjust-stock', methods=['POST']) # Route to handle stock adjustments (increase/decrease)
@requires_auth
def adjust_stock(material_id):

    amount = float(request.form.get('amount', 0)) # Get the amount to adjust (convert to number)
    action = request.form.get('action') # Get whether to increase or decrease stock

    if action == 'increase':
        result = increase_raw_material(material_id, amount) # Call function to increase stock
    else:
        result = decrease_raw_material(material_id, amount) # Call function to decrease stock (returns new stock level or None if failed)

    if result is not None:
        return redirect(url_for('edit_material', material_id=material_id, msg=f'Stock updated to {result}'))
    else:
        return redirect(url_for('edit_material', material_id=material_id, err='Stock update failed. Check there is enough stock to decrease.'))
    
# Note: Similar POST routes would be needed for updating details and deleting the material, following the same pattern of processing the form data and redirecting back to the edit page with a success or error message.




@app.route('/edit-material/<int:material_id>/update-details', methods=['POST']) 
# Route to handle updating material details (name, category, etc)
@requires_auth
def update_material_details(material_id): 
    name = request.form.get('name') # Get updated name from form
    category = request.form.get('category') or None # Get updated category (or None if empty)
    unit = request.form.get('unit') or None # Get updated unit (or None if empty)
    reorder_level_str = request.form.get('reorder_level') 
    cost_per_unit_str = request.form.get('cost_per_unit')
    reorder_level = float(reorder_level_str) if reorder_level_str else None
    cost_per_unit = float(cost_per_unit_str) if cost_per_unit_str else None
    supplier = request.form.get('supplier') or None

    result = update_raw_material(material_id, name=name, category=category, unit=unit,
                                 reorder_level=reorder_level, cost_per_unit=cost_per_unit, supplier=supplier)

    if result:
        return redirect(url_for('edit_material', material_id=material_id, msg='Details updated successfully'))
    else:
        return redirect(url_for('edit_material', material_id=material_id, err='Failed to update details'))
# Note: The update_raw_material function would need to be implemented in the database module to handle updating the material details based on the provided parameters.

@app.route('/edit-material/<int:material_id>/delete', methods=['POST']) 
# Route to handle deleting a material from inventory
@requires_auth
def delete_material(material_id):
    delete_raw_material(material_id)
    return redirect(url_for('manage_materials'))


##############
# BATCHES PAGES
###############

#View all batches
@app.route('/batches')
@requires_auth
def view_batches():

    data = get_batches()
    batches = data.to_dict(orient='records') if not data.empty else []
    columns = list(data.columns) if not data.empty else []
    return render_template("batches.html",
        batches=batches, columns=columns, count=len(batches),
        back_link=True, back_link_url="/", back_link_label="Back to Home"
)


# NEW: Excel export route for batches
@app.route('/export/batches-excel')
@requires_auth
def export_batches_excel():
    """
    Export batches to Excel file

    Useful for:
    - Creating shipping manifests
    - Sharing batch info with logistics team
    - Record keeping of completed batches
    """
    df = get_batches()  # Get all ready batches

    if df.empty:
        return "No data to export", 400  # No batches to export

    # Create Excel file (e.g., batches_20260203_143022.xlsx)
    filepath = export_to_excel(df, 'batches')

    # Trigger browser download
    return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))


# NEW: View shipped batches
@app.route('/shipped-batches')
@requires_auth
def view_shipped_batches():
    """
    gets all shipped batches and displays them in a table
    """

    data = get_batches_shipped()
    batches = data.to_dict(orient='records') if not data.empty else []
    columns = list(data.columns) if not data.empty else []
    return render_template("shipped_batches.html",
        batches=batches, columns=columns, count=len(batches),
        back_link=True, back_link_url="/", back_link_label="Back to Home"
)


#########################STILL NEED TO ADD EXPORT ROUTE FOR SHIPPED BATCHES EXCEL#########################


# craete a new batch
@app.route('/create-batch', methods=['GET', 'POST'])
@requires_auth
def create_batch():

    if request.method == 'POST':
        # When form is submitted, get all the form data and add to database
        product_name = request.form.get('product_name')
        quantity = float(request.form.get('quantity'))
        Notes = request.form.get('notes') or None
        batch_id_str = request.form.get('batch_id')
        batch_id = int(batch_id_str) if batch_id_str else None
        
        try:

            result = add_to_batches(product_name, quantity, notes=Notes, batch_id = batch_id, deduct_resources=True)
            # If successful, redirect to batches page, otherwise show error
            if result:
                return redirect(url_for('view_batches'))
            else: 
                #show generic error page
                return f"<h1>Error:</h1><p>Failed to create batch. Check terminal for details.</p><a href='/create-batch'>Go back to Create Batch</a>", 500

        except ValueError as e:
            #show the specific error message from add_to_batches
            # For example, if not enough materials, show that message
            return f"<h1>Error:</h1><p>{str(e)}</p><a href='/create-batch'>Go back to Create Batch</a>", 400

        except Exception as e:
            # Catch-all for unexpected errors
            return f"<h1>Unexpected Error:</h1><p>{str(e)}</p><a href='/create-batch'>Go back to Create Batch</a>", 500
        

    # If it's a GET request, show the form to create a new batch
    return render_template("create_batch.html",
    back_link=True,
    back_link_url="/",
    back_link_label="Back to Home"
)



    








#================
# RECIPE PAGES
#=================
@app.route('/recipes')
@requires_auth
def view_recipes():
    """
    View All Recipes Page

    Displays recipes in a grouped format where:
    - Recipe name and notes appear only on the FIRST row of each recipe
    - Subsequent rows for the same recipe show only materials (name blank)
    - This makes it easy to see which materials belong to which recipe
    """

    # ========================================
    # STEP 1: Get raw data from database
    # ========================================
    # Each row = one material in a recipe
    # Example raw data:
    #   recipe_product_name | notes | material_name | quantity | unit
    #   matcha latte        | sweet | sugar         | 10       | grams
    #   matcha latte        | sweet | matcha powder | 20       | grams
    #   lavender tea        | None  | lavender      | 10       | grams
    df = get_all_recipes()
    if df.empty:
        return render_template("recipes.html",
            recipes=[], recipe_count=0,
            back_link=True, back_link_url="/", back_link_label="Back to Home"
    )

    df_display = df.copy()
    duplicate_mask = df_display['recipe_product_name'].duplicated()
    df_display.loc[duplicate_mask, 'recipe_product_name'] = ''
    df_display.loc[duplicate_mask, 'notes'] = ''
    recipe_count = df['recipe_product_name'].nunique()
    recipes = df_display.to_dict(orient='records')

    return render_template("recipes.html",
        recipes=recipes,
        recipe_count=recipe_count,
        back_link=True, back_link_url="/", back_link_label="Back to Home"
    )


# NEW: Excel export route for recipes
@app.route('/export/recipes-excel')
@requires_auth
def export_recipes_excel():
    """
    Export all recipes and their materials to Excel file

   

    Note: DataFrame has one row per material per recipe
    (A recipe with 3 materials will have 3 rows)
    """
    df = get_all_recipes()  # Get all recipes with materials

    if df.empty:
        return "No data to export", 400  # No recipes to export

    # Create Excel file (e.g., recipes_20260203_143022.xlsx)
    filepath = export_to_excel(df, 'recipes')

    # Trigger browser download
    return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))



# ========================
# ADD NEW RECIPE ROUTE
# ========================
#
# PURPOSE:
# This route handles the "Add New Recipe" functionality, allowing users to create
# new recipes with multiple materials/ingredients. Recipes define what materials
# are needed to produce a product (e.g., "Matcha Latte" needs Matcha Powder + Milk).
#
# HOW IT WORKS:
# 1. GET request: Display the form with dynamic material inputs
# 2. POST request: Process the form, validate data, and save to database
#
# COMPLEXITY NOTE:
# Unlike simple forms (like add-material), recipes require MULTIPLE materials.
# We use JavaScript on the frontend to dynamically add/remove material rows,
# then parse them on the backend using indexed form field names (material_name_0, etc.)
#

@app.route('/add-recipe', methods=['GET', 'POST'])
@requires_auth
def add_recipe_route():
    """
    Add Recipe Route - Handles both displaying the form and processing submissions

    FORM STRUCTURE:
    - Product Name: The name of the recipe/product being created
    - Notes: Optional notes about the recipe (e.g., "sweetened", "vegan")
    - Materials: Dynamic list of materials, each with:
        - Material Name: What ingredient is needed
        - Quantity Needed: How much of that material per batch

    DATA FLOW:
    1. User fills out form with product name and adds materials
    2. JavaScript allows adding/removing material rows dynamically
    3. On submit, form data is sent as POST request
    4. Backend parses indexed fields (material_name_0, quantity_0, etc.)
    5. Builds materials list and calls add_recipe() from inventory_app.py
    6. Redirects to recipes page on success

    FORM FIELD NAMING CONVENTION:
    - Material rows use indexed names: material_name_0, quantity_0, material_name_1, etc.
    - This allows parsing an arbitrary number of materials on the backend
    """

    # ========================
    # HANDLE POST REQUEST (Form Submission)
    # ========================
    if request.method == 'POST':

        # -----------------------
        # Step 1: Extract basic recipe info
        # -----------------------
        # Get the product name (required field)
        product_name = request.form.get('product_name')

        # Get optional notes field (None if empty)
        notes = request.form.get('notes') or None

        # -----------------------
        # Step 2: Parse dynamic material fields
        # -----------------------
        # Materials are submitted with indexed field names:
        # material_name_0, quantity_0, material_name_1, quantity_1, etc.
        #
        # We iterate through indices until we stop finding fields
        # This allows for any number of materials to be added

        materials = []  # Will hold list of material dictionaries
        index = 0       # Start at first material (index 0)

        # Loop through all submitted material rows
        while True:
            # Try to get material at current index
            material_name = request.form.get(f'material_name_{index}')
            quantity_str = request.form.get(f'quantity_{index}')

            # If no material name found at this index, we've processed all materials
            if not material_name:
                break

            # Skip empty rows (user added row but didn't fill it in)
            # This prevents errors from blank material entries
            if material_name.strip() and quantity_str:
                try:
                    # Convert quantity to float for decimal support
                    quantity = float(quantity_str)

                    # Add material to our list in the format expected by add_recipe()
                    # Each material is a dict with 'material_name' and 'quantity_needed'
                    materials.append({
                        'material_name': material_name.strip(),
                        'quantity_needed': quantity
                    })
                except ValueError:
                    # If quantity can't be converted to number, skip this row
                    # Could also return an error here if strict validation needed
                    pass

            # Move to next index
            index += 1

        # -----------------------
        # Step 3: Validate required data
        # -----------------------
        # Check that we have both a product name and at least one material
        if not product_name or not materials:
            # Return error if missing required fields
            return """<!DOCTYPE html><html><head><title>Error</title><style>
            body{font-family:Arial;padding:40px;background:#f5f5f5}
            .error-box{background:white;padding:30px;border-radius:10px;max-width:500px;margin:0 auto;border-left:5px solid #dc3545}
            h1{color:#dc3545;margin-top:0}
            a{color:#2c5f2d}
            </style></head><body>
            <div class="error-box">
            <h1>Missing Required Fields</h1>
            <p>Please provide a product name and at least one material.</p>
            <a href="/add-recipe">← Go back and try again</a>
            </div></body></html>""", 400

        # -----------------------
        # Step 4: Call database function to save recipe
        # -----------------------
        try:
            # add_recipe() is imported from inventory_app.py
            # It inserts into 'recipes' table and 'recipe_materials' table
            result = add_recipe(product_name, materials, notes)

            if result:
                # Success! Redirect to recipes page to see the new recipe
                # Using Post/Redirect/Get pattern to prevent duplicate submissions
                return redirect(url_for('view_recipes'))
            else:
                # Database function returned False/None - generic failure
                return """<!DOCTYPE html><html><head><title>Error</title><style>
                body{font-family:Arial;padding:40px;background:#f5f5f5}
                .error-box{background:white;padding:30px;border-radius:10px;max-width:500px;margin:0 auto;border-left:5px solid #dc3545}
                h1{color:#dc3545;margin-top:0}
                a{color:#2c5f2d}
                </style></head><body>
                <div class="error-box">
                <h1>Error Adding Recipe</h1>
                <p>Failed to add recipe. Please check that all materials exist in inventory.</p>
                <a href="/add-recipe">← Go back and try again</a>
                </div></body></html>""", 500

        except Exception as e:
            # Catch any unexpected errors and display them
            # In production, you might want to log this and show a generic message
            return f"""<!DOCTYPE html><html><head><title>Error</title><style>
            body{{font-family:Arial;padding:40px;background:#f5f5f5}}
            .error-box{{background:white;padding:30px;border-radius:10px;max-width:500px;margin:0 auto;border-left:5px solid #dc3545}}
            h1{{color:#dc3545;margin-top:0}}
            a{{color:#2c5f2d}}
            code{{background:#f8f9fa;padding:2px 6px;border-radius:3px}}
            </style></head><body>
            <div class="error-box">
            <h1>Error Adding Recipe</h1>
            <p>An error occurred: <code>{str(e)}</code></p>
            <a href="/add-recipe">← Go back and try again</a>
            </div></body></html>""", 500

    # ========================
    # HANDLE GET REQUEST (Display Form)
    # ========================
    # When user visits /add-recipe, show the form for creating a new recipe
    #
    # JAVASCRIPT FUNCTIONALITY:
    # - addMaterial(): Adds a new material row to the form
    # - removeMaterial(): Removes a material row (but keeps at least one)
    # - Material rows use indexed IDs for proper form submission
    #
    # CSS STYLING:
    # - Follows existing app styling patterns (green theme, rounded corners)
    # - Material rows have visual grouping with border
    # - Remove button is red for clear visual distinction

    return render_template("add_recipe.html",
    back_link=True,
    back_link_url="/",
    back_link_label="Back to Home"
)















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

"""
THE FLASK REQUEST/RESPONSE CYCLE
=================================
When you run app.run(), Flask starts a web server that listens for requests.
Here's what happens when a user visits your site:

1. USER ACTION:
   User types http://localhost:8000/inventory in browser

2. HTTP REQUEST:
   Browser sends: GET /inventory HTTP/1.1
   (HTTP verb + path + protocol version)

3. FLASK ROUTING:
   Flask looks through all @app.route() decorators
   Finds: @app.route('/inventory')
   Calls: view_inventory()

4. FUNCTION EXECUTION:
   - Checks authentication (if @requires_auth)
   - Runs your Python code
   - Queries database
   - Generates HTML

5. HTTP RESPONSE:
   Flask sends back:
   - Status code (200 = success, 404 = not found, 500 = error)
   - Headers (content type, cookies, etc.)
   - Body (your HTML)

6. BROWSER RENDERING:
   Browser receives HTML and displays it

This cycle repeats for every request (page load, form submission, etc.)
"""

if __name__ == '__main__':
    """
    START THE WEB SERVER
    ====================
    This block only runs when you execute this file directly:
      python app.py

    It doesn't run when you import this file as a module.

    CONFIGURATION EXPLAINED:
    """

    # Get port number from environment variable (for cloud hosting)
    # Railway, Heroku, etc. set PORT environment variable
    # If not set (local development), use 8000
    port = int(os.environ.get('PORT', 8000))

    # Start the Flask development server
    app.run(
        host='0.0.0.0',  # Listen on all network interfaces
                         # '0.0.0.0' = accessible from any IP address
                         # '127.0.0.1' = only accessible from this computer
                         # For cloud hosting, must be '0.0.0.0'

        port=port,       # Port number (default 8000)
                         # Access via: http://localhost:8000

        debug=False      # Production mode
                         # debug=True: Shows detailed errors, auto-reloads on code changes
                         # debug=False: Hides error details (safer for production)
    )

    """
    AFTER app.run():
    ===============
    Your terminal will show:
    * Running on http://0.0.0.0:8000
    * Do not use the development server in a production environment

    The server is now listening for requests!
    - Visit http://localhost:8000 in your browser
    - Press Ctrl+C to stop the server
    - Each request will print to the terminal (useful for debugging)
    """
