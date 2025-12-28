import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import toml
import os

# Constants
SHEET_URL_KEY = "spreadsheet"
SECRETS_PATH = ".streamlit/secrets.toml"

def get_config():
    """
    Retrieve configuration from Streamlit secrets or local Config file.
    Returns (sheet_url, creds_dict)
    """
    # 1. Try Streamlit Secrets (Works in Cloud & Local "streamlit run")
    try:
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
             sheet_url = st.secrets["connections"]["gsheets"][SHEET_URL_KEY]
             creds_dict = dict(st.secrets["gcp_service_account"])
             return sheet_url, creds_dict
    except FileNotFoundError:
        pass # Not running in streamlit or no secrets found yet
    except KeyError:
        pass
        
    # 2. Try loading .streamlit/secrets.toml manually (Works for standalone scripts)
    if os.path.exists(SECRETS_PATH):
        try:
            secrets = toml.load(SECRETS_PATH)
            sheet_url = secrets["connections"]["gsheets"][SHEET_URL_KEY]
            creds_dict = secrets["gcp_service_account"]
            return sheet_url, creds_dict
        except Exception as e:
            print(f"Error loading secrets.toml: {e}")
            
    return None, None

def get_client():
    """Authenticate and return gspread client."""
    sheet_url, creds_dict = get_config()
    if not creds_dict:
        raise ValueError("Credentials not found. Please configure .streamlit/secrets.toml")
    
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

def get_spreadsheet():
    """Open and return the spreadsheet object."""
    client = get_client()
    sheet_url, _ = get_config()
    if not sheet_url:
         raise ValueError("Sheet URL not found. Please configure .streamlit/secrets.toml")
    return client.open_by_url(sheet_url)

def get_worksheet(name):
    """Get a specific worksheet, create if not exists."""
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=name, rows=100, cols=20)
    return ws

def init_db():
    """
    Initialize the Google Sheet with required worksheets and headers.
    Checks if sheets exist, creates them if not, and ensures headers are present.
    """
    sh = get_spreadsheet()
    
    # 1. Transactions
    try:
        ws_trans = sh.worksheet("transactions")
    except gspread.WorksheetNotFound:
        ws_trans = sh.add_worksheet("transactions", rows=1000, cols=10)
    
    curr_headers_trans = ws_trans.row_values(1)
    req_headers_trans = ["id", "date", "type", "category", "subcategory", "account", "amount", "original_amount", "note", "nhi_month"]
    if not curr_headers_trans:
        ws_trans.append_row(req_headers_trans)

    # 2. Monthly Closings
    try:
        ws_closing = sh.worksheet("monthly_closings")
    except gspread.WorksheetNotFound:
        ws_closing = sh.add_worksheet("monthly_closings", rows=100, cols=10)
        
    curr_headers_closing = ws_closing.row_values(1)
    req_headers_closing = ["month", "bank_actual", "cash_actual", "bank_calc", "cash_calc", "note", "closed_at"]
    if not curr_headers_closing:
        ws_closing.append_row(req_headers_closing)

    # 3. NHI Records
    try:
        ws_nhi = sh.worksheet("nhi_records")
    except gspread.WorksheetNotFound:
        ws_nhi = sh.add_worksheet("nhi_records", rows=100, cols=10)
        
    curr_headers_nhi = ws_nhi.row_values(1)
    req_headers_nhi = ["month", "total_fee", "deduction", "rejection", "chronic_count", "general_count", "drug_fee", "updated_at"]
    if not curr_headers_nhi:
        ws_nhi.append_row(req_headers_nhi)


def add_transaction(date, type, category, subcategory, account, amount, original_amount=None, note="", nhi_month=None):
    """Add a new transaction to the Google Sheet."""
    ws = get_worksheet("transactions")
    
    # Generate ID: Simple Max ID + 1 strategy
    # Read all IDs first.
    # Note: This is not race-condition safe for high concurrency, but fine for this app.
    ids = ws.col_values(1)[1:] # Skip header
    if ids:
        new_id = max([int(i) for i in ids if i.isdigit()] or [0]) + 1
    else:
        new_id = 1
        
    row = [
        new_id,
        date.strftime('%Y-%m-%d'),
        type,
        category,
        subcategory,
        account,
        amount,
        original_amount if original_amount is not None else "",
        note,
        nhi_month if nhi_month is not None else ""
    ]
    ws.append_row(row)

