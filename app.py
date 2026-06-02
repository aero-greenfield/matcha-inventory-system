
try:
    from dotenv import load_dotenv # load enviroment varibales, python has build in libracy that loads them in. 
    load_dotenv()
    
except ImportError:
   
    pass

# =======================
# IMPORTS
# =======================




from flask import Flask, json, request, redirect, url_for, jsonify, send_file, render_template, flash  # ADDED: flash for session-backed messages

# - Flask: The main application class
# - request: obejct that give you access to income http request data. 
# - redirect:  instructs the browser to go to a different URL
# - url_for:  builds urls for different functions (useful for redirects)
# - jsonify:  converests python data structures (lists, dicts) to JSON format 
# - send_file:  sends file to browser for download

import os  # Operating system functions (file paths, environment variables)
import math  # ADDED: math.ceil for computing total_pages in paginated routes
from datetime import datetime  # For timestamps in exports

from flask_wtf.csrf import CSRFProtect # security necesity. 

#Service layer imports. :




from services.setup import create_database
from services.audit import log_action, view_logs
from services.materials import (
    add_raw_material, get_all_materials,
    get_material_by_id,
    update_raw_material,
    delete_raw_material, get_material_id,
    get_low_stock_materials,  # ADDED: was missing — /low-stock route raised NameError without this
)
from services.lots import (
    get_all_lots,
    get_lot_by_id,
    receive_lot as inventory_receive_lot,
    update_lot,
    delete_lot,
    get_batches_for_lot,
)
from services.recipes import (
    add_recipe, get_all_recipes, get_all_recipes_with_id,
    get_recipe_by_id, update_recipe, delete_recipe_by_id,
    check_negative_stock,
)
from services.batches import (
    add_to_batches, get_batches, get_batches_shipped, get_batches_planned,
    get_all_batches_with_id, get_batch_by_id, mark_as_shipped, delete_batch,
    update_batch, update_batch_status, get_batch_materials,
    adjust_batch_material, check_batch_materials_stock,
)


# Import helper functions for exporting data
# - export_to_csv: Exports DataFrames to CSV files (not currently used)
# - export_to_excel: NEW - Exports DataFrames to Excel files (.xlsx format)

from helper_functions import ( export_to_excel,)

from auth import requires_auth
from routes.api import api_bp

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
secret = os.environ.get('SECRET_KEY')
if not secret:
    raise RuntimeError("SECRET_KEY environment variable must be set")
app.config['SECRET_KEY'] = secret

# ADDED: harden session cookie — HTTPONLY blocks JS access, Lax prevents cross-site leakage.
# SESSION_COOKIE_SECURE is omitted here; enable it at the deployment level when HTTPS is enforced
# (setting it to True over plain HTTP would break sessions entirely).
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

csrf = CSRFProtect(app)
app.register_blueprint(api_bp)


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
    from database import get_connection
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
# RATE LIMITING
# ========================
# ADDED: prevents brute-force attacks against the HTTP Basic Auth endpoint.
# Limits are applied per source IP. flask-limiter added to requirements.txt.
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
# ========================

# ADDED: upper bound for ?page= query param.
# Without this, ?page=99999999 generates a massive OFFSET query that stalls the database.
MAX_PAGE = 10_000











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

    
    # ADDED: read page number from URL (?page=N); default to page 1
    PER_PAGE = 50
    page = min(max(1, int(request.args.get('page', 1))), MAX_PAGE)  # CHANGED: capped at MAX_PAGE to prevent large-OFFSET DoS

    # CHANGED: was get_all_materials() returning a plain df.
    #          Now returns (df, total) tuple; page= triggers LIMIT/OFFSET in the query.
    df, total = get_all_materials(page=page, per_page=PER_PAGE)

    materials = df.to_dict(orient='records') if not df.empty else []
    # ADDED: compute total page count for pagination controls in the template
    total_pages = math.ceil(total / PER_PAGE) if total else 1

    return render_template("inventory.html",
        materials=materials,
        count=len(df),
        page=page,
        total_pages=total_pages,
        total=total,
        back_link=True,
        back_link_url="/",
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
    # CHANGED: get_all_materials now returns (df, total). page=None skips LIMIT/OFFSET
    #          so the export still contains all rows, not just one page.
    df, _ = get_all_materials(page=None)

    # Return error if no data to export
    if df.empty:
        return "No data to export", 400

    # Create Excel file with timestamp (e.g., inventory_20260203_143022.xlsx)
    filepath = export_to_excel(df, 'inventory') # from helper_functions, this creates the excel file and returns the file path.

    # Send file to browser as download
    # - as_attachment=True: Forces download instead of opening in browser
    # - download_name: Sets the filename shown in download dialog
    return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))


