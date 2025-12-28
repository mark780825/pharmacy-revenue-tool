import utils

print("Testing Login Verification...")

# Test 1: Admin Login
role = utils.verify_user("admin", "admin123")
print(f"Test 1 (Admin): Input admin -> Role {role}")
assert role == "admin"

# Test 2: Staff Login
role = utils.verify_user("staff", "staff123")
print(f"Test 2 (Staff): Input staff -> Role {role}")
assert role == "staff"

# Test 3: Invalid Password
role = utils.verify_user("admin", "wrongpass")
print(f"Test 3 (Invalid Pass): Input admin/wrongpass -> Role {role}")
assert role == None

# Test 4: Invalid User
role = utils.verify_user("hacker", "admin123")
print(f"Test 4 (Invalid User): Input hacker -> Role {role}")
assert role == None

print("ALL LOGIN TESTS PASSED")
