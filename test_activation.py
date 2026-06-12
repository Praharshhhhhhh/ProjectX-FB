import sys
import os
sys.path.insert(0, os.path.abspath("client"))
# pyrefly: ignore [missing-import]
from client.services.api_client import api

print("Logging in as owner...")
api.login("owner@projectx.io", "Admin@123")

print("Creating tenant...")
t = api.create_tenant("TestCompany")
print(t)

print("Generating key...")
k = api.generate_key(t["id"])
print(k)

print("Activating key...")
try:
    res = api.activate_key(k["key_code"], "master@test.com", "Test Master", "12345678")
    print("Success:", res)
except Exception as e:
    print("Error:", e)
