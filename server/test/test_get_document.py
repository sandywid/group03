# test_get_document.py
"""
Test suite för /api/get-document endpoint.

Denna endpoint hämtar PDF-filer och stödjer flera metoder för att ta emot document ID:
- Path parameter: /api/get-document/<id>
- Query parameter: /api/get-document?id=<id> eller ?documentid=<id>
"""
import pytest
import io


class TestGetDocumentEndpoint:
    """Tester för GET /api/get-document endpoint."""

    def test_get_document_requires_authentication(self, client):
        """Verifiera att endpointen kräver autentisering."""
        response = client.get("/api/get-document/1")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_get_document_with_path_parameter(self, client, auth_headers):
        """Testa hämtning med document ID i path."""
        # Ladda upp dokument
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"
        pdf_io = io.BytesIO(pdf_content)
        data = {"file": (pdf_io, "getpath.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc_id = r.get_json()["id"]
        
        # Hämta via path parameter
        response = client.get(f"/api/get-document/{doc_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        # Verifiera att det är en PDF
        assert response.data.startswith(b"%PDF-")

    def test_get_document_with_query_parameter_id(self, client, auth_headers):
        """Testa hämtning med ?id= query parameter."""
        # Ladda upp dokument
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "getqid.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc_id = r.get_json()["id"]
        
        # Hämta via query parameter ?id=
        response = client.get(f"/api/get-document?id={doc_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        assert response.data.startswith(b"%PDF-")

    def test_get_document_with_query_parameter_documentid(self, client, auth_headers):
        """Testa hämtning med ?documentid= query parameter."""
        # Ladda upp dokument
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "getqdocid.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc_id = r.get_json()["id"]
        
        # Hämta via query parameter ?documentid=
        response = client.get(f"/api/get-document?documentid={doc_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        assert response.data.startswith(b"%PDF-")

    def test_get_document_missing_id(self, client, auth_headers):
        """Testa utan document ID - ska ge 400."""
        response = client.get("/api/get-document", headers=auth_headers)
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_get_document_invalid_id(self, client, auth_headers):
        """Testa med ogiltigt document ID."""
        response = client.get("/api/get-document?id=invalid", headers=auth_headers)
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_get_document_not_found(self, client, auth_headers):
        """Testa hämtning av dokument som inte finns."""
        response = client.get("/api/get-document/999999", headers=auth_headers)
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "not found" in data["error"].lower()

    def test_get_document_owned_by_other_user(self, client):
        """Verifiera att man inte kan hämta någon annans dokument."""
        from server import app
        
        # Skapa användare 1
        c = app.test_client()
        login1 = "getuser1"
        email1 = f"{login1}@example.test"
        pwd1 = "Passw0rd!"
        
        r = c.post("/api/create-user", json={
            "login": login1,
            "email": email1,
            "password": pwd1
        })
        assert r.status_code in (200, 201)
        
        js1 = c.post("/api/login", json={"email": email1, "password": pwd1}).get_json()
        token1 = js1["token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        # Användare 1 laddar upp dokument
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "getuser1doc.pdf", "application/pdf")}
        r = c.post(
            "/api/upload-document",
            headers=headers1,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc1_id = r.get_json()["id"]
        
        # Skapa användare 2
        login2 = "getuser2"
        email2 = f"{login2}@example.test"
        pwd2 = "Passw0rd!"
        
        r = c.post("/api/create-user", json={
            "login": login2,
            "email": email2,
            "password": pwd2
        })
        assert r.status_code in (200, 201)
        
        js2 = c.post("/api/login", json={"email": email2, "password": pwd2}).get_json()
        token2 = js2["token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        # Användare 2 försöker hämta användare 1:s dokument
        response = c.get(f"/api/get-document/{doc1_id}", headers=headers2)
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_get_document_inline_disposition(self, client, auth_headers):
        """Verifiera att dokumentet returneras inline (för visning i browser)."""
        # Ladda upp dokument
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "inline.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc_id = r.get_json()["id"]
        
        # Hämta dokument
        response = client.get(f"/api/get-document/{doc_id}", headers=auth_headers)
        assert response.status_code == 200
        # Verifiera Content-Disposition header (inline för visning i browser)
        content_disp = response.headers.get("Content-Disposition", "")
        assert "inline" in content_disp.lower() or content_disp == ""

    def test_get_document_content_matches_upload(self, client, auth_headers):
        """Verifiera att nedladdad PDF matchar uppladdad PDF."""
        # Skapa en specifik PDF med identifierbart innehåll
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Count 0 >>\nendobj\nxref\n0 3\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\ntrailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n110\n%%EOF\n"
        pdf_io = io.BytesIO(pdf_content)
        data = {"file": (pdf_io, "contentmatch.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc_id = r.get_json()["id"]
        
        # Hämta dokument
        response = client.get(f"/api/get-document/{doc_id}", headers=auth_headers)
        assert response.status_code == 200
        
        # Verifiera att innehållet matchar
        assert response.data == pdf_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
