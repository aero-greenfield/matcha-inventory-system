"""
Matcha Inventory Management System - CLI Interface
Main entry point for user interaction
"""

import sys
import os
from datetime import datetime

# Import all functions from your existing inventory_app.py
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

# Import utility functions
from helper_functions import (
    get_float_input,
    get_int_input,
    get_yes_no_input,
    get_optional_batch_id,
    display_dataframe,
    export_to_csv,
    backup_database,
    auto_backup_on_startup,
    print_header,
    print_success,
    print_error,
    print_warning,
    pause
)



# MAIN MENU
"""
main menu functions for Matcha Inventory CLI
handles user interaction, displays menus, and calls inventory_app functions

"""

def clear_screen():
    """
    Clears terminal screen for clean display.
    
    Why: Makes menus easier to read (not cluttered with old output)
    Works on both Windows (cls) and Mac/Linux (clear)
    """
    os.system('cls' if os.name == 'nt' else 'clear')




def display_main_menu():
    """
    Shows main menu options.
    
    Design decision: 
    Operations people use most are at top (1-3)
     Admin functions at bottom (4-6)
    """
    clear_screen()
    print("\n" + "="*60)
    print("   MATCHA INVENTORY MANAGEMENT SYSTEM")
    print("="*60)
    print("\n INVENTORY & MATERIALS")
    print("  1. View Current Inventory")
    print("  2. Add New Raw Material")
    print("  3. Restock Material")
    print("  4. Check Low Stock Alerts")
    
    print("\n BATCH MANAGEMENT")
    print("  5. Create New Batch")
    print("  6. View Ready Batches")
    print("  7. Mark Batch as Shipped")
    print("  8. Delete Batch")
    
    print("\n RECIPES")
    print("  9. View Recipe")
    print("  10. Add New Recipe")
    print("  11. Modify Recipe")
    print("  12. Delete Recipe")
    
    print("\n📊 REPORTS & EXPORTS")
    print("  13. Export Inventory to CSV")
    print("  14. Export Low Stock Report")
    
    print("\n🔧 SYSTEM")
    print("  15. Create Manual Backup")
    print("  0. Exit")
    
    print("\n" + "="*60)


def main_menu():
    """
    Main menu loop CRITICAL FUNCTION
    
    Architecture pattern: Dictionary dispatch for menu actions.
    
    
    """
    
    # Map menu choices to functions
    menu_actions = {
        '1': view_inventory,
        '2': add_material,
        '3': restock_material,
        '4': check_low_stock,
        '5': create_batch,
        '6': view_ready_batches,
        '7': ship_batch,
        '8': remove_batch,
        '9': view_recipe_details,
        '10': add_new_recipe,
        '11': modify_recipe,
        '12': remove_recipe,
        '13': export_inventory,
        '14': export_low_stock,
        '15': manual_backup,
        '0': exit_program
    }
    # display menu and handle user input in loop
    while True:
        display_main_menu()
        choice = input("Select an option: ").strip()
        
        # Look up function in dictionary and call it
        action = menu_actions.get(choice)
        
        if action:
            action()  # Execute the selected function
        else:
            print_error("Invalid choice. Please select a number from the menu.")
            pause()# wait for user to read message 






# INVENTORY FUNCTIONS


def view_inventory():
    """
    Displays all raw materials in inventory.
    
    Uses: get_all_materials() from inventory_app.py
    Shows: Material name, category, stock, unit, reorder level, cost, supplier
    """
    print_header("CURRENT INVENTORY")# call header function
    
    df = get_all_materials() # get all materials from inventory_app
    
    if df.empty:
        print_warning("No materials in inventory. Add materials using option 2.")
    else:
        # Clean up column names for better readability
        df = df.rename(columns={
            'name': 'Material Name',
            'category': 'Category',
            'stock_level': 'Stock',
            'unit': 'Unit',
            'reorder_level': 'Reorder Level',
            'cost_per_unit': 'Cost/Unit',
            'supplier': 'Supplier'
        })
        display_dataframe(df, empty_message="No materials found.") #call display function
    

    
    pause()# wait for user to read output


