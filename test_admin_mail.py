#!/usr/bin/env python3
"""
Test script to verify admin_app mail configuration
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import admin app
try:
    from admin_app import admin_app, mail
    print("✅ Successfully imported admin_app and mail")
except ImportError as e:
    print(f"❌ Failed to import admin_app: {e}")
    sys.exit(1)

def test_admin_mail_config():
    """Test admin app mail configuration"""
    print("\n🔍 Testing Admin App Mail Configuration")
    print("=" * 50)
    
    # Test within admin app context
    with admin_app.app_context():
        print("\n📧 Mail Configuration:")
        mail_config = {
            'MAIL_SERVER': admin_app.config.get('MAIL_SERVER'),
            'MAIL_PORT': admin_app.config.get('MAIL_PORT'),
            'MAIL_USERNAME': admin_app.config.get('MAIL_USERNAME'),
            'MAIL_PASSWORD': admin_app.config.get('MAIL_PASSWORD'),
            'MAIL_USE_TLS': admin_app.config.get('MAIL_USE_TLS'),
            'MAIL_USE_SSL': admin_app.config.get('MAIL_USE_SSL'),
            'MAIL_DEFAULT_SENDER': admin_app.config.get('MAIL_DEFAULT_SENDER')
        }
        
        for key, value in mail_config.items():
            if 'PASSWORD' in key:
                display_value = '*' * len(str(value)) if value else None
            else:
                display_value = value
            print(f"  {key}: {display_value}")
        
        # Check for missing required config
        required_configs = ['MAIL_SERVER', 'MAIL_USERNAME', 'MAIL_PASSWORD', 'MAIL_DEFAULT_SENDER']
        missing_configs = [key for key in required_configs if not mail_config.get(key)]
        
        if missing_configs:
            print(f"\n❌ Missing required configurations: {', '.join(missing_configs)}")
            return False
        
        # Test mail object initialization
        print(f"\n🔧 Mail Object Status:")
        print(f"  Mail object exists: {mail is not None}")
        print(f"  Mail app context: {hasattr(mail, 'app') and mail.app is not None}")
        print(f"  Mail app name: {mail.app.name if hasattr(mail, 'app') and mail.app else 'N/A'}")
        
        return True

def test_send_admin_email():
    """Test sending email through admin app"""
    print("\n📤 Testing Email Send Through Admin App")
    print("=" * 50)
    
    try:
        from flask_mail import Message
        
        with admin_app.app_context():
            # Create test message
            msg = Message(
                subject='Test Email from Admin App',
                recipients=['racunidzm@gmail.com']
            )
            
            msg.html = """
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #1976d2;">Admin App Email Test</h2>
                <p>This is a test email sent from the admin_app through the WSGI configuration.</p>
                <p><strong>Status:</strong> ✅ Admin app mail is working correctly!</p>
                <p><strong>Configuration:</strong></p>
                <ul>
                    <li>Server: {}</li>
                    <li>Port: {}</li>
                    <li>Username: {}</li>
                    <li>Use TLS: {}</li>
                    <li>Use SSL: {}</li>
                </ul>
                <p>Best regards,<br>Modern360 Admin System</p>
            </body>
            </html>
            """.format(
                admin_app.config.get('MAIL_SERVER'),
                admin_app.config.get('MAIL_PORT'),
                admin_app.config.get('MAIL_USERNAME'),
                admin_app.config.get('MAIL_USE_TLS'),
                admin_app.config.get('MAIL_USE_SSL')
            )
            
            # Send email
            print("  Sending test email...")
            mail.send(msg)
            print("  ✅ Email sent successfully through admin app!")
            return True
            
    except Exception as e:
        print(f"  ❌ Failed to send email: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Admin App Mail Configuration Test")
    print("=" * 50)
    
    # Test configuration
    config_ok = test_admin_mail_config()
    
    if config_ok:
        # Test email sending
        email_ok = test_send_admin_email()
        
        if email_ok:
            print(f"\n🎉 All tests passed! Admin app mail is working correctly.")
        else:
            print(f"\n❌ Email sending test failed.")
    else:
        print(f"\n❌ Configuration test failed.")
    
    print("\n" + "=" * 50)
