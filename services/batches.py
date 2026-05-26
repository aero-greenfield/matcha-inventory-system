# ADDED: these imports were all at the top of inventory_app.py — only the ones
#        actually used by the functions in this file are kept here.
from database import get_db_connection
import pandas as pd
from datetime import datetime
import logging
import time
import json

_BATCH_UPDATABLE_COLS = frozenset({"product_name", "quantity", "date_completed", "notes",
                                    "batch_number", "expiration_date", "planned_completion_date"})

# ADDED: batches.py calls get_raw_material (for mix batch logic in add_to_batches
#        and promote_planned_batches) and get_recipe (for deduction and promotion).
#        They live in their own service modules now, so we import them explicitly.
from services.materials import get_raw_material
from services.recipes import get_recipe

# ADDED: promote_planned_batches calls log_action directly to record promotions.
#        log_action moved to services.audit, so we import it here.
from services.audit import log_action

# ADDED: _UNSET was defined at the top of inventory_app.py (line 13).
#        It only affects update_batch, so it moves here with the batch functions.
_UNSET = object()  # sentinel for optional fields that can be explicitly set to None

# ADDED: _last_promote_time was defined at the top of inventory_app.py (line 14).
#        It's only read/written by get_batches(), so it moves here.
_last_promote_time = 0


# ========================
# BATCHES FUNCTIONS
# ========================