def add_material():
    """
    Adds new raw material to inventory.
    
    Walkthrough of data collection:
    1. Ask for all required fields
    2. Validate numeric inputs 
    3. Call add_raw_material()
    4. Confirm success to user
    

    """
    print_header("ADD NEW RAW MATERIAL")#call header function
    
    print("Please enter material details:\n") # prompt user for details
    
    name = input("Material Name: ").strip() # input material name
    if not name:
        print_error("Material name cannot be empty.")
        pause()
        return
    
    category = input("Category (e.g., Powder, Liquid, Packaging): ").strip() # input category
    
    stock_level = get_float_input("Initial Stock Level: ", min_val=0)# get initial stock level, calling helper function
    
    unit = input("Unit of Measurement (e.g., kg, L, units): ").strip()# get unit of measurement
    
    reorder_level = get_float_input("Reorder Level (alert threshold): ", min_val=0)# reorder level input, also from helper function
    
    cost_per_unit = get_float_input("Cost per Unit: ", min_val=0)# ^^
    
    supplier = input("Supplier (optional, press Enter to skip): ").strip()
    if supplier:
        supplier = supplier
    else:
        supplier = None

    # Call the function from inventory_app
    result = add_raw_material(
        name=name,
        category=category,
        stock_level=stock_level,
        unit=unit,
        reorder_level=reorder_level,
        cost_per_unit=cost_per_unit,
        supplier=supplier
    )
    
    if result:
        print_success(f"Material '{name}' added successfully!")
    else:
        print_error("Failed to add material. Check console for details.")
    
    pause()

# CONTINUE HERE ***********************************************

def restock_material():
    """
    Increases stock level of existing material.
    
    Business logic: Common operation (receiving shipments)
    Should be easy and fast to use
    """
    print_header("RESTOCK MATERIAL")
    
    material_name = input("Enter material name to restock: ").strip()
    
    if not material_name:
        print_error("Material name cannot be empty.")
        pause()
        return
    
    # Check if material exists first
    material_info = get_raw_material(material_name)
    
    if not material_info:
        print_error(f"Material '{material_name}' not found in inventory.")
        pause()
        return
    
    # Show current stock before asking for increase
    _, name, current_stock, reorder_level, cost = material_info
    print(f"\n📊 Current stock: {current_stock} units")
    print(f"   Reorder level: {reorder_level} units\n")
    
    amount_to_add = get_float_input("Enter amount to add: ", min_val=0, allow_zero=False)
    
    # Call inventory_app function
    new_stock = increase_raw_material(material_name, amount_to_add)
    
    if new_stock is not None:
        print_success(f"Stock updated! New level: {new_stock} units")
    else:
        print_error("Failed to update stock.")
    
    pause()


def check_low_stock():
    """
    Shows materials below reorder level.
    
    Critical for operations: Prevents stockouts
    Portfolio value: Shows you understand business process automation
    """
    print_header("LOW STOCK ALERTS")
    
    df = get_low_stock_materials()
    
    if df.empty:
        print_success("All materials are adequately stocked!")
    else:
        print(f"⚠️  {len(df)} material(s) need reordering:\n")
        
        # Clean up column names
        df = df.rename(columns={
            'name': 'Material',
            'category': 'Category',
            'stock_level': 'Current Stock',
            'reorder_level': 'Reorder Level',
            'unit': 'Unit'
        })
        
        display_dataframe(df)
    
    pause()


# ========================
# BATCH MANAGEMENT
# ========================

def create_batch():
    """
    Creates new production batch.
    
    Complex workflow:
    1. Ask for product name
    2. Verify recipe exists
    3. Show recipe and cost calculation
    4. Ask for quantity
    5. Check material availability
    6. Optionally set custom batch ID
    7. Create batch (auto-deducts materials)
    8. Create backup before operation (safety!)
    
    This is the most critical function - handles inventory transactions
    """
    print_header("CREATE NEW BATCH")
    
    product_name = input("Enter product name: ").strip()
    
    if not product_name:
        print_error("Product name cannot be empty.")
        pause()
        return
    
    # Check if recipe exists
    recipe_df = get_recipe(product_name)
    
    if recipe_df is None or recipe_df.empty:
        print_error(f"No recipe found for '{product_name}'.")
        print("Please create a recipe first (option 10).")
        pause()
        return
    
    # Show recipe to user
    print(f"\n📋 Recipe for {product_name}:")
    display_dataframe(
        recipe_df[['material_name', 'quantity_needed']],
        empty_message="No materials in recipe."
    )
    
    quantity = get_int_input("\nEnter batch quantity to produce: ", min_val=1, allow_zero=False)
    
    # Show what materials will be consumed
    print(f"\n📊 This batch will consume:")
    for _, row in recipe_df.iterrows():
        total_needed = row['quantity_needed'] * quantity
        print(f"   • {row['material_name']}: {total_needed} units")
    
    # Confirm with user
    if not get_yes_no_input("\nProceed with batch creation?"):
        print("❌ Batch creation cancelled.")
        pause()
        return
    
    # Get batch ID (optional manual or auto-generate)
    batch_id = get_optional_batch_id()
    
    # Create backup before modifying database
    print("\n📦 Creating safety backup before batch creation...")
    backup_database(reason="before_batch")
    
    # Create the batch
    result = add_to_batches(
        product_name=product_name,
        quantity=quantity,
        batch_id=batch_id,
        deduct_resources=True
    )
    
    if result:
        print_success(f"Batch created successfully! Batch ID: {result}")
    else:
        print_error("Batch creation failed. Database rolled back to previous state.")
    
    pause()


