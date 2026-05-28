# ADDED: these imports were all at the top of inventory_app.py — only the ones
#        actually used by the functions in this file are kept here.
from database import get_db_connection
import pandas as pd
import logging
from datetime import datetime

# ADDED: get_raw_material lives in services.materials. recipes.py calls it inside
#        add_recipe, change_recipe, update_recipe, and check_negative_stock to
#        validate that a material exists before inserting into recipe_materials.
# REMOVED: get_raw_material import — add_recipe/change_recipe/update_recipe now batch-fetch
#          all material names in one query instead of calling this per ingredient
# REMOVED: get_material_stock_from_lots import — check_negative_stock now uses an inline
#          batch GROUP BY query instead of calling this per ingredient


# ========================
# RECIPE FUNCTIONS
# ========================


def get_recipe_names(q=""):
    # ADDED: lightweight name-search for the /api/recipes autocomplete endpoint.
    #        Returns up to 50 distinct recipe names matching the search string.
    #        Filtering happens in SQL, not by fetching the full recipes table into Python.
    db = get_db_connection()
    cursor = db.cursor()
    try:
        db.execute(cursor,
            "SELECT DISTINCT product_name FROM recipes WHERE LOWER(product_name) LIKE LOWER(%s) ORDER BY product_name LIMIT 50",
            (f"%{q}%",))
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logging.error(f"get_recipe_names: {e}")
        return []
    finally:
        db.close()


