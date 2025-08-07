#!/usr/bin/env python3
"""
Test script to verify domain redirect functionality
"""

import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_redirect():
    """Test the domain redirect functionality"""
    print("🔗 Testing Domain Redirect Functionality")
    print("=" * 50)
    
    # Test URLs
    old_domain = "http://65.21.185.169:5000"
    new_domain = os.environ.get('REDIRECT_DOMAIN', 'https://asistentica.online')
    
    test_token = "01TYmJdIk9hoZ1THLYgOVF0cvw9XKoapxpAA8P4RXM8"
    test_url = f"{old_domain}/respond/{test_token}"
    expected_redirect = f"{new_domain}/respond/{test_token}"
    
    print(f"Testing URL: {test_url}")
    print(f"Expected redirect: {expected_redirect}")
    print()
    
    try:
        # Make request without following redirects
        response = requests.get(test_url, allow_redirects=False, timeout=10)
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code in [301, 302]:
            redirect_location = response.headers.get('Location', 'No location header')
            print(f"Redirect Location: {redirect_location}")
            
            if redirect_location == expected_redirect:
                print("✅ Redirect is working correctly!")
            else:
                print("❌ Redirect location doesn't match expected URL")
        else:
            print("❌ No redirect detected")
            print(f"Response content preview: {response.text[:200]}...")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error making request: {e}")
    
    print("\n" + "=" * 50)

def test_env_config():
    """Test environment configuration"""
    print("⚙️  Environment Configuration")
    print("=" * 30)
    
    redirect_domain = os.environ.get('REDIRECT_DOMAIN')
    enable_redirect = os.environ.get('ENABLE_DOMAIN_REDIRECT', 'false')
    
    print(f"REDIRECT_DOMAIN: {redirect_domain}")
    print(f"ENABLE_DOMAIN_REDIRECT: {enable_redirect}")
    
    if redirect_domain and enable_redirect.lower() == 'true':
        print("✅ Redirect configuration is properly set")
    else:
        print("❌ Redirect configuration is missing or disabled")
    
    print()

if __name__ == "__main__":
    print("🚀 Domain Redirect Test")
    print("=" * 50)
    
    test_env_config()
    test_redirect()