def view_ready_batches():
    """Shows all batches with status 'Ready'."""
    print_header("READY TO SHIP BATCHES")
    
    df = get_batches()
    
    if df.empty:
        print_warning("No batches ready for shipment.")
    else:
        df = df.rename(columns={
            'batch_id': 'Batch ID',
            'product_name': 'Product',
            'quantity': 'Quantity',
            'date_completed': 'Completed',
            'status': 'Status',
            'notes': 'Notes'
        })
        display_dataframe(df)
    
    pause()


def ship_batch():
    """
    Marks batch as shipped.
    
    Records shipment date in database.
    Portfolio: Shows you understand status workflows and audit trails
    """
    print_header("MARK BATCH AS SHIPPED")
    
    # Show available batches first
    df = get_batches()
    
    if df.empty:
        print_warning("No batches available to ship.")
        pause()
        return
    
    print("Available batches:\n")
    display_dataframe(df[['batch_id', 'product_name', 'quantity']])
    
    batch_id = get_int_input("\nEnter Batch ID to mark as shipped: ", min_val=1)
    
    # Confirm action
    if not get_yes_no_input(f"Mark Batch {batch_id} as shipped?"):
        print("❌ Operation cancelled.")
        pause()
        return
    
    success = mark_as_shipped(batch_id)
    
    if success:
        print_success(f"Batch {batch_id} marked as shipped!")
    else:
        print_error("Failed to update batch status.")
    
    pause()


def remove_batch():
    """
    Deletes batch with optional material reallocation.
    
    Critical decision: Should materials go back to inventory?
    - Yes if batch was defective/cancelled
    - No if batch was already used/consumed
    
    Creates backup before deletion (safety!)
    """
    print_header("DELETE BATCH")
    
    # Show available batches
    df = get_batches()
    
    if df.empty:
        print_warning("No batches available to delete.")
        pause()
        return
    
    print("Available batches:\n")
    display_dataframe(df[['batch_id', 'product_name', 'quantity', 'status']])
    
    batch_id = get_int_input("\nEnter Batch ID to delete: ", min_val=1)
    
    # Ask about material reallocation
    print("\n🔄 Material Reallocation:")
    print("  • Choose 'Yes' if batch was defective (materials go back to inventory)")
    print("  • Choose 'No' if batch was consumed/damaged (materials are lost)")
    
    reallocate = get_yes_no_input("\nReallocate materials back to inventory?")
    
    # Final confirmation
    action = "delete and reallocate" if reallocate else "delete permanently"
    if not get_yes_no_input(f"\nConfirm: {action} Batch {batch_id}?"):
        print("❌ Operation cancelled.")
        pause()
        return
    
    # Backup before deletion
    print("\n📦 Creating safety backup before deletion...")
    backup_database(reason="before_delete")
    
    # Delete the batch
    result = delete_batch(batch_id, reallocate=reallocate)
    
    if result is not None:
        print_success(f"Batch {batch_id} deleted successfully!")
    else:
        print_error("Failed to delete batch.")
    
    pause()


# ========================
# RECIPE MANAGEMENT
# ========================

