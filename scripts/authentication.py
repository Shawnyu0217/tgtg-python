import sys
from pathlib import Path

# Ensure project root is in sys.path for direct execution
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tgtg import TgtgClient

# Prompt user to enter their email
email = input("Enter your email for authentication: ")
client = TgtgClient(email=email)

# This will trigger the email authentication flow
credentials = client.get_credentials()

print(credentials)