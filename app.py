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
    from dotenv import load_dotenv # load enviroment varibales, python has build in libracy that loads them in. 
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
# - request: obejct that give you access to income http request data. 
# - redirect:  instructs the browser to go to a different URL
# - url_for:  builds urls for different functions (useful for redirects)
# - jsonify:  converests python data structures (lists, dicts) to JSON format 
# - send_file:  sends file to browser for download

import os  # Operating system functions (file paths, environment variables)
from datetime import datetime  # For timestamps in exports
from functools import wraps  # Used for creating decorators (like @requires_auth)

from flask_wtf.csrf import CSRFProtect # security necesity. 

# Import all our inventory functions from inventory_app.py
from inventory_app import (
    create_database, add_raw_material, delete_recipe_by_id, get_all_batches_with_id, get_all_materials, get_all_recipes, get_batches_shipped, get_low_stock_materials,
    increase_raw_material, decrease_raw_material, get_raw_material, add_to_batches,
    get_batches, mark_as_shipped, delete_batch, get_recipe, add_recipe,
    change_recipe, delete_recipe, delete_raw_material, get_material_by_id, get_all_materials_with_id, update_raw_material, get_all_batches_with_id, get_batch_by_id,
    update_batch, update_batch_status, update_recipe, get_all_recipes_with_id, get_recipe_by_id, log_action, view_logs)


# Import helper functions for exporting data
# - export_to_csv: Exports DataFrames to CSV files (not currently used)
# - export_to_excel: NEW - Exports DataFrames to Excel files (.xlsx format)

from helper_functions import (export_to_csv, export_to_excel,)

# logging for actions. 
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

"""
instead of print statements for actions (ex. adding batche, etc). it logs them with time stamp. will show up in render logs. 

use logging.info("...") instead of print
""" 

# =======================
# CREATE FLASK APP
# =======================

app = Flask(__name__)  # creates flask instance, so this web app name is 'app' which can be used to run the server and define routes.

# CSRFprotect 
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
csrf = CSRFProtect(app)

# WHAT IS 'app':
# Think of 'app' as your web server. When you do @app.route('/inventory'),
# you're telling this server "when someone visits /inventory, run this function"






# =======================
# DATABASE SETUP & CHECKS
# ========================




# for local development. 
if not os.path.exists('data'): # Make sure we have a 'data' folder for local SQLite database 
    os.makedirs('data') 


DATABASE_URL = os.environ.get('DATABASE_URL')
try:
    from database import get_connection, get_db_connection
    conn = get_connection()
    conn.close()
    logging.info("[SUCCESS] Database connection successful")
    if not DATABASE_URL:
        create_database()  # SQLite: always ensure tables exist
except:
    logging.info("[INIT] Initializing database...")
    create_database()



# =======================
# AUTHENTICATION SYSTEM
# ========================




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


# takes authentication credentials from environment variables (or .env file) and checks them against incoming requests.

AUTH_USERNAME = os.environ.get('AUTH_USERNAME')
AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD')

assert(AUTH_USERNAME and AUTH_PASSWORD), "Error: AUTH_USERNAME and AUTH_PASSWORD must be set in environment variables or .env file" 
#assert that it exists, otherwise app would run withouth authentication. 





# using authentication decorator to protect routes that require login.




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


    This funciton 
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
            logging.warning(f"Failed auth attempt for user: {auth.username if auth else 'no credentials'}")
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



# =======================
# HOME PAGE ROUTE
# =======================
# This is the main landing page of your app

@app.route('/')  # using app name: 'app', it uses '/' to route as main page. (landing page)
@requires_auth   # User must login to see this page
def index():
    """
    The index is the home page of app, provides links to other pages in dashboard.
    """
    
    return render_template("index.html") #return the html file for the home page. 

#???:
# does this actually create buttons for pages? is the html code in idex. html responsible for the buttons?

#=================
#LOGGING PAGE
#===============

@app.route('/audit-log')
@requires_auth
def view_audit_log():
    df = view_logs()
    logs = df.to_dict(orient='records') if not df.empty else []
    return render_template("audit_log.html",
        logs=logs,
        count=len(logs),
        back_link=True,
        back_link_url="/",
        back_link_label="Back to Home"
    )






# ========================
# INVENTORY PAGES
# ========================

"""
This section is all routes related to raw materials. 

1. view inventory page (/inventory) [GET route only, no POST since this page is just for viewing]

    - also export to excell button. (/export/inventory-excel) [GET route that triggers excel export and download]

2. add material page (/add-material) [GET and POST routes]

3. low stock alerts page (/low-stock) [just GET route for now, no POST route since this page is just for viewing alerts]

4. manage materials page (/manage-materials) - view all materials with edit/delete options [GET and POST routes]


"""