def add_to_batches(product_name, quantity, notes=None, batch_number=None, deduct_resources=True, expiration_date=None, planned_completion_date=None, batch_type='standard', allow_negative=False, lot_selections=None):
    """
    adds batch to ready to ship, but asks user if they want to deduct from resources, or just add it.
    If planned_completion_date is provided, batch is created with status 'Planned' instead of 'Ready'.
    batch_type can be 'standard', 'mix', or 'finished' — used to auto-determine whether to defer deduction for planned batches.
    if standard or mix, deduction happens immediately at batch creation regardless of planned vs ready status. and adds mixed batch to raw_materials with is_housemade = True, so they can be used in future batches.
    if finished, deduction is deferred until promotion time for planned batches, happens immediately for ready batches.


    lot number changes:
    1. mixed batches now insert into raw_material_lots table. with lot_number = MIX-BATCH-{batch_number}
    2. lot_selection paramater --> a paramater that is passed to funciton is a dictionary where the key is the material in recipe,
        each value to said key is a LIST each lot for the material, but each lot is in the form of a dicitonary.
        ex: lot_selections = {
            "Matcha": [
                {"lot_id": 1, "quantity_used": 10},
                {"lot_id": 2, "quantity_used": 5}
            ],
            "Sugar": [
                {"lot_id": 5, "quantity_used": 8}
            ]
        }

    3.
    """
    # Connect to the database
    db = get_db_connection()
    cursor = db.cursor()



    try:

        #get recipe data frame
        recipe_df = get_recipe(product_name)

        if recipe_df is None or recipe_df.empty:
            raise ValueError(
                f"Recipe '{product_name}' has no materials. "
                "A material may have been deleted — please recreate it or update the recipe."
            )

        # Determine status and date_completed based on whether a planned date was given
        if planned_completion_date:
            status = 'Planned'
            date_completed = None
        else:
            status = 'Ready'
            date_completed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


        # Auto-derive whether to defer deduction.
        # finished + Planned = skip deduction now, will deduct at promotion time.
        # mix and standard always deduct immediately, regardless of status.
        defer_deduction = (batch_type == 'finished' and status == 'Planned')


        # serialize lot_selections to JSON for deferred finished batches so promote_planned_batches
        # can use the same user-picked lots at promotion time instead of falling back to FIFO.
        # JSON keys must be strings, so material_id ints become strings — we'll re-cast on read.
        planned_lot_selections_json = json.dumps(lot_selections) if (defer_deduction and lot_selections is not None) else None

        db.execute(cursor, """
            INSERT INTO batches (batch_number, product_name, quantity, date_completed, status, notes, expiration_date, planned_completion_date, batch_type, planned_lot_selections)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (batch_number, product_name, quantity, date_completed, status, notes, expiration_date, planned_completion_date, batch_type, planned_lot_selections_json))
        batch_id = db.get_last_insert_id(cursor)



        #Deducting resources:


        if deduct_resources and not defer_deduction: # if defer_deduction, will be deducted later in promotion from planned.



            #validate lot selection is not None
            if lot_selections is None:
                raise ValueError("Lot selections must be provided for batch creation to validate stock and deduct from specific lots.")

            #check in there is needed resources
            for _, row in recipe_df.iterrows():
                material_id = row['material_id']
                material_name = row['material_name']
                required_amount = row['quantity_needed'] * quantity
                # get recipe mats



                #validation section for material and lots:




                #get lot list for each material
                lot_list = lot_selections.get(material_id)
                if lot_list is None:
                    raise ValueError(f"No lot selection provided for material '{material_name}'")



                #validate total sum of lots selected matches neededamount for recipe
                material_sum = sum(lot['qty'] for lot in lot_list) # sum up the total quantity from the lots for this material
                if abs(material_sum - required_amount) > 1e-6: # if the sum of the lots is less than the required amount, raise error before doing any deduction
                        raise ValueError(f"Total quantity from selected lots for material {material_name} is insufficient. Required: {required_amount}")



                # specific lot validation:
                for lot in lot_list:
                    lot_id = lot['lot_id']
                    qty = lot['qty']

                    #check each lot for validation
                    db.execute (cursor, """
                    SELECT quantity, cost_per_unit
                    FROM raw_material_lots
                    WHERE lot_id = %s AND material_id = %s AND status = 'active' AND (expiration_date IS NULL OR expiration_date > %s)

                        """, (lot_id, material_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    lot_row = cursor.fetchone() # we got our raw lot data

                    #existance validation
                    if not lot_row:
                        raise ValueError(f"Lot ID {lot_id} for material {material_name} not found or is not active/expired.")

                    available_qty = lot_row[0] #got  our quantity for lot
                    
                    #quantity validation
                    if available_qty < qty: # available quanitity must be greater than qty user wants from said lot
                        raise ValueError(f"Insufficient quantity in lot {lot_id} for material {material_name}. Required: {required_amount}, Available: {available_qty}")

                    cost_per_unit = lot_row[1] # got our cost per unit for lot, will need it for batch_materials log

                    # if we pass all validation, then we can do the deduction from the lots and materials.

                    # deduct immediately after validation passes for this lot
                    db.execute(cursor, """
                        UPDATE raw_material_lots
                        SET quantity = quantity - %s
                        WHERE lot_id = %s
                    """, (qty, lot_id))
                    #deduction

                    if cursor.rowcount == 0:
                        raise ValueError(f"Lot {lot_id} not found during deduction.")
                    #deduciton validation

                    db.execute(cursor, """
                        INSERT INTO batch_materials (batch_id, material_id, lot_id, quantity_used, cost_per_unit)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (batch_id, material_id, lot_id, qty, cost_per_unit))
                    #log into batch_materials

                    #validaiton and deduciton done for lot



        # ALSO IF BATCH TYPE IS MIX, ADD THE MIXED PRODUCT TO RAW_MATERIALS WITH is_housemade = True, SO IT CAN BE USED IN FUTURE BATCHES.if not already in raw_materials,
        # otherwise if its already in raw_materials, just update the stock level by adding the quantity of the batch we just made.
        if batch_type == 'mix':
            existing_mix = get_raw_material(product_name)
            if existing_mix:
                mix_material_id = existing_mix[0]
            else:
                db.execute(cursor, """
                    INSERT INTO raw_materials (name, category, unit, reorder_level, is_housemade)
                    VALUES (%s, %s, %s, %s, %s)
                """, (product_name, 'Mix', 'units', 0, True))
                mix_material_id = db.get_last_insert_id(cursor)

            lot_number = f"MIX-BATCH-{batch_number}"
            db.execute(cursor, """
                INSERT INTO raw_material_lots (lot_number, material_id, quantity, received_date, status)
                VALUES (%s, %s, %s, %s, %s)
            """, (lot_number, mix_material_id, quantity, datetime.now().strftime('%Y-%m-%d'), 'active'))
            if cursor.rowcount == 0:
                raise ValueError(f"Failed to create lot for mixed batch {batch_number}")
            
            #get lot_id for mixed batch itself. 
            mix_lot_id = db.get_last_insert_id(cursor)
            db.execute(cursor, """
                UPDATE batches SET mix_lot_id = %s WHERE batch_id = %s
            """, (mix_lot_id, batch_id))

        db.commit()
        print(f"Added {quantity} units of {product_name} (Batch {batch_id})")
        return batch_id


    except ValueError as e:
        # Re-raise ValueError so app.py can catch it and show to user
        logging.error(f"Error adding to batches: {e}")
        db.rollback()
        raise  # ← Re-raises the ValueError to app.py

    except Exception as e:
        # If any error occurs during the process, print it and undo all changes
        logging.error(f"Error adding to batches: {e}")
        db.rollback()  # Rollback ensures database stays consistent
        return None

    finally:
        # Always close the database connection, even if an error occurred
        db.close()


