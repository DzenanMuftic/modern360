#!/usr/bin/env python3
"""
Test script for the Add Company API endpoint
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from admin_app import app, db, Company
import json

def test_add_company_api():
    """Test the /api/companies endpoint"""
    with app.test_client() as client:
        with app.app_context():
            # Test data
            test_company = {
                'name': 'Test Company API',
                'industry': 'IT',
                'description': 'Test company for API testing'
            }
            
            # Send POST request
            response = client.post('/api/companies', 
                                 data=json.dumps(test_company),
                                 content_type='application/json')
            
            print(f"Response status: {response.status_code}")
            print(f"Response data: {response.get_json()}")
            
            if response.status_code == 200:
                data = response.get_json()
                if data.get('success'):
                    print("✅ API test successful!")
                    print(f"Created company: {data['company']}")
                    
                    # Clean up - delete the test company
                    test_comp = Company.query.filter_by(name='Test Company API').first()
                    if test_comp:
                        db.session.delete(test_comp)
                        db.session.commit()
                        print("🧹 Test company cleaned up")
                else:
                    print("❌ API returned success=False")
            else:
                print("❌ API test failed!")

if __name__ == '__main__':
    test_add_company_api()