@app.route('/inventory')  # URL path 
# when only using GET, Flask assumes it's a GET route, so we don't need to specify methods=['GET'] here.
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

    
    df = get_all_materials() # get data in dataframe format from inventory.app func. 

    materials = df.to_dict(orient='records') if not df.empty else [] 
    #converts dataframe to list of dictionaries, where each dictionary represents what a material (one row). 
    # the "orient = recors" is just a specific dictionary format.
    

    return render_template("inventory.html", # render the inventory page html from template. 
        materials=materials, # pass material data in list of dictionary form to html. 
        count=len(df), # number of materials for display in html. this is needed because we need to check if there are materials in the html to decide whether to show the table or a "no materials" message.
        back_link=True,  # back link, this is to present the back link in top left corner. back link is in the base.html, and this variable is used to decide whether to show it or not.
        back_link_url="/", # back link to home. (index)
        back_link_label="Back to Home"
)



@app.route('/export/inventory-excel') # URL path for exporting inventory to excel, this is a button in inventory.html. 
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
    filepath = export_to_excel(df, 'inventory') # from helper_functions, this creates the excel file and returns the file path.

    # Send file to browser as download
    # - as_attachment=True: Forces download instead of opening in browser
    # - download_name: Sets the filename shown in download dialog
    return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))



@app.route('/add-material', methods=['GET', 'POST'])
# methods=['GET', 'POST'] tells Flask this route handles both GET and POST requests
@requires_auth
def add_material_route():
    """
    Add Material Route - Handles both showing form and processing submission

    This is a common pattern in web development:
    1. User visits /add-material (GET) → Show empty form (add_material.html)
    2. User fills form and clicks submit → Browser sends POST request
    3. Server processes POST → Adds material to database
    4. Server redirects to inventory page to show the new material
    """

    # Check which HTTP method was used
    if request.method == 'POST':
        """
        POST:

        request.form is a dictionary containing all form fields:
        - request.form.get('name') → Value from input with name="name"
        - request.form.get('category') → Value from input with name="category"
        - etc.

        Note: HTML form sends everything as strings, so we convert:
        - float() for decimal numbers (stock_level, cost_per_unit)
        - int() for whole numbers (if needed)
        """
        #input string parsing
        name = request.form.get('name') # Get value from <input name="name"> handled in add_material.html
        category=request.form.get('category')
        unit=request.form.get('unit')
        supplier=request.form.get('supplier')

        name = name.strip() if name else None
        category = category.strip() if category else None
        unit = unit.strip() if unit else None
        supplier = supplier.strip() if supplier else None

        
        
        #string input validation ( cant be none)
        if not name:
                return render_template('error.html',
                    title="Invalid Input",
                    message="Material name cannot be blank.",
                    back_link=True, back_link_url="/add-material", back_link_label="Go back"
                ), 400
        
        if not category:
                return render_template('error.html',
                    title="Invalid Input",
                    message="Material Category cannot be blank.",
                    back_link=True, back_link_url="/add-material", back_link_label="Go back"
                ), 400
        
        if not unit:
                return render_template('error.html',
                    title="Invalid Input",
                    message="Material Unit cannot be blank.",
                    back_link=True, back_link_url="/add-material", back_link_label="Go back"
                ), 400
        
    
        #supplier can be blank

        # numeric input validation (cant be <0 )
        try: 
            cost_per_unit=float(request.form.get('cost_per_unit', 0)) # Convert to number ( if cant get anything, return 0)
            stock_level=float(request.form.get('stock_level', 0))
            reorder_level=float(request.form.get('reorder_level', 0))

        except ValueError:
            return render_template('error.html',
                title="Invalid Input",
                message="Stock Level, Reorder Level, and Cost must be valid numbers.",
                back_link=True, back_link_url="/add-material", back_link_label="Go back"
            ), 400
        
        if cost_per_unit <= 0 or reorder_level <= 0 or stock_level <= 0:
            return render_template('error.html',
                title="Invalid Input",
                message="Stock Level, Reorder Level, and Cost must be valid numbers and more than 0",
                back_link=True, back_link_url="/add-material", back_link_label="Go back"
            ), 400
        


        #function call.
        
        
            # get new material data from html input from add_material.html, and call add_raw_material() to add it to database.
        result = add_raw_material(
                name=name,  
                category= category, 
                stock_level=stock_level,  
                unit= unit,
                reorder_level=reorder_level,
                cost_per_unit= cost_per_unit,
                supplier= supplier # Optional field
            )    

        # after getting data, use REDIRECT to go back to inventory page. this is needed because if we just return the inventory page 
        # html here, the URL would still be /add-material, which is not ideal. we want the URL to reflect the 
        # actual page we're on, which is /inventory. also, redirecting after POST is a common 
        # best practice to prevent form resubmission if user refreshes the page.
        if result:
            logging.info(f"Material added: '{name}' | category={category}, stock={stock_level}, unit={unit}")
            log_action('material_added', f"name={name}, category={category}, stock={stock_level}, unit={unit}")
            # if succesful data addition. Redirect to inventory page to show updated inventory with new material.
            return redirect(url_for('view_inventory'))
        else:
            # Failed! Return error message with 500 status code
            return ("Error adding material", 500)

        

   
 #note: we dont need if request.method == 'GET' here, because if it's not POST, it must be GET (since we only specified those two methods). 
 # so we can just put the code to show the form outside of the if statement, and it will run when it's a GET request.

    return render_template("add_material.html", # if its a GET request, just show the add material form.
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
    """
    to show stock that is below the reorder level.
    simple GET request
    """
    # Get all materials where stock is below reorder level
    df = get_low_stock_materials()
    materials = df.to_dict(orient='records') if not df.empty else [] # convert each material (row) into dictionary, all dictionarys in a list. 
    return render_template("low_stock.html",
        materials=materials,
        count=len(df),
        back_link=True,
        back_link_url="/",
        back_link_label="Back to Home"
)



@app.route('/export/low-stock-excel')
@requires_auth
def export_low_stock_excel():
   """
   uses GET request to export low stock materials to excel, similar to export_inventory_excel but for low stock items. this is a button in low_stock.html.
   """
   
   df = get_low_stock_materials()  # Get materials below reorder level

   if df.empty:
        return "No data to export", 400  # No low stock items to export

    # Create Excel file (e.g., low_stock_20260203_143022.xlsx)
   filepath = export_to_excel(df, 'low_stock')

    # Trigger browser download
   return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))



