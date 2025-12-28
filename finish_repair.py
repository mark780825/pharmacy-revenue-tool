with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

cut_index = -1
for i, line in enumerate(lines):
    # Match the specific corrupted line pattern seen in view_file
    if 'elif page ==' in line and 'Import' in line:
        cut_index = i
        break

if cut_index != -1:
    lines = lines[:cut_index]
    
    # Ensure clean separation
    while lines and lines[-1].strip() == '':
        lines.pop()
    lines.append('\n\n')
        
    new_code = """elif page == "匯入 歷史資料 (Import Legacy Data)":
    st.header("匯入歷史收支資料")
    st.info("支援一般會計軟體匯出之帳簿格式 (日期, 借方科目, 借方金額, 貸方科目, 貸方金額, 說明)")
    
    uploaded_file = st.file_uploader("請選擇 Excel 或 CSV 檔案", type=['xlsx', 'xls', 'csv'])
    
    if uploaded_file:
        st.subheader("資料預覽與解析")
        
        # Process File
        df_import = data_import.process_file(uploaded_file)
        
        if isinstance(df_import, str):
            st.error(f"讀取檔案失敗: {df_import}")
        elif df_import.empty:
            st.warning("檔案中找不到可匯入的交易資料 (需包含日期與科目)")
        else:
            st.caption(f"解析出 {len(df_import)} 筆有效收支")
            st.dataframe(df_import, use_container_width=True)
            
            # Confirmation
            st.write("---")
            col1, col2 = st.columns([1, 4])
            with col1:
                confirm_btn = st.button("確認匯入資料", type="primary")
                
            if confirm_btn:
                success_count = 0
                fail_count = 0
                
                # Progress bar
                my_bar = st.progress(0)
                total = len(df_import)
                
                for index, row in df_import.iterrows():
                    try:
                        db.add_transaction(
                            date=row['date'],
                            type=row['type'],
                            category=row['category'],
                            subcategory=row['subcategory'],
                            account=row['account'],
                            amount=row['amount'],
                            original_amount=None,
                            note=row['note']
                        )
                        success_count += 1
                    except Exception as e:
                        print(f"Error adding transaction: {e}")
                        fail_count += 1
                        
                    my_bar.progress((index + 1) / total)
                    
                st.success(f"匯入完成 成功: {success_count} 筆 失敗: {fail_count} 筆")
                st.balloons()
"""
    lines.append(new_code)
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Fixed Import section.")
else:
    print("Could not find Import section to replace.")
