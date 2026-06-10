import os
import json
import hashlib
from datetime import datetime

def main():
    # Setup directory and path
    mcporter_dir = os.path.expanduser("~/.mcporter")
    credentials_path = os.path.join(mcporter_dir, "credentials.json")
    os.makedirs(mcporter_dir, exist_ok=True)
    
    # Token values from the OTT exchange
    access_token = "eyJraWQiOiJwbGF5bWNwLXJzYS1rZXkiLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIyMTM3MSIsImF1ZCI6IkhFbE1VV2RWb3JvVHNyWHhlemVUU2VtZzhnWHp6Q0tXQVJiNU1KdXg4Z1kiLCJuYmYiOjE3ODEwNjM5NjcsInNjb3BlIjpbImRlZmF1bHQiXSwiaXNzIjoiaHR0cHM6Ly9wbGF5YXV0aC5rYWthby5jb20vcGxheW1jcCIsImV4cCI6MTc4MTEwNzE2NywiaWF0IjoxNzgxMDYzOTY3LCJqdGkiOiI5ZWNhOTUwZC1lMTliLTRkM2UtYTRhOC0zZWFiZDljZjExM2MifQ.FDdj7KOHk5VIx059BzVhy8SowaPOKYvykcGEPTQcmmpfdVn41x9bfUGsLmqpDZHf4MFGkfp4sGGPhZXoI8QWqu4f7BkBCU_-iklDR7y03t2ZbzuXMm58x3II4XjlworAGk9rSB9N-WWAtwalWn0gdM5j02kT1_hXLmoMIfYFyYqEt0tclCnJ1AQaC5eq-LBEGKKCxEtQXLWvRXZw09BlWLDC-uncS1Cr1XJwknVZQzYbHQk4tMTw9i7GXcCNQx9-LyQYsA8n58zyLL5pfHZz00q3a029sANBqQcO912YEeHN7SZB_xG9H0FBA_TtOq6f-yNRMAguPsXzVj3QLNbNRg"
    refresh_token = "RZdmq4Zr7twAGXmzzIofQ05gML77GPxd64w98U8BB3U41banjnwo-V6ONcC-nn-74else7WgKEMJ3Vi1nbf4rTJDdjdKEqU78rtYNoja-VAQ8l2vN5qeAbKikzS3IhJ0"
    
    # Calculate target hash key
    # Formula: printf '{"name":"mcp-gateway","url":"https://playmcp.kakao.com/mcp","command":null}' | shasum -a 256 | cut -c1-16
    raw_str = '{"name":"mcp-gateway","url":"https://playmcp.kakao.com/mcp","command":null}'
    sha256_hash = hashlib.sha256(raw_str.encode('utf-8')).hexdigest()
    hash_val = sha256_hash[:16]
    entry_key = f"mcp-gateway|{hash_val}"
    
    # Load existing credentials or initialize
    if os.path.exists(credentials_path):
        try:
            with open(credentials_path, 'r', encoding='utf-8') as f:
                cred_data = json.load(f)
        except Exception:
            cred_data = {"version": 1, "entries": {}}
    else:
        cred_data = {"version": 1, "entries": {}}
        
    # Standard keys check
    if "version" not in cred_data:
        cred_data["version"] = 1
    if "entries" not in cred_data:
        cred_data["entries"] = {}
        
    # Write entries
    current_time = datetime.utcnow().isoformat() + "Z"
    cred_data["entries"][entry_key] = {
        "serverName": "mcp-gateway",
        "serverUrl": "https://playmcp.kakao.com/mcp",
        "tokens": {
            "access_token": access_token,
            "token_type": "Bearer",
            "refresh_token": refresh_token
        },
        "clientInfo": {
            "client_id": "HElMUWdVoroTsrXxezeTSemg8gXzzCKWARb5MJux8gY"
        },
        "updatedAt": current_time
    }
    
    # Save back to file
    with open(credentials_path, 'w', encoding='utf-8') as f:
        json.dump(cred_data, f, indent=2)
        
    print(f"Successfully configured credentials.json at: {credentials_path}")
    print(f"Added Server Key: {entry_key}")

if __name__ == "__main__":
    main()
