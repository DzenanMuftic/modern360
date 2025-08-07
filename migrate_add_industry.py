#!/usr/bin/env python3
"""
Migration script to add industry column to Company table
Run this after updating the Company model to add industry field
"""

import sqlite3
import os

def migrate_add_industry():
    """Add industry column to Company table"""
    
    # Path to the database
    db_path = 'instance/modern360.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("This is normal for new installations.")
        return
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if industry column already exists
        cursor.execute("PRAGMA table_info(company)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'industry' in columns:
            print("Industry column already exists in Company table.")
            conn.close()
            return
        
        # Add industry column
        print("Adding industry column to Company table...")
        cursor.execute("ALTER TABLE company ADD COLUMN industry VARCHAR(100)")
        
        # Update some sample companies with industries (optional)
        sample_updates = [
            ("Evlot", "IT"),
            ("Microsoft", "IT"),
            ("Google", "IT"),
            ("Apple", "IT"),
            ("Tesla", "Manufacturing"),
            ("Amazon", "Retail"),
            ("Netflix", "Media"),
        ]
        
        for company_name, industry in sample_updates:
            cursor.execute(
                "UPDATE company SET industry = ? WHERE name LIKE ?", 
                (industry, f"%{company_name}%")
            )
            rows_affected = cursor.rowcount
            if rows_affected > 0:
                print(f"Updated {company_name} with industry: {industry}")
        
        # Commit changes
        conn.commit()
        print("✅ Successfully added industry column to Company table!")
        print("✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔄 Starting migration to add industry column...")
    migrate_add_industry()
