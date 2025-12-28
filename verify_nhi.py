import database as db
import pandas as pd
import os

def verify_nhi_feature():
    print("Verifying NHI Feature...")
    
    # 1. Initialize DB (ensure table exists)
    db.init_db()
    print("Database initialized.")
    
    # 2. Test Data
    month = "2024-01"
    total = 100000
    deduction = 10000
    rejection = 500
    chronic_count = 100
    
    # 3. Save Record
    print(f"Saving record for {month}...")
    db.save_nhi_record(month, total, deduction, rejection, chronic_count)
    
    # 4. Retrieve Record
    print("Retrieving record...")
    df = db.get_nhi_records(start_month=month, end_month=month)
    
    if df.empty:
        print("❌ Error: No record found!")
        return
    
    rec = df.iloc[0]
    print(f"Retrieved: {rec.to_dict()}")
    
    # 5. Verify Values
    assert rec['month'] == month
    assert rec['total_fee'] == total
    assert rec['deduction'] == deduction
    assert rec['rejection'] == rejection
    assert rec['chronic_count'] == chronic_count
    
    print("✅ Data persistence verified.")
    
    # 6. Verify Logic Calculation (emulate UI logic)
    actual_received = rec['total_fee'] - rec['deduction'] - rec['rejection']
    point_value = 1 - (rec['deduction'] / rec['total_fee'])
    chronic_income = point_value * 75 * rec['chronic_count']
    general_income = actual_received - chronic_income
    
    print(f"Calculated Point Value: {point_value}")
    print(f"Calculated Chronic Income: {chronic_income}")
    print(f"Calculated General Income: {general_income}")
    
    expected_received = 100000 - 10000 - 500 # 89500
    expected_pv = 1 - (10000 / 100000) # 0.9
    expected_chronic = 0.9 * 75 * 100 # 6750
    
    assert actual_received == expected_received
    assert abs(point_value - expected_pv) < 0.0001
    assert abs(chronic_income - expected_chronic) < 0.0001
    
    print("✅ Calculation logic verified.")

if __name__ == "__main__":
    verify_nhi_feature()
