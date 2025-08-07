#!/usr/bin/env python3
"""
Modern360 Assessment - WSGI Application Entry Point
This file is used by deployment platforms like Render, Heroku, etc.
Integrates both main app and admin app under one server
"""

import os
from dotenv import load_dotenv
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# Load environment variables
load_dotenv()

# Import both applications
from app import app as main_app
from admin_app import admin_app

# Ensure admin app mail is properly initialized with current context
def ensure_admin_mail_init():
    """Ensure admin app mail configuration is properly initialized"""
    try:
        # Force reload mail configuration in admin app context
        with admin_app.app_context():
            # Verify mail configuration
            mail_config = {
                'MAIL_SERVER': admin_app.config.get('MAIL_SERVER'),
                'MAIL_PORT': admin_app.config.get('MAIL_PORT'),
                'MAIL_USERNAME': admin_app.config.get('MAIL_USERNAME'),
                'MAIL_PASSWORD': admin_app.config.get('MAIL_PASSWORD'),
                'MAIL_USE_TLS': admin_app.config.get('MAIL_USE_TLS'),
                'MAIL_USE_SSL': admin_app.config.get('MAIL_USE_SSL'),
                'MAIL_DEFAULT_SENDER': admin_app.config.get('MAIL_DEFAULT_SENDER')
            }
            
            # Print configuration for debugging
            print("Admin App Mail Configuration:")
            for key, value in mail_config.items():
                if 'PASSWORD' in key:
                    print(f"  {key}: {'*' * len(str(value)) if value else None}")
                else:
                    print(f"  {key}: {value}")
            
            # Verify mail object is properly initialized
            from admin_app import mail
            if mail and hasattr(mail, 'app') and mail.app:
                print("✅ Admin Mail object properly initialized")
            else:
                print("❌ Admin Mail object not properly initialized")
                
    except Exception as e:
        print(f"❌ Error initializing admin mail: {e}")

# Initialize admin mail configuration
ensure_admin_mail_init()

# Create the main application with admin mounted at /admin
application = DispatcherMiddleware(main_app, {
    '/admin': admin_app
})

# For deployment platforms that expect 'app'
app = application

if __name__ == "__main__":
    # This runs when file is executed directly (not recommended for production)
    from werkzeug.serving import run_simple
    port = int(os.environ.get('PORT', 5000))
    run_simple('0.0.0.0', port, application, use_reloader=True, use_debugger=True)
