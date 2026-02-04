"""
helping functions for Matcha Inventory CLI
handles input validation, data export, and database backups

functions dont let program crash if there are invalid inputs

functions will be called in cli.py
"""

import os
import shutil
import pandas as pd
from datetime import datetime
from tabulate import tabulate



# INPUT VALIDATION

"""
Functions that get validated user input for floats, int, yes/no, and optional batch-ids

"""


def get_float_input(prompt, min_val=0, allow_zero=True):
    """


    Gets a float input from the user, preventing invalid input crashes
    
    input: the prompt user is inputing, min val of prompt, and whether zero is allowed

    return: the float but validated
    """
    while True:
       
        try:
            value = float(input(prompt)) # the input
            
            if not allow_zero and value == 0: 
                print("|ERROR| Value cannot be zero. Please try again.") # if zero not allowed, invalid input
                continue
            
            if value < min_val:
                print(f"|ERROR| Value must be at least {min_val}. Please try again.") # cant be less then min val
                continue
            
            return value
        
        except ValueError:
            print("|ERROR| Invalid input. Please enter a valid number.")




def get_int_input(prompt, min_val=0, allow_zero=True):
    """
    gets validated int input from user

    returns int value. works same as float function
    """
    while True:
        try:
            value = int(input(prompt))
            
            if not allow_zero and value == 0:
                print("|ERROR| Value cannot be zero. Please try again.")
                continue
            
            if value < min_val:
                print(f"|ERROR| Value must be at least {min_val}. Please try again.")
                continue
            
            return value
        
        except ValueError:
            print("|ERROR| Invalid input. Please enter a valid whole number.")




def get_yes_no_input(prompt):
    """
    Gets yes/no input from user without having to worry about case sensitive issues

    returns True / False

    """
    while True:
        response = input(f"{prompt} (y/n): ").strip().lower() # make input lower case and without trailing spaces etc. 
        
        if response in ['y', 'yes']: # if its just a y or yes
            return True
        elif response in ['n', 'no']: 
            return False
        else:
            print("|ERROR| Please enter 'y' or 'n'.")


def get_optional_batch_id():
    """
    prompts user with choise of custom batch_id or auto generated

    
    
    function allows for autogeneration of batch_id, 

    
    returns int for batch_id or None for autogenerate
    if user inputs wrong batch_id, it re-prompts
    """
    # prompts for user
    print("\n Batch ID Options:")
    print("  • Press Enter to auto-generate ")
    print("  • Or type a custom batch ID number") 
    
    while True:
        user_input = input("Your choice: ").strip() # no extra trail
        
        if not user_input:
            return None  # autogenerate if no choice chosen
        
        try:
            batch_id = int(user_input) # batch_id now user input
            if batch_id <= 0: #cant be negitive
                print("|ERROR| Batch ID must be positive. Please try again.")
                continue #reprompts
            return batch_id
        except ValueError:
            print("|ERROR| Invalid batch ID. Please enter a valid number.")


# DATA DISPLAY


def display_dataframe(df, title=None, empty_message="No data found."):
    """
    Using tabulate to prettify DataFrame output for better user experience
    inputs: the dataframe, the title, and the empty message if there is no data in dataframe. 
    """
    if title:# if there is title, use clean formatting
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    
    if df.empty:# if no data, print empty message
        print(f"\n{empty_message}\n")
        return
    
    # tablefmt="grid" creates  boxes around data
    # headers="keys" uses df column names
    print("\n" + tabulate(df, headers='keys', tablefmt='grid', showindex=False))
    print()  # extra spacing for readability



# DATA EXPORT
"""
for exporting data to a csv file with timestamp

funcitons ensure folder exists and exports the df to csv




"""

def ensure_export_folder():
    """

    if a folder doesnt exist, it makes it

    folder is cleaner than csv files in root directory
    """
    if not os.path.exists('exports'): #if folder doesnt exist it makes it
        os.makedirs('exports')




def export_to_csv(df, filename_prefix):
    """


    exports the dataframe to a csv file with timestamp, and it returns the path to the file.

    inputs: the DF and file name




    """
    ensure_export_folder() # makes sure folder exists

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') # current time timestamp
    filename = f"{filename_prefix}_{timestamp}.csv" # file name with prefix and timestamp
    filepath = os.path.join('exports', filename) # full path to file

    df.to_csv(filepath, index=False) # exports to csv without index

    return filepath


def export_to_excel(df, filename_prefix):
    """
    Exports the dataframe to an Excel file with timestamp

    Similar to export_to_csv but creates .xlsx files instead of .csv
    Used by web app export buttons to download Excel files

    inputs:
        - df: pandas DataFrame to export
        - filename_prefix: string to prefix the filename (e.g., 'inventory', 'batches')

    returns: the filepath to the created Excel file

    Example: export_to_excel(df, 'inventory')
             creates 'exports/inventory_20260203_143022.xlsx'
    """
    ensure_export_folder() # makes sure exports/ folder exists, creates if needed

    # Create timestamp for unique filename (format: YYYYMMDD_HHMMSS)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Build filename with prefix, timestamp, and .xlsx extension
    filename = f"{filename_prefix}_{timestamp}.xlsx"

    # Construct full path: exports/filename.xlsx
    filepath = os.path.join('exports', filename)

    # Export DataFrame to Excel file
    # - index=False: Don't include row numbers in the export
    # - engine='openpyxl': Use openpyxl library for .xlsx format (required for Excel)
    df.to_excel(filepath, index=False, engine='openpyxl')

    return filepath # Return path so Flask can send the file to browser