@app.route('/receive-lot', methods=['GET', 'POST'])
@requires_auth
def receive_lot():
    """
    Route to receive a new lot of raw materials.

    GET: Show form to input lot details (material, quantity, etc.)
    POST: Process form submission, add lot to database, update inventory

    This route allows users to log the receipt of new raw material lots, which is essential for inventory management.
    
    adds row to raw_material_lots table, 

    inputs needed: (when calling receive_lot)
    material_id, lot_number, quantity, received_date, expiry_date=None, location=None, supplier=None, cost_per_unit=None):

    """

    if request.method == 'POST':
        # all string inputs
        name          = request.form.get('material_name', '').strip()
        lot_number    = request.form.get('lot_number', '').strip()
        quantity_str  = request.form.get('quantity', '').strip()
        received_date = request.form.get('received_date', '').strip()
        expiry_date       = request.form.get('expiry_date', '').strip() or None
        location          = request.form.get('location', '').strip() or None
        supplier          = request.form.get('supplier', '').strip() or None
        cost_per_unit_str = request.form.get('cost_per_unit', '').strip()


        # for the required fields, check if they are blank 
        if not name:
            return render_template('error.html', title="Invalid Input", message="Material name cannot be blank.",
                back_link=True, back_link_url="/receive-lot", back_link_label="Go back"), 400
        if not lot_number:
            return render_template('error.html', title="Invalid Input", message="Lot number cannot be blank.",
                back_link=True, back_link_url="/receive-lot", back_link_label="Go back"), 400
        if not quantity_str:
            return render_template('error.html', title="Invalid Input", message="Quantity cannot be blank.",
                back_link=True, back_link_url="/receive-lot", back_link_label="Go back"), 400
        if not received_date:
            return render_template('error.html', title="Invalid Input", message="Received date cannot be blank.",
                back_link=True, back_link_url="/receive-lot", back_link_label="Go back"), 400

        #get material_id, if no material_id redirect user to add_material route. 
        material_id = get_material_id(name)
        if material_id is None:
            return redirect(url_for('add_material_route',
                from_receive_lot='1',
                material_name=name,
                lot_number=lot_number,
                quantity=quantity_str,
                received_date=received_date,
                expiry_date=expiry_date or '',
                location=location or '',
                supplier=supplier or '',
                cost_per_unit_lot=cost_per_unit_str,
            ))

            #user will fill out needed on this route, 
            #then it will be directed back here. 

        #validate non string inputs.
        try:
            quantity = float(quantity_str)
            cost_per_unit = float(cost_per_unit_str) if cost_per_unit_str else None
        except ValueError:
            return render_template('error.html', title="Invalid Input", message="Quantity and Cost per Unit must be valid numbers.",
                back_link=True, back_link_url="/receive-lot", back_link_label="Go back"), 400

        #quant cant be negative
        if quantity <= 0:
            return render_template('error.html', title="Invalid Input", message="Quantity must be greater than 0.",
                back_link=True, back_link_url="/receive-lot", back_link_label="Go back"), 400

        if cost_per_unit is not None and cost_per_unit <= 0:
            return render_template('error.html', title="Invalid Input", message="Cost per Unit must be greater than 0.",
                back_link=True, back_link_url="/receive-lot", back_link_label="Go back"), 400

        #call function, add to lots
        lot_id = inventory_receive_lot(material_id, lot_number, quantity, received_date, expiry_date, location, supplier, cost_per_unit)
        
        if lot_id is None: # if failed to add lot, return error page.
            return render_template('error.html', title="Error", message="Failed to add lot. Check logs for details.",
                back_link=True, back_link_url="/receive-lot", back_link_label="Go back"), 500

        #success. 
        log_action('lot_received', f"material={name}, lot={lot_number}, qty={quantity}, date={received_date}")
        return redirect(url_for('view_inventory'))



    # if GET request, show the receive lot form. if redirected from add_material route due to missing material, pre-fill the form with the data they entered.
    return render_template('receive_lot.html',
        material_name=request.args.get('material_name', ''),
        lot_number=request.args.get('lot_number', ''),
        quantity=request.args.get('quantity', ''),
        received_date=request.args.get('received_date', ''),
        expiry_date=request.args.get('expiry_date', ''),
        location=request.args.get('location', ''),
        supplier=request.args.get('supplier', ''),
        cost_per_unit=request.args.get('cost_per_unit', ''),
    )




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
        - float() for decimal numbers (stock_level, reorder_level)
        - int() for whole numbers (if needed)
        """
        #input string parsing
        name = request.form.get('name') # Get value from <input name="name"> handled in add_material.html
        category=request.form.get('category')
        unit=request.form.get('unit')

        name = name.strip() if name else None
        category = category.strip() if category else None
        unit = unit.strip() if unit else None

        
        
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
        
    
        # numeric input validation (cant be <0 )
        try:
            reorder_level=float(request.form.get('reorder_level', 0))

        except ValueError:
            return render_template('error.html',
                title="Invalid Input",
                message="Reorder Level must be a valid number.",
                back_link=True, back_link_url="/add-material", back_link_label="Go back"
            ), 400

        if reorder_level <= 0:
            return render_template('error.html',
                title="Invalid Input",
                message="Reorder Level must be more than 0",
                back_link=True, back_link_url="/add-material", back_link_label="Go back"
            ), 400


        #function call.
        result = add_raw_material(
                name=name,
                category=category,
                unit=unit,
                reorder_level=reorder_level,
            )

        from_receive_lot = request.form.get('from_receive_lot', '')

        if result == "duplicate": # error if name exists.
            return render_template("add_material.html",
                error=f"A material named '{name}' already exists. Please use a different name or update the existing one.",
                from_receive_lot=from_receive_lot,
                material_name=name,
                lot_number=request.form.get('lot_number', ''),
                quantity=request.form.get('quantity', ''),
                received_date=request.form.get('received_date', ''),
                expiry_date=request.form.get('expiry_date', ''),
                location=request.form.get('location', ''),
                supplier_lot=request.form.get('supplier_lot', ''),
                cost_per_unit_lot=request.form.get('cost_per_unit_lot', ''),
            )

        elif result: # if result is good.
            logging.info(f"Material added: '{name}' | category={category}, unit={unit}")
            log_action('material_added', f"name={name}, category={category}, unit={unit}")
            if from_receive_lot == '1': #if this route was directed via lot recieve func, go back to that when done.
                return redirect(url_for('receive_lot',
                    material_name=name,
                    lot_number=request.form.get('lot_number', ''),
                    quantity=request.form.get('quantity', ''),
                    received_date=request.form.get('received_date', ''),
                    expiry_date=request.form.get('expiry_date', ''),
                    location=request.form.get('location', ''),
                    supplier=request.form.get('supplier_lot', ''),
                    cost_per_unit=request.form.get('cost_per_unit_lot', ''),
                ))
            return redirect(url_for('view_inventory'))
        else:
            return ("Error adding material", 500)

        

   
 #note: we dont need if request.method == 'GET' here, because if it's not POST, it must be GET (since we only specified those two methods). 
 # so we can just put the code to show the form outside of the if statement, and it will run when it's a GET request.

    # if GET request, show the add material form. if redirected from receive_lot route due to missing material, pre-fill the form with the data they entered in receive_lot.
    from_receive_lot = request.args.get('from_receive_lot', '')
    return render_template("add_material.html",
        back_link=True,
        back_link_url="/",
        back_link_label="Back to Home",
        from_receive_lot=from_receive_lot,
        material_name=request.args.get('material_name', ''),
        lot_number=request.args.get('lot_number', ''),
        quantity=request.args.get('quantity', ''),
        received_date=request.args.get('received_date', ''),
        expiry_date=request.args.get('expiry_date', ''),
        location=request.args.get('location', ''),
        supplier_lot=request.args.get('supplier', ''),
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
    # ADDED: pagination for manage-materials page
    PER_PAGE = 50
    page = min(max(1, int(request.args.get('page', 1))), MAX_PAGE)  # CHANGED: capped at MAX_PAGE to prevent large-OFFSET DoS

    # CHANGED: get_all_materials now returns (df, total) tuple
    df, total = get_all_materials(page=page, per_page=PER_PAGE)

    materials = df.to_dict(orient='records') if (df is not None and not df.empty) else []
    # ADDED: total_pages for pagination controls in template
    total_pages = math.ceil(total / PER_PAGE) if total else 1

    return render_template("manage_materials.html",
        materials=materials,
        count=len(materials),
        page=page,
        total_pages=total_pages,
        total=total,
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


    
    mat_id, name, category,  unit, reorder_level = material # unpack material details for display in edit form.

    msg = request.args.get('msg', '')
    err = request.args.get('err', '')
    return render_template("edit_material.html",
        mat_id=mat_id, name=name, category=category,
        unit=unit, reorder_level=reorder_level,
        msg=msg, err=err,
        back_link=True,
        back_link_url="/manage-materials",
        back_link_label="Back to Manage Materials"
)





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
        reorder_level = float(reorder_level_str) if reorder_level_str else None
    
    except ValueError:
        return render_template('error.html',
            title="Invalid Input",
            message = "Reorder Level must be a valid number.",
            back_link=True, back_link_url=f"/edit-material/{material_id}", back_link_label="Go back"
        ), 400

    if reorder_level is not None and reorder_level <= 0:
        return render_template('error.html',
            title="Invalid Input",
            message = "Reorder Level must be greater than 0.",
            back_link=True, back_link_url=f"/edit-material/{material_id}", back_link_label="Go back"
        ), 400

    result = update_raw_material(material_id, name=name, category=category, unit=unit,
                                 reorder_level=reorder_level)

    if result:
        logging.info(f"Material details updated: material_id={material_id}, name={name}, category={category}, unit={unit}")
        log_action('material_updated', f"material_id={material_id}, name={name}, category={category}")
        # CHANGED: was url_for(..., msg=...) — moved to flash() so messages are session-backed
        flash('Details updated successfully', 'success')
        return redirect(url_for('edit_material', material_id=material_id))
    else:
        flash('Failed to update details', 'error')
        return redirect(url_for('edit_material', material_id=material_id))
# Note: The update_raw_material function would need to be implemented in the database module to handle updating the material details based on the provided parameters.

@app.route('/edit-material/<int:material_id>/delete', methods=['POST']) 
# Route to handle deleting a material from inventory
@requires_auth
def delete_material(material_id):
    
    result = delete_raw_material(material_id)
    if not result:
        return render_template('error.html',
            title="Delete Failed",
            message="Could not delete material. Please try again.",
        ), 500
    logging.info(f"Material deleted: material_id={material_id}")
    log_action('material_deleted', f"material_id={material_id}")
    if result.get("affected_batches"):
        count = len(result["affected_batches"])
        warning = f"Material deleted. Note: it was used in {count} batch(es) — those records no longer show this ingredient."
        # CHANGED: was url_for(..., warning=...) — moved to flash()
        flash(warning, 'warning')
        return redirect(url_for('manage_materials'))
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

    # ADDED: two independent page params — ready and planned sections paginate separately
    PER_PAGE = 50
    ready_page   = max(1, int(request.args.get('ready_page', 1)))
    planned_page = min(max(1, int(request.args.get('planned_page', 1))), MAX_PAGE)  # CHANGED: capped at MAX_PAGE to prevent large-OFFSET DoS

    # CHANGED: get_batches and get_batches_planned now return (df, total) tuples
    data, ready_total         = get_batches(page=ready_page, per_page=PER_PAGE)
    planned_data, planned_total = get_batches_planned(page=planned_page, per_page=PER_PAGE)

    # PRESERVED: Python standard/mix split — unchanged, still runs on whatever slice the query returned
    all_ready    = data.to_dict(orient='records') if not data.empty else []
    ready_standard = [b for b in all_ready if b.get('batch_type') != 'mix']
    ready_mix      = [b for b in all_ready if b.get('batch_type') == 'mix']

    all_planned    = planned_data.to_dict(orient='records') if not planned_data.empty else []
    planned_standard = [b for b in all_planned if b.get('batch_type') != 'mix']
    planned_mix      = [b for b in all_planned if b.get('batch_type') == 'mix']

    # ADDED: compute total pages for each section's pagination nav
    ready_total_pages   = math.ceil(ready_total / PER_PAGE) if ready_total else 1
    planned_total_pages = math.ceil(planned_total / PER_PAGE) if planned_total else 1

    return render_template("batches.html",
        ready_standard=ready_standard,
        ready_mix=ready_mix,
        planned_standard=planned_standard,
        planned_mix=planned_mix,
        ready_page=ready_page,
        ready_total_pages=ready_total_pages,
        planned_page=planned_page,
        planned_total_pages=planned_total_pages,
        back_link=True, back_link_url="/", back_link_label="Back to Home"
)

# mark as shipped button. 
@app.route('/batches/<int:batch_id>/mark-shipped', methods=['POST']) # this is a button in batches.html for each batch, it sends a POST request to this route with the batch_id to mark that batch as shipped.
@requires_auth
def mark_batch_as_shipped(batch_id):
    """
    click button, mark batch as shipped. this is a POST route
    
    """
    result = mark_as_shipped(batch_id) # call function to update batch status in database.
    if not result:
        return render_template('error.html',
            title="Ship Failed",
            message="Could not mark batch as shipped. The batch may not exist.",
        ), 500
    logging.info(f"Batch marked as shipped: batch_id={batch_id}")
    log_action('batch_shipped', f"batch_id={batch_id}")
    return redirect(url_for('view_batches')) # after marking as shipped, redirect back to batches page to see updated status.


@app.route('/batches/<int:batch_id>/materials')
@requires_auth
def batch_materials(batch_id):
    """
    shows in details when clicking on detials of batch, 
    when calling function, it returns: material name, quantity, unit, batch material lot id, lot number, and batch id,
    but for batch details, user only sees: material name, quantity used, unit, and lot number. 
    
    the batch material lot id and batch id are just for reference and not shown to user.
    
    
    """
    rows = get_batch_materials(batch_id)
    materials = [
        {'material_name': r[0], 'quantity_used': r[1], 'unit': r[2], 'batch_material_lot_id': r[3], 'lot_number': r[4], 'material_id': r[5]}
        for r in rows
    ]
    return jsonify(materials)



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
    # CHANGED: get_batches now returns (df, total). page=None skips LIMIT/OFFSET
    #          so the export still contains all ready-batch rows, not just one page.
    df, _ = get_batches(page=None)

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

    # ADDED: pagination for shipped batches
    PER_PAGE = 50
    page = min(max(1, int(request.args.get('page', 1))), MAX_PAGE)  # CHANGED: capped at MAX_PAGE to prevent large-OFFSET DoS

    # CHANGED: get_batches_shipped now returns (df, total) tuple
    df, total = get_batches_shipped(page=page, per_page=PER_PAGE)

    batches = df.to_dict(orient='records') if not df.empty else []
    columns = list(df.columns) if not df.empty else []
    # ADDED: total_pages for pagination controls in the template
    total_pages = math.ceil(total / PER_PAGE) if total else 1

    return render_template("shipped_batches.html",
        batches=batches, columns=columns, count=len(batches),
        page=page,
        total_pages=total_pages,
        total=total,
        back_link=True, back_link_url="/", back_link_label="Back to Home"
)


@app.route('/export/shipped-batches-excel')
@requires_auth
def export_shipped_batches_excel():
    """
    Export shipped batches to Excel file
 
 
    """
    # CHANGED: get_batches_shipped now returns (df, total). page=None skips LIMIT/OFFSET
    #          so the export still contains all shipped-batch rows, not just one page.
    df, _ = get_batches_shipped(page=None)

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
        expiration_date = request.form.get('expiration_date', '').strip() or None
        planned_completion_date = request.form.get('planned_completion_date', '').strip() or None
        batch_type = request.form.get('batch_type', 'standard').strip()
        # Text validation
        if not product_name:
            return render_template('error.html',
                title="Invalid Input",
                message="Product name cannot be blank.",
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 400

        batch_number = request.form.get('batch_number', '').strip()
        if not batch_number:
            return render_template('error.html',
                title="Invalid Input",
                message="Batch number cannot be blank.",
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 400

        #  numeric parsing
        try:
            quantity = float(request.form.get('quantity'))
        except ValueError:
            return render_template('error.html',
                title="Invalid Input",
                message="Quantity must be a valid number.",
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 400

        # numeric validation
        if quantity <= 0:
            return render_template('error.html',
                title="Invalid Input",
                message="Quantity must be greater than zero.",
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 400

        if expiration_date:
            try:
                datetime.strptime(expiration_date, '%Y-%m-%d')
            except ValueError:
                return render_template('error.html',
                    title="Invalid Input",
                    message="Invalid expiration date format. Use YYYY-MM-DD.",
                    back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
                ), 400

        # validate planned_completion_date
        
        if planned_completion_date:
            try:
                pcd = datetime.strptime(planned_completion_date, '%Y-%m-%d') #valid date
                if pcd.date() < datetime.now().date(): # planned date cant be in the past
                    return render_template('error.html',
                        title="Invalid Input",
                        message="Planned completion date cannot be in the past.",
                        back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
                    ), 400
            except ValueError:
                return render_template('error.html',
                    title="Invalid Input",
                    message="Invalid planned completion date format. Use YYYY-MM-DD.",
                    back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
                ), 400
        
        # batch type validation:
        if batch_type not in ('standard', 'mix', 'finished'):
            return render_template('error.html',
                title="Invalid Input",
                message="Invalid batch type. Must be standard, mix, or finished.",
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 400


        #LOT SELECTION PARSING:
        lot_selections_raw = request.form.get('lot_selection', '').strip()# get the raw string from the form
        lot_selections = None
        if lot_selections_raw:
            try:
                raw = json.loads(lot_selections_raw) # parse the JSON string into a Python object (list of dicts)
                lot_selections = {int(k): v for k, v in raw.items()} # convert keys to int for easier handling later
            except (ValueError, TypeError):
                return render_template(
                    'error.html',
                    title="Invalid Input",
                    message="Invalid lot selection format.",
                    back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
                ), 400




        #INPUT VALIDATION DONE===============================


        # see if its okay that batch creation makes stock go negative. 
        defer_deduction = (batch_type == 'finished' and bool(planned_completion_date)) 
        confirm_negative = request.form.get('confirm_negative') == '1'

        if not defer_deduction and not confirm_negative:
            negative_materials = check_negative_stock(product_name, quantity)
            if negative_materials:
                return render_template('confirm_negative_stock.html',
                    negative_materials=negative_materials,
                    form_data={
                        'product_name': product_name,
                        'quantity': quantity,
                        'notes': notes or '',
                        'batch_number': batch_number,
                        'expiration_date': expiration_date or '',
                        'planned_completion_date': planned_completion_date or '',
                        'batch_type': batch_type,
                        'lot_selections': lot_selections_raw, # raw JSON string, must be string because
                        #confirm_negative_stock.html needs to pass back an GTML form hidden input (whcih only holds strings).
                    }
                )

        # call function
        try:
            result = add_to_batches(product_name, quantity, notes=notes, batch_number=batch_number, deduct_resources=True, expiration_date=expiration_date, planned_completion_date=planned_completion_date, batch_type=batch_type, allow_negative=confirm_negative, lot_selections=lot_selections)
            if result:
                logging.info(f"Batch created: product='{product_name}', quantity={quantity}, batch_number={batch_number}, batch_type={batch_type}")
                log_action('batch_created', f"product={product_name}, quantity={quantity}, batch_id={result}, batch_number={batch_number}, batch_type={batch_type}")
                return redirect(url_for('view_batches'))
            else:
                return render_template('error.html',
                    title="Error",
                    message="Failed to create batch. Check terminal for details.",
                    back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
                ), 500

        except ValueError as e:
            # CHANGED: was str(e) — raw ValueError messages can leak internal schema/logic details.
            # Log the real error server-side and show a safe generic message to the user.
            logging.warning(f"create_batch ValueError: {e}")
            return render_template('error.html',
                title="Error",
                message="Invalid input. Please check your selections and try again.",
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 400

        except Exception as e:
            logging.error(f"create_batch: {e}", exc_info=True)
            return render_template('error.html',
                title="Unexpected Error",
                message="An unexpected error occurred. Please try again.",
                back_link=True, back_link_url="/create-batch", back_link_label="Go back to Create Batch"
            ), 500


    # CHANGED: get_all_materials now returns (df, total). page=None fetches the full table
    #          so the housemade filter below still sees every material.
    all_materials_df, _ = get_all_materials(page=None)
    if not all_materials_df.empty:
        housemade_materials = all_materials_df[all_materials_df['is_housemade'] == True][['name', 'stock_level', 'unit']].to_dict(orient='records')
    else:
        housemade_materials = []
    return render_template("create_batch.html",
        housemade_materials = housemade_materials,
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
    # ADDED: pagination for manage-batches page
    PER_PAGE = 50
    page = min(max(1, int(request.args.get('page', 1))), MAX_PAGE)  # CHANGED: capped at MAX_PAGE to prevent large-OFFSET DoS

    # CHANGED: get_all_batches_with_id now returns (df, total) tuple
    df, total = get_all_batches_with_id(page=page, per_page=PER_PAGE)

    batches = df.to_dict(orient='records') if (df is not None and not df.empty) else []
    # ADDED: total_pages for pagination controls in the template
    total_pages = math.ceil(total / PER_PAGE) if total else 1

    return render_template("manage_batches.html",
        batches=batches,
        count=len(batches),
        page=page,
        total_pages=total_pages,
        total=total,
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
    batch_materials_rows = get_batch_materials(batch_id) # get materials used in this batch, to show in the edit page and allow adjustments.
    batch_materials = [] #get materials df and convert to list of dicts for display in edit batch page.
    for r in batch_materials_rows:
        batch_materials.append({'material_name': r[0], 'quantity_used': r[1], 'lot_id': r[3], 'lot_number': r[4], 'material_id': r[5]}) # convert materials to a format for display in the edit batch page.
    
    if not batch:
        return render_template('error.html', # if batch not found, show error page.
            title="Batch Not Found",
            message="The batch you requested could not be found.",
            back_link=True, back_link_url="/manage-batches", back_link_label="Back to Manage Batches"
        ), 404
    
    if not batch_materials_rows:
        return render_template('error.html', # if batch not found, show error page.
            title="Batch Materials Not Found",
            message="The batch materials you requested could not be found.",
            back_link=True, back_link_url="/manage-batches", back_link_label="Back to Manage Batches"
        ), 404
    
    msg = request.args.get('msg', '') # get success message from URL parameters, if any (e.g., after updating batch details)
    err = request.args.get('err', '') # get error message from URL parameters, if any (e.g., if updating batch details failed)

    return render_template("edit_batch.html", # show the edit batch form, with current batch details and any success/error messages.
        batch = batch,
        batch_materials = batch_materials,
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
        expiration_date = request.form.get('expiration_date', '').strip() or None
        planned_completion_date = request.form.get('planned_completion_date', '').strip() or None

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

    if expiration_date:
        try:
            datetime.strptime(expiration_date, '%Y-%m-%d')
        except ValueError:
            return render_template('error.html',
                title="Invalid Input",
                message="Invalid expiration date format. Use YYYY-MM-DD.",
                back_link=True, back_link_url=f"/edit-batch/{batch_id}", back_link_label="Go back to Edit Batch"
            ), 400

    #validate planned completion date
    
    if planned_completion_date:
        try:
            datetime.strptime(planned_completion_date, '%Y-%m-%d')
        except ValueError:
            return render_template('error.html',
                title="Invalid Input",
                message="Invalid planned completion date format. Use YYYY-MM-DD.",
                back_link=True, back_link_url=f"/edit-batch/{batch_id}", back_link_label="Go back to Edit Batch"
            ), 400
        
    new_quantities = {}
    lot_selections = {}
    if request.form.get('adjust_deductions') == '1':
        for key, value in request.form.items():
            if key.startswith('material_'):
                try:
                    material_id = int(key[len('material_'):])
                    new_quantities[material_id] = float(value)
                except (ValueError, TypeError):
                    pass

        # Parse lot selections for materials where quantity is increasing
        import json as _json
        raw_lot_selections = request.form.get('lot_selections_json', '')
        if raw_lot_selections:
            try:
                parsed = _json.loads(raw_lot_selections)
                lot_selections = {int(k): int(v) for k, v in parsed.items()}
            except (ValueError, TypeError, _json.JSONDecodeError):
                pass

        if new_quantities and not check_batch_materials_stock(batch_id, new_quantities, lot_selections or None):
            # CHANGED: was url_for(..., err=...) — moved to flash()
            flash('Could not update — insufficient stock for new material quantities', 'error')
            return redirect(url_for('edit_batch', batch_id=batch_id))

    result = update_batch(batch_id, product_name=product_name, quantity=quantity, notes=notes, expiration_date=expiration_date, planned_completion_date=planned_completion_date)

    if result:
        logging.info(f"Batch details updated: batch_id={batch_id}, product_name={product_name}, quantity={quantity}")
        log_action('batch_updated', f"batch_id={batch_id}, product_name={product_name}, quantity={quantity}")

        if new_quantities:
            adj_result = adjust_batch_material(batch_id, new_quantities, lot_selections or None)
            if adj_result:
                log_action('batch_materials_adjusted', f"batch_id={batch_id}, adjustments={new_quantities}")
                # CHANGED: was url_for(..., msg=...) — moved to flash()
                flash('Batch details and material deductions updated successfully', 'success')
                return redirect(url_for('edit_batch', batch_id=batch_id))
            else:
                flash('Batch details saved but failed to adjust material deductions — insufficient stock or material not found', 'error')
                return redirect(url_for('edit_batch', batch_id=batch_id))

        flash('Batch details updated successfully', 'success')
        return redirect(url_for('edit_batch', batch_id=batch_id))
    else:
        flash('Failed to update batch details', 'error')
        return redirect(url_for('edit_batch', batch_id=batch_id))


@app.route('/edit-batch/<int:batch_id>/change-status', methods=['POST']) 
@requires_auth
def change_batch_status(batch_id):
    """
    Change the status of a batch  
     
    This is a POST route that takes the new status from the form submission in the edit batch page, updates the batch status in the database, and redirects back to the edit batch page with a success or error message.
    """

    new_status = request.form.get('status') # Get the new status from the form submission (e.g., "ready", "shipped", etc.)

    
    if new_status == 'Planned': 
        planned_completion_date = request.form.get('planned_completion_date', '').strip() or None #get planned date of completion
        if not planned_completion_date:
            # CHANGED: was url_for(..., err=...) — moved to flash()
            flash('A planned completion date is required when setting status to Planned', 'error')
            return redirect(url_for('edit_batch', batch_id=batch_id))
        try:
            pcd = datetime.strptime(planned_completion_date, '%Y-%m-%d')
            if pcd.date() < datetime.now().date():
                flash('Planned completion date cannot be in the past', 'error')
                return redirect(url_for('edit_batch', batch_id=batch_id))
        except ValueError:
            flash('Invalid planned completion date format', 'error')
            return redirect(url_for('edit_batch', batch_id=batch_id))
        update_batch(batch_id, planned_completion_date=planned_completion_date)

    result = update_batch_status(batch_id, new_status)
    if result:
        logging.info(f"Batch status changed: batch_id={batch_id}, new_status={new_status}")
        log_action('batch_status_changed', f"batch_id={batch_id}, new_status={new_status}")
        # CHANGED: was url_for(..., msg=...) — moved to flash()
        flash(f'Batch status updated to {new_status}', 'success')
        return redirect(url_for('edit_batch', batch_id=batch_id))
    else:
        flash('Failed to update batch status', 'error')
        return redirect(url_for('edit_batch', batch_id=batch_id))
    

@app.route('/edit-batch/<int:batch_id>/delete', methods=['POST'])
@requires_auth
def delete_batch_route(batch_id):
    
    checked_ids = request.form.getlist('reallocate_material')  #getlist() only returns values for checked boxes, uncheck ones are excluded. 

    materials_to_reallocate = []
    for mid in checked_ids: # for each material that was check, get id by just taking value of checkbox, quantity by 
        #looking for form field with name qty_{material_id}, and material name by looking for form field with name matname_{material_id}. 
        materials_to_reallocate.append({
            'material_id': int(mid),
            'quantity_used': float(request.form.get(f'qty_{mid}', 0)),
            'material_name': request.form.get(f'matname_{mid}', '')
        })
    

    



    result = delete_batch(batch_id, materials_to_reallocate, reallocate=bool(materials_to_reallocate))
    if not result:
        return render_template('error.html',
            title="Delete Failed",
            message="Could not delete batch. The batch may not exist.",
        ), 500
    logging.info(f"Batch deleted: batch_id={batch_id}, reallocate={bool(materials_to_reallocate)}")
    log_action('batch_deleted', f"batch_id={batch_id}, reallocate={bool(materials_to_reallocate)}")
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

    # ADDED: read page number from URL (?page=N); default to page 1
    PER_PAGE = 50
    page = min(max(1, int(request.args.get('page', 1))), MAX_PAGE)  # CHANGED: capped at MAX_PAGE to prevent large-OFFSET DoS

    # CHANGED: get_all_recipes now returns (df, total). Pagination is at the recipe level
    #          (never splits a recipe across pages). total = total number of distinct recipes.
    df, total = get_all_recipes(page=page, per_page=PER_PAGE)

    if df.empty:
        return render_template("recipes.html",
            recipes=[], recipe_count=0,
            page=1, total_pages=1, total=0,
            back_link=True, back_link_url="/", back_link_label="Back to Home"
    )

    # Show recipe name and notes only on the first ingredient row of each recipe —
    # duplicate rows get blank values so the name doesn't repeat in the table.
    df_display = df.copy()
    duplicate_mask = df_display['recipe_product_name'].duplicated()
    df_display.loc[duplicate_mask, 'recipe_product_name'] = ''
    df_display.loc[duplicate_mask, 'notes'] = ''

    # CHANGED: recipe_count now comes from the total returned by the service (all recipes),
    #          not nunique() on the current page (which would undercount when paginated).
    recipe_count = total
    recipes = df_display.to_dict(orient='records')

    # ADDED: total_pages for pagination controls in the template
    total_pages = math.ceil(total / PER_PAGE) if total else 1

    return render_template("recipes.html",
        recipes=recipes,
        recipe_count=recipe_count,
        page=page,
        total_pages=total_pages,
        total=total,
        back_link=True, back_link_url="/", back_link_label="Back to Home"
    )



# NEW: Excel export route for recipes
@app.route('/export/recipes-excel')
@requires_auth
def export_recipes_excel():
    """
    Export all recipes and their materials to Excel file
 

    """
    # CHANGED: get_all_recipes now returns (df, total). page=None skips LIMIT/OFFSET
    #          so the export still contains every recipe row, not just one page.
    df, _ = get_all_recipes(page=None)

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
            logging.error(f"add_recipe_route: {e}", exc_info=True)
            return render_template('error.html',
                title="Error Adding Recipe",
                message="An unexpected error occurred. Please try again.",
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
    # ADDED: pagination for manage-recipes page
    PER_PAGE = 50
    page = min(max(1, int(request.args.get('page', 1))), MAX_PAGE)  # CHANGED: capped at MAX_PAGE to prevent large-OFFSET DoS

    # CHANGED: get_all_recipes_with_id now returns (df, total) tuple
    df, total = get_all_recipes_with_id(page=page, per_page=PER_PAGE)

    recipes = df.to_dict(orient='records') if (df is not None and not df.empty) else []
    # ADDED: total_pages for pagination controls in template
    total_pages = math.ceil(total / PER_PAGE) if total else 1

    return render_template("manage_recipes.html",
        recipes=recipes,
        count=len(recipes),
        page=page,
        total_pages=total_pages,
        total=total,
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
        # CHANGED: was url_for(..., msg=...) — moved to flash()
        flash('Recipe details updated successfully', 'success')
        return redirect(url_for('edit_recipe', recipe_id=recipe_id))
    else:
        flash('Failed to update recipe details', 'error')
        return redirect(url_for('edit_recipe', recipe_id=recipe_id))



@app.route('/edit-recipe/<int:recipe_id>/delete', methods=['POST'])
@requires_auth
def delete_recipe_route(recipe_id):
    """
    simply deletes the recipe from database,
    POST route
    """
    
    result = delete_recipe_by_id(recipe_id)
    if not result:
        return render_template('error.html',
            title="Delete Failed",
            message="Could not delete recipe. Please try again.",
        ), 500
    logging.info(f"Recipe deleted: recipe_id={recipe_id}")
    log_action('recipe_deleted', f"recipe_id={recipe_id}")
    return redirect(url_for('manage_recipes'))





#==================
#LOT PAGES
#==================

@app.route('/manage-lots') # Page to view all lots with edit/delete options (view only)
@requires_auth
def manage_lots():
    """
    This is a page to view all lots with edit/delete options.
    simple GET, just viewing, but with buttons. 
    """
    # ADDED: pagination for manage-lots page
    PER_PAGE = 50
    page = min(max(1, int(request.args.get('page', 1))), MAX_PAGE)  # CHANGED: capped at MAX_PAGE to prevent large-OFFSET DoS

    # CHANGED: get_all_lots now returns (df, total) tuple
    df, total = get_all_lots(page=page, per_page=PER_PAGE)

    lots = df.to_dict(orient='records') if (df is not None and not df.empty) else []
    # ADDED: total_pages for pagination controls in template
    total_pages = math.ceil(total / PER_PAGE) if total else 1

    return render_template("manage_lots.html",
        lots=lots,
        count=len(lots),
        page=page,
        total_pages=total_pages,
        total=total,
        back_link=True,
        back_link_url="/",
        back_link_label="Back to Home"
)





@app.route('/edit-lot/<int:lot_id>') # dynamic URL for editing a specific lot, identified by lot_id. (view only)
@requires_auth
def edit_lot(lot_id):
    """
    view lot details page, with form to edit lot details. 
    this is from manage lots page, 
    where each lot has an edit button that takes you to this page with the lot_id in the URL. 
    this page will show lot details, but no editing allowed for now since lot management is more complex and we want to avoid accidental stock changes. 

    GET page route
    """

    df = get_lot_by_id(lot_id) #get lot details for the lot being viewed

    
    
    if df is None or df.empty:
        return render_template('error.html',
            title="Lot Not Found",
            message="The lot you requested could not be found.",
            back_link=True, back_link_url="/manage-lots", back_link_label="Back to Manage Lots"
        ), 404
    
    lot = df.to_dict(orient='records') if (df is not None and not df.empty) else [] # convert to dictionary for HTML display, like usual.
    lot_batches = get_batches_for_lot(lot_id)

    return render_template("edit_lot.html",
        lot=lot,
        lot_batches=lot_batches,
        back_link=True,
        back_link_url="/manage-lots",
        back_link_label="Back to Manage Lots"
    )


@app.route('/edit-lot/<int:lot_id>/update', methods=['POST']) # dynamic URL for editing a specific lot, identified by lot_id. (view only)
@requires_auth
def update_lot_route(lot_id):
    """

    calls update_lot function. 
    POST route for processing edit lot submission.
    takes user requests: lot number, quantity (if not homemade mat), expiration date, location, supplier, cost per unit, 
    status. 

    """
    
    try:




        #see if quantity field needs to be removed
        lot_df = get_lot_by_id(lot_id)
        if lot_df is None or lot_df.empty:
            return render_template('error.html',
                title="Lot Not Found",
                message="The lot you are trying to update could not be found.",
                back_link=True, back_link_url=f"/edit-lot/{lot_id}", back_link_label="Go back to Edit Lot"
            ), 404
        
        


        lot_number_raw = request.form.get('lot_number')
        lot_number = lot_number_raw.strip() if lot_number_raw else None

        quantity_str = request.form.get('quantity', '').strip()
        quantity = float(quantity_str) if quantity_str else None

        expiration_date_raw = request.form.get('expiration_date')
        expiration_date = expiration_date_raw.strip() if expiration_date_raw else None

        location_raw = request.form.get('location')
        location = location_raw.strip() if location_raw else None

        supplier_raw = request.form.get('supplier')
        supplier = supplier_raw.strip() if supplier_raw else None


        cost_per_unit_str = request.form.get('cost_per_unit', '').strip()
        cost_per_unit = float(cost_per_unit_str) if cost_per_unit_str else None

        
        if lot_df['is_housemade'].iloc[0]: # if this is a housemade material,
            quantity = None
        
        #validate float inputs
        if quantity is not None and quantity <= 0:
            return render_template('error.html',
                title="Invalid Input",
                message="Quantity must be greater than zero.",
                back_link=True, back_link_url=f"/edit-lot/{lot_id}", back_link_label="Go back to Edit Lot"
            ), 400
        
        if cost_per_unit is not None and cost_per_unit < 0:
            return render_template('error.html',
                title="Invalid Input",
                message="Cost per unit cannot be negative.",
                back_link=True, back_link_url=f"/edit-lot/{lot_id}", back_link_label="Go back to Edit Lot"
            ), 400
        
        #validate date input
        if expiration_date:
            try:
                datetime.strptime(expiration_date, '%Y-%m-%d')
            except ValueError:
                return render_template('error.html',
                    title="Invalid Input",
                    message="Invalid expiration date format. Use YYYY-MM-DD.",
                    back_link=True, back_link_url=f"/edit-lot/{lot_id}", back_link_label="Go back to Edit Lot"
                ), 400
            
        result = update_lot(lot_id, lot_number=lot_number, quantity=quantity, expiration_date=expiration_date, location=location, cost_per_unit=cost_per_unit, supplier=supplier)

        
        


        if result:
            logging.info(f"Lot updated: lot_id={lot_id}, lot_number={lot_number}, quantity={quantity}")
            log_action('lot_updated', f"lot_id={lot_id}, lot_number={lot_number}, quantity={quantity}")
            # CHANGED: was url_for(..., msg=...) — moved to flash()
            flash('Lot details updated successfully', 'success')
            return redirect(url_for('edit_lot', lot_id=lot_id))
        else:
            flash('Failed to update lot details', 'error')
            return redirect(url_for('edit_lot', lot_id=lot_id))


    
    except ValueError as e:
            logging.error(f"update_lot_route: {e}", exc_info=True)
            return render_template('error.html',
                title="Invalid Input",
                message="Please ensure all fields are filled out correctly.",
                back_link=True, back_link_url=f"/edit-lot/{lot_id}", back_link_label="Go back to Edit Lot"
            ), 400
        

        
    
    




@app.route('/edit-lot/<int:lot_id>/delete', methods=['POST'])
@requires_auth
def delete_lot_route(lot_id):
    """
    POST route to permanently delete a lot.
    """
    lot_df = get_lot_by_id(lot_id)
    if lot_df is None or lot_df.empty:
        return render_template('error.html',
            title="Lot Not Found",
            message="The lot you are trying to delete could not be found.",
            back_link=True, back_link_url="/manage-lots", back_link_label="Back to Manage Lots"
        ), 404

    lot_number = lot_df['lot_number'].iloc[0]
    result = delete_lot(lot_id)

    if result:
        log_action('lot_deleted', f"lot_id={lot_id}, lot_number={lot_number}")
        # CHANGED: was url_for(..., msg=...) — moved to flash()
        flash('Lot deleted successfully', 'success')
        return redirect(url_for('manage_lots'))
    else:
        flash('Failed to delete lot', 'error')
        return redirect(url_for('edit_lot', lot_id=lot_id))


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
