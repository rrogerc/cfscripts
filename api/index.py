import sys
import os

# Add the src directory to the Python path so Vercel can find the cfscripts module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from cfscripts.web.server import app
