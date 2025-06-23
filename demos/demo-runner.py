#!/usr/bin/env python3
"""
Demo Runner for Haven Health Passport UI
This simple server hosts the Haven Health Passport UI demo
"""

import http.server
import socketserver
import os
import webbrowser
import threading
import sys
from pathlib import Path

# Define the port to serve on
PORT = 8000
# Get the current directory (where this script is located)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# Get the project root directory (parent of current directory)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

class DemoHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler for the demo server"""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to the current directory
        super().__init__(*args, directory=CURRENT_DIR, **kwargs)
    
    def translate_path(self, path):
        """Override to handle paths correctly"""
        # First try the standard translation
        translated = super().translate_path(path)
        
        # Check if the file exists
        if os.path.exists(translated):
            return translated
        
        # If the path starts with /web, try to serve from the project root
        if path.startswith('/web/'):
            relative_path = path[1:]  # Remove leading slash
            return os.path.join(PROJECT_ROOT, relative_path)
        
        return translated
    
    def do_GET(self):
        """Handle GET requests"""
        # Print the requested path for debugging
        print(f"Requested: {self.path}")
        return super().do_GET()

def open_browser():
    """Open a browser tab to the demo"""
    webbrowser.open(f'http://localhost:{PORT}/demo-ui.html')

def main():
    """Run the demo server"""
    print("Haven Health Passport UI Demo")
    print("-----------------------------")
    print(f"Demo files directory: {CURRENT_DIR}")
    print(f"Project root directory: {PROJECT_ROOT}")
    
    # Ensure the demo files exist
    required_files = ['demo-ui.html', 'demo-app.js', 'demo-styles.css']
    for file in required_files:
        if not os.path.exists(os.path.join(CURRENT_DIR, file)):
            print(f"Error: Required file {file} not found!")
            sys.exit(1)
    
    # Check if the React components exist
    components = [
        'web/src/components/patient/PatientRegistration.jsx',
        'web/src/components/auth/TOTPSetup.jsx',
        'web/src/components/auth/BackupCodes.jsx',
        'web/src/components/ConflictResolutionDialog.jsx'
    ]
    
    missing_components = []
    for component in components:
        component_path = os.path.join(PROJECT_ROOT, component)
        if not os.path.exists(component_path):
            missing_components.append(component)
    
    if missing_components:
        print("Warning: Some React components could not be found:")
        for component in missing_components:
            print(f"  - {component}")
        print("The demo will use mock components instead.")
    
    # Start the server
    with socketserver.TCPServer(("", PORT), DemoHandler) as httpd:
        print(f"Starting server at http://localhost:{PORT}/demo-ui.html")
        print("Press Ctrl+C to stop the server")
        
        # Open browser after a short delay
        threading.Timer(1, open_browser).start()
        
        # Serve until interrupted
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")

if __name__ == "__main__":
    main()
