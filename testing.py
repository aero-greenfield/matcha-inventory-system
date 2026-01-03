
"""

if __name__ == "__main__":
    
    if os.path.exists("data/inventory.db"):
        os.remove("data/inventory.db")
    
    
    
    # Step 1: Create database
    create_database()

    # Step 2: Add raw materials
    add_raw_material("Matcha", "Powder", 1000, "g", 100, 0.05)
    add_raw_material("Milk Powder", "Powder", 5000, "g", 200, 0.02)
    add_raw_material("Sugar", "Powder", 2000, "g", 100, 0.01)

    # Step 3: Add a recipe
    materials = [
        {"material_name": "Matcha", "quantity_needed": 2},   # per unit
        {"material_name": "Milk Powder", "quantity_needed": 30},
        {"material_name": "Sugar", "quantity_needed": 5}
    ]
    add_recipe("Matcha Latte", materials, notes="Classic sweetened")

    # Step 4: Produce a batch
    print("\n--- Produce a batch ---")
    batch_id = add_to_batches("Matcha Latte", 10, notes="Morning batch", batch_id = 67)
    print(f"Batch created: {batch_id}")

    # Step 5: Check tables
    print("\n--- Raw Materials ---")
    print(get_all_materials())

    print("\n--- Ready to Ship ---")
    print(get_batches())

    print("\n--- Recipe ---")
    print(get_recipe("Matcha Latte"))


    #more testing:
    #increase raw_material:
    increase_raw_material('Matcha', 42067, )

    print("\n--- Raw Materials  2 ---")
    print(get_all_materials())


    """