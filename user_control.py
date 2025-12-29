# usercontrol.py
"""
User Control CLI for Matcha Inventory Management System
Dictionary-based controls for raw materials, recipes, and batches.
"""

import sys
from inventory_app import (
    create_database,
    add_raw_material,
    get_all_materials,
    get_low_stock_materials,
    increase_raw_material,
    decrease_raw_material,
    add_recipe,
    change_recipe,
    delete_recipe,
    get_recipe,
    add_to_batches,
    get_batches,
    mark_as_shipped,
    delete_batch
)

def input_float(prompt):
    return float(input(prompt))

def input_int(prompt):
    return int(input(prompt))

def raw_add_material():
    name = input("Material name: ")
    category = input("Category: ")
    stock_level = input_float("Initial stock level: ")
    unit = input("Unit (e.g., kg, L): ")
    reorder_level = input_float("Reorder level: ")
    cost_per_unit = input_float("Cost per unit: ")
    supplier = input("Supplier (optional): ") or None
    add_raw_material(name, category, stock_level, unit, reorder_level, cost_per_unit, supplier)

def raw_increase_stock():
    name = input("Material name to increase: ")
    amount = input_float("Amount to add: ")
    increase_raw_material(name, amount)

def raw_decrease_stock():
    name = input("Material name to decrease: ")
    amount = input_float("Amount to subtract: ")
    decrease_raw_material(name, amount)

def raw_show_all():
    print(get_all_materials())

def raw_show_low():
    print(get_low_stock_materials())

raw_materials_actions = {
    "1": raw_add_material,
    "2": raw_increase_stock,
    "3": raw_decrease_stock,
    "4": raw_show_all,
    "5": raw_show_low
}


def recipes_add():
    product_name = input("Product name: ")
    notes = input("Notes (optional): ") or None
    materials = []
    while True:
        mat_name = input("Material name (or 'done' to finish): ")
        if mat_name.lower() == "done":
            break
        qty = input_float("Quantity needed: ")
        materials.append({"material_name": mat_name, "quantity_needed": qty})
    add_recipe(product_name, materials, notes)

def recipes_change():
    product_name = input("Product name to change: ")
    notes = input("Notes (optional): ") or None
    materials = []
    while True:
        mat_name = input("Material name (or 'done' to finish): ")
        if mat_name.lower() == "done":
            break
        qty = input_float("Quantity needed: ")
        materials.append({"material_name": mat_name, "quantity_needed": qty})
    change_recipe(product_name, materials, notes)

def recipes_delete():
    product_name = input("Product name to delete: ")
    delete_recipe(product_name)

def recipes_view():
    product_name = input("Product name to view: ")
    df = get_recipe(product_name)
    if df is not None:
        print(df)

recipes_actions = {
    "1": recipes_add,
    "2": recipes_change,
    "3": recipes_delete,
    "4": recipes_view
}


def batches_add():
    product_name = input("Product name: ")
    quantity = input_int("Quantity: ")
    notes = input("Notes (optional): ") or None
    deduct = input("Deduct resources? (y/n): ").lower() == "y"
    add_to_batches(product_name, quantity, notes=notes, deduct_resources=deduct)

def batches_view():
    print(get_batches())

def batches_ship():
    batch_id = input_int("Batch ID to mark as shipped: ")
    mark_as_shipped(batch_id)

def batches_delete():
    batch_id = input_int("Batch ID to delete: ")
    reallocate = input("Reallocate materials back? (y/n): ").lower() == "y"
    delete_batch(batch_id, reallocate=reallocate)

batches_actions = {
    "1": batches_add,
    "2": batches_view,
    "3": batches_ship,
    "4": batches_delete
}


def run_menu(actions_dict, prompt="Select an option: "):
    while True:
        for key, func in actions_dict.items():
            print(f"{key}. {func.__name__.replace('_', ' ').title()}")
        print("0. Back")
        choice = input(prompt)
        if choice == "0":
            break
        action = actions_dict.get(choice)
        if action:
            action()
        else:
            print("Invalid choice. Try again.")


def main():
    create_database()
    main_menu = {
        "1": ("Raw Materials", raw_materials_actions),
        "2": ("Recipes", recipes_actions),
        "3": ("Batches", batches_actions),
        "4": ("Exit", None)
    }

    while True:
        print("\n===== Matcha Inventory User Control =====")
        for key, (label, _) in main_menu.items():
            print(f"{key}. {label}")
        choice = input("Select an option: ")
        if choice == "4":
            print("Exiting User Control. Goodbye!")
            sys.exit()
        if choice in main_menu:
            _, actions = main_menu[choice]
            run_menu(actions)
        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()
