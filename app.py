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

        options = ["每日 記帳 (Data Entry)"]

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
                # Create TWO transactions for transfer
                # 1. Transfer Out
                db.add_transaction(
                    date=date,
                    type="資金調度",
                    category="轉出",
                    subcategory="",
                    account=account_from,
                    amount=amount,
                    original_amount=None,
                    note=f"{note} (轉入 {account})",
                    nhi_month=""
                )
                # 2. Transfer In
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

    else:

        st.write("尚無今日紀錄")



elif page == "一般帳務分析 (General Analysis)":

    st.header("一般帳務分析")

    

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

        st.error("帳號或密碼錯誤")



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



