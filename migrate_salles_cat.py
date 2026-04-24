import sqlite3
import os

db_path = 'instance/app.db'

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Updating database schema for salles table...")
    
    # Add categorie column to salles
    try:
        cursor.execute('ALTER TABLE salles ADD COLUMN categorie VARCHAR(50)')
        print("Added categorie column to salles")
    except sqlite3.OperationalError as e:
        print(f"Error or already exists: {e}")
        
    conn.commit()
    conn.close()
    print("Database update complete.")
else:
    print("Database not found.")
