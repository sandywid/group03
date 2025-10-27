# test_list_versions.py
"""
Test suite för /api/list-versions endpoint.

Denna endpoint listar alla versioner för ett specifikt dokument.
Stödjer både path parameter och query parameters.
"""
import pytest
import io
from sqlalchemy import text


class TestListVersionsEndpoint:
    """Tester för GET /api/list-versions endpoint."""

    def test_list_versions_requires_authentication(self, client):
        """Verifiera att endpointen kräver autentisering."""
        response = client.get("/api/list-versions/1")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_list_versions_with_path_parameter(self, client, auth_headers):
        """Testa med document ID i path."""
        from server import app
        
        # Ladda upp ett dokument
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "pathtest.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc_id = r.get_json()["id"]
        
        # Skapa version
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, method, path)
                    VALUES (:doc_id, :link, :intended_for, :method, :path)
                """),
                {
                    "doc_id": doc_id,
                    "link": "pathtest123",
                    "intended_for": "path@example.com",
                    "method": "watermark",
                    "path": "/tmp/pathtest.pdf",
                }
            )
        
        # Hämta versioner via path parameter
        response = client.get(f"/api/list-versions/{doc_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        assert len(data["versions"]) >= 1
        
        # Verifiera att vår version finns
        found = any(v["link"] == "pathtest123" for v in data["versions"])
        assert found

    def test_list_versions_with_query_parameter_id(self, client, auth_headers):
        """Testa med document ID via ?id= query parameter - TÄCKER MISSAD RAD 595."""
        from server import app
        
        # Ladda upp dokument
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "queryid.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc_id = r.get_json()["id"]
        
        # Skapa version
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, method, path)
                    VALUES (:doc_id, :link, :intended_for, :method, :path)
                """),
                {
                    "doc_id": doc_id,
                    "link": "queryid123",
                    "intended_for": "query@example.com",
                    "method": "watermark",
                    "path": "/tmp/queryid.pdf",
                }
            )
        
        # Hämta versioner via query parameter ?id=
        response = client.get(f"/api/list-versions?id={doc_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        
        found = any(v["link"] == "queryid123" for v in data["versions"])
        assert found

    def test_list_versions_with_query_parameter_documentid(self, client, auth_headers):
        """Testa med document ID via ?documentid= query parameter - TÄCKER MISSAD RAD 595."""
        from server import app
        
        # Ladda upp dokument
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "querydocid.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc_id = r.get_json()["id"]
        
        # Skapa version
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, method, path)
                    VALUES (:doc_id, :link, :intended_for, :method, :path)
                """),
                {
                    "doc_id": doc_id,
                    "link": "querydocid123",
                    "intended_for": "querydoc@example.com",
                    "method": "watermark",
                    "path": "/tmp/querydocid.pdf",
                }
            )
        
        # Hämta versioner via query parameter ?documentid=
        response = client.get(f"/api/list-versions?documentid={doc_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        
        found = any(v["link"] == "querydocid123" for v in data["versions"])
        assert found

    def test_list_versions_missing_document_id(self, client, auth_headers):
        """Testa utan document ID - ska ge 400 - TÄCKER MISSAD RAD 599."""
        response = client.get("/api/list-versions", headers=auth_headers)
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "document id required" in data["error"].lower()

    def test_list_versions_invalid_document_id_string(self, client, auth_headers):
        """Testa med ogiltigt document ID (sträng) - TÄCKER MISSADE RADER 596-599."""
        response = client.get("/api/list-versions?id=invalid", headers=auth_headers)
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "document id required" in data["error"].lower()

    def test_list_versions_document_not_found(self, client, auth_headers):
        """Testa med document ID som inte finns."""
        response = client.get("/api/list-versions/999999", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        assert len(data["versions"]) == 0

    def test_list_versions_document_owned_by_other_user(self, client):
        """Verifiera att man inte kan se versioner för någon annans dokument."""
        from server import app
        
        # Skapa användare 1
        c = app.test_client()
        login1 = "listver1"
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
        data = {"file": (pdf_io, "user1doc.pdf", "application/pdf")}
        r = c.post(
            "/api/upload-document",
            headers=headers1,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc1_id = r.get_json()["id"]
        
        # Skapa version för användare 1:s dokument
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, method, path)
                    VALUES (:doc_id, :link, :intended_for, :method, :path)
                """),
                {
                    "doc_id": doc1_id,
                    "link": "user1version",
                    "intended_for": "user1@example.com",
                    "method": "watermark",
                    "path": "/tmp/user1.pdf",
                }
            )
        
        # Skapa användare 2
        login2 = "listver2"
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
        
        # Användare 2 försöker hämta användare 1:s versioner
        response = c.get(f"/api/list-versions/{doc1_id}", headers=headers2)
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        # Ska vara tom eftersom användare 2 inte äger dokumentet
        assert len(data["versions"]) == 0

    def test_list_versions_empty_list(self, client, auth_headers):
        """Testa dokument som finns men inte har några versioner."""
        # Ladda upp dokument
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "noversions.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc_id = r.get_json()["id"]
        
        # Hämta versioner (ska vara tom lista)
        response = client.get(f"/api/list-versions/{doc_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        assert isinstance(data["versions"], list)
        assert len(data["versions"]) == 0

    def test_list_versions_multiple_versions_same_document(self, client, auth_headers):
        """Testa dokument med flera versioner."""
        from server import app
        
        # Ladda upp dokument
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "multiversions.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc_id = r.get_json()["id"]
        
        # Skapa flera versioner
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            for i in range(3):
                conn.execute(
                    text("""
                        INSERT INTO Versions (documentid, link, intended_for, method, path)
                        VALUES (:doc_id, :link, :intended_for, :method, :path)
                    """),
                    {
                        "doc_id": doc_id,
                        "link": f"multiversion{i}",
                        "intended_for": f"user{i}@example.com",
                        "method": "watermark" if i % 2 == 0 else "encryption",
                        "path": f"/tmp/multiversion{i}.pdf",
                    }
                )
        
        # Hämta versioner
        response = client.get(f"/api/list-versions/{doc_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        assert len(data["versions"]) == 3
        
        # Verifiera att alla versioner finns
        links = [v["link"] for v in data["versions"]]
        assert "multiversion0" in links
        assert "multiversion1" in links
        assert "multiversion2" in links

    def test_list_versions_response_structure(self, client, auth_headers):
        """Verifiera strukturen på response-objektet."""
        from server import app
        
        # Ladda upp dokument
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "structure.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202)
        doc_id = r.get_json()["id"]
        
        # Skapa version
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, method, path)
                    VALUES (:doc_id, :link, :intended_for, :method, :path)
                """),
                {
                    "doc_id": doc_id,
                    "link": "structuretest",
                    "intended_for": "structure@example.com",
                    "method": "watermark",
                    "path": "/tmp/structure.pdf",
                }
            )
        
        # Hämta versioner
        response = client.get(f"/api/list-versions/{doc_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        
        # Verifiera huvudstrukturen
        assert isinstance(data, dict)
        assert "versions" in data
        assert isinstance(data["versions"], list)
        
        # Verifiera version-objektets struktur
        version = data["versions"][0]
        assert "id" in version
        assert isinstance(version["id"], int)
        assert "documentid" in version
        assert version["documentid"] == doc_id
        assert "link" in version
        assert version["link"] == "structuretest"
        assert "intended_for" in version
        assert version["intended_for"] == "structure@example.com"
        assert "method" in version
        assert version["method"] == "watermark"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
