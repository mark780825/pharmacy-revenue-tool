import database as db
import utils
from datetime import datetime
import os

# Clean up any existing test db
if os.path.exists("pharmacy.db"):
    os.remove("pharmacy.db")

print("Initializing DB...")
db.init_db()

print("Testing Utils Logic...")
# Test 1: Line Pay Fee
cat = "銷貨收入"
sub = "Line Pay收入"
amount = 1000
net, adjusted = utils.calculate_net_amount(cat, sub, amount)
print(f"Test 1 ({sub}): Input {amount} -> Net {net}. Adjusted? {adjusted}")
assert net == 977.0
assert adjusted == True

# Test 2: Cash (Default)
sub = "現金收入"
net, adjusted = utils.calculate_net_amount(cat, sub, amount)
print(f"Test 2 ({sub}): Input {amount} -> Net {net}. Adjusted? {adjusted}")
assert net == 1000.0
assert adjusted == False

print("Testing Database Insertion...")
# Test 3: Insert Transaction
date = datetime.now()
db.add_transaction(date, "收入", "銷貨收入", "Line Pay收入", "銀行", 977.0, 1000.0, "Test Note")

df = db.get_transactions()
print("Transactions in DB:")
print(df)

assert len(df) == 1
assert df.iloc[0]['amount'] == 977.0
assert df.iloc[0]['original_amount'] == 1000.0

print("ALL TESTS PASSED")