def get_transactions(start_date=None, end_date=None):
    """Retrieve transactions within a date range."""
    ws = get_worksheet("transactions")
    data = ws.get_all_records() # Returns list of dicts
    
    df = pd.DataFrame(data)
    
    if df.empty:
         return df

    # Convert date column to datetime
    df['date'] = pd.to_datetime(df['date'])
    
    if start_date and end_date:
        mask = (df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)
        df = df.loc[mask]
    elif start_date:
         mask = (df['date'].dt.date >= start_date)
         df = df.loc[mask]
         
    df = df.sort_values(by='date', ascending=False)
    return df

def delete_transaction(tx_id):
    """Delete a transaction by ID."""
    ws = get_worksheet("transactions")
    cell = ws.find(str(tx_id), in_column=1)
    
    if cell:
        ws.delete_rows(cell.row)

def save_closing(month, bank_actual, cash_actual, bank_calc, cash_calc, note):
    """Save monthly closing record."""
    ws = get_worksheet("monthly_closings")
    
    # Check if month exists
    try:
        cell = ws.find(month, in_column=1)
    except gspread.CellNotFound:
        cell = None
        
    row_data = [
        month, 
        bank_actual, 
        cash_actual, 
        bank_calc, 
        cash_calc, 
        note, 
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ]
    
    if cell:
        # Update existing row
        # gspread uses 1-based index. 
        # Easier to update range.
        # But `update` needs range.
        # Let's just build the range string "A{row}:G{row}"
        r = cell.row
        ws.update(range_name=f"A{r}:G{r}", values=[row_data])
    else:
        # Append
        ws.append_row(row_data)

def get_closing(month):
    """Get closing record for a specific month."""
    ws = get_worksheet("monthly_closings")
    try:
        cell = ws.find(month, in_column=1)
        if cell:
            p = ws.row_values(cell.row)
            # Map list to dict accessible object or tuple as expected by app
            # Previous sqlite returned tuple. 
            # Headers: month, bank_actual, cash_actual, bank_calc, cash_calc, note, closed_at
            # Make sure types are correct (gspread returns strings usually, or floats if auto-converted)
            # We better cast them.
            return (
                p[0], 
                float(p[1]) if p[1] else 0.0, 
                float(p[2]) if p[2] else 0.0, 
                float(p[3]) if p[3] else 0.0, 
                float(p[4]) if p[4] else 0.0, 
                p[5], 
                p[6]
            )
    except gspread.CellNotFound:
        pass
    return None

def get_previous_closing(current_month_str):
    """Get the most recent closing record before the current month."""
    # This is harder in Sheets than SQL. Need to fetch all and sort.
    ws = get_worksheet("monthly_closings")
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    
    if df.empty:
        return None
        
    df = df[df['month'] < current_month_str]
    df = df.sort_values(by='month', ascending=False)
    
    if not df.empty:
        # Return first row as tuple
        row = df.iloc[0]
        return (
            row['month'],
            float(row['bank_actual']),
            float(row['cash_actual']),
            float(row['bank_calc']),
            float(row['cash_calc']),
            row['note'],
            row['closed_at']
        )
    return None

def save_nhi_record(month, total_fee, deduction, rejection, chronic_count, general_count, drug_fee):
    """Save or update NHI monthly record."""
    ws = get_worksheet("nhi_records")
    
    try:
        cell = ws.find(month, in_column=1)
    except gspread.CellNotFound:
        cell = None
        
    row_data = [
        month, 
        total_fee, 
        deduction, 
        rejection, 
        chronic_count, 
        general_count, 
        drug_fee, 
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ]
    
    if cell:
        r = cell.row
        ws.update(range_name=f"A{r}:H{r}", values=[row_data])
    else:
        ws.append_row(row_data)

def get_nhi_records(start_month=None, end_month=None):
    """Retrieve NHI records within a month range (YYYY-MM)."""
    ws = get_worksheet("nhi_records")
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    
    if df.empty:
        return df
        
    if start_month and end_month:
        mask = (df['month'] >= start_month) & (df['month'] <= end_month)
        df = df.loc[mask]
        
    df = df.sort_values(by='month', ascending=False)
    return df