def view_recipe_details():
    """Shows detailed recipe breakdown."""
    print_header("VIEW RECIPE DETAILS")
    
    product_name = input("Enter product name: ").strip()
    
    if not product_name:
        print_error("Product name cannot be empty.")
        pause()
        return
    
    recipe_df = get_recipe(product_name)
    
    if recipe_df is None or recipe_df.empty:
        print_error(f"No recipe found for '{product_name}'.")
        pause()
        return
    
    print(f"\n📋 Recipe: {product_name}")
    
    if 'notes' in recipe_df.columns and not recipe_df['notes'].isna().all():
        notes = recipe_df['notes'].iloc[0]
        if notes:
            print(f"   Notes: {notes}")
    
    print("\nIngredients:")
    display_dataframe(
        recipe_df[['material_name', 'quantity_needed']],
        empty_message="No materials in recipe."
    )
    
    pause()


def add_new_recipe():
    """
    Adds new recipe to database.
    
    User-friendly loop: Add materials one at a time
    Portfolio: Shows you can design intuitive data entry workflows
    """
    print_header("ADD NEW RECIPE")
    
    product_name = input("Product Name: ").strip()
    
    if not product_name:
        print_error("Product name cannot be empty.")
        pause()
        return
    
    # Check if recipe already exists
    existing_recipe = get_recipe(product_name)
    if existing_recipe is not None and not existing_recipe.empty:
        print_error(f"Recipe for '{product_name}' already exists.")
        print("Use option 11 to modify it instead.")
        pause()
        return
    
    notes = input("Recipe Notes (optional, press Enter to skip): ").strip()
    notes = notes if notes else None
    
    # Collect materials in a loop
    materials = []
    print("\n📝 Add materials to recipe (type 'done' when finished):\n")
    
    while True:
        material_name = input("  Material name (or 'done'): ").strip()
        
        if material_name.lower() == 'done':
            if len(materials) == 0:
                print_error("Recipe must have at least one material.")
                continue
            break
        
        if not material_name:
            print("  ⚠️  Material name cannot be empty.")
            continue
        
        # Check if material exists in inventory
        material_info = get_raw_material(material_name)
        if not material_info:
            print(f"  ⚠️  Warning: '{material_name}' not in inventory yet.")
            if not get_yes_no_input("  Add it anyway?"):
                continue
        
        quantity_needed = get_float_input("  Quantity needed: ", min_val=0, allow_zero=False)
        
        materials.append({
            'material_name': material_name,
            'quantity_needed': quantity_needed
        })
        
        print(f"  ✅ Added: {material_name} ({quantity_needed} units)\n")
    
    # Confirm before saving
    print(f"\n📋 Recipe Summary for '{product_name}':")
    for mat in materials:
        print(f"   • {mat['material_name']}: {mat['quantity_needed']} units")
    
    if not get_yes_no_input("\nSave this recipe?"):
        print("❌ Recipe not saved.")
        pause()
        return
    
    # Save recipe
    result = add_recipe(product_name, materials, notes)
    
    if result:
        print_success(f"Recipe for '{product_name}' created successfully!")
    else:
        print_error("Failed to create recipe.")
    
    pause()


def modify_recipe():
    """
    Modifies existing recipe.
    
    Design: Complete replacement (not incremental edit)
    Why: Simpler for Phase 1, clearer for users
    """
    print_header("MODIFY RECIPE")
    
    product_name = input("Enter product name to modify: ").strip()
    
    if not product_name:
        print_error("Product name cannot be empty.")
        pause()
        return
    
    # Check if recipe exists
    existing_recipe = get_recipe(product_name)
    if existing_recipe is None or existing_recipe.empty:
        print_error(f"No recipe found for '{product_name}'.")
        pause()
        return
    
    # Show current recipe
    print(f"\n📋 Current Recipe for '{product_name}':")
    display_dataframe(
        existing_recipe[['material_name', 'quantity_needed']],
        empty_message="No materials."
    )
    
    if not get_yes_no_input("\nProceed with modifying this recipe?"):
        print("❌ Modification cancelled.")
        pause()
        return
    
    # Backup before modification
    backup_database(reason="before_recipe_change")
    
    notes = input("\nNew Recipe Notes (press Enter to keep current): ").strip()
    notes = notes if notes else None
    
    # Collect new materials
    materials = []
    print("\n📝 Enter new materials (type 'done' when finished):\n")
    
    while True:
        material_name = input("  Material name (or 'done'): ").strip()
        
        if material_name.lower() == 'done':
            if len(materials) == 0:
                print_error("Recipe must have at least one material.")
                continue
            break
        
        if not material_name:
            continue
        
        quantity_needed = get_float_input("  Quantity needed: ", min_val=0, allow_zero=False)
        
        materials.append({
            'material_name': material_name,
            'quantity_needed': quantity_needed
        })
        
        print(f"  ✅ Added: {material_name}\n")
    
    # Save changes
    result = change_recipe(product_name, materials, notes)
    
    if result:
        print_success(f"Recipe for '{product_name}' updated successfully!")
    else:
        print_error("Failed to update recipe.")
    
    pause()


