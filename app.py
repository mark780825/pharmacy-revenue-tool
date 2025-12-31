import streamlit as st

import pandas as pd

from datetime import datetime

import database as db

import utils

import altair as alt





# 初始化資料庫

# @st.cache_resource (Removed to ensure schema migration runs)

def init_app_db():

    db.init_db()



# Call explicit init

db.init_db()



st.set_page_config(page_title="藥局營收管理工具", layout="wide")



st.title("藥局營收管理工具")



# Initialize Session State

if 'logged_in' not in st.session_state:

    st.session_state['logged_in'] = False

if 'role' not in st.session_state:

    st.session_state['role'] = None

if 'username' not in st.session_state:

    st.session_state['username'] = None



# Sidebar Navigation & Login

with st.sidebar:

    if st.session_state['logged_in']:

        st.success(f"您好 {st.session_state['username']} ({st.session_state['role']})")
        st.caption("v1.6 (Cloud Optimized)")

        if st.button("登出", type="secondary"):

            st.session_state['logged_in'] = False

            st.session_state['role'] = None

            st.session_state['username'] = None

            st.rerun()

            

        st.divider()

        

        # Navigation Options based on Role

        options = ["每日 記帳 (Data Entry)", "結帳工具 (Checkout Tool)"]

        if st.session_state['role'] == 'admin':

            options.append("一般帳務分析 (General Analysis)")

            options.append("每月 結算 (Monthly Closing)")

            options.append("健保營收分析 (NHI Analysis)")



            

        page = st.selectbox("功能選單", options)

        

    else:

        st.header("登入系統")

        username = st.text_input("帳號")

        password = st.text_input("密碼", type="password")

        if st.button("登入", type="primary"):

            role = utils.verify_user(username, password)

            if role:

                st.session_state['logged_in'] = True

                st.session_state['role'] = role

                st.session_state['username'] = username

                st.rerun()

            else:

                st.error("帳號或密碼錯誤")

        page = None # No page access if not logged in



# Main Content

if not st.session_state['logged_in']:

    st.info("提示 請先從左側登入系統以開始使用")

    st.stop()  # Stop execution here if not logged in



# Only proceed if logged in