def optional_export_to_csv(df, default_prefix):
    """
    Asks user if they want to export dataframe to csv.
    
    If yes, prompts for custom filename prefix or uses default.
    Exports and returns file path, else returns None.
    """
    if df.empty:
        print("|WARNING| No data to export.")
        return None
    
    if get_yes_no_input("Would you like to export this data to a CSV file?"):
        custom_prefix = input(f"Enter filename prefix (or press Enter for '{default_prefix}'): ").strip()
        prefix = custom_prefix if custom_prefix else default_prefix
        
        filepath = export_to_csv(df, prefix)
        print(f" Data exported to: {filepath}")
        return filepath
    else:
        print(" Export cancelled by user.")
        return None
# DATABASE BACKUP

"""
backup functions to protect data integrity

creates backup folder if not exists


and backups database with timestamped filenames

also function to check last backup time for auto-backup on startup

"""


def ensure_backup_folder():
    """Creates data/backups/ folder if it doesn't exist."""

    backup_dir = os.path.join('data', 'backups')# path to backup dir
    if not os.path.exists(backup_dir): # if it doesnt exist, make it
        os.makedirs(backup_dir)



def backup_database(reason="manual"):
    """
    creates a backup of the database with a timestamped filename

    ciritcal for protecting against accidental deletions, allows rollback if batch creation goes wrong

    input: reason for backup (for filename clarity)

    returns: path to backup file, or None if failed
    """
    ensure_backup_folder() # make sure backup folder exists
    
    source = 'data/inventory.db' # source database file
    
    if not os.path.exists(source):
        print("|ERROR|  Warning: Database file not found. Cannot create backup.") # if no database, cant backup
        return None
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') # time stamp of current time
    
    backup_filename = f"inventory_backup_{reason}_{timestamp}.db" # backup file name

    backup_path = os.path.join('data', 'backups', backup_filename) # path to file
    
    try:
        shutil.copy2(source, backup_path)# copys the source(database) to backup path
        print(f" Database backed up: {backup_filename}") 
        return backup_path 
    
    except Exception as e:
        print(f"|ERROR| Backup failed: {e}")
        return None


def get_last_backup_time():
    """

    
  


    checks the data/backups/ folder for latest backup file

    returns the time stamp of latest backup, or None if no backups exist
      Used to trigger daily auto-backups on CLI startup
    """
    backup_dir = os.path.join('data', 'backups')# path to backup dir
    
    if not os.path.exists(backup_dir):# if no backup dir, return none
        return None
    
    backups = [f for f in os.listdir(backup_dir) if f.endswith('.db')] #iterates through file in backup dir and get .db files
    
    if not backups: # if no backups
        return None
    
  
    for f in backups:
        backup_paths = os.path.join(backup_dir, f)  # full path to each backup file
    latest_backup = max(backup_paths, key=os.path.getmtime)# get the latest backup file by modification time
    
    return datetime.fromtimestamp(os.path.getmtime(latest_backup))


def auto_backup_on_startup():
    """
    Creates backup if last backup is >24 hours old.
    
    Why run on startup: Ensures fresh backup exists before user
    makes any changes. Safety net for the day's operations.
    
    Design decision: Non-blocking - prints message but doesn't
    stop user from continuing if backup fails

    uses try except to prevent crashes
     - Wraps everything in try-except (catches unexpected errors) 
   - If backup check fails, creates backup anyway (safe default) 
   - Continues even if backup fails (app doesn't crash)
    """
    try: 
        last_backup = get_last_backup_time() # call function to get last backup time 
        
        if last_backup is None:
            print(" No previous backup found. Creating initial backup...")# if no backup found, create initial backup
            backup_database(reason="initial") # first backup
            return
        
        hours_since_backup = (datetime.now() - last_backup).total_seconds() / 3600 # hours since last backup
        
        if hours_since_backup > 24: # if more than 24 hours back up 
            print(f" Last backup was {int(hours_since_backup)} hours ago. Creating fresh backup...")
            backup_database(reason="daily")
        else:
            print(f"✅ Recent backup exists ({int(hours_since_backup)} hours ago)")
    except Exception as e: 
        print(f"|ERROR|  Backup check skipped: {e}")
        print("📦 Creating backup to be safe...")
        try:
            backup_database(reason="startup") 
       
        except: 
           # Even if backup fails, let app continue 
           print("⚠️  Backup failed, but app will continue") 
           pass


# PRETTY PRINTING HELPERS
"""
will help with printing messages to user in consistent format


"""


def print_header(text):
    """Prints a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_success(message):
    """Prints success message with checkmark."""
    print(f"\n✅ {message}\n")


def print_error(message):
    """Prints error message with X mark."""
    print(f"\n❌ {message}\n")


def print_warning(message):
    """Prints warning message with warning sign."""
    print(f"\n⚠️  {message}\n")

#important
def pause():
    """Waits for user to press Enter before continuing."""
    input("\nPress Enter to continue...")