import os
import sys

# Add project root directory to sys.path for Vercel imports
root_dir = os.path.dirname(os.path.dirname(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.main import app
