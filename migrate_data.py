import sqlite3
import pandas as pd
from database import init_db, get_worksheet
from datetime import datetime
import time

def migrate():
    print("Starting migration...")
    
    # 1. Initialize Google Sheets
    print("Initializing Google Sheets...")
    try:
        init_db()
    except Exception as e:
        print(f"Error initializing DB (Check secrets.toml or credentials): {e}")
        return
    
    # 2. Connect to SQLite
    print("Connecting to local database...")
    try:
        conn = sqlite3.connect('pharmacy.db')
        # Check if tables exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Found tables in SQLite: {tables}")
    except Exception as e:
        print(f"Error connecting to pharmacy.db: {e}")
        return

    # 3. Migrate Transactions
    if 'transactions' in tables:
        print("Migrating transactions...")
        try:
            df_trans = pd.read_sql_query("SELECT * FROM transactions", conn)
            if not df_trans.empty:
                # Target columns in order
                cols = ["id", "date", "type", "category", "subcategory", "account", "amount", "original_amount", "note", "nhi_month"]
                
                # Ensure all cols exist
                for c in cols:
                    if c not in df_trans.columns:
                        df_trans[c] = ""
                
                # Fill NaNs
                df_trans = df_trans.fillna("")
                
                # Convert to list of lists
                data = df_trans[cols].values.tolist()
                
                ws = get_worksheet("transactions")
                ws.clear()
                ws.append_row(cols) # Header
                ws.append_rows(data)
                print(f"Successfully migrated {len(data)} transactions.")
            else:
                print("Transactions table is empty.")
        except Exception as e:
            print(f"Error migrating transactions: {e}")
    else:
        print("Table 'transactions' not found in SQLite.")

    # 4. Migrate Monthly Closings
    if 'monthly_closings' in tables:
        print("Migrating monthly closings...")
        try:
            df_closing = pd.read_sql_query("SELECT * FROM monthly_closings", conn)
            if not df_closing.empty:
                cols = ["month", "bank_actual", "cash_actual", "bank_calc", "cash_calc", "note", "closed_at"]
                for c in cols:
                    if c not in df_closing.columns:
                        df_closing[c] = ""
                
                df_closing = df_closing.fillna("")
                data = df_closing[cols].values.tolist()
                
                ws = get_worksheet("monthly_closings")
                ws.clear()
                ws.append_row(cols)
                ws.append_rows(data)
                print(f"Successfully migrated {len(data)} closings.")
        except Exception as e:
            print(f"Error migrating closings: {e}")
    
    # 5. Migrate NHI Records
    if 'nhi_records' in tables:
        print("Migrating NHI records...")
        try:
            df_nhi = pd.read_sql_query("SELECT * FROM nhi_records", conn)
            if not df_nhi.empty:
                cols = ["month", "total_fee", "deduction", "rejection", "chronic_count", "general_count", "drug_fee", "updated_at"]
                for c in cols:
                    if c not in df_nhi.columns:
                        df_nhi[c] = ""
                
                df_nhi = df_nhi.fillna("")
                data = df_nhi[cols].values.tolist()
                
                ws = get_worksheet("nhi_records")
                ws.clear()
                ws.append_row(cols)
                ws.append_rows(data)
                print(f"Successfully migrated {len(data)} NHI records.")
        except Exception as e:
            print(f"Error migrating NHI records: {e}")

    conn.close()
    print("Migration completed!")

if __name__ == "__main__":
    migrate()