def get_batches():
    """Gets all batches ready to ship"""
    global _last_promote_time
    now = time.time()
    if now - _last_promote_time > 60:
        promote_planned_batches()
        _last_promote_time = now
    db = get_db_connection()

    query = """
    SELECT batch_id, batch_number, product_name, batch_type, quantity, date_completed, notes, expiration_date
    FROM batches
    WHERE status = 'Ready'
    ORDER BY batch_id DESC
    """

    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result


def get_batches_shipped():
    """Gets all batches that have been shipped"""
    db = get_db_connection()

    query = """
    SELECT batch_id, batch_number, product_name, quantity, date_completed, date_shipped, notes, expiration_date
    FROM batches
    WHERE status = 'Shipped'
    ORDER BY date_shipped DESC
    """

    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result

def mark_as_shipped(batch_id):
    """Marks a batch as shipped"""
    db = get_db_connection()
    cursor = db.cursor()

    try:
        db.execute(cursor, """
        UPDATE batches
        SET status = 'Shipped', date_shipped = %s
        WHERE batch_id = %s
        """, (datetime.now().strftime('%Y-%m-%d'), batch_id))


        if cursor.rowcount == 0: # make sure the batch id exists and was updated
            print(f"Batch ID {batch_id} not found. No batch marked as shipped.") # if doesnt exist, there was an error marking batch as shipped.
            db.rollback()
            return False


        db.commit()
        print(f" Marked batch {batch_id} as shipped")
        return True

    except Exception as e:
        logging.error(f" Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def delete_batch(batch_id, materials_to_reallocate=None, reallocate=False):
    """
    Deletes a batch from batches.
    Optionally reallocates raw materials back into inventory.
    materials_to_reallocate: list of dicts with keys 'material_id', 'quantity_used', 'material_name' for each material to reallocate back to inventory. Only used if reallocate is True.
    """

    db = get_db_connection()
    cursor = db.cursor()

    try:
        # Get batch info
        db.execute(cursor, """
            SELECT product_name, quantity, batch_type, mix_lot_id
            FROM batches
            WHERE batch_id = %s
        """, (batch_id,))
        row = cursor.fetchone()

        if not row:
            logging.info(f"Batch ID {batch_id} not found in batches.")
            return None

        product_name, quantity, batch_type, mix_lot_id = row




        if reallocate and materials_to_reallocate: # if reallocate is True and there are materials to reallocate, add them back to inventory and then delete the batch and its materials. otherwise just delete batch and its materials without adding back to inventory.

            materials_added = []
            #get batch material info from batch id


            for mat in materials_to_reallocate: #for each material to reallocate, add back to stock level
                material_id = mat['material_id']
                material_name = mat['material_name']

                # get all lot rows for this material in this batch (may span multiple lots)
                db.execute(cursor, """
                    SELECT lot_id, quantity_used
                    FROM batch_materials
                    WHERE material_id = %s AND batch_id = %s
                """, (material_id, batch_id))
                lot_rows = cursor.fetchall()

                if not lot_rows:
                    raise ValueError(f"No batch_materials record found for material {material_name} in batch {batch_id}. Cannot reallocate.")

                for lot_id, qty_to_restore in lot_rows:
                    if lot_id is None:
                        raise ValueError(f"Lot ID for material {material_name} in batch {batch_id} is not tracked. Cannot reallocate.")

                    # look up lot_number for logging
                    db.execute(cursor, "SELECT lot_number FROM raw_material_lots WHERE lot_id = %s", (lot_id,))
                    rml_row = cursor.fetchone()
                    lot_number = rml_row[0] if rml_row else str(lot_id)


                    #Reallocate
                    db.execute(cursor, """
                        UPDATE raw_material_lots
                        SET quantity = quantity + %s
                        WHERE lot_id = %s
                    """, (qty_to_restore, lot_id))

                    materials_added.append({
                        "material": material_name,
                        "quantity_added": qty_to_restore,
                        "lot_number": lot_number
                    })
                
                

            # delete batch materials after adding to list
            db.execute(cursor, """
                DELETE
                FROM batch_materials
                WHERE batch_id = %s

                   """,(batch_id,))
            # Delete batch
            db.execute(cursor, """
                DELETE FROM batches
                WHERE batch_id = %s
            """, (batch_id,))
            #make sure it deleted it
            if cursor.rowcount == 0:
                raise ValueError(f"batch ID {batch_id} not found — nothing deleted")

            if batch_type == 'mix' and mix_lot_id:
                db.execute(cursor, """
                    UPDATE raw_material_lots
                    SET quantity = 0, status = 'inactive'
                    WHERE lot_id = %s
                """, (mix_lot_id,))

            db.commit()

            logging.info(
                f"Successfully deleted batch {batch_id}.\n"
                f"Reallocated materials: {materials_added}"
                )
            return True

        else:
            db.execute(cursor, """
                DELETE FROM batch_materials
                WHERE batch_id = %s
            """, (batch_id,))
            db.execute(cursor, """
                DELETE FROM batches
                WHERE batch_id = %s
            """, (batch_id,))
            #check it deleted
            if cursor.rowcount == 0:
                raise ValueError(f"batch ID {batch_id} not found — nothing deleted")

            if batch_type == 'mix' and mix_lot_id:
                db.execute(cursor, """
                    UPDATE raw_material_lots
                    SET quantity = 0, status = 'inactive'
                    WHERE lot_id = %s
                """, (mix_lot_id,))

            db.commit()
            logging.info(f"Successfully deleted batch {batch_id}.")
            return True




    except Exception as e:
        db.rollback()
        logging.error(f"Error deleting batch: {e}")
        return None

    finally:
        db.close()

def get_all_batches_with_id():
    """
    Get all batches including shipped ones, using batch_id

    used for manage page
    """
    promote_planned_batches()
    db = get_db_connection()

    try:
        query = """

        SELECT batch_id, batch_number, product_name, quantity, date_completed, status, notes, date_shipped, expiration_date, planned_completion_date, batch_type
        FROM batches
        ORDER BY date_completed DESC
        """

        result = pd.read_sql_query(query, db.conn)

        return result

    except Exception as e:
        logging.error(f"error getting all materials with id: {e}")

        return None

    finally:
        db.close()

def get_batch_by_id(batch_id):
    """
    get batch using its id,
    for manage page.

    """

    db = get_db_connection()
    cursor = db.cursor()

    try:
        query = """
        SELECT batch_id, product_name, quantity, date_completed, status, notes, date_shipped, expiration_date, planned_completion_date, batch_type, batch_number
        FROM batches
        WHERE batch_id = %s

        """
        db.execute(cursor, query, (batch_id,))
        result = cursor.fetchone()
        return result

    except Exception as e:
        logging.error(f"error getting batch by id: {e}")

        return None

    finally:
        db.close()

def update_batch(batch_id, product_name=None, quantity=None, date_completed=None, notes=None, expiration_date=_UNSET, planned_completion_date=_UNSET, batch_number=None):
    """
    changes the details of batch, BESIDES STATUS, doesnt change status.

    note: similar to update_materials func

    for quantity change, must deduct from raw materials if quantity is increased, and add back to raw materials if quantity is decreased. will check for sufficient stock if quantity is increased.
    """

    db = get_db_connection()
    cursor = db.cursor()

    field = {} # dictionary to hold fields to update, only the ones that are not None

    #iterate through params, if not None, add to field dict to update
    for key, value in [("product_name", product_name), ("quantity", quantity), ("date_completed", date_completed), ("notes", notes), ("batch_number", batch_number)]:
        if value is not None:
            field[key] = value
    # expiration_date and planned_completion_date use sentinel so None can explicitly clear the field
    if expiration_date is not _UNSET:
        field["expiration_date"] = expiration_date

    if planned_completion_date is not _UNSET:
        field["planned_completion_date"] = planned_completion_date

    if not field: #empty dictionary, no fields to update
        logging.info("No fields to update")
        return

    invalid = set(field) - _BATCH_UPDATABLE_COLS
    if invalid:
        raise ValueError(f"Invalid column name(s): {invalid}")

    try:
        set_clause = ', '.join(f"{key} = %s" for key in field)
        params = (*field.values(), batch_id)
        db.execute(cursor, f"UPDATE batches SET {set_clause} WHERE batch_id = %s", params)

        if cursor.rowcount == 0:
                raise ValueError(f"batch ID {batch_id} not found — nothing updated")
        db.commit()
        logging.info(f"Updated batch with id:{batch_id}")

        return True

    except Exception as e:
        logging.error(f"Error changing batch details: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def update_batch_status(batch_id, new_status):
    """
    changes the status of batch, only changes status, not other details.
    """

    db = get_db_connection()
    cursor = db.cursor()

    try:
        if new_status == 'Shipped':
            db.execute(cursor, """
            UPDATE batches
            SET status = %s, date_shipped = %s
            WHERE batch_id = %s
            """, (new_status, datetime.now().strftime('%Y-%m-%d'), batch_id))


        elif new_status == 'Planned':
            # Batch is not yet done — clear completion and ship dates
            db.execute(cursor, """
            UPDATE batches
            SET status = 'Planned', date_completed = NULL, date_shipped = NULL
            WHERE batch_id = %s
            """, (batch_id,))

        else:
            # Manually marking Ready — stamp the actual completion time
            db.execute(cursor, """
            UPDATE batches
            SET status = %s, date_shipped = NULL, date_completed = %s
            WHERE batch_id = %s
            """, (new_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), batch_id))

        if cursor.rowcount == 0:
                raise ValueError(f"batch ID {batch_id} not found — nothing updated")

        db.commit()
        logging.info(f"Batch {batch_id} status updated to {new_status}")
        return True

    except Exception as e:
        logging.error(f"Error updating batch status: {e}")
        db.rollback()
        return None

    finally:
        db.close()

def promote_planned_batches():

    """
    Promotes overdue Planned batches to Ready.
    - standard/mix batches: flip status directly (deduction already happened at creation)
    - finished batches: deduct from lots now and promote; leave as Planned if stock is insufficient
    Called lazily from get_batches() and get_all_batches_with_id().

    For finished batches, lot deduction uses one of two paths depending on what was stored at creation:
    1. stored lots (planned_lot_selections JSON column): user picked specific lots when creating the batch —
       validate and deduct from exactly those lots, same logic as add_to_batches.
    2. FIFO fallback: no stored selections — automatically deduct from oldest active lots first.

    For mix batches: also inserts a new lot into raw_material_lots for the produced quantity
    so the housemade material is available for use in future batches.
    """


    db = get_db_connection()
    cursor = db.cursor()
    try:
        now = datetime.now().strftime('%Y-%m-%d')

        # fetch all overdue planned batches.
        # planned_lot_selections is the JSON-serialized lot picks the user made at creation time —
        # used by finished batches to deduct from specific lots instead of falling back to FIFO.
        db.execute(cursor, """
            SELECT batch_id, batch_number, product_name, quantity, batch_type, planned_completion_date, planned_lot_selections
            FROM batches
            WHERE status = 'Planned'
            AND planned_completion_date IS NOT NULL
            AND planned_completion_date <= %s

                   """, (now,))
        overdue = cursor.fetchall()

        for batch_id, batch_number, product_name, quantity, batch_type, planned_completion_date, planned_lot_selections_json in overdue:

            if batch_type in ('standard', 'mix'):
                # standard and mix batches already had their raw_material_lots deducted at creation time,
                # so all we need to do here is flip the status to Ready.
                db.execute(cursor, """
                    UPDATE batches
                    SET status = 'Ready',
                        date_completed = %s,
                        promotion_failure_reason = NULL
                    WHERE batch_id = %s

                           """, (planned_completion_date, batch_id))

                if cursor.rowcount == 0:
                    raise ValueError(f"Batch {batch_id} not found during promotion — nothing updated")

                # mix batches also produce a housemade material that gets used in future batches.
                # just like add_to_batches does at creation time for immediate mix batches, we insert
                # a new lot into raw_material_lots so the produced quantity is trackable and deductable.
                if batch_type == 'mix':
                    existing_mix = get_raw_material(product_name)
                    if existing_mix:
                        mix_material_id = existing_mix[0]
                        lot_number = f"MIX-BATCH-{batch_number}"
                        db.execute(cursor, """
                            INSERT INTO raw_material_lots (lot_number, material_id, quantity, received_date, status)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (lot_number, mix_material_id, quantity, planned_completion_date, 'active'))
                    else:
                        # if the mix product somehow isn't in raw_materials, log a warning but don't block promotion
                        logging.warning(f"Mix batch {batch_id}: could not find '{product_name}' in raw_materials to create lot.")

                log_action('planned_batch_promoted',
                           f"batch_id={batch_id}, product={product_name}, type={batch_type}")

            # finished batches deferred their deduction at creation time (defer_deduction=True in add_to_batches).
            # now at promotion time we do the actual lot-level deduction, mirroring add_to_batches' lot logic.

            elif batch_type == 'finished':
                recipe_df = get_recipe(product_name)
                if recipe_df is None or recipe_df.empty:
                    db.execute(cursor, """
                        UPDATE batches
                        SET promotion_failure_reason = %s
                        WHERE batch_id = %s

                               """, (f"No recipe found for {product_name}", batch_id,))
                    continue

                failure_reason = None  # will be set if any material can't be covered by its lots
                all_allocations = {}   # material_id -> [(lot_id, qty_to_take, cost_per_unit)]

                # parse stored lot selections if the user picked specific lots at creation time.
                # JSON keys are always strings, so re-cast material_id back to int to match recipe_df.
                stored_lot_selections = None
                if planned_lot_selections_json:
                    raw = json.loads(planned_lot_selections_json)
                    stored_lot_selections = {int(k): v for k, v in raw.items()}

                # --- PASS 1: lot allocation + coverage check (reads only, no writes yet) ---
                for _, row in recipe_df.iterrows():
                    material_id = row['material_id']
                    material_name = row['material_name']
                    required = row['quantity_needed'] * quantity

                    if stored_lot_selections is not None:
                        # --- user-picked lots path: validate stored selections same as add_to_batches ---

                        lot_list = stored_lot_selections.get(material_id) #
                        if lot_list is None:
                            failure_reason = f"No stored lot selection for material '{material_name}'"
                            break

                        # total qty across stored lots must equal required (mirrors add_to_batches sum check)
                        material_sum = sum(lot['qty'] for lot in lot_list)
                        if abs(material_sum - required) > 1e-6:
                            failure_reason = (
                                f"Stored lot quantities for '{material_name}' don't match required "
                                f"(stored: {material_sum}, required: {required})"
                            )
                            break

                        # validate each stored lot individually: must exist, be active, not expired, have enough qty
                        allocations = []
                        for lot in lot_list:
                            lot_id = lot['lot_id']
                            qty = lot['qty']
                            db.execute(cursor, """
                                SELECT quantity, cost_per_unit FROM raw_material_lots
                                WHERE lot_id = %s AND material_id = %s AND status = 'active'
                                  AND (expiration_date IS NULL OR expiration_date > %s)
                            """, (lot_id, material_id, now))
                            lot_row = cursor.fetchone()
                            if not lot_row:
                                failure_reason = f"Lot {lot_id} for '{material_name}' not found, inactive, or expired."
                                break
                            if lot_row[0] < qty:
                                failure_reason = (
                                    f"Lot {lot_id} for '{material_name}' has insufficient quantity "
                                    f"(need {qty}, have {lot_row[0]})."
                                )
                                break
                            allocations.append((lot_id, qty, lot_row[1]))

                        if failure_reason:
                            break  # stop checking other materials

                    else:
                        # --- FIFO fallback path: auto-select oldest active lots first ---

                        # fetch active, non-expired lots for this material, oldest first
                        db.execute(cursor, """
                            SELECT lot_id, quantity, cost_per_unit FROM raw_material_lots
                            WHERE material_id = %s
                              AND status = 'active'
                              AND (expiration_date IS NULL OR expiration_date > %s)
                              AND quantity > 0
                            ORDER BY received_date ASC
                        """, (material_id, now))
                        lots = cursor.fetchall()

                        # greedily fill required from lots oldest-first
                        remaining = required
                        allocations = []
                        for lot_id, lot_qty, cost in lots:
                            if remaining <= 0:
                                break
                            take = min(lot_qty, remaining)
                            allocations.append((lot_id, take, cost))
                            remaining -= take

                        if remaining > 1e-6:
                            available = required - remaining
                            failure_reason = (
                                f"Insufficient lot stock: {material_name} "
                                f"(need {required}, have {round(available, 4)} across active lots)"
                            )
                            break  # no point checking other materials

                    # both paths confirmed coverage for this material — store allocations for the write pass
                    all_allocations[material_id] = allocations

                # --- handle failure: leave batch as Planned, record why ---
                if failure_reason:
                    db.execute(cursor, """
                        UPDATE batches
                        SET promotion_failure_reason = %s
                        WHERE batch_id = %s
                    """, (failure_reason, batch_id))
                    logging.warning(f"Batch {batch_id} could not promote: {failure_reason}")

                else:
                    # --- PASS 2: deduct from lots + insert batch_materials (writes) ---
                    # all materials passed the coverage check, so now we do the actual deductions.
                    # for each allocated lot: subtract the taken quantity and log it in batch_materials with lot_id.
                    for _, row in recipe_df.iterrows():
                        material_id = row['material_id']
                        for lot_id, take, cost in all_allocations[material_id]:

                            # deduct the allocated quantity from this specific lot
                            db.execute(cursor, """
                                UPDATE raw_material_lots
                                SET quantity = quantity - %s
                                WHERE lot_id = %s
                            """, (take, lot_id))

                            # record the usage in batch_materials with lot_id so we have full traceability
                            db.execute(cursor, """
                                INSERT INTO batch_materials (batch_id, material_id, lot_id, quantity_used, cost_per_unit)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (batch_id, material_id, lot_id, take, cost))

                    # all deductions succeeded — flip batch to Ready
                    db.execute(cursor, """
                        UPDATE batches
                        SET status = 'Ready',
                            date_completed = %s,
                            promotion_failure_reason = NULL
                        WHERE batch_id = %s
                    """, (planned_completion_date, batch_id))

                    if cursor.rowcount == 0:
                        raise ValueError(f"Batch {batch_id} not found during promotion — nothing updated")

                    log_action('planned_batch_promoted',
                               f"batch_id={batch_id}, product={product_name}, type=finished")

        db.commit()


    except Exception as e:
        logging.error(f"Error transitioning planned batches: {e}")
        db.rollback()

    finally:
        db.close()


def get_batches_planned():
    """Gets all Planned batches ordered by planned_completion_date ascending."""
    db = get_db_connection()
    query = """
    SELECT batch_id, batch_number, product_name, batch_type, quantity, planned_completion_date, notes, expiration_date, promotion_failure_reason
    FROM batches
    WHERE status = 'Planned'
    ORDER BY batch_id DESC
    """
    result = pd.read_sql_query(query, db.conn)
    db.close()
    return result


def get_batch_materials(batch_id):
    """
    Gets all batch materials for specific batch_id

    will return: material name, quantity used, unit, lot_id (not visible to user), lot_number, and material_id(not visible to user)

    """
    db = get_db_connection()
    cursor = db.cursor()

    try:

        query="""
        SELECT rm.name AS material_name, bm.quantity_used, rm.unit, bm.lot_id, rml.lot_number, bm.material_id
        FROM batch_materials bm
        JOIN raw_materials rm ON bm.material_id = rm.material_id
        JOIN raw_material_lots rml ON bm.lot_id = rml.lot_id
        WHERE bm.batch_id = %s
        ORDER BY rm.name ASC
        """
        db.execute(cursor, query, (batch_id,))
        result = cursor.fetchall()
        return result if result else []

    except Exception as e:
        logging.error(f"Error getting batch materials: {e}")
        return []

    finally:
        db.close()


def adjust_batch_material(batch_id, new_quantities: dict, lot_selections: dict = None):
    """
    Updates batch_materials.quantity_used and applies delta to raw_materials.stock_level.
    new_quantities: {material_id (int): new_quantity_used (float)}
    lot_selections: {material_id (int): lot_id (int)} — lot to deduct from when delta > 0
    Delta logic: stock_level -= (new - old), so increasing qty deducts more, decreasing returns stock.
    When lot_selections provided: also tracks deduction/return at the lot level.
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        for material_id, new_qty in new_quantities.items():
            db.execute(cursor, """
                SELECT quantity_used, lot_id FROM batch_materials
                WHERE batch_id = %s AND material_id = %s
            """, (batch_id, material_id))
            row = cursor.fetchone()
            if row is None:
                logging.warning(f"No batch_material record for batch {batch_id}, material {material_id} — aborting")
                db.rollback()
                return None

            old_qty = row[0]
            original_lot_id = row[1]
            delta = new_qty - old_qty

            if delta > 0:
                db.execute(cursor, """
                    SELECT stock_level FROM raw_materials WHERE material_id = %s
                """, (material_id,))
                stock_row = cursor.fetchone()
                if not stock_row:
                    logging.warning(f"Material ID {material_id} not found in raw_materials during batch adjustment — aborting")
                    db.rollback()
                    return None
                if stock_row[0] < delta:
                    logging.warning(f"Insufficient stock to increase material {material_id} for batch {batch_id}: need {delta}, have {stock_row[0]} — aborting")
                    db.rollback()
                    return None

                # Deduct from user-selected lot if provided, otherwise from original lot
                lot_id = (lot_selections or {}).get(material_id, original_lot_id)
                if lot_id:
                    db.execute(cursor, """
                        UPDATE raw_material_lots SET quantity = quantity - %s WHERE lot_id = %s
                    """, (delta, lot_id))

            elif delta < 0:
                # Return material to the original lot
                if original_lot_id:
                    db.execute(cursor, """
                        UPDATE raw_material_lots SET quantity = quantity + %s WHERE lot_id = %s
                    """, (abs(delta), original_lot_id))

            db.execute(cursor, """
                UPDATE batch_materials SET quantity_used = %s
                WHERE batch_id = %s AND material_id = %s
            """, (new_qty, batch_id, material_id))

            db.execute(cursor, """
                UPDATE raw_materials SET stock_level = stock_level - %s WHERE material_id = %s
            """, (delta, material_id))

        db.commit()
        logging.info(f"Adjusted materials for batch {batch_id} with changes: {new_quantities}")
        return True

    except Exception as e:
        logging.error(f"Error adjusting batch materials: {e}")
        db.rollback()
        return None

    finally:
        db.close()


def check_batch_materials_stock(batch_id, new_quantities: dict, lot_selections: dict = None):
    """
    Checks if new quantities for batch materials are available in stock before adjusting.
    lot_selections: {material_id: lot_id} — when provided, also validates the specific lot has enough.
    """
    db = get_db_connection()
    cursor = db.cursor()

    try:
        for material_id, new_qty in new_quantities.items():
            db.execute(cursor, """
                SELECT quantity_used, lot_id FROM batch_materials
                WHERE batch_id = %s AND material_id = %s
            """, (batch_id, material_id))
            row = cursor.fetchone()
            if row is None:
                logging.warning(f"No batch_material record for batch {batch_id}, material {material_id} during stock check")
                return False

            old_qty = row[0]
            original_lot_id = row[1]
            delta = new_qty - old_qty

            if delta > 0:
                db.execute(cursor, """
                    SELECT stock_level FROM raw_materials WHERE material_id = %s
                """, (material_id,))
                stock_row = cursor.fetchone()
                if not stock_row:
                    logging.warning(f"Material ID {material_id} not found in raw_materials during stock check")
                    return False
                if stock_row[0] < delta:
                    logging.warning(f"Insufficient overall stock for material {material_id}: need {delta}, have {stock_row[0]}")
                    return False

                # Validate the specific lot has enough if one was selected
                lot_id = (lot_selections or {}).get(material_id, original_lot_id)
                if lot_id:
                    db.execute(cursor, """
                        SELECT quantity FROM raw_material_lots WHERE lot_id = %s
                    """, (lot_id,))
                    lot_row = cursor.fetchone()
                    if not lot_row or lot_row[0] < delta:
                        logging.warning(f"Lot {lot_id} has insufficient quantity for material {material_id}: need {delta}, have {lot_row[0] if lot_row else 0}")
                        return False

        return True

    except Exception as e:
        logging.error(f"Error checking batch materials stock: {e}")
        return False

    finally:
        db.close()
