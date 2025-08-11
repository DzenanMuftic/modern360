#!/bin/bash

# CSP Testing Script for asistentica.online
echo "=== CSP Testing Script ==="
echo "Testing https://asistentica.online security headers and functionality"
echo ""

# Test 1: Check CSP Header
echo "1. Testing CSP Headers:"
csp_header=$(curl -I https://asistentica.online/ 2>/dev/null | grep -E "(Content-Security-Policy|Content-Security-Policy-Report-Only)")
if [[ -n "$csp_header" ]]; then
    echo "✅ CSP Header Present"
    echo "   $csp_header"
else
    echo "❌ CSP Header Missing"
fi
echo ""

# Test 2: Check for nonce in CSP
if echo "$csp_header" | grep -q "nonce-"; then
    echo "✅ Nonce-based CSP detected"
else
    echo "❌ No nonce found in CSP"
fi
echo ""

# Test 3: Main site functionality
echo "2. Testing Main Site:"
if curl -s https://asistentica.online/ | grep -q "Modern360 Assessment Platform"; then
    echo "✅ Main site loads correctly"
else
    echo "❌ Main site loading issue"
fi

# Test 4: Admin site functionality
echo "3. Testing Admin Site:"
if curl -s https://asistentica.online/pravo/login | grep -q "Admin Login"; then
    echo "✅ Admin login page loads correctly"
else
    echo "❌ Admin login page loading issue"
fi

# Test 5: HTTPS redirect
echo "4. Testing HTTPS Redirect:"
redirect_response=$(curl -I http://asistentica.online/ 2>/dev/null | head -1)
if echo "$redirect_response" | grep -q "301"; then
    echo "✅ HTTP to HTTPS redirect working"
else
    echo "❌ HTTP redirect issue"
fi

# Test 6: Other security headers
echo "5. Testing Other Security Headers:"
security_headers=$(curl -I https://asistentica.online/ 2>/dev/null | grep -E "(Strict-Transport-Security|X-Frame-Options|X-Content-Type-Options|Referrer-Policy|Permissions-Policy)")

if echo "$security_headers" | grep -q "Strict-Transport-Security"; then
    echo "✅ HSTS Header Present"
else
    echo "❌ HSTS Header Missing"
fi

if echo "$security_headers" | grep -q "X-Frame-Options"; then
    echo "✅ X-Frame-Options Present"
else
    echo "❌ X-Frame-Options Missing"
fi

if echo "$security_headers" | grep -q "X-Content-Type-Options"; then
    echo "✅ X-Content-Type-Options Present"
else
    echo "❌ X-Content-Type-Options Missing"
fi

echo ""
echo "=== Test Complete ==="
echo "Check browser console at https://asistentica.online for any CSP violations"
echo "Check browser console at https://asistentica.online/pravo/dashboard for admin functionality"
