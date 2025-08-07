#!/usr/bin/env python3
"""
Test script to verify that invitation URLs are generated with the new domain
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_main_app_url():
    """Test that MAIN_APP_URL is properly configured"""
    print("🔗 Testing MAIN_APP_URL Configuration")
    print("=" * 50)
    
    main_app_url = os.environ.get('MAIN_APP_URL')
    expected_url = 'https://asistentica.online'
    
    print(f"Current MAIN_APP_URL: {main_app_url}")
    print(f"Expected URL: {expected_url}")
    
    if main_app_url == expected_url:
        print("✅ MAIN_APP_URL is correctly configured!")
    else:
        print("❌ MAIN_APP_URL is not set to the expected value")
        if not main_app_url:
            print("   MAIN_APP_URL is not set in environment")
        else:
            print(f"   Current value: {main_app_url}")
            print(f"   Expected value: {expected_url}")
    
    return main_app_url == expected_url

def test_invitation_url_generation():
    """Test how invitation URLs would be generated"""
    print("\n📧 Testing Invitation URL Generation")
    print("=" * 40)
    
    main_app_url = os.environ.get('MAIN_APP_URL', 'http://65.21.185.169:5000')
    test_token = '01TYmJdIk9hoZ1THLYgOVF0cvw9XKoapxpAA8P4RXM8'
    
    # This is how the admin app generates invitation URLs
    invitation_url = f"{main_app_url}/respond/{test_token}"
    
    print(f"Generated invitation URL: {invitation_url}")
    
    if invitation_url.startswith('https://asistentica.online'):
        print("✅ Invitation URL uses the new domain!")
    else:
        print("❌ Invitation URL still uses the old domain")
    
    return invitation_url

def simulate_admin_app_context():
    """Simulate how admin app would generate URLs"""
    print("\n🎭 Simulating Admin App Email Generation")
    print("=" * 45)
    
    try:
        # Import admin app to test in context
        from admin_app import admin_app
        
        with admin_app.app_context():
            main_app_url = os.environ.get('MAIN_APP_URL', 'http://65.21.185.169:5000')
            test_token = '01TYmJdIk9hoZ1THLYgOVF0cvw9XKoapxpAA8P4RXM8'
            invitation_url = f"{main_app_url}/respond/{test_token}"
            
            print(f"Admin app context - MAIN_APP_URL: {main_app_url}")
            print(f"Generated URL: {invitation_url}")
            
            if 'asistentica.online' in invitation_url:
                print("✅ Admin app will generate URLs with new domain!")
                return True
            else:
                print("❌ Admin app will still use old domain")
                return False
                
    except Exception as e:
        print(f"❌ Error testing admin app context: {e}")
        return False

if __name__ == "__main__":
    print("🚀 URL Configuration Test")
    print("=" * 50)
    
    # Test environment configuration
    config_ok = test_main_app_url()
    
    # Test URL generation
    generated_url = test_invitation_url_generation()
    
    # Test admin app context
    admin_ok = simulate_admin_app_context()
    
    print(f"\n📋 Summary")
    print("=" * 20)
    print(f"Environment config: {'✅ OK' if config_ok else '❌ FAIL'}")
    print(f"URL generation: {'✅ OK' if 'asistentica.online' in generated_url else '❌ FAIL'}")
    print(f"Admin app context: {'✅ OK' if admin_ok else '❌ FAIL'}")
    
    if config_ok and 'asistentica.online' in generated_url and admin_ok:
        print(f"\n🎉 All tests passed! New domain URLs will be generated correctly.")
    else:
        print(f"\n❌ Some tests failed. Check the configuration.")
    
    print("\n" + "=" * 50)