if page == "每日 記帳 (Data Entry)":

    st.header("每日收支紀錄")

    

    col1, col2 = st.columns(2)

    

    with col1:
        date = st.date_input("日期", datetime.now())
        tx_type = st.radio("類型", ["收入", "支出", "資金調度"], horizontal=True)
        
        if tx_type == "收入":
            main_cat = st.selectbox("主類別", list(utils.INCOME_CATEGORIES.keys()))
            sub_cat_options = list(utils.INCOME_CATEGORIES[main_cat].keys())
            sub_cat = st.selectbox("子類別", sub_cat_options)
            account_from = None
        elif tx_type == "支出":
            # Expense
            expense_cats = [k for k in utils.EXPENSE_CATEGORIES.keys() if k != "帳戶類別"]
            main_cat = st.selectbox("主科目", expense_cats)
            sub_cat_options = utils.EXPENSE_CATEGORIES.get(main_cat, [])
            if sub_cat_options:
                sub_cat = st.selectbox("子類別", sub_cat_options)
            else:
                sub_cat = None
            account_from = None
        else:
            # 資金調度 (Transfer)
            st.info("ℹ️ 資金調度：僅調整帳戶餘額，不影響損益計算。")
            main_cat = "資金調度"
            sub_cat = ""
            
            # Show "From" Account here in Col 1
            account_options = utils.ACCOUNT_TYPES
            account_from = st.selectbox("轉出帳戶 (From)", account_options, key="acc_from")

    with col2:
        account_options = utils.ACCOUNT_TYPES
        
        if tx_type == "資金調度":
             # Show "To" Account
             # remove the 'from' account from options to avoid self-transfer?
             to_options = [x for x in account_options if x != account_from]
             to_options.append("提出") # Add Withdraw option
             account = st.selectbox("轉入帳戶 (To)", to_options, key="acc_to")
             
        else:
            # Normal Income/Expense Account Selection
            if st.session_state['role'] != 'admin':
                # Non-admin users can only select Cash
                account_options = ["現金"]
                
            account = st.selectbox("帳戶", account_options)

        amount = st.number_input("金額 (TWD)", min_value=0, step=1)
        note = st.text_input("備註")



    # Preview Calculation for Income

    net_amount = amount

    is_adjusted = False

    if tx_type == "收入" and sub_cat:

        net_amount, is_adjusted = utils.calculate_net_amount(main_cat, sub_cat, amount)

        if is_adjusted:

            st.info(f"提示 系統將自動扣除手續費: 輸入 {amount} -> 實帳 {net_amount:.2f}")



    # NHI Month Linking

    nhi_selected_month_str = None

    if tx_type == "收入" and main_cat == "健保收入" and sub_cat in ["健保一暫", "健保二暫"]:

        st.write("---")

        st.caption("健保申報月份關聯")

        

        # UI for Year/Month Selection (Reuse logic or keep simple)

        # Using a simpler approach here to save space or similar to previous

        nm_col1, nm_col2 = st.columns(2)

        today = datetime.now()

        # Default to previous month

        def_date = today.replace(day=1) - pd.Timedelta(days=1)

        

        with nm_col1:

            n_year = st.selectbox("申報年份", range(today.year - 2, today.year + 2), index=2, key="nhi_tx_year")

        with nm_col2:

            n_month = st.selectbox("申報月份", range(1, 13), index=def_date.month-1, key="nhi_tx_month")

            

        nhi_selected_month_str = f"{n_year}-{n_month:02d}"



    if st.button("登入", type="primary"):

        if amount > 0:

            if tx_type == "資金調度":
                # Create transactions for transfer
                
                # 1. Transfer Out (Always happens)
                # Note logic: If withdrawal, note is just "Withdrawal". If internal transfer, note "Transfer to X".
                note_out = f"{note} (提出)" if account == "提出" else f"{note} (轉入 {account})"
                
                db.add_transaction(
                    date=date,
                    type="資金調度",
                    category="轉出",
                    subcategory="",
                    account=account_from,
                    amount=amount,
                    original_amount=None,
                    note=note_out,
                    nhi_month=""
                )
                
                # 2. Transfer In (Only if NOT '提出')
                if account != "提出":
                    db.add_transaction(
                        date=date,
                        type="資金調度",
                        category="轉入",
                        subcategory="",
                        account=account, # This is 'account_to' from UI
                        amount=amount,
                        original_amount=None,
                        note=f"{note} (來自 {account_from})",
                        nhi_month=""
                    )
                
            else:
                # Normal Transaction
                db.add_transaction(
                    date=date,
                    type=tx_type,
                    category=main_cat,
                    subcategory=sub_cat if sub_cat else "",
                    account=account,
                    amount=net_amount,
                    original_amount=amount if is_adjusted else None,
                    note=note,
                    nhi_month=nhi_selected_month_str
                )

            st.success("紀錄已新增")

        else:

            st.error("帳號或密碼錯誤")



    st.divider()

    st.subheader("今日紀錄")

    df_today = db.get_transactions(start_date=date, end_date=date)

    if not df_today.empty:

        # Prepare dataframe for editing
        df_today_edit = df_today.copy()
        df_today_edit['刪除'] = False
        
        # Reorder columns to put '刪除' first
        cols = ['刪除', 'id', 'type', 'category', 'subcategory', 'account', 'amount', 'note']
        df_today_edit = df_today_edit[cols]

        edited_df = st.data_editor(
            df_today_edit,
            column_config={
                "刪除": st.column_config.CheckboxColumn(
                    "刪除",
                    help="勾選以刪除此筆紀錄",
                    default=False,
                ),
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "type": st.column_config.TextColumn("類型", disabled=True),
                "category": st.column_config.TextColumn("主類別", disabled=True),
                "subcategory": st.column_config.TextColumn("子類別", disabled=True),
                "account": st.column_config.TextColumn("帳戶", disabled=True),
                "amount": st.column_config.NumberColumn("金額", disabled=True),
                "note": st.column_config.TextColumn("備註", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="editor_today"
        )
        
        st.markdown("")
        if st.button("刪除所選紀錄 (Delete Selected)", type="secondary"):
             # Filter rows where '刪除' is True
             to_delete = edited_df[edited_df['刪除'] == True]
             if not to_delete.empty:
                 count = 0
                 for index, row in to_delete.iterrows():
                     # Use the ID to delete
                     try:
                         db.delete_transaction(row['id'])
                         count += 1
                     except Exception as e:
                         st.error(f"刪除 ID {row['id']} 失敗: {e}")
                 
                 if count > 0:
                     st.success(f"成功刪除 {count} 筆紀錄")
                     st.rerun()
             else:
                 st.info("請先勾選欲刪除的紀錄")


elif page == "結帳工具 (Checkout Tool)":
    st.header("門市結帳工具")
    st.caption("依照早班/晚班流程輸入，系統將自動計算營收並彙整寫入帳本")

    # Date Selection
    check_date = st.date_input("結帳日期", datetime.now())

    # --- Session State for Temp Items ---
    if 'co_exp_m' not in st.session_state: st.session_state['co_exp_m'] = []
    if 'co_inc_m' not in st.session_state: st.session_state['co_inc_m'] = []
    if 'co_exp_e' not in st.session_state: st.session_state['co_exp_e'] = []
    if 'co_inc_e' not in st.session_state: st.session_state['co_inc_e'] = []

    # --- Helper Functions ---
    def add_exp(target_list_name, cat, subcat, amt, note):
        if amt > 0:
            st.session_state[target_list_name].append({
                "category": cat,
                "subcategory": subcat,
                "amount": amt,
                "note": note
            })
    
    def add_inc(target_list_name, cat, subcat, amt, note, account):
        if amt > 0:
            st.session_state[target_list_name].append({
                "category": cat,
                "subcategory": subcat,
                "amount": amt,
                "note": note,
                "account": account
            })

    def remove_item(target_list_name, idx):
        st.session_state[target_list_name].pop(idx)

    def render_list(list_name, is_income=False):
        items = st.session_state[list_name]
        if items:
            df = pd.DataFrame(items)
            # Add simple index for removal
            for i, row in enumerate(items):
                col_str = f"{row['category']} - {row['subcategory']} ${row['amount']}"
                if is_income:
                   col_str += f" ({row['account']})"
                
                c1, c2 = st.columns([0.8, 0.2])
                c1.text(col_str)
                if c2.button("刪除", key=f"del_{list_name}_{i}"):
                    remove_item(list_name, i)
                    st.rerun()
            return sum(item['amount'] for item in items)
        return 0

    st.divider()

    # --- Step 1: Morning Shift (早班) ---
    st.subheader("☀️ 早班 (下午結帳)")
    
    c_m1, c_m2, c_m3 = st.columns(3)
    with c_m1:
        hold_A = st.number_input("承 (A) - 昨日交接金", value=26850, step=100, help="預設 26850")
    with c_m2:
        handover_B = st.number_input("交 (B) - 早班實點金額", min_value=0, step=100)

    with st.expander("早班 - 支出明細 (C)", expanded=True):
        # Input Form
        ec1, ec2, ec3 = st.columns([2, 2, 1])
        with ec1:
            e_main = st.selectbox("主科目", [k for k in utils.EXPENSE_CATEGORIES.keys() if k != "帳戶類別"], key="m_e_main")
        with ec2:
            e_sub = st.selectbox("子類別", utils.EXPENSE_CATEGORIES.get(e_main, []), key="m_e_sub")
        with ec3:
            e_amt = st.number_input("金額", min_value=0, key="m_e_amt")
            e_note = st.text_input("備註", key="m_e_note")
        
        if st.button("加入早班支出", key="add_m_exp"):
            add_exp('co_exp_m', e_main, e_sub, e_amt, e_note)
            st.rerun()

        # List
        total_exp_m = render_list('co_exp_m')
        st.caption(f"早班支出總計: ${total_exp_m}")

    with st.expander("早班 - 非現金收入 (LinePay/刷卡/銀行)", expanded=False):
        ic1, ic2, ic3 = st.columns([2, 2, 1])
        with ic1:
            # Only Non-Cash Categories? User said "Non-Cash Income"
            # Usually '銷貨收入' -> 'Line Pay', 'Credit Card', 'Bank'
            i_main = "銷貨收入"
            # Filter utility keys for relevant ones
            non_cash_subs = ["Line Pay收入", "信用卡收入", "銀行收入"]
            i_sub = st.selectbox("項目", non_cash_subs, key="m_i_sub")
        with ic2:
            # Account mapping? User said "Account... same as Daily Record".
            # For Non-Cash, Account is usually "銀行" or "現金"? 
            # Actually LinePay/CreditCard usually go to Bank?
            # User image shows "非現金收入".
            # Let's let them choose Account, default to Bank for non-cash.
            i_acc = st.selectbox("入帳帳戶", ["銀行", "現金"], index=0, key="m_i_acc")
        with ic3:
            i_amt = st.number_input("金額", min_value=0, key="m_i_amt")
            i_note = st.text_input("備註", key="m_i_note")
            
        if st.button("加入早班收入", key="add_m_inc"):
            add_inc('co_inc_m', i_main, i_sub, i_amt, i_note, i_acc)
            st.rerun()
            
        total_inc_nano_m = render_list('co_inc_m', is_income=True)
        st.caption(f"早班非現金收入總計: ${total_inc_nano_m}")

    # Calculate Morning Revenue (Ref: B + C + NonCash - A)
    # Revenue D = (Handover B + Expense C + NonCash) - Hold A
    # Wait, B is Cash Handover.
    # Revenue = (New Cash B - Old Cash A) + Expenses C + NonCash
    # formula image: B+C-A = D (This assumes D is TOTAL revenue? Or Cash Revenue?)
    # Image says: "非現金收入(C)" ... wait image labels are reused.
    # Image 1: Morning: "交+支-承=營 (B+C-A=D)"
    # Image 2: Morning Non-Cash is separate column?
    # Let's follow Image 2 Formula: "交(B) + 支(D) + 非現金(C) - 承(A) = 營(E)"
    # Note labels in app: B=Handover(Cash), C=TotalExp, NonCash=TotalNonCash
    revenue_m = (handover_B + total_exp_m + total_inc_nano_m) - hold_A
    st.info(f"早班推算營收: ${revenue_m:,.0f} (公式: 交{handover_B} + 支{total_exp_m} + 非現金{total_inc_nano_m} - 承{hold_A})")

    st.divider()

    # --- Step 2: Evening Shift (晚班) ---
    st.subheader("🌙 晚班 (晚上結帳)")

    c_e1, c_e2, c_e3 = st.columns(3)
    with c_e1:
        st.metric("承 (B) - 早班交接", f"${handover_B}")
    with c_e2:
        handover_F = st.number_input("交 (F) - 晚班實點金額", min_value=0, step=100)

    with st.expander("晚班 - 支出明細 (H)", expanded=True):
        ec1, ec2, ec3 = st.columns([2, 2, 1])
        with ec1:
            e_main2 = st.selectbox("主科目", [k for k in utils.EXPENSE_CATEGORIES.keys() if k != "帳戶類別"], key="e_e_main")
        with ec2:
            e_sub2 = st.selectbox("子類別", utils.EXPENSE_CATEGORIES.get(e_main2, []), key="e_e_sub")
        with ec3:
            e_amt2 = st.number_input("金額", min_value=0, key="e_e_amt")
            e_note2 = st.text_input("備註", key="e_e_note")
        
        if st.button("加入晚班支出", key="add_e_exp"):
            add_exp('co_exp_e', e_main2, e_sub2, e_amt2, e_note2)
            st.rerun()

        total_exp_e = render_list('co_exp_e')
        st.caption(f"晚班支出總計: ${total_exp_e}")

    with st.expander("晚班 - 非現金收入 (G)", expanded=False):
        ic1, ic2, ic3 = st.columns([2, 2, 1])
        with ic1:
            i_main2 = "銷貨收入"
            i_sub2 = st.selectbox("項目", non_cash_subs, key="e_i_sub")
        with ic2:
            i_acc2 = st.selectbox("入帳帳戶", ["銀行", "現金"], index=0, key="e_i_acc")
        with ic3:
            i_amt2 = st.number_input("金額", min_value=0, key="e_i_amt")
            i_note2 = st.text_input("備註", key="e_i_note")
            
        if st.button("加入晚班收入", key="add_e_inc"):
            add_inc('co_inc_e', i_main2, i_sub2, i_amt2, i_note2, i_acc2)
            st.rerun()
            
        total_inc_nano_e = render_list('co_inc_e', is_income=True)
        st.caption(f"晚班非現金收入總計: ${total_inc_nano_e}")

    # Revenue I = (Handover F + Expense H + NonCash G) - Handover B
    revenue_e = (handover_F + total_exp_e + total_inc_nano_e) - handover_B
    st.info(f"晚班推算營收: ${revenue_e:,.0f} (公式: 交{handover_F} + 支{total_exp_e} + 非現金{total_inc_nano_e} - 承{handover_B})")

    st.divider()

    # --- Step 3: Daily Settlement (日結) ---
    st.subheader("🏁 日結算 (End of Day)")
    
    # Total Calculation
    # Formula Image 2:
    # J (Next Day Hold, Default 26850)
    # K (Withdrawal/Refill) = F - J
    # Total Exp M = D+H
    # Total Rev N = J + L + M + K - A
    # Wait, J+K = F. So F + L + M - A.
    # L = Total Non-Cash (C+G)
    # M = Total Exp (D+H)
    # A = Start Hold
    
    hold_J = st.number_input("明日備用金 (J)", value=26850, step=100)
    
    withdrawal_K = handover_F - hold_J
    
    total_non_cash_L = total_inc_nano_m + total_inc_nano_e
    total_exp_M = total_exp_m + total_exp_e
    
    total_daily_revenue_N = (hold_J + withdrawal_K + total_non_cash_L + total_exp_M) - hold_A
    
    # Validation
    # Cash Income (Implied) = (Handover F - Start A) + Total Exp + Withdrawal?
    # Actually Cash Revenue = (F - A) + Total Exp.  (Assuming non-cash didn't touch cash drawer)
    # Wait, if withdrawal K exists, it came out of F? 
    # Logic: F is "Actual Count BEFORE Withdrawal"?
    # Image 2 says: "交給隔天的金額(J)...額外的錢提出(K)...交(F)" is not explicitly linked but implied J+K = F?
    # Or is F the count result, and we split F into J and K?
    # Yes, "若餘額不足...內提".
    # So F is the physical cash present. We split it into J (keep) and K (take out).
    
    c_f1, c_f2 = st.columns(2)
    with c_f1:
        if withdrawal_K > 0:
             st.success(f"💰 應提出金額 (K): ${withdrawal_K:,.0f}")
        elif withdrawal_K < 0:
             st.error(f"⚠️ 應內提補足 (K): ${abs(withdrawal_K):,.0f}")
        else:
             st.info("金額剛好，無須提領或補足。")
             
    with c_f2:
        st.metric("當日總營收 (N)", f"${total_daily_revenue_N:,.0f}", help=f"公式: 交{handover_F} + 非現金{total_non_cash_L} + 總支出{total_exp_M} - 期初{hold_A}")

    if st.button("確認結帳並寫入每日帳務 (Confirm & Save)", type="primary"):
        if total_daily_revenue_N != (revenue_m + revenue_e):
            st.warning(f"⚠️ 警告：早晚班營收加總 ({revenue_m + revenue_e}) 與日結總營收 ({total_daily_revenue_N}) 不符，請檢查輸入數據。")
        else:
            # 1. Aggregate Expenses
            all_expenses = st.session_state['co_exp_m'] + st.session_state['co_exp_e']
            # Group by (Category, Subcategory)
            exp_groups = {}
            for x in all_expenses:
                key = (x['category'], x['subcategory'])
                if key not in exp_groups:
                    exp_groups[key] = {'amount': 0, 'notes': []}
                exp_groups[key]['amount'] += x['amount']
                if x['note']: exp_groups[key]['notes'].append(x['note'])
            
            # Write Expenses
            for (cat, sub), data in exp_groups.items():
                final_note = " | ".join(data['notes'])
                # Suffix to note to indicate source
                final_note = f"[結帳] {final_note}"
                db.add_transaction(
                    date=check_date,
                    type="支出",
                    category=cat,
                    subcategory=sub,
                    account="現金", # Expenses paid from Cash Drawer
                    amount=data['amount'],
                    original_amount=None,
                    note=final_note,
                    nhi_month=""
                )
            
            # 2. Aggregate Non-Cash Income
            all_income = st.session_state['co_inc_m'] + st.session_state['co_inc_e']
            # Group by (Category, Subcategory, Account)
            inc_groups = {}
            for x in all_income:
                key = (x['category'], x['subcategory'], x['account'])
                if key not in inc_groups:
                    inc_groups[key] = {'amount': 0, 'notes': []}
                inc_groups[key]['amount'] += x['amount']
                if x['note']: inc_groups[key]['notes'].append(x['note'])

            # Write Non-Cash Income
            for (cat, sub, acc), data in inc_groups.items():
                final_note = " | ".join(data['notes'])
                final_note = f"[結帳] {final_note}"
                # Calculate net? The add_transaction or calculate_net_amount logic usually handles checking rates.
                # But here we are bulk adding. 
                # Should we apply rate? Yes.
                # calculate_net_amount(cat, sub, amount) -> (net, adjusted)
                # But we are calling db.add_transaction directly.
                # We should replicate the logic or call helper.
                # Reuse util logic?
                net_amt, _ = utils.calculate_net_amount(cat, sub, data['amount'])
                
                db.add_transaction(
                    date=check_date,
                    type="收入",
                    category=cat,
                    subcategory=sub,
                    account=acc,
                    amount=net_amt,
                    original_amount=data['amount'] if net_amt != data['amount'] else None,
                    note=final_note,
                    nhi_month=""
                )

            # 3. Calculate and Write "Cash Sales Income"
            # Cash Revenue = Total Daily Revenue - Total Non-Cash (L)
            # Or derived from Cash Flow: (F - A) + Total Exp - (Inner Refill if any? No, F is final cash).
            # Let's stick to: Cash Sales = Total Revenue N - NonCash L
            # Wait, N = F + L + M - A
            # Cash Sales = (F + L + M - A) - L = F + M - A.
            # F (Night Handover) + M (Expenses Paid) - A (Start Hold)
            cash_sales = handover_F + total_exp_M - hold_A
            
            if cash_sales > 0:
                db.add_transaction(
                    date=check_date,
                    type="收入",
                    category="銷貨收入",
                    subcategory="現金收入",
                    account="現金",
                    amount=cash_sales,
                    original_amount=None,
                    note="[結帳] 當日現金營收",
                    nhi_month=""
                )
            elif cash_sales < 0:
                # Negative Revenue? Possible if errors or huge refund?
                st.error(f"計算出現金營收為負數 (${cash_sales})，請檢查交接金額是否正確。")
                st.stop()
            
            # 4. Clear State
            st.session_state['co_exp_m'] = []
            st.session_state['co_inc_m'] = []
            st.session_state['co_exp_e'] = []
            st.session_state['co_inc_e'] = []
            
            st.success("✅ 結帳完成！所有帳務已寫入資料庫。")


elif page == "一般帳務分析 (General Analysis)":

    st.header("一般帳務分析")

    # Mode Selection
    analysis_mode = st.radio(
        "分析模式", 
        ["帳務細目分析 (每一筆收支加總)", "實際月營收 (每月結算餘額比較)"], 
        horizontal=True
    )

    if analysis_mode == "帳務細目分析 (每一筆收支加總)":
        
        st.caption("加總此區間內每一筆「收入」與「支出」紀錄來計算損益。")

        col1, col2 = st.columns(2)

        with col1:

            start_date = st.date_input("開始日期", datetime(datetime.now().year, datetime.now().month, 1))

        with col2:

            end_date = st.date_input("結束日期", datetime.now())



        if start_date <= end_date:

            df = db.get_transactions(start_date=start_date, end_date=end_date)

            

            if not df.empty:

                # KPI Cards
                # Exclude Owner's Equity
                total_income = df[(df['type'] == '收入') & (df['category'] != '業主資本')]['amount'].sum()

                total_expense = df[df['type'] == '支出']['amount'].sum()

                net_profit = total_income - total_expense

                

                kpi1, kpi2, kpi3 = st.columns(3)

                kpi1.metric("總收入", f"${total_income:,.0f}")

                kpi2.metric("總支出", f"${total_expense:,.0f}")

                kpi3.metric("淨利", f"${net_profit:,.0f}", delta_color="normal")

                

                st.divider()

                

                # Charts

                c1, c2 = st.columns(2)

                

                with c1:

                    st.subheader("收入分析 (依子科目)")

                    income_df = df[(df['type'] == '收入') & (df['category'] != '業主資本')]

                    if not income_df.empty:

                        income_chart = income_df.groupby('subcategory')['amount'].sum()

                        st.bar_chart(income_chart)

                    else:

                        st.write("無收入資料")

                

                with c2:

                    st.subheader("支出分析 (依主科目)")

                    expense_df = df[df['type'] == '支出']

                    if not expense_df.empty:

                        expense_chart = expense_df.groupby('category')['amount'].sum()

                        st.bar_chart(expense_chart)

                    else:

                        st.write("無支出資料")



                st.divider()

                st.subheader("詳細交易紀錄")

                

                # Show dataframe with ID for reference

                st.dataframe(df, use_container_width=True)



                # Export Button

                csv = df.to_csv(index=False).encode('utf-8-sig')

                st.download_button(

                    label="匯出 資料 (CSV)",

                    data=csv,

                    file_name=f'pharmacy_revenue_{start_date}_{end_date}.csv',

                    mime='text/csv',

                )

            else:

                st.info("此日期區間無資料")
        else:
             st.error("開始日期不能晚於結束日期")

    else:
        # Actual Monthly Revenue Mode
        st.subheader("實際月營收分析")
        st.caption("透過比較「每月結算」的期末餘額，計算實際現金流增減。可檢視包含資金調度等所有影響後的最終獲利。")
        
        # Date Selection (Year/Month Range)
        c1, c2, c3, c4 = st.columns(4)
        today = datetime.now()
        year_opts = list(range(today.year - 3, today.year + 2))
        month_opts = list(range(1, 13))
        
        with c1:
            start_year = st.selectbox("開始年份", year_opts, index=year_opts.index(today.year), key="mr_sy")
        with c2:
            start_month = st.selectbox("開始月份", month_opts, index=0, key="mr_sm")
        with c3:
            end_year = st.selectbox("結束年份", year_opts, index=year_opts.index(today.year), key="mr_ey")
        with c4:
            end_month = st.selectbox("結束月份", month_opts, index=today.month-1, key="mr_em")
            
        start_str = f"{start_year}-{start_month:02d}"
        end_str = f"{end_year}-{end_month:02d}"
        
        if start_str > end_str:
            st.error("開始月份不能晚於結束月份")
        else:
            # Logic: We need Closing of (Start Month - 1) as "Opening Balance"
            # And Closings of all months in range.
            
            # Calculate Previous Month
            start_date_obj = datetime(start_year, start_month, 1)
            prev_month_date = start_date_obj - pd.Timedelta(days=1)
            prev_month_str = prev_month_date.strftime("%Y-%m")
            
            # Fetch all closings from prev_month to end_month
            df_closings = db.get_closings_range(prev_month_str, end_str)
            
            if df_closings.empty:
                st.warning("在此區間內找不到任何結算資料。請確認是否已至「每月 結算」功能執行結帳。")
            else:
                # Check for missing months
                # Generate expected list (inclusive of prev_month for calculation basis)
                expected_months = []
                curr = prev_month_date.replace(day=1) # Start from prev month
                end_date_obj = datetime(end_year, end_month, 1)
                
                while curr <= end_date_obj:
                    expected_months.append(curr.strftime("%Y-%m"))
                    # Next month
                    if curr.month == 12:
                        curr = datetime(curr.year + 1, 1, 1)
                    else:
                        curr = datetime(curr.year, curr.month + 1, 1)
                        
                found_months = df_closings['month'].tolist()
                missing = [m for m in expected_months if m not in found_months]
                
                if missing:
                    st.warning(f"⚠️ 注意：缺少以下月份的結算資料，分析結果可能不準確：{', '.join(missing)}")
                    
                # Process Data
                # We need to calculate Profit = (This Month Total) - (Prev Month Total) - (Owner Injection)
                df_closings['Total'] = df_closings['bank_actual'] + df_closings['cash_actual']
                df_closings['Prev_Total'] = df_closings['Total'].shift(1)
                df_closings['Gross_Change'] = df_closings['Total'] - df_closings['Prev_Total']
                
                # Fetch Owner's Capital Injections for the period
                # Construct exact dates for query
                t_start_date = datetime(start_year, start_month, 1)
                # End date: last day of end_month
                if end_month == 12:
                    t_end_date = datetime(end_year + 1, 1, 1) - pd.Timedelta(days=1)
                else:
                    t_end_date = datetime(end_year, end_month + 1, 1) - pd.Timedelta(days=1)
                
                df_tx = db.get_transactions(start_date=t_start_date, end_date=t_end_date)
                
                # Init columns via mapping to ensure correct alignment without merge suffix issues
                
                # Default to 0.0
                capital_series = pd.Series(0.0, index=df_closings['month'])
                withdrawal_series = pd.Series(0.0, index=df_closings['month'])

                if not df_tx.empty:
                    df_tx['month'] = df_tx['date'].dt.strftime('%Y-%m')

                    # 1. Capital Injection (Owner)
                    mask_cap = (df_tx['category'] == '業主資本') & (df_tx['subcategory'] == '一般投入')
                    df_cap = df_tx[mask_cap].copy()
                    
                    if not df_cap.empty:
                         # Group by month and sum
                         cap_grouped = df_cap.groupby('month')['amount'].sum()
                         # Align with df_closings['month']
                         # We can use map.
                         capital_series = df_closings['month'].map(cap_grouped).fillna(0.0)

                    # 2. Capital Withdrawal (資金調度 - 提出)
                    # Logic: Type="資金調度", Category="轉出", Note contains "(提出)"
                    mask_withdraw = (df_tx['type'] == '資金調度') & (df_tx['category'] == '轉出') & (df_tx['note'].str.contains(r'\(提出\)', na=False))
                    df_withdraw = df_tx[mask_withdraw].copy()
                    
                    if not df_withdraw.empty:
                        with_grouped = df_withdraw.groupby('month')['amount'].sum()
                        withdrawal_series = df_closings['month'].map(with_grouped).fillna(0.0)
                
                df_closings['Capital_Injection'] = capital_series.values
                df_closings['Withdrawal'] = withdrawal_series.values

                # Net Profit = Gross Change - Capital Injection + Withdrawal
                # (Gross Change = Total - Prev Total. Withdrawal reduces Total. So we add it back to neutralize.)
                df_closings['Net_Profit'] = df_closings['Gross_Change'] - df_closings['Capital_Injection'] + df_closings['Withdrawal']
                
                # Filter out the 'prev_month' row from display, only show target range
                df_result = df_closings[df_closings['month'] >= start_str].copy()
                
                if not df_result.empty:
                    # Total Period Profit
                    # Logic: Sum of Net_Profit in the period
                    total_profit = df_result['Net_Profit'].sum()
                    
                    st.metric(f"區間總獲利 ({start_str} ~ {end_str})", f"${total_profit:,.0f}", help="區間期末總資產 - 區間期初總資產 - 業主投入 + 資金提出")
                    st.divider()
                    
                    # Chart
                    st.subheader("每月獲利趨勢")
                    if not df_result['Net_Profit'].isna().all():
                        st.bar_chart(df_result.set_index('month')['Net_Profit'])
                    else:
                        st.info("無法產生圖表 (資料不足)")
                    
                    # Table
                    st.subheader("詳細數據")
                    tbl = df_result[['month', 'Prev_Total', 'Total', 'Gross_Change', 'Capital_Injection', 'Withdrawal', 'Net_Profit']].copy()
                    tbl.columns = ['月份', '期初餘額 (上期末)', '期末總資產', '資產增減', '扣除業主投入', '加回資金提出', '實際獲利']
                    
                    st.dataframe(tbl.style.format({
                        '期初餘額 (上期末)': '${:,.0f}', 
                        '期末總資產': '${:,.0f}', 
                        '資產增減': '${:,.0f}',
                        '扣除業主投入': '${:,.0f}',
                        '加回資金提出': '${:,.0f}',
                        '實際獲利': '${:,.0f}'
                    }).applymap(lambda v: 'color: red;' if v < 0 else 'color: green;', subset=['實際獲利']), use_container_width=True)
                else:
                    st.info("尚無目標月份的完整結算資料 (可能缺上個月的期末餘額)。")



elif page == "每月 結算 (Monthly Closing)":

    st.header("每月結算")

    

    # 1. Select Month

    col1, col2 = st.columns(2)

    with col1:

        # Default to previous month

        today = datetime.now()

        last_month_date = today.replace(day=1) - pd.Timedelta(days=1)

        

        # UI for Year/Month Selection

        m_year, m_month = st.columns(2)

        with m_year:

            current_year = today.year

            # Year range: Current year - 3 to Current year + 1

            year_options = list(range(current_year - 3, current_year + 2))

            selected_year = st.selectbox("年份", year_options, index=year_options.index(last_month_date.year), key="mc_year")

            

        with m_month:

            month_options = list(range(1, 13))

            selected_month = st.selectbox("月份", month_options, index=month_options.index(last_month_date.month), key="mc_month")

            

        selected_month_str = f"{selected_year}-{selected_month:02d}"

        

        # Calculate Start/End Date for Query

        m_start = datetime(selected_year, selected_month, 1)

        # Handle end of month - simplest way to get next month 1st - 1 day

        if selected_month == 12:

            m_end = datetime(selected_year + 1, 1, 1) - pd.Timedelta(days=1)

        else:

            m_end = datetime(selected_year, selected_month + 1, 1) - pd.Timedelta(days=1)

            

    # 2. Get Previous Closing (REMOVED: Rely on Transactions)

    # prev_closing = db.get_previous_closing(selected_month_str)

    

    start_bank = 0.0

    start_cash = 0.0

    

    st.info("ℹ️ 期初餘額說明：本月期初餘額將由「業主資本-上期結轉」交易紀錄決定。若為首月使用，請手動新增一筆「業主資本」收入作為開帳金額。")



    # 3. Calculate This Month's Flow

    df_month = db.get_transactions(start_date=m_start, end_date=m_end)

    

    flow_bank = 0.0

    flow_cash = 0.0

    

    if not df_month.empty:

        # Bank Income

        flow_bank += df_month[(df_month['type']=='收入') & (df_month['account']=='銀行')]['amount'].sum()

        # Bank Expense

        flow_bank -= df_month[(df_month['type']=='支出') & (df_month['account']=='銀行')]['amount'].sum()

        

        # Cash Income

        flow_cash += df_month[(df_month['type']=='收入') & (df_month['account']=='現金')]['amount'].sum()

        # Cash Expense
        flow_cash -= df_month[(df_month['type']=='支出') & (df_month['account']=='現金')]['amount'].sum()
        
        # Transfers (Adjust Balances)
        # Bank Transfer In
        flow_bank += df_month[(df_month['type']=='資金調度') & (df_month['category']=='轉入') & (df_month['account']=='銀行')]['amount'].sum()
        # Bank Transfer Out
        flow_bank -= df_month[(df_month['type']=='資金調度') & (df_month['category']=='轉出') & (df_month['account']=='銀行')]['amount'].sum()
        
        # Cash Transfer In
        flow_cash += df_month[(df_month['type']=='資金調度') & (df_month['category']=='轉入') & (df_month['account']=='現金')]['amount'].sum()
        # Cash Transfer Out
        flow_cash -= df_month[(df_month['type']=='資金調度') & (df_month['category']=='轉出') & (df_month['account']=='現金')]['amount'].sum()

    

    calc_bank = start_bank + flow_bank

    calc_cash = start_cash + flow_cash



    st.divider()

    

    # 4. Input Actual & Compare

    st.subheader(f"{selected_month_str} 結帳核對")

    

    # Load existing closing if any

    current_closing = db.get_closing(selected_month_str)

    existing_bank = calc_bank

    existing_cash = calc_cash

    existing_note = ""

    

    if current_closing:

        existing_bank = current_closing[1]

        existing_cash = current_closing[2]

        existing_note = current_closing[5]

        st.success(f"✅ 本月已於 {current_closing[6]} 結帳過。")



    c1, c2 = st.columns(2)

    

    with c1:

        st.markdown("### 🏦 銀行")

        st.metric("期初", f"{start_bank:,.0f}")

        st.metric("本月異動", f"{flow_bank:,.0f}")

        st.metric("系統計算應有", f"{calc_bank:,.0f}")

        

        actual_bank = st.number_input("銀行實際餘額", value=existing_bank, step=1.0)

        diff_bank = actual_bank - calc_bank

        if diff_bank != 0:

            st.error(f"差異: {diff_bank:,.0f}")

        else:

            st.success("無差異")



    with c2:

        st.markdown("### 💵 現金")

        st.metric("期初", f"{start_cash:,.0f}")

        st.metric("本月異動", f"{flow_cash:,.0f}")

        st.metric("系統計算應有", f"{calc_cash:,.0f}")

        

        actual_cash = st.number_input("現金實際餘額", value=existing_cash, step=1.0)

        diff_cash = actual_cash - calc_cash

        if diff_cash != 0:

            st.error(f"差異: {diff_cash:,.0f}")

        else:

            st.success("無差異")



    note = st.text_area("結帳備註", value=existing_note)

    

    if st.button("儲存結帳資料 (Save)", type="primary"):

        db.save_closing(selected_month_str, actual_bank, actual_cash, calc_bank, calc_cash, note)

        

        # Auto-Create Carryover for Next Month

        try:
            next_month_date = m_end + pd.Timedelta(days=1)
            
            # Simple Append (User can manage duplicates if they re-save)
            if actual_bank != 0:
                db.add_transaction(next_month_date, "收入", "業主資本", "上期結轉", "銀行", actual_bank, None, f"系統自動結轉 - {selected_month_str} 期末")
            
            if actual_cash != 0:
                db.add_transaction(next_month_date, "收入", "業主資本", "上期結轉", "現金", actual_cash, None, f"系統自動結轉 - {selected_month_str} 期末")
                
            st.success(f"結帳成功！已自動建立 {next_month_date.strftime('%Y-%m-%d')} 的期初結轉紀錄。")

        except Exception as e:
            st.error(f"自動結轉失敗: {e}")

        st.rerun()



elif page == "健保營收分析 (NHI Analysis)":

    st.header("健保營收分析")

    

    tab1, tab2 = st.tabs(["📝 資料登錄 (Data Entry)", "📊 分析報表 (Analysis)"])

    

    with tab1:

        st.subheader("每月健保申報資料登錄")

        

        # Month Selection

        today = datetime.now()

        last_month_date = today.replace(day=1) - pd.Timedelta(days=1)

        

        # UI for Year/Month Selection

        c_year, c_month = st.columns(2)

        with c_year:

            current_year = today.year

            # Year range: Current year - 3 to Current year + 1

            year_options = list(range(current_year - 3, current_year + 2))

            selected_year = st.selectbox("年份", year_options, index=year_options.index(last_month_date.year), key="mc_year")

            

        with c_month:

            month_options = list(range(1, 13))

            selected_month = st.selectbox("月份", month_options, index=month_options.index(last_month_date.month), key="mc_month")

            

        target_month_str = f"{selected_year}-{selected_month:02d}"

        

        # Load existing data if any

        # We need to implement get_nhi_records to filter by a single month or just get all and filter in python, 

        # or simplify and just use get_nhi_records(start, end)

        existing_recs = db.get_nhi_records(start_month=target_month_str, end_month=target_month_str)

        

        def_total = 0.0

        def_deduction = 0.0

        def_rejection = 0.0

        def_chronic = 0

        def_drug_fee = 0.0

        def_general = 0



        if not existing_recs.empty:

            rec = existing_recs.iloc[0]

            def_total = rec['total_fee']

            def_deduction = rec['deduction']

            def_rejection = rec['rejection']

            def_chronic = int(rec['chronic_count'])

            # Check if general_count exists (for backward compatibility if DB not reset)

            if 'general_count' in rec:

                 def_general = int(rec['general_count'])

            if 'drug_fee' in rec:

                 def_drug_fee = rec['drug_fee']

                 

            st.info(f"ℹ️ 已載入 {target_month_str} 的現有資料，最後更新: {rec['updated_at']}")

        

        col1, col2 = st.columns(2)

        with col1:

            total_fee = st.number_input("總調劑費 (核扣點值前)", value=def_total, step=1.0, help="申報 A")

            rejection = st.number_input("核刪費用", value=def_rejection, step=1.0, help="核刪 E")

            chronic_count = st.number_input("慢箋數量 (張)", value=def_chronic, step=1, help="當月慢箋總張數")

            

        with col2:

            drug_fee = st.number_input("健保藥費 (實支實付)", value=def_drug_fee, step=1.0, help="藥費")

            deduction = st.number_input("點值核扣金額", value=def_deduction, step=1.0, help="核扣 D")

            general_count = st.number_input("一般箋數量 (張)", value=def_general, step=1, help="當月一般箋總張數")

            

        # Real-time Verification Calc

        if total_fee > 0:

            # Formula: (Dispensing + Drug) - Deduction - Rejection

            actual_received = (total_fee + drug_fee) - deduction - rejection

            point_value = 1 - (deduction / total_fee)

            st.metric("試算實際點值 (Effective Point Value)", f"{point_value:.4f}", help="1 - (核扣 / 總調劑費)")

            st.metric("預估健保總收入", f"${actual_received:,.0f}", help="調劑費 + 藥費 - 核扣 - 核刪")

        

        if st.button("登入", type="primary"):

            db.save_nhi_record(target_month_str, total_fee, deduction, rejection, chronic_count, general_count, drug_fee)

            st.success(f"✅ {target_month_str} 資料已儲存！")

            st.rerun()



    with tab2:

        st.subheader("健保營收結構分析")

        

        # Date Selection with Year/Month only

        # Layout: Start Year | Start Month | -> | End Year | End Month

        st.write("選擇分析區間")

        sel_c1, sel_c2, sel_c3, sel_c4 = st.columns(4)

        

        current_year = datetime.now().year

        year_options = list(range(current_year - 3, current_year + 2))

        month_options = list(range(1, 13))

        

        with sel_c1:

            start_year = st.selectbox("開始年份", year_options, index=year_options.index(current_year), key="an_start_y")

        with sel_c2:

            start_month = st.selectbox("開始月份", month_options, index=0, key="an_start_m") # Default Jan

            

        with sel_c3:

            end_year = st.selectbox("結束年份", year_options, index=year_options.index(current_year), key="an_end_y")

        with sel_c4:

            end_month = st.selectbox("結束月份", month_options, index=datetime.now().month-1, key="an_end_m") # Default Current Month

            

        start_str = f"{start_year}-{start_month:02d}"

        end_str = f"{end_year}-{end_month:02d}"

        

        if start_str <= end_str:

            df_nhi = db.get_nhi_records(start_month=start_str, end_month=end_str)

            

            if not df_nhi.empty:

                # Ensure columns exist (handling potential schema lag or empty initial states)

                if 'drug_fee' not in df_nhi.columns:

                    df_nhi['drug_fee'] = 0.0

                if 'chronic_count' not in df_nhi.columns:

                     df_nhi['chronic_count'] = 0

                if 'general_count' not in df_nhi.columns:

                     df_nhi['general_count'] = 0

                     

                # Calculations

                df_nhi['drug_fee'].fillna(0, inplace=True)

                df_nhi['actual_received'] = df_nhi['total_fee'] + df_nhi['drug_fee'] - df_nhi['deduction'] - df_nhi['rejection']

                df_nhi['point_value'] = df_nhi.apply(lambda x: 1 - (x['deduction'] / x['total_fee']) if x['total_fee'] > 0 else 0, axis=1)

                

                # Chronic Income = Point Value * 75 * Chronic Count

                df_nhi['chronic_income'] = df_nhi['point_value'] * 75 * df_nhi['chronic_count']

                

                # General Income = Actual Received (Calculated) - Chronic Income - Drug Fee

                # Note: User's revenue model likely considers Drug Fee as cost-neutral or separate. 

                # If they want "Revenue Analysis", usually they care about Service Fee.

                # However, previous formula was: General Income = Actual Received - Chronic Income.

                # With Drug Fee added to Actual Received, we should probably subtract it to get pure "Service Income" for General?

                # The user asked: "Estimated General Prescription Revenue". 

                # Let's assume General Income = (Total Fee - Deduction - Rejection) - Chronic Income. 

                # Drug Fee is pass-through.

                # Let's keep logic simple: 

                # 1. Total Calculated Receivable = Dispensing + Drug - Deduction - Rejection

                # 2. Comparison with Real Accounting Data

                

                # For the "Revenue Structure" charts, usually Drug Fee is excluded if it's pass-through, or included if it's total revenue.

                # Given previous context, they tracked "Dispensing Fee Income".

                # Let's subtract Drug Fee from the "Income" metrics if they are meant to be pure profit/service fee?

                # Or keep them as total.

                # Let's stick to previous metric: "General Income" was derived from "Actual Received". 

                # Now Actual Received includes Drug Fee.

                # Let's adjust "General Income" to exclude Drug Fee to keep it consistent with "Dispensing Fee"?

                # Formula:

                # Total Service Fee (After deduction) = Total Fee - Deduction - Rejection

                # Chronic Service Fee = 75 * Point * Count

                # General Service Fee = Total Service Fee - Chronic Service Fee

                

                total_service_fee = df_nhi['total_fee'] - df_nhi['deduction'] - df_nhi['rejection']

                df_nhi['chronic_income'] = df_nhi['point_value'] * 75 * df_nhi['chronic_count']

                df_nhi['general_income'] = total_service_fee - df_nhi['chronic_income']

                

                # Metrics Display

                st.markdown("### 區間總結")

                m1, m2, m3, m4 = st.columns(4)

                m1.metric("預估健保淨額 (含藥費)", f"${df_nhi['actual_received'].sum():,.0f}")

                m2.metric("平均點值", f"{df_nhi['point_value'].mean():.4f}")

                m3.metric("慢箋調劑費總收入 (推估)", f"${df_nhi['chronic_income'].sum():,.0f}")

                m4.metric("一般箋調劑費總收入 (推估)", f"${df_nhi['general_income'].sum():,.0f}")

                

                st.divider()

                st.markdown("### 財務對帳 (預估 vs 實際入帳)")

                

                # Fetch actual accounting data for these months

                # We need to query transactions where nhi_month is in the list

                months = df_nhi['month'].tolist()

                # Determine date range for query optimization (though we need to filter by nhi_month column, not date)

                # Since we don't have an index on nhi_month or a direct query for it in `get_transactions` without modifying it substantially,

                # We can fetch all income transactions for a wider range or just fetch them all if dataset small, 

                # OR add a specific query function. 

                # For now, let's fetch all NHI Income and filter in Pandas. 

                # Assuming data volume is manageable.

                

                all_tx = db.get_transactions() # Get all to be safe for now, or fetch last 2 years?

                

                # Check column existence (migration safeguard)

                if 'nhi_month' not in all_tx.columns:

                    all_tx['nhi_month'] = None

                

                # Filter for NHI Income

                nhi_tx = all_tx[

                    (all_tx['category'] == '健保收入') & 

                    (all_tx['subcategory'].isin(['健保一暫', '健保二暫'])) &

                    (all_tx['nhi_month'].isin(months))

                ]

                

                # Group by nhi_month

                if not nhi_tx.empty:

                    actual_sums = nhi_tx.groupby('nhi_month')['amount'].sum().reset_index()

                    actual_sums.rename(columns={'amount': '實際入帳', 'nhi_month': 'month'}, inplace=True)

                    

                    # Merge with df_nhi

                    df_merge = pd.merge(df_nhi, actual_sums, on='month', how='left')

                    df_merge['實際入帳'].fillna(0, inplace=True)

                else:

                    df_merge = df_nhi.copy()

                    df_merge['實際入帳'] = 0

                    

                df_merge['差異'] = df_merge['實際入帳'] - df_merge['actual_received']

                

                # Display Comparison Table

                comp_display = df_merge[['month', 'total_fee', 'drug_fee', 'deduction', 'rejection', 'actual_received', '實際入帳', '差異']].copy()

                comp_display.columns = ['月份', '申報調劑費', '藥費', '點值核扣', '核刪', '應收總額(預估)', '實際入帳', '差異']

                

                st.dataframe(comp_display.style.format({

                    '申報調劑費': '${:,.0f}',

                    '藥費': '${:,.0f}',

                    '點值核扣': '${:,.0f}',

                    '核刪': '${:,.0f}',

                    '應收總額(預估)': '${:,.0f}',

                    '實際入帳': '${:,.0f}',

                    '差異': '${:,.0f}'

                }).applymap(lambda v: 'color: red;' if v < -100 else ('color: green;' if v > 100 else ''), subset=['差異']), 

                use_container_width=True)



                

                st.divider()

                

                # Visualization

                st.markdown("### 健保營收結構趨勢")

                

                # Prepare data for stacked bar chart: Chronic Income, General Income, Drug Fee

                chart_data = df_nhi.set_index('month')[['chronic_income', 'general_income', 'drug_fee']]

                chart_data.columns = ['慢箋調劑費', '一般箋調劑費', '藥費']

                st.bar_chart(chart_data, stack=True)

                

                # Point Value Trend

                st.markdown("### 點值趨勢")

                # st.line_chart(df_nhi.set_index('month')['point_value'])

                

                # Use Altair for fixed Y-axis scaling

                chart_point = alt.Chart(df_nhi).mark_line(point=True).encode(

                    x=alt.X('month', title='月份'),

                    y=alt.Y('point_value', title='點值', scale=alt.Scale(domain=[0.75, 1.0])),

                    tooltip=['month', alt.Tooltip('point_value', format='.4f')]

                ).interactive()

                

                st.altair_chart(chart_point, use_container_width=True)

                

                st.divider()

                st.markdown("### 詳細數據")

                

                # Rename columns for display

                df_display = df_nhi.rename(columns={

                    'month': '月份',

                    'total_fee': '總調劑費',

                    'deduction': '點值核扣',

                    'rejection': '核刪費用',

                    'chronic_count': '慢箋張數',

                    'general_count': '一般箋張數',

                    'updated_at': '更新時間',

                    'actual_received': '實收金額',

                    'point_value': '點值',

                    'chronic_income': '慢箋收入',

                    'general_income': '一般箋收入'

                })

                

                st.dataframe(df_display.style.format({

                    '總調劑費': '${:,.0f}',

                    '點值核扣': '${:,.0f}',

                    '核刪費用': '${:,.0f}',

                    '實收金額': '${:,.0f}',

                    '點值': '{:.4f}',

                    '慢箋收入': '${:,.0f}',

                    '一般箋收入': '${:,.0f}'

                }), use_container_width=True)

                

            else:

                st.info("此區間無健保申報資料")

        else:

            st.error("帳號或密碼錯誤")



