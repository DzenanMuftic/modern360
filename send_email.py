#!/usr/bin/env python3
"""
Email sender script for Modern360 Assessment Platform
Sends emails using configuration from .env file
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
from datetime import datetime

def load_email_config():
    """Load email configuration from .env file"""
    load_dotenv()
    
    config = {
        'server': os.getenv('MAIL_SERVER'),
        'port': int(os.getenv('MAIL_PORT', 587)),
        'username': os.getenv('MAIL_USERNAME'),
        'password': os.getenv('MAIL_PASSWORD'),
        'sender': os.getenv('MAIL_DEFAULT_SENDER'),
        'use_tls': os.getenv('MAIL_USE_TLS', 'True').lower() == 'true',
        'use_ssl': os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
    }
    
    # Validate required fields
    required_fields = ['server', 'username', 'password', 'sender']
    missing_fields = [field for field in required_fields if not config[field]]
    
    if missing_fields:
        raise ValueError(f"Missing required email configuration: {', '.join(missing_fields)}")
    
    return config

def create_message(to_email, subject, body_text, body_html=None, sender_email=None, sender_name=None):
    """Create email message"""
    msg = MIMEMultipart('alternative')
    
    # Set sender
    if sender_name:
        msg['From'] = f"{sender_name} <{sender_email}>"
    else:
        msg['From'] = sender_email
    
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
    
    # Add text part
    text_part = MIMEText(body_text, 'plain', 'utf-8')
    msg.attach(text_part)
    
    # Add HTML part if provided
    if body_html:
        html_part = MIMEText(body_html, 'html', 'utf-8')
        msg.attach(html_part)
    
    return msg

def send_email(to_email, subject, body_text, body_html=None, sender_name="Modern360 Platform"):
    """Send email using configuration from .env file"""
    try:
        # Load configuration
        config = load_email_config()
        
        print(f"Loading email configuration...")
        print(f"Server: {config['server']}:{config['port']}")
        print(f"Username: {config['username']}")
        print(f"Use TLS: {config['use_tls']}")
        print(f"Use SSL: {config['use_ssl']}")
        
        # Create message
        msg = create_message(
            to_email=to_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            sender_email=config['sender'],
            sender_name=sender_name
        )
        
        # Connect to server and send email
        print(f"Connecting to {config['server']}...")
        
        if config['use_ssl']:
            # Use SSL connection (port 465)
            server = smtplib.SMTP_SSL(config['server'], config['port'])
        else:
            # Use regular connection with optional TLS
            server = smtplib.SMTP(config['server'], config['port'])
            if config['use_tls']:
                server.starttls()
        
        print("Authenticating...")
        server.login(config['username'], config['password'])
        
        print(f"Sending email to {to_email}...")
        server.send_message(msg)
        server.quit()
        
        print("✅ Email sent successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        return False

def send_test_email():
    """Send a test email to racunidzm@gmail.com"""
    to_email = "racunidzm@gmail.com"
    subject = "Test Email from Modern360 Platform"
    
    body_text = """
Hello!

This is a test email from the Modern360 Assessment Platform.

The email system is working correctly and configured to use the settings from the .env file.

Best regards,
Modern360 Platform
    """.strip()
    
    body_html = """
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #1976d2; border-bottom: 2px solid #1976d2; padding-bottom: 10px;">
                Modern360 Assessment Platform
            </h2>
            
            <p>Hello!</p>
            
            <p>This is a test email from the <strong>Modern360 Assessment Platform</strong>.</p>
            
            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0;">
                    ✅ The email system is working correctly and configured to use the settings from the .env file.
                </p>
            </div>
            
            <p>Features tested:</p>
            <ul>
                <li>SMTP configuration from .env file</li>
                <li>Authentication with email credentials</li>
                <li>HTML and text email formats</li>
                <li>Proper email headers and encoding</li>
            </ul>
            
            <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
            
            <p style="color: #666; font-size: 14px;">
                Best regards,<br>
                <strong>Modern360 Platform</strong><br>
                Professional 360-degree feedback and assessment solution
            </p>
        </div>
    </body>
    </html>
    """.strip()
    
    return send_email(to_email, subject, body_text, body_html)

if __name__ == "__main__":
    print("🚀 Modern360 Email Sender")
    print("=" * 40)
    
    # Check if python-dotenv is available
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("❌ Error: python-dotenv not installed")
        print("Please install it with: pip install python-dotenv")
        exit(1)
    
    # Send test email
    success = send_test_email()
    
    if success:
        print("\n🎉 Test completed successfully!")
    else:
        print("\n❌ Test failed. Please check your .env configuration.")
        print("\nRequired .env variables:")
        print("- MAIL_SERVER")
        print("- MAIL_PORT") 
        print("- MAIL_USERNAME")
        print("- MAIL_PASSWORD")
        print("- MAIL_DEFAULT_SENDER")
        print("- MAIL_USE_TLS (optional)")
        print("- MAIL_USE_SSL (optional)")