#=============
#INVENTORY MANAGEMENT PAGES (edit/delete materials)
#=============

@app.route('/manage-materials') # Page to view all materials with edit/delete options 
@requires_auth
def manage_materials():
    """
    This is a page to view all materials with edit/delete options.
    simple GET, just viewing, but with buttons. 
    """
    df = get_all_materials_with_id()
    materials = df.to_dict(orient='records') if (df is not None and not df.empty) else [] # convert to HTML format like usual. 
    return render_template("manage_materials.html", # load html template for this page.
        materials=materials,
        count=len(materials),
        back_link=True,
        back_link_url="/",
        back_link_label="Back to Home"
)



# edit material page
@app.route('/edit-material/<int:material_id>') # dynamic URL, the main difference of this url is that it takes material_id as a parameter, 
# which is used to identify which material to edit. this is needed because we have multiple 
# materials and we need to know which one we're editing. the <int:material_id> part tells Flask to expect an 
# integer parameter in that part of the URL, and it will pass it to the function as material_id.

# it knows which material to edit based on the material_id in the URL, which is passed to the function as a parameter. when user clicks "edit" button for a material, 
# it takes them to /edit-material/<material_id>, the route to this funciton is in manage_materials.html, where the edit button for each material has a link to 
# /edit-material/{{ material.material_id }}.
@requires_auth

def edit_material(material_id):
    """
    function to edit a material, 

    uses GET to show the edit form with current material details.
    """
    material = get_material_by_id(material_id) # get the material being edited. 
    if not material:
        return render_template('error.html', # if not found, show error page.
            title="Material Not Found",
            message="The material you requested could not be found.",
            back_link=True, back_link_url="/manage-materials", back_link_label="Back to Manage Materials"
        ), 404


    
    mat_id, name, category, stock_level, unit, reorder_level, cost_per_unit, supplier = material # unpack material details for display in edit form.
    
    # msg and err are for redirecting back to this page after form submission with a success or error message. (after adjusting stock or updating details)

    msg = request.args.get('msg', '') # if there's a 'msg' parameter in the URL (e.g., /edit-material/1?msg=Stock+updated), 
    # get its value to show success messages after form submissions. if not, default to empty string.

    err = request.args.get('err', '') # similarly, get 'err' parameter for error messages.
    return render_template("edit_material.html", # show the edit material form, with current material details filled in, and any success/error messages.
        mat_id=mat_id, name=name, category=category,
        stock_level=stock_level, unit=unit, reorder_level=reorder_level,
        cost_per_unit=cost_per_unit, supplier=supplier,
        msg=msg, err=err,
        back_link=True,
        back_link_url="/manage-materials",
        back_link_label="Back to Manage Materials"
)


