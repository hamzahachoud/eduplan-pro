import sqlite3
import os

db_path = 'instance/app.db'

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Updating database schema...")
    
    # 1. Add Salle table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS salles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom VARCHAR(50) NOT NULL,
        type_salle VARCHAR(10) NOT NULL,
        capacite INTEGER
    )
    ''')
    
    # 2. Add columns to users
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN enseignant_id INTEGER REFERENCES enseignants(id)')
        print("Added enseignant_id to users")
    except sqlite3.OperationalError:
        print("enseignant_id already exists in users or error")

    # 3. Add salle_id to seances
    try:
        cursor.execute('ALTER TABLE seances ADD COLUMN salle_id INTEGER REFERENCES salles(id)')
        print("Added salle_id to seances")
    except sqlite3.OperationalError:
        print("salle_id already exists in seances or error")
        
    conn.commit()
    conn.close()
    print("Database update complete.")
else:
    print("Database not found, init_db.py will handle creation.")