def remove_recipe():
    """
    Deletes recipe from database.
    
    Safety: Shows what will be deleted before confirming
    Creates backup before deletion
    """
    print_header("DELETE RECIPE")
    
    product_name = input("Enter product name to delete: ").strip()
    
    if not product_name:
        print_error("Product name cannot be empty.")
        pause()
        return
    
    # Check if recipe exists and show it
    recipe_df = get_recipe(product_name)
    
    if recipe_df is None or recipe_df.empty:
        print_error(f"No recipe found for '{product_name}'.")
        pause()
        return
    
    print(f"\n📋 Recipe to be deleted: '{product_name}'")
    display_dataframe(
        recipe_df[['material_name', 'quantity_needed']],
        empty_message="No materials."
    )
    
    # Double confirmation for destructive action
    if not get_yes_no_input(f"\nAre you sure you want to delete '{product_name}' recipe?"):
        print("❌ Deletion cancelled.")
        pause()
        return
    
    # Backup before deletion
    backup_database(reason="before_recipe_delete")
    
    # Delete recipe
    delete_recipe(product_name)
    
    print_success(f"Recipe '{product_name}' deleted successfully!")
    pause()


# ========================
# REPORTS & EXPORTS
# ========================

def export_inventory():
    """
    Exports current inventory to CSV.
    
    Portfolio value: Shows ETL skills (Extract from DB, Load to CSV)
    Practical value: Boss can open in Excel for analysis
    """
    print_header("EXPORT INVENTORY TO CSV")
    
    df = get_all_materials()
    
    if df.empty:
        print_warning("No inventory data to export.")
        pause()
        return
    
    filepath = export_to_csv(df, "inventory")
    
    print_success(f"Inventory exported successfully!")
    print(f"📁 File location: {filepath}")
    print(f"📊 Total materials exported: {len(df)}")
    
    pause()


def export_low_stock():
    """
    Exports low-stock alert report to CSV.
    
    Business value: Purchasing department can use this for ordering
    Portfolio: Shows you understand stakeholder needs
    """
    print_header("EXPORT LOW STOCK REPORT")
    
    df = get_low_stock_materials()
    
    if df.empty:
        print_success("No low-stock items to export!")
        pause()
        return
    
    filepath = export_to_csv(df, "low_stock_alert")
    
    print_success(f"Low stock report exported successfully!")
    print(f"📁 File location: {filepath}")
    print(f"⚠️  Items needing reorder: {len(df)}")
    
    pause()


# ========================
# SYSTEM FUNCTIONS
# ========================

def manual_backup():
    """
    Creates manual database backup.
    
    Why offer this: Gives users control over backups before major operations
    Example: Before training new employee, backup first
    """
    print_header("CREATE MANUAL BACKUP")
    
    reason = input("Backup reason (optional, for filename): ").strip()
    reason = reason if reason else "manual"
    
    backup_path = backup_database(reason=reason)
    
    if backup_path:
        print_success("Backup created successfully!")
        print(f"📁 Location: {backup_path}")
    else:
        print_error("Backup failed.")
    
    pause()


def exit_program():
    """Graceful exit with confirmation."""
    print("\n" + "="*60)
    print("  👋 Thank you for using Matcha Inventory System!")
    print("="*60 + "\n")
    sys.exit(0)


# ========================
# PROGRAM ENTRY POINT
# ========================

def main():
    """
    Program entry point.
    
    Startup sequence:
    1. Ensure database exists
    2. Check for recent backup (create if needed)
    3. Enter main menu loop
    
    Why this order: Database must exist before backup check
    """
    
    # Ensure database is initialized
    if not os.path.exists('data/inventory.db'):
        print("🔧 Database not found. Creating new database...")
        create_database()
        print("✅ Database created successfully!\n")
    
    # Auto-backup on startup (if >24 hours since last)
    auto_backup_on_startup()
    
    # Enter main menu loop
    main_menu()


if __name__ == "__main__":
    main()