@app.route('/edit-material/<int:material_id>/adjust-stock', methods=['POST']) # This is a route that is part of the edit material page, 
# but is specifically for handling stock adjustments (POST request). it takes the material_id to know which material's stock to adjust, and it only accepts POST requests since it's processing a form submission.
@requires_auth
def adjust_stock(material_id):

    """
    a partner to edit material function, this function is specifically for handling stock adjustments (increasing or decreasing stock level).
    ONLY uses POST since it's processing a form submission, and it takes material_id to know which material to adjust.

    only adjusts stock level, not specific details of material. 
    """
    try:

        amount = float(request.form.get('amount', 0)) # Get the amount to adjust (convert to number), this is from the form input in edit_material.html 

        


    except ValueError:
        return render_template('error.html', # if not found, show error page.
            title="Invalid Input",
            message="Please enter a valid number for the stock adjustment.",
            back_link=True, back_link_url=f"/edit-material/{material_id}", back_link_label="Back to Edit Material"
        ), 400
    
    #input validation: > =0
    if amount <= 0:
        return render_template('error.html', # if not found, show error page.
            title="Invalid Input",
            message="Please enter a valid number more than 0.",
            back_link=True, back_link_url=f"/edit-material/{material_id}", back_link_label="Back to Edit Material"
        ), 400
    
    action = request.form.get('action') # Get the action (increase or decrease) from the form submission, this is from the submit button name in edit_material.html, where we have two buttons with name="action" and value="increase" or "decrease".

    if action == 'increase':
        result = increase_raw_material(material_id, amount) # Call function to increase stock
    else:
        result = decrease_raw_material(material_id, amount) # Call function to decrease stock (returns new stock level or None if failed)

    if result is not None:
        logging.info(f"Stock adjusted: material_id={material_id}, action={action}, amount={amount}, new_stock={result}")
        log_action('stock_adjusted', f"material_id={material_id}, action={action}, amount={amount}, new_stock={result}")
        return redirect(url_for('edit_material', material_id=material_id, msg=f'Stock updated to {result}')) # if successful, REDIRECT back to edit materil page.
    else:
        return redirect(url_for('edit_material', material_id=material_id, err='Stock update failed. Check there is enough stock to decrease.'))
    
# Note: Similar POST routes would be needed for updating details and deleting the material, following the same pattern of processing the form data and redirecting back to the edit page with a success or error message.




@app.route('/edit-material/<int:material_id>/update-details', methods=['POST'])  # very similar to adjust_stock route, but for updating material details instead of stock level. it also takes material_id to know which material to update, and only accepts POST requests since it's processing a form submission.
# Route to handle updating material details (name, category, etc)
@requires_auth

def update_material_details(material_id): 
    
    try:
    
        name = request.form.get('name') # Get updated name from form
        name = name.strip() if name else None#validate
        category = request.form.get('category')  # Get updated category (or None if empty)
        category = category.strip() if category else None#validate
        unit = request.form.get('unit') # Get updated unit (or None if empty)
        unit = unit.strip() if unit else None #validate
        reorder_level_str = request.form.get('reorder_level')
        cost_per_unit_str = request.form.get('cost_per_unit')
        reorder_level = float(reorder_level_str) if reorder_level_str else None#validate
        cost_per_unit = float(cost_per_unit_str) if cost_per_unit_str else None#validate
        supplier = request.form.get('supplier')
        supplier = supplier.strip() if supplier else None 
    
    except ValueError:
        return render_template('error.html', # if there's a value error (e.g., user entered text in reorder level), show error page.
            title="Invalid Input",
            message = "Reorder Level and Cost must be valid numbers.",
            back_link=True, back_link_url=f"/edit-material/{material_id}", back_link_label="Go back"
        ), 400
    
    #numeric input validation( cant be be zero or less)
    if (reorder_level is not None and reorder_level <= 0)  or (cost_per_unit is not None and cost_per_unit<= 0):
        return render_template('error.html', # if there's a value error (e.g., user entered text in reorder level), show error page.
            title="Invalid Input",
            message = "Reorder Level and Cost must be greater than 0.",
            back_link=True, back_link_url=f"/edit-material/{material_id}", back_link_label="Go back"
        ), 400
    



    result = update_raw_material(material_id, name=name, category=category, unit=unit,
                                 reorder_level=reorder_level, cost_per_unit=cost_per_unit, supplier=supplier) # call function, with updated details. 

    if result:
        logging.info(f"Material details updated: material_id={material_id}, name={name}, category={category}, unit={unit}")
        log_action('material_updated', f"material_id={material_id}, name={name}, category={category}")
        return redirect(url_for('edit_material', material_id=material_id, msg='Details updated successfully'))
    else:
        return redirect(url_for('edit_material', material_id=material_id, err='Failed to update details'))
# Note: The update_raw_material function would need to be implemented in the database module to handle updating the material details based on the provided parameters.

@app.route('/edit-material/<int:material_id>/delete', methods=['POST']) 
# Route to handle deleting a material from inventory
@requires_auth
def delete_material(material_id):
    
    delete_raw_material(material_id)
    logging.info(f"Material deleted: material_id={material_id}")
    log_action('material_deleted', f"material_id={material_id}")
    return redirect(url_for('manage_materials'))





##############
# BATCHES PAGES
###############

"""
1. View ready batches page (/batches) - shows all batches with details and status (ready only). NEW IMPLIMENTATION: 
button to move batch as shipped from ready [POST route to mark as shipped], and button to export ready batches to excel [GET to see batches page, then click export button to trigger excel export and download]

2. create batch page (/create-batch) - form to create a new batch by selecting product recipe, quantity, and optional notes [GET and POST routes]

3. view shipped batches page (/shipped-batches) - shows all shipped batches with details [GET route]
   - has export to excell option as well [GET route to trigger excel export and download]
4. manage batches page (/manage-batches) - view all batches with edit/delete options [GET and POST routes] (similar to manage materials page)
- edit batch page (/edit-batch/<batch_id>) - form to edit batch details, change status, or delete batch [GET and POST routes]
"""

