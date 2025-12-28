import pandas as pd
import utils
from datetime import datetime
import io

def identify_transaction_type(row):
    """
    Identify if the row is Income, Expense, or Transfer based on Debit/Credit accounts.
    Returns: 'Income', 'Expense', 'Transfer', or None
    """
    debit = str(row.get('借方科目', '')).strip()
    credit = str(row.get('貸方科目', '')).strip()
    
    # Asset Accounts (Aligned with common accounting inputs)
    assets = ['現金', '銀行存款', '銀行', '庫存現金']
    
    # Logic:
    # Debit Asset, Credit Non-Asset -> Income (e.g. Cash Dr, Sales Cr)
    # Debit Non-Asset, Credit Asset -> Expense (e.g. Expense Dr, Cash Cr)
    # Debit Asset, Credit Asset -> Transfer
    
    debit_is_asset = any(a in debit for a in assets)
    credit_is_asset = any(a in credit for a in assets)
    
    if debit_is_asset and not credit_is_asset:
        return 'Income'
    elif not debit_is_asset and credit_is_asset:
        return 'Expense'
    elif debit_is_asset and credit_is_asset:
        return 'Transfer'
    else:
        # Fallback: simple logic if assets not detected but columns imply direction
        return None

def normalize_account_name(name):
    """Map legacy account names to system account names."""
    if '現金' in name:
        return '現金'
    if '銀行' in name:
        return '銀行'
    if 'Line' in name:
        # Sometimes Line Pay accumulation is treated as an account
        return '銀行' 
    return '現金' # Default fallback

def normalize_category(category_name, tx_type, note):
    """
    Map legacy category names to system categories.
    """
    category_name = str(category_name).strip()
    note = str(note).strip()
    
    if tx_type == 'Income':
        # INCOME_CATEGORIES keys: 銷貨收入, 健保收入
        if '銷貨' in category_name or '收入' in category_name:
            main = "銷貨收入"
            # Subcategory heuristic
            if '刷卡' in note or '信用卡' in note:
                sub = "信用卡收入"
            elif 'Line' in note or 'LINE' in note:
                sub = "Line Pay收入"
            else:
                sub = "現金收入"
            return main, sub
            
        if '健保' in category_name:
            main = "健保收入"
            # Sub heuristic
            if '補助' in note:
                sub = "健保補助"
            elif '一暫' in note:
                sub = "健保一暫"
            elif '二暫' in note:
                sub = "健保二暫"
            else:
                sub = "健保補助" # Default
            return main, sub
            
    elif tx_type == 'Expense':
        # EXPENSE_CATEGORIES keys from utils.py
        # Direct Match attempt
        for key, subs in utils.EXPENSE_CATEGORIES.items():
            if key in category_name:
                # Found clean match, use first subcategory as default if unknown
                return key, subs[0] if subs else ""
        
        # Fuzzy Match
        if '成本' in category_name or '進貨' in category_name:
            return "銷貨成本", "調劑藥品"
        if '薪' in category_name:
            return "薪資支出", "月薪"
        if '水' in category_name or '電' in category_name or '費' in category_name:
            # Check explicit exclusions or more parsing
            return "水電雜費", "其他雜費"
        if '稅' in category_name:
            return "稅務支出", "營業稅"
        if '家庭' in category_name or '家事' in category_name:
            return "家庭支出", "其他"
            
    return "其他", "其他"

def process_file(uploaded_file):
    """
    Process the uploaded Excel/CSV file and return a DataFrame of valid transactions.
    """
    df = pd.DataFrame()
    try:
        # Check if uploaded_file is a file-like object available for seeking
        if hasattr(uploaded_file, 'name') and uploaded_file.name.lower().endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file)
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='cp950')
            except Exception:
                 # Fallback for other encodings if needed
                 uploaded_file.seek(0)
                 df = pd.read_csv(uploaded_file, encoding='big5') 
        else:
            df = pd.read_excel(uploaded_file)
            
        # Standardize columns
        # Expected Headers: 日期, 借方科目, 借方金額, 貸方科目, 貸方金額, 說明 (or similar)
        
        df.columns = [str(c).strip() for c in df.columns]
        
        col_map = {}
        # Dynamic Mapping
        for c in df.columns:
            if '日期' in c: col_map[c] = '日期'
            elif '借方科目' in c or ('借方' in c and '金額' not in c): col_map[c] = '借方科目'
            elif '借方金額' in c: col_map[c] = '借方金額'
            elif '貸方科目' in c or ('貸方' in c and '金額' not in c): col_map[c] = '貸方科目'
            elif '貸方金額' in c: col_map[c] = '貸方金額'
            elif '說明' in c or '摘要' in c: col_map[c] = '說明'
            
        df = df.rename(columns=col_map)
        
        # Validation checks
        required = ['日期', '借方科目', '借方金額', '貸方科目', '貸方金額']
        missing = [req for req in required if req not in df.columns]
        
        # If headers are missing, try positional if 6 columns exist
        if missing and len(df.columns) >= 6:
            # Assume standard format: Date, DrAcct, DrAmt, CrAcct, CrAmt, Note
            df.columns.values[0] = '日期'
            df.columns.values[1] = '借方科目'
            df.columns.values[2] = '借方金額'
            df.columns.values[3] = '貸方科目'
            df.columns.values[4] = '貸方金額'
            df.columns.values[5] = '說明'
            missing = []
            
        if missing:
            return f"缺少必要欄位: {', '.join(missing)}"
        
        transactions = []
        
        for index, row in df.iterrows():
            if pd.isna(row.get('日期')): continue
            
            tx_type = identify_transaction_type(row)
            
            if not tx_type:
                continue
                
            note = str(row.get('說明', ''))
            date_val = row['日期']
            
            # Date Parsing
            if isinstance(date_val, str):
                try:
                    date_obj = datetime.strptime(date_val, '%Y/%m/%d')
                except:
                    try:
                        date_obj = datetime.strptime(date_val, '%Y-%m-%d')
                    except:
                        # Continue or use today? Use today with warning? 
                        # Better to skip or flag. Using today as safe fallback for now.
                        date_obj = datetime.now()
            else:
                date_obj = date_val
                
            amount = 0
            account = ""
            main_cat = ""
            sub_cat = ""
            
            if tx_type == 'Income':
                account = normalize_account_name(row['借方科目'])
                try:
                    amount = float(row['借方金額']) if not pd.isna(row['借方金額']) else 0
                except: amount = 0
                cat_source = row.get('貸方科目', '')
                main_cat, sub_cat = normalize_category(cat_source, 'Income', note)
                
            elif tx_type == 'Expense':
                account = normalize_account_name(row.get('貸方科目', ''))
                try:
                    amount = float(row['貸方金額']) if not pd.isna(row['貸方金額']) else 0
                except: amount = 0
                cat_source = row.get('借方科目', '')
                main_cat, sub_cat = normalize_category(cat_source, 'Expense', note)
            
            elif tx_type == 'Transfer':
                continue
                
            if amount > 0:
                transactions.append({
                    'date': date_obj,
                    'type': '收入' if tx_type == 'Income' else '支出',
                    'category': main_cat,
                    'subcategory': sub_cat,
                    'account': account,
                    'amount': amount,
                    'note': note
                })
                
        return pd.DataFrame(transactions)
        
    except Exception as e:
        return str(e)