def get_recipe(product_name):
    """
    Gets recipe from recipes, which refrences recipe materials

    """

    db = get_db_connection()
    cursor = db.cursor()

    try:

        db.execute(cursor,"""
        SELECT recipe_id
        FROM recipes
        WHERE LOWER(product_name) = LOWER(%s)
                       """,(product_name,))
        row = cursor.fetchone() # get recipe_id from product name

        if not row:
            print(f"{product_name} not found in recipes")
            return None
        recipe_id = row[0]

        query = ("""
        SELECT r.product_name,
        r.notes,
        rm.material_id,
        raw.name AS material_name,
        rm.quantity_needed
        FROM recipes r
        JOIN recipe_materials rm ON r.recipe_id = rm.recipe_id
        JOIN raw_materials raw ON rm.material_id = raw.material_id
        WHERE r.recipe_id = %s
        ORDER BY rm.material_name ASC
        """)

        db.execute(cursor, query, (recipe_id,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(rows, columns=columns)

        return df




    except Exception as e:
        logging.error(f"Error: {e} \ngetting recipe:{product_name}.")
        return None

    finally:
        db.close()


def check_negative_stock(product_name, quantity):
    """
    Returns a list of dicts for materials that would go negative if this batch was created.
    Each dict has: material_name, current_stock, required_amount, resulting_stock.
    Returns [] if all materials are sufficient, recipe is missing, or any lookup fails.
    """
    recipe_df = get_recipe(product_name)
    if recipe_df is None or recipe_df.empty:
        return []

    # ISSUE: the original loop called get_material_stock_from_lots(material_id) once per
    #        ingredient row. Each call opened its own DB connection and ran SELECT SUM(...).
    #        A 10-ingredient recipe = 11 total connections and 11 round-trips.
    # FIX: collect all material_ids, fetch their stock totals in one GROUP BY query,
    #      build a dict, then loop the DataFrame with no DB calls inside.

    # ADDED: gather all material ids so we can batch-fetch stock in one query
    material_ids = recipe_df['material_id'].tolist()
    placeholders = ', '.join(['%s'] * len(material_ids))  # one %s per id; DatabaseConnection.execute converts to ? for SQLite

    db = get_db_connection()
    cursor = db.cursor()
    try:
        date_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # ADDED: single GROUP BY query replacing N per-material SUM queries
        db.execute(cursor, f"""
            SELECT material_id, COALESCE(SUM(quantity), 0)
            FROM raw_material_lots
            WHERE material_id IN ({placeholders})
              AND status = 'active'
              AND (expiration_date IS NULL OR expiration_date > %s)
            GROUP BY material_id
        """, (*material_ids, date_now))
        stock_map = {row[0]: row[1] for row in cursor.fetchall()}  # ADDED: {material_id: stock}
    except Exception as e:
        import logging as _log
        _log.error(f"check_negative_stock: batch stock query failed: {e}")
        return []
    finally:
        db.close()

    negative = []
    for _, row in recipe_df.iterrows():
        material_name = row['material_name']
        material_id = row['material_id']
        required_amount = row['quantity_needed'] * quantity

        # REMOVED: get_material_stock_from_lots(material_id) — opened a new connection each iteration
        # current_stock = get_material_stock_from_lots(material_id)

        # ADDED: dict lookup — no DB call
        current_stock = stock_map.get(material_id, 0.0)
        if current_stock < required_amount:
            negative.append({
                'material_name': material_name,
                'current_stock': current_stock,
                'required_amount': required_amount,
                'resulting_stock': current_stock - required_amount,
            })
    return negative


def get_all_recipes(page=None, per_page=50):
    """
    Returns all recipes and their materials as a DataFrame.

    Columns returned:
    - recipe_product_name: Name of the recipe/product
    - notes: Optional notes about the recipe
    - material_name: Name of the material/ingredient
    - quantity: Amount of material needed per batch
    - unit: Unit of measurement (from raw_materials table)

    # ADDED: page/per_page pagination parameters. Pagination is at the RECIPE level, not the
    #        ingredient-row level, so a recipe is never split across page boundaries.
    # page=None → full table, no LIMIT (used by export routes); returns (df, None)
    # page=int  → recipes N through N+per_page and all their ingredients; returns (df, total_recipe_count)
    #
    # CHANGED: was pd.read_sql_query(query, db.conn) — converted to cursor approach so the
    #          %s→? wrapper handles both SQLite and PostgreSQL consistently.
    """
    db = get_db_connection()
    cursor = db.cursor()
    columns = ['recipe_product_name', 'notes', 'material_name', 'quantity', 'unit']

    try:
        full_query = """
        SELECT r.product_name AS recipe_product_name, r.notes,
               raw.name AS material_name, rm.quantity_needed AS quantity, raw.unit
        FROM recipes r
        JOIN recipe_materials rm ON r.recipe_id = rm.recipe_id
        JOIN raw_materials raw ON rm.material_id = raw.material_id
        ORDER BY r.product_name ASC, raw.name ASC
        """
        # Note: unit comes from raw_materials (raw.unit), NOT recipe_materials

        if page is None:
            # ADDED: page=None → full table without LIMIT (for exports)
            db.execute(cursor, full_query)
            result = cursor.fetchall()
            return (pd.DataFrame(result, columns=columns), None)

        # ADDED: total distinct recipe count for pagination metadata
        db.execute(cursor, "SELECT COUNT(*) FROM recipes")
        total = cursor.fetchone()[0]

        # ADDED: paginate at the recipe level using a subquery so no recipe is split across pages.
        #        Inner SELECT gets the recipe_ids for this page; outer JOIN fetches all their ingredients.
        paginated_query = """
        SELECT r.product_name AS recipe_product_name, r.notes,
               raw.name AS material_name, rm.quantity_needed AS quantity, raw.unit
        FROM recipes r
        JOIN recipe_materials rm ON r.recipe_id = rm.recipe_id
        JOIN raw_materials raw ON rm.material_id = raw.material_id
        WHERE r.recipe_id IN (
            SELECT recipe_id FROM recipes ORDER BY product_name ASC LIMIT %s OFFSET %s
        )
        ORDER BY r.product_name ASC, raw.name ASC
        """
        db.execute(cursor, paginated_query, (per_page, (page - 1) * per_page))
        result = cursor.fetchall()
        return (pd.DataFrame(result, columns=columns), total)

    except Exception as e:
        logging.error(f"Error getting all recipes: {e}")
        return (pd.DataFrame(), 0)

    finally:
        db.close()


def add_recipe(product_name, materials, notes=None):

    db = get_db_connection()
    cursor = db.cursor()


    """
    Adds a new recipe to the database.

    Parameters:
        product_name (str): Name of the product.
        materials (list of dict): Each dict contains 'material_name' and 'quantity_needed'.
        notes (str, optional): Additional notes for the recipe.

    Example:
        materials = [
            {'material_name': 'Matcha Powder', 'quantity_needed': 10},
            {'material_name': 'Milk', 'quantity_needed': 200}
        ]
        add_recipe('Matcha Latte', materials, notes='Sweetened')
    """

    try:

        db.execute(cursor,"""
        INSERT INTO recipes (product_name, notes)
        VALUES (%s, %s)
         """,(product_name, notes))
        recipe_id = db.get_last_insert_id(cursor) # get recipe_id, able to add to recipe_materials

        # ISSUE: the loop below called get_raw_material(name) once per material — each call
        #        opened its own DB connection (SELECT on raw_materials) and closed it.
        #        10 ingredients = 10 extra connections inside a function that already has one open.
        # FIX: batch-fetch all material names in one query on the already-open connection,
        #      build a name→id dict, then resolve ids from the dict inside the loop.

        # ADDED: collect all names so we can look them all up in one query
        names = [m["material_name"] for m in materials]
        placeholders = ', '.join(['%s'] * len(names))  # one %s per name; wrapper converts to ? for SQLite
        db.execute(cursor, f"""
            SELECT material_id, name
            FROM raw_materials
            WHERE LOWER(name) IN ({placeholders})
        """, [n.lower() for n in names])
        # ADDED: {lowercase_name: material_id} lookup dict — replaces per-name get_raw_material calls
        material_lookup = {row[1].lower(): row[0] for row in cursor.fetchall()}

        for material in materials:
            material_name = material["material_name"]
            quantity_needed = material['quantity_needed']

            # REMOVED: get_raw_material(material_name) — opened a new connection per iteration
            # material_info = get_raw_material(material_name)

            # ADDED: dict lookup — no extra connection or query
            material_id = material_lookup.get(material_name.lower())
            if material_id is None:
                logging.error(f"Material '{material_name}' not found in raw_materials while adding recipe '{product_name}'.")
                raise ValueError(f"Material '{material_name}' not found in raw_materials. Please add it to inventory before creating the recipe.")

            db.execute(cursor,"""
            INSERT INTO recipe_materials (
                   recipe_id,
                   material_name,
                   material_id,
                   quantity_needed)
            VALUES (%s,%s,%s,%s)
              """,(recipe_id, material_name, material_id, quantity_needed))


        db.commit()
        print(f"Recipe '{product_name}' added successfully with {len(materials)} materials.")
        return recipe_id



    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def change_recipe(product_name, materials, notes= None):
    """
    changes a pre exisitng recipe

    Parameters:
        product_name (str): Name of the product.
        materials (list of dict): Each dict contains 'material_name' and 'quantity_needed'.
        notes (str, optional): Additional notes for the recipe.

    Example:
        materials = [
            {'material_name': 'Matcha Powder', 'quantity_needed': 10},
            {'material_name': 'Milk', 'quantity_needed': 200}
        ]
        change_recipe('Matcha Latte', materials, notes='Sweetened')



        """

    db = get_db_connection()
    cursor = db.cursor()

    try:

        db.execute(cursor,"""
        SELECT recipe_id
        FROM recipes
        WHERE LOWER(product_name) = LOWER(%s)

                       """,(product_name,))
        recipe_id = cursor.fetchone()

        if not recipe_id:
            print(f"No recipe found for {product_name}")
            return None
        recipe_id = recipe_id[0]



        db.execute(cursor,"""
        UPDATE recipes
        SET notes = %s
        WHERE LOWER(product_name) = LOWER(%s)

                       """,(notes, product_name,))


        db.execute(cursor,"""
        DELETE FROM recipe_materials
        WHERE recipe_id = %s
                       """,(recipe_id,))

        # ISSUE: loop called get_raw_material(name) once per material — new connection each time.
        # FIX: batch-fetch all names on the already-open connection, resolve from dict in the loop.

        # ADDED: one batch SELECT replacing N per-name get_raw_material calls
        names = [m["material_name"] for m in materials]
        placeholders = ', '.join(['%s'] * len(names))
        db.execute(cursor, f"""
            SELECT material_id, name
            FROM raw_materials
            WHERE LOWER(name) IN ({placeholders})
        """, [n.lower() for n in names])
        material_lookup = {row[1].lower(): row[0] for row in cursor.fetchall()}

        for material in materials:
            material_name = material["material_name"]
            quantity_needed = material['quantity_needed']

            # REMOVED: get_raw_material(material_name) — opened a new connection per iteration
            # material_info = get_raw_material(material_name)

            # ADDED: dict lookup — no extra connection or query
            material_id = material_lookup.get(material_name.lower())
            if material_id is None:
                logging.error(f"Material '{material_name}' not found in raw_materials while updating recipe '{product_name}'.")
                raise ValueError(f"Material '{material_name}' not found in raw_materials. Please add it to inventory before updating the recipe.")

            db.execute(cursor,"""
            INSERT INTO recipe_materials (

            recipe_id,
            material_name,
            material_id,
            quantity_needed)
            VALUES (%s,%s,%s,%s)
                """, (recipe_id, material_name, material_id, quantity_needed))


        db.commit()
        print(f"Recipe '{product_name}' changed successfully with {len(materials)} materials.")
        return recipe_id


    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def delete_recipe(product_name):



    "deletes recipe"

    db = get_db_connection()
    cursor = db.cursor()

    try:

        #get id
        db.execute(cursor,"""
        SELECT recipe_id
        FROM recipes
        WHERE LOWER(product_name) = LOWER(%s)
                       """,(product_name,))
        row = cursor.fetchone()

        if not row:
            print(f"Recipe for {product_name} not found.")
            return None
        recipe_id = row[0]



        #get materials that will be deleted
        query = ("""
        SELECT material_name, quantity_needed
        FROM recipe_materials
        WHERE recipe_id = %s
                       """)
        df = pd.read_sql_query(query, db.conn, params=(recipe_id,) )

        #clean query for presentation

        df = df.rename(columns={
            'material_name': 'Material',
        'quantity_needed': 'Quantity Needed'
            })


        #delete recipe from recipes
        db.execute(cursor,"""
        DELETE FROM recipes
        WHERE LOWER(product_name) = LOWER(%s)
                       """,(product_name,))

        if cursor.rowcount == 0:
            print(f"Recipe '{product_name}' not found.")
            db.close()
            return None


        db.execute(cursor, """
        DELETE FROM recipe_materials
        WHERE recipe_id = %s
                       """,(recipe_id,))




        db.commit()

        print(f"Deleted {product_name} from recipe log, {product_name}'s recipe:\n{df}")

    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def get_all_recipes_with_id(page=None, per_page=50):
    """
    returns all recipes with their recipe_id,
    used for manage page when editing recipe,
    to get recipe id from product name.

    # ADDED: page/per_page pagination parameters. One row per recipe (DISTINCT), so
    #        simple LIMIT/OFFSET is safe here — no risk of splitting a recipe across pages.
    # page=None → full table; returns (df, None)
    # page=int  → paginated slice; returns (df, total_recipe_count)
    #
    # CHANGED: was pd.read_sql_query(query, db.conn) — converted to cursor approach so
    #          LIMIT/OFFSET params go through the %s→? wrapper consistently.
    """

    db = get_db_connection()
    cursor = db.cursor()
    columns = ['recipe_id', 'product_name', 'notes']

    try:
        # uses DISTINCT to return one row per recipe; joins ensure only recipes with
        # at least one valid material are included (same list as the recipes view page).
        base_query = """
        SELECT DISTINCT r.recipe_id, r.product_name, r.notes
        FROM recipes r
        JOIN recipe_materials rm ON rm.recipe_id = r.recipe_id
        JOIN raw_materials raw ON rm.material_id = raw.material_id
        ORDER BY r.product_name ASC
        """

        if page is None:
            # ADDED: full table path — no LIMIT/OFFSET
            db.execute(cursor, base_query)
            result = cursor.fetchall()
            return (pd.DataFrame(result, columns=columns), None)

        # ADDED: total distinct recipe count for pagination metadata
        db.execute(cursor, "SELECT COUNT(*) FROM recipes")
        total = cursor.fetchone()[0]

        # ADDED: LIMIT/OFFSET for the requested page
        db.execute(cursor, base_query + " LIMIT %s OFFSET %s", (per_page, (page - 1) * per_page))
        result = cursor.fetchall()
        return (pd.DataFrame(result, columns=columns), total)

    except Exception as e:
        logging.error(f"Error getting all recipes with id: {e}")
        return (pd.DataFrame(), 0)

    finally:
        db.close()


def get_recipe_by_id(recipe_id):
    """
    gets recipe by id, used for managment page,

    returns full recipe details, including materials and quantities,
    given recipe_id, used for manage page when editing recipe,
    to get recipe details from recipe id.

    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        query = ("""
       SELECT r.recipe_id,
       r.product_name,
       r.notes,
       rm.material_id,
       raw.name AS material_name,
       rm.quantity_needed
       FROM recipes r
       JOIN recipe_materials rm ON rm.recipe_id = r.recipe_id
       JOIN raw_materials raw ON rm.material_id = raw.material_id
       WHERE r.recipe_id = %s
        """)

        db.execute(cursor, query, (recipe_id,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(rows, columns=columns)

        return df

    except Exception as e:
        logging.error(f"Error: {e} \ngetting recipe by id:{recipe_id}.")
        return None

    finally:
        db.close()


def update_recipe(recipe_id, product_name=None, materials=None, notes=None):
    """
    changes a pre exisitng recipe

    Parameters:
        recipe_id (int): The ID of the recipe to change.
        materials (list of dict): Each dict contains 'material_name' and 'quantity_needed'.
        notes (str, optional): Additional notes for the recipe.

    Example:
        materials = [
            {'material_name': 'Matcha Powder', 'quantity_needed': 10},
            {'material_name': 'Milk', 'quantity_needed': 200}
        ]
        change_recipe('Matcha Latte', materials, notes='Sweetened')



        """

    db = get_db_connection()
    cursor = db.cursor()

    try:


        # for changing notes
        db.execute(cursor,"""
        UPDATE recipes
        SET notes = %s
        WHERE recipe_id = %s

                """,(notes, recipe_id,))

        if product_name is not None:
            db.execute(cursor, """
            UPDATE recipes
            SET product_name = %s
            WHERE recipe_id = %s
            """, (product_name, recipe_id))


        db.execute(cursor,"""
        DELETE FROM recipe_materials
        WHERE recipe_id = %s
                       """,(recipe_id,)) # delete old materials

        # ISSUE: loop called get_raw_material(name) once per material — new connection each time.
        # FIX: batch-fetch all names on the already-open connection, resolve from dict in the loop.

        # ADDED: one batch SELECT replacing N per-name get_raw_material calls
        names = [m["material_name"] for m in materials]
        placeholders = ', '.join(['%s'] * len(names))
        db.execute(cursor, f"""
            SELECT material_id, name
            FROM raw_materials
            WHERE LOWER(name) IN ({placeholders})
        """, [n.lower() for n in names])
        material_lookup = {row[1].lower(): row[0] for row in cursor.fetchall()}

        for material in materials:
            material_name = material["material_name"]
            quantity_needed = material['quantity_needed']

            # REMOVED: get_raw_material(material_name) — opened a new connection per iteration
            # material_info = get_raw_material(material_name)

            # ADDED: dict lookup — no extra connection or query
            material_id = material_lookup.get(material_name.lower())
            if material_id is None:
                print(f"Warning: Material '{material_name}' not found in raw_materials.")

            db.execute(cursor,"""
            INSERT INTO recipe_materials (

            recipe_id,
            material_name,
            material_id,
            quantity_needed)
            VALUES (%s,%s,%s,%s)
                """, (recipe_id, material_name, material_id, quantity_needed))


            if cursor.rowcount == 0:
                    raise ValueError(f"recipe ID {recipe_id} not found — nothing inserted")
        db.commit()
        logging.info(f"Recipe with recipe_id:{recipe_id} changed successfully with {len(materials)} materials.")
        return recipe_id


    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def delete_recipe_by_id(recipe_id):
    "deletes recipe by id"

    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        DELETE FROM recipe_materials
        WHERE recipe_id = %s
        """, (recipe_id,))

        db.execute(cursor, """
        DELETE FROM recipes
        WHERE recipe_id = %s
        """, (recipe_id,))

        if cursor.rowcount == 0:
            raise ValueError(f"Recipe with id {recipe_id} not found.")

        db.commit()
        logging.info(f"Deleted recipe with id {recipe_id}")
        return True

    except Exception as e:
        logging.error(f"Error: {e}")
        db.rollback()
        return None

    finally:
        db.close()