#View all batches
@app.route('/batches')
@requires_auth
def view_batches():
    """
    currently only uses get to show all ready batches, but we will need to add POST routes for marking as shipped.
    
    """

    data = get_batches() # get all batches in df, from inventory_app.py. 
    batches = data.to_dict(orient='records') if not data.empty else [] # convert to HTML friendly like usual.
    columns = list(data.columns) if not data.empty else [] # get column names for table header in html, if data is not empty. 
    #if data is empty, set columns to empty list to avoid errors in html.
    # we need to get columns separately because the batches page shows a table with dynamic columns based on the batch data, so we need to pass the column names to the html to generate the table header.
    return render_template("batches.html", # render the batches page html template.
        batches=batches, columns=columns, count=len(batches),
        back_link=True, back_link_url="/", back_link_label="Back to Home"
)

# mark as shipped button. 
@app.route('/batches/<int:batch_id>/mark-shipped', methods=['POST']) # this is a button in batches.html for each batch, it sends a POST request to this route with the batch_id to mark that batch as shipped.
@requires_auth
def mark_batch_as_shipped(batch_id):
    """
    click button, mark batch as shipped. this is a POST route
    
    """
    mark_as_shipped(batch_id) # call function to update batch status in database.
    logging.info(f"Batch marked as shipped: batch_id={batch_id}")
    log_action('batch_shipped', f"batch_id={batch_id}")
    return redirect(url_for('view_batches')) # after marking as shipped, redirect back to batches page to see updated status.




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


@app.route('/export/shipped-batches-excel')
@requires_auth
def export_shipped_batches_excel():
    """
    Export shipped batches to Excel file
 
 
    """
    df = get_batches_shipped()  # Get all shipped batches

    if df.empty:
        return "No data to export", 400  # No shipped batches to export

    # Create Excel file (e.g., shipped_batches_20260203_143022.xlsx)
    filepath = export_to_excel(df, 'shipped_batches')

    # Trigger browser download
    return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))




@app.route('/create-batch', methods=['GET', 'POST'])
@requires_auth
def create_batch():
    """
    Adds batches to database based on form submission.
    uses GET to show the form, and POST to process the form submission.
    """

    if request.method == 'POST':

        # test parsing
        product_name = request.form.get('product_name')
        product_name = product_name.strip() if product_name else None
        notes = request.form.get('notes')
        notes = notes.strip() if notes else None

        # Text validation 
        if not product_name:
            return render_template('error.html',
                title="Invalid Input",
                message="Product name cannot be blank.",
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 400

        #  numeric parsing 
        try:
            quantity = float(request.form.get('quantity'))
            batch_id_str = request.form.get('batch_id')
            batch_id = int(batch_id_str) if batch_id_str else None

        except ValueError:
            return render_template('error.html',
                title="Invalid Input",
                message="Quantity and batch ID must be valid numbers.",
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 400

        # numeric validation 
        if quantity <= 0:
            return render_template('error.html',
                title="Invalid Input",
                message="Quantity must be greater than zero.",
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 400

        if batch_id is not None and batch_id <= 0:
            return render_template('error.html',
                title="Invalid Input",
                message="Batch ID must be a positive number.",
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 400

        # call function
        try:
            result = add_to_batches(product_name, quantity, notes=notes, batch_id=batch_id, deduct_resources=True)
            if result:
                logging.info(f"Batch created: product='{product_name}', quantity={quantity}, batch_id={batch_id}")
                log_action('batch_created', f"product={product_name}, quantity={quantity}, batch_id={result}")
                return redirect(url_for('view_batches'))
            else:
                return render_template('error.html',
                    title="Error",
                    message="Failed to create batch. Check terminal for details.",
                    back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
                ), 500

        except ValueError as e:
            return render_template('error.html',
                title="Error",
                message=str(e),
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 400

        except Exception as e:
            logging.error(f"create_batch: {e}")
            return render_template('error.html',
                title="Unexpected Error",
                message=str(e),
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 500

    return render_template("create_batch.html",
        back_link=True,
        back_link_url="/",
        back_link_label="Back to Home"
    )

#========================
#MANAGMENT OF BATCHES 
#======================
    
@app.route('/manage-batches') # Page to view all batches with edit/delete options 
@requires_auth
def manage_batches():
    """
    This is a page to view all batches with edit/delete options.
    simple GET, just viewing, but with buttons. 
    """
    df = get_all_batches_with_id()
    batches = df.to_dict(orient='records') if (df is not None and not df.empty) else [] # convert to HTML format like usual. 
    return render_template("manage_batches.html", # load html template for this page.
        batches=batches,
        count=len(batches),
        back_link=True,
        back_link_url="/",
        back_link_label="Back to Home"
)




@app.route('/edit-batch/<int:batch_id>') # dynamic URL for editing a specific batch, identified by batch_id. 
@requires_auth
def edit_batch(batch_id):
    """
    edit batch details, not status, this is from manage batches page,
      where each batch has an edit button that takes you to 
      this page with the batch_id in the URL. this page will show a form
        with current batch details filled in

        GET page route
    """

    batch = get_batch_by_id(batch_id) # get batch details for the batch being edited.
    if not batch:
        return render_template('error.html', # if batch not found, show error page.
            title="Batch Not Found",
            message="The batch you requested could not be found.",
            back_link=True, back_link_url="/manage-batches", back_link_label="Back to Manage Batches"
        ), 404
    
    msg = request.args.get('msg', '') # get success message from URL parameters, if any (e.g., after updating batch details)
    err = request.args.get('err', '') # get error message from URL parameters, if any (e.g., if updating batch details failed)

    return render_template("edit_batch.html", # show the edit batch form, with current batch details and any success/error messages.
        batch = batch,
        msg=msg, err=err,
        back_link=True,
        back_link_url="/manage-batches",
        back_link_label="Back to Manage Batches" )



@app.route('/edit-batch/<int:batch_id>/update-details', methods=['POST']) # POST route for processing the edit batch form submission, where batch_id identifies which batch to update.
@requires_auth
def update_batch_details(batch_id):
    """
    processes the form submission from edit batch page to update batch details (not status). 
    this is a POST route that takes the updated details from the form and updates the batch in the database, then redirects back to the edit batch page with a success or error message.
    """
    try:
        product_name = request.form.get('product_name')
        product_name = product_name.strip() if product_name else None
        quantity_str = request.form.get('quantity')
        notes = request.form.get('notes') 
        notes = notes.strip() if notes else None
        quantity = float(quantity_str) if quantity_str else None

    except ValueError:
        return render_template('error.html',
            title="Invalid Input",
            message="Quantity must be a valid number.",
            back_link=True, back_link_url=f"/edit-batch/{batch_id}", back_link_label="Go back to Edit Batch"
        ), 400

    if quantity is not None and quantity <= 0:
        return render_template('error.html',
            title="Invalid Input",
            message="Quantity must be greater than 0.",
            back_link=True, back_link_url=f"/edit-batch/{batch_id}", back_link_label="Go back to Edit Batch"
        ), 400
    
    result = update_batch(batch_id, product_name=product_name, quantity=quantity, notes=notes)

    if result:
        logging.info(f"Batch details updated: batch_id={batch_id}, product_name={product_name}, quantity={quantity}")
        log_action('batch_updated', f"batch_id={batch_id}, product_name={product_name}, quantity={quantity}")
        return redirect(url_for('edit_batch', batch_id=batch_id, msg='Batch details updated successfully'))
    else:
        return redirect(url_for('edit_batch', batch_id=batch_id, err='Failed to update batch details'))


@app.route('/edit-batch/<int:batch_id>/change-status', methods=['POST']) 
@requires_auth
def change_batch_status(batch_id):
    """
    Change the status of a batch  
     
    This is a POST route that takes the new status from the form submission in the edit batch page, updates the batch status in the database, and redirects back to the edit batch page with a success or error message.
    """

    new_status = request.form.get('status') # Get the new status from the form submission (e.g., "ready", "shipped", etc.)

    result = update_batch_status(batch_id, new_status)
    if result:
        logging.info(f"Batch status changed: batch_id={batch_id}, new_status={new_status}")
        log_action('batch_status_changed', f"batch_id={batch_id}, new_status={new_status}")
        return redirect(url_for('edit_batch', batch_id=batch_id, msg=f'Batch status updated to {new_status}'))
    
    else:
        return redirect(url_for('edit_batch', batch_id=batch_id, err='Failed to update batch status'))
    

@app.route('/edit-batch/<int:batch_id>/delete', methods=['POST'])
@requires_auth
def delete_batch_route(batch_id):
    reallocate = request.form.get('reallocate') == 'true'
    
    delete_batch(batch_id, reallocate=reallocate)
    logging.info(f"Batch deleted: batch_id={batch_id}, reallocate={reallocate}")
    log_action('batch_deleted', f"batch_id={batch_id}, reallocate={reallocate}")
    return redirect(url_for('manage_batches'))






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

    GET route
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

    # extra df display alteration to show recipe name and notes only on the first row of each recipe, 
    # for better readability in the HTML table. 
    # this is just for display purposes, it doesn't change the actual data in the database or how we process it.
    
    df_display = df.copy() #make copy of dataframe for display
    duplicate_mask = df_display['recipe_product_name'].duplicated() # create mask for duplicate recipe names, will have all rows except the first occurrence of each recipe name marked as True.
    df_display.loc[duplicate_mask, 'recipe_product_name'] = '' # make them invisible. 
    df_display.loc[duplicate_mask, 'notes'] = '' # also make notes invisible for duplicate rows, 
    recipe_count = df['recipe_product_name'].nunique() # count unique recipe names
    recipes = df_display.to_dict(orient='records') # convert to list of dictionaries for HTML display, like usual.

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
 

    """
    df = get_all_recipes()  # Get all recipes with materials

    if df.empty:
        return "No data to export", 400  # No recipes to export

    # Create Excel file (e.g., recipes_20260203_143022.xlsx)
    filepath = export_to_excel(df, 'recipes')

    # Trigger browser download
    return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))






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

   
    COMPLEXITY NOTE:
    Unlike simple forms (like add-material), recipes require MULTIPLE materials.
    We use JavaScript on the frontend to dynamically add/remove material rows,
    then parse them on the backend using indexed form field names (material_name_0, etc.)

    """

    if request.method == 'POST':

        
        product_name = request.form.get('product_name')

        product_name = product_name.strip() if product_name else None # cant be none

        notes = request.form.get('notes')#can be none

        notes = notes.strip() if notes else None
        
        if not product_name:
            return render_template('error.html',
                title="Invalid Input",
                message="Product name cannot be blank.",
                back_link=True, back_link_url="/add-recipe", back_link_label="Go back"
                 ), 400
    


        #  Parse dynamic material fields
      
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

            # proccess the quantiy (convert to float)and material name, and add to materials list if valid
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
                    return render_template('error.html',
                        title="Invalid Input",
                        message=f"Quantity for material '{material_name}' must be a valid number.",
                        back_link=True, back_link_url="/add-recipe", back_link_label="Go back and fix it"
                    ), 400

            # Move to next index
            index += 1

        

        #Validate required data
        # Check that we have both a product name and at least one material
        if not product_name or not materials:
            return render_template('error.html',
                title="Missing Required Fields",
                message="Please provide a product name and at least one material.",
                back_link=True, back_link_url="/add-recipe", back_link_label="Go back and try again"
            ), 400

        


        #  save recipe
        
        try:
            
            result = add_recipe(product_name, materials, notes)
            # materials is the list of dictionaries we build from form data. 
            if result:
                #success
                logging.info(f"Recipe added: '{product_name}' with {len(materials)} materials")
                log_action('recipe_added', f"product_name={product_name}, materials={len(materials)}")
                return redirect(url_for('view_recipes'))
            else:
                
                return render_template('error.html',
                    title="Error Adding Recipe",
                    message="Failed to add recipe. Please check that all materials exist in inventory.",
                    back_link=True, back_link_url="/add-recipe", back_link_label="Go back and try again"
                ), 500

        except Exception as e:
            logging.error(f"add_recipe_route: {e}")
            # Catch any unexpected errors and display them
            # In production, you might want to log this and show a generic message
            return render_template('error.html',
                title="Error Adding Recipe",
                message="An error occurred.",
                error_detail=str(e),
                back_link=True, back_link_url="/add-recipe", back_link_label="Go back and try again"
            ), 500

   
   
   #GET handeling. 

    return render_template("add_recipe.html",
    back_link=True,
    back_link_url="/",
    back_link_label="Back to Home"
)



#==============
#RECIPE MANAGEMENT PAGES (edit/delete recipes)
#==============

@app.route('/manage-recipes') # Page to view all recipes with edit/delete options
@requires_auth
def manage_recipes():
    """
    This is a page to view all recipes with edit/delete options.
    simple GET, just viewing, but with buttons. 
    """
    df = get_all_recipes_with_id()
    recipes = df.to_dict(orient='records') if (df is not None and not df.empty) else [] # convert to HTML format like usual. 
    return render_template("manage_recipes.html", # load html template for this page.
        recipes=recipes,
        count=len(recipes),
        back_link=True,
        back_link_url="/",
        back_link_label="Back to Home"
)

@app.route('/edit-recipe/<int:recipe_id>') # dynamic URL for editing a specific recipe, identified by recipe_id.
@requires_auth
def edit_recipe(recipe_id):
    """
    view edit recipe page, with form to edit recipe details and materials. 
    this is from manage recipes page, 
    where each recipe has an edit button that takes you to this page with the recipe_id in the URL. 
    this page will show a form with current recipe details filled in, and allow editing of both the recipe details 
    (name, notes) and the materials (add/remove materials, change quantities).
    
    GET page route
    """

    df = get_recipe_by_id(recipe_id) #get recipe details for the recipe being edited

    if df is None or df.empty:
        return render_template('error.html',
            title="Recipe Not Found",
            message="The recipe you requested could not be found.",
            back_link=True, back_link_url="/manage-recipes", back_link_label="Back to Manage Recipes"
        ), 404

    # Extract recipe-level info from first row (same for all rows)
    recipe_id_val = df['recipe_id'].iloc[0]
    product_name = df['product_name'].iloc[0]
    notes = df['notes'].iloc[0]

    # Extract materials list — one dict per row
    materials = df[['material_name', 'quantity_needed']].to_dict(orient='records') # html friendly format. 

    msg = request.args.get('msg', '')
    err = request.args.get('err', '')

    return render_template("edit_recipe.html",
        recipe_id=recipe_id_val,
        product_name=product_name,
        notes=notes,
        materials=materials,
        msg=msg,
        err=err,
        back_link=True,
        back_link_url="/manage-recipes",
        back_link_label="Back to Manage Recipes"
    )



    
@app.route('/edit-recipe/<int:recipe_id>/update', methods=['POST']) # POST route for processing the edit recipe form submission, where recipe_id identifies which recipe to update.
@requires_auth
def update_recipe_route(recipe_id):
    """
    updates the recipe details and materials based on the form submission
    from the edit recipe page.

    POST route for processing edit recipe submission. 
    """
    try:
        
        notes = request.form.get('notes') 

        notes = notes.strip() if notes else None

        product_name = request.form.get('product_name') 

        product_name = product_name.strip() if product_name else None

        

        materials = [] # materials come in as indexed fields, so we have to parse same as recipe
        index = 0
        while True:
            material_name = request.form.get(f'material_name_{index}')
            quantity_str = request.form.get(f'quantity_{index}')
            if not material_name: #loop until out of material name
                break
            if material_name.strip() and quantity_str: # if we have a material name and quantity, add to materials list
                try:
                    materials.append({ #as a dictionary. 
                        'material_name': material_name.strip(),
                        'quantity_needed': float(quantity_str)
                    })
                except ValueError:
                    return render_template('error.html',
                        title="Invalid Input",
                        message=f"Quantity for '{material_name}' must be a valid number.",
                        back_link=True, back_link_url=f"/edit-recipe/{recipe_id}", back_link_label="Go back"
                    ), 400
            index += 1

    except ValueError:
        return render_template('error.html',
            title="Invalid Input",
            message="Quantity must be a valid number",
            back_link=True, back_link_url=f"/edit-recipe/{recipe_id}", back_link_label="Go back to Edit Recipe"
        ), 400
    
    if not product_name:
        return render_template('error.html',
            title="Invalid Input",
            message="Product name cannot be blank.",
            back_link=True, back_link_url=f"/edit-recipe/{recipe_id}", back_link_label="Go back"
        ), 400

    if not materials:
        return render_template('error.html',
            title="Invalid Input",
            message="Recipe must have at least one material.",
            back_link=True, back_link_url=f"/edit-recipe/{recipe_id}", back_link_label="Go back"
        ), 400
    
    result = update_recipe(recipe_id, product_name=product_name, notes=notes, materials=materials)
    

    if result:
        logging.info(f"Recipe updated: recipe_id={recipe_id}, product_name={product_name}")
        log_action('recipe_updated', f"recipe_id={recipe_id}, product_name={product_name}")
        return redirect(url_for('edit_recipe', recipe_id=recipe_id, msg='Recipe details updated successfully'))
    else:
        return redirect(url_for('edit_recipe', recipe_id=recipe_id, err='Failed to update recipe details'))



@app.route('/edit-recipe/<int:recipe_id>/delete', methods=['POST'])
@requires_auth
def delete_recipe_route(recipe_id):
    """
    simply deletes the recipe from database,
    POST route
    """
    
    delete_recipe_by_id(recipe_id)
    logging.info(f"Recipe deleted: recipe_id={recipe_id}")
    log_action('recipe_deleted', f"recipe_id={recipe_id}")
    return redirect(url_for('manage_recipes'))





# ========================
# API ENDPOINTS
# ========================

@app.route('/api/health')
def health_check():
    try:
        db = get_db_connection() # check if connection string is working
        cursor = db.cursor() # make sure we can get a cursor
        db.execute(cursor, "SELECT 1") # simple query  to check if we can execute queries
        db.close() # close connection after check
        db_status = 'connected' # status is connected if all above steps work. 
    except Exception as e:
        logging.error(f"health_check: {e}")
        db_status = f'error: {str(e)}'
    return jsonify({'status': 'healthy', 'db': db_status, 'service': 'matcha-inventory', 'timestamp': datetime.now().isoformat()})


# api for drop down autocomplete search on recipes, (required js to impliment)
@app.route('/api/materials')
@requires_auth
def api_materials():
    df = get_all_materials()
    if df.empty:
        return jsonify([])
    return jsonify(df['name'].dropna().sort_values().tolist())


# api for drop down autocomplete search on batches, (required js to impliment)
#automatically detects users search when making batch
@app.route('/api/recipes')
@requires_auth
def api_recipes():
    df = get_all_recipes()
    if df.empty:
        return jsonify([])
    return jsonify(df['recipe_product_name'].dropna().drop_duplicates().sort_values().tolist())

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
