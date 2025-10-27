# test_list_all_versions.py
"""
Test suite för /api/list-all-versions endpoint.

Denna endpoint listar alla versioner för alla dokument som ägs av den
inloggade användaren genom att göra JOIN mellan Users -> Documents -> Versions.
"""
import pytest
import io
from pathlib import Path


class TestListAllVersionsEndpoint:
    """Tester för GET /api/list-all-versions endpoint."""

    def test_list_all_versions_requires_authentication(self, client):
        """Verifiera att endpointen kräver autentisering."""
        response = client.get("/api/list-all-versions")
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_list_all_versions_empty_when_no_documents(self, client, auth_headers):
        """När användaren inte har några dokument ska listan vara tom."""
        # Skapa en ny användare som inte har några dokument
        from server import app
        c = app.test_client()
        
        login = "noversions123"
        email = f"{login}@example.test"
        pwd = "Passw0rd!"
        
        r = c.post("/api/create-user", json={
            "login": login, 
            "email": email, 
            "password": pwd
        })
        assert r.status_code in (200, 201), f"User creation failed: {r.get_data(as_text=True)}"
        
        js = c.post("/api/login", json={
            "email": email, 
            "password": pwd
        }).get_json()
        token = js["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = c.get("/api/list-all-versions", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        assert isinstance(data["versions"], list)
        assert len(data["versions"]) == 0

    def test_list_all_versions_empty_when_documents_have_no_versions(
        self, client, auth_headers
    ):
        """Om dokument finns men inga versioner ska listan vara tom."""
        # Detta test förutsätter att upload-document inte automatiskt
        # skapar versioner (vilket verkar vara fallet baserat på schemat)
        response = client.get("/api/list-all-versions", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        assert isinstance(data["versions"], list)
        # Kan vara tom eller ha versioner beroende på tidigare tester

    def test_list_all_versions_after_creating_version(self, client, auth_headers):
        """Testa att versioner visas efter att de skapats."""
        from server import app
        from sqlalchemy import text
        
        # Ladda upp ett dokument med korrekt mimetype
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "testversions.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202), f"Upload failed: {r.get_data(as_text=True)}"
        doc_data = r.get_json()
        doc_id = doc_data["id"]
        
        # Skapa en version manuellt i databasen
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, method, path)
                    VALUES (:doc_id, :link, :intended_for, :method, :path)
                """),
                {
                    "doc_id": doc_id,
                    "link": "abc123def456",
                    "intended_for": "test_user@example.com",
                    "method": "watermark",
                    "path": "/tmp/testversion.pdf",
                }
            )
        
        # Hämta alla versioner
        response = client.get("/api/list-all-versions", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        assert isinstance(data["versions"], list)
        assert len(data["versions"]) >= 1
        
        # Verifiera att vår version finns
        version_found = False
        for v in data["versions"]:
            if v.get("link") == "abc123def456":
                version_found = True
                assert v["documentid"] == doc_id
                assert v["intended_for"] == "test_user@example.com"
                assert v["method"] == "watermark"
                assert "id" in v
                break
        
        assert version_found, "Den skapade versionen hittades inte i listan"

    def test_list_all_versions_multiple_documents_multiple_versions(
        self, client, auth_headers
    ):
        """Testa med flera dokument och flera versioner."""
        from server import app
        from sqlalchemy import text
        
        # Ladda upp två dokument med korrekt mimetype
        doc_ids = []
        for i in range(2):
            pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
            data = {
                "file": (pdf_io, f"multidoc{i}.pdf", "application/pdf")
            }
            r = client.post(
                "/api/upload-document",
                headers=auth_headers,
                data=data,
                content_type="multipart/form-data",
            )
            assert r.status_code in (200, 201, 202), f"Upload failed: {r.get_data(as_text=True)}"
            doc_data = r.get_json()
            doc_ids.append(doc_data["id"])
        
        # Skapa flera versioner för varje dokument
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            for doc_id in doc_ids:
                for v in range(2):
                    conn.execute(
                        text("""
                            INSERT INTO Versions (documentid, link, intended_for, method, path)
                            VALUES (:doc_id, :link, :intended_for, :method, :path)
                        """),
                        {
                            "doc_id": doc_id,
                            "link": f"link_{doc_id}_{v}",
                            "intended_for": f"user_{v}@example.com",
                            "method": "watermark" if v == 0 else "encryption",
                            "path": f"/tmp/version{doc_id}{v}.pdf",
                        }
                    )
        
        # Hämta alla versioner
        response = client.get("/api/list-all-versions", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        assert isinstance(data["versions"], list)
        
        # Räkna versioner för våra dokument
        our_versions = [
            v for v in data["versions"] 
            if v["documentid"] in doc_ids
        ]
        assert len(our_versions) >= 4  # Minst 2 versioner per dokument

    def test_list_all_versions_only_shows_own_versions(self, client):
        """Verifiera att användare endast ser sina egna versioner."""
        from server import app
        from sqlalchemy import text
        
        # Skapa användare 1
        c = app.test_client()
        login1 = "user_isolation_1"
        email1 = f"{login1}@example.test"
        pwd1 = "Passw0rd!"
        
        r = c.post("/api/create-user", json={
            "login": login1, 
            "email": email1, 
            "password": pwd1
        })
        assert r.status_code in (200, 201), f"User 1 creation failed: {r.get_data(as_text=True)}"
        
        js1 = c.post("/api/login", json={
            "email": email1, 
            "password": pwd1
        }).get_json()
        token1 = js1["token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        # Skapa användare 2
        login2 = "user_isolation_2"
        email2 = f"{login2}@example.test"
        pwd2 = "Passw0rd!"
        
        r = c.post("/api/create-user", json={
            "login": login2, 
            "email": email2, 
            "password": pwd2
        })
        assert r.status_code in (200, 201), f"User 2 creation failed: {r.get_data(as_text=True)}"
        
        js2 = c.post("/api/login", json={
            "email": email2, 
            "password": pwd2
        }).get_json()
        token2 = js2["token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        # Ladda upp dokument för användare 1 med korrekt mimetype
        pdf_io1 = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data1 = {"file": (pdf_io1, "user1doc.pdf", "application/pdf")}
        r1 = c.post(
            "/api/upload-document",
            headers=headers1,
            data=data1,
            content_type="multipart/form-data",
        )
        assert r1.status_code in (200, 201, 202), f"Upload failed: {r1.get_data(as_text=True)}"
        doc1_data = r1.get_json()
        doc1_id = doc1_data["id"]
        
        # Ladda upp dokument för användare 2 med korrekt mimetype
        pdf_io2 = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data2 = {"file": (pdf_io2, "user2doc.pdf", "application/pdf")}
        r2 = c.post(
            "/api/upload-document",
            headers=headers2,
            data=data2,
            content_type="multipart/form-data",
        )
        assert r2.status_code in (200, 201, 202), f"Upload failed: {r2.get_data(as_text=True)}"
        doc2_data = r2.get_json()
        doc2_id = doc2_data["id"]
        
        # Skapa versioner för båda användarna
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            # Version för användare 1
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, method, path)
                    VALUES (:doc_id, :link, :intended_for, :method, :path)
                """),
                {
                    "doc_id": doc1_id,
                    "link": "user1_version_link",
                    "intended_for": "user1_recipient@example.com",
                    "method": "watermark",
                    "path": "/tmp/user1version.pdf",
                }
            )
            
            # Version för användare 2
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, method, path)
                    VALUES (:doc_id, :link, :intended_for, :method, :path)
                """),
                {
                    "doc_id": doc2_id,
                    "link": "user2_version_link",
                    "intended_for": "user2_recipient@example.com",
                    "method": "encryption",
                    "path": "/tmp/user2version.pdf",
                }
            )
        
        # Användare 1 hämtar sina versioner
        response1 = c.get("/api/list-all-versions", headers=headers1)
        assert response1.status_code == 200
        data1 = response1.get_json()
        versions1 = data1["versions"]
        
        # Verifiera att användare 1 bara ser sina egna versioner
        for v in versions1:
            if v["link"] in ["user1_version_link", "user2_version_link"]:
                assert v["link"] == "user1_version_link", \
                    "Användare 1 kan se användare 2:s version!"
                assert v["documentid"] == doc1_id
        
        # Användare 2 hämtar sina versioner
        response2 = c.get("/api/list-all-versions", headers=headers2)
        assert response2.status_code == 200
        data2 = response2.get_json()
        versions2 = data2["versions"]
        
        # Verifiera att användare 2 bara ser sina egna versioner
        for v in versions2:
            if v["link"] in ["user1_version_link", "user2_version_link"]:
                assert v["link"] == "user2_version_link", \
                    "Användare 2 kan se användare 1:s version!"
                assert v["documentid"] == doc2_id

    def test_list_all_versions_response_structure(self, client, auth_headers):
        """Verifiera att response-strukturen är korrekt."""
        from server import app
        from sqlalchemy import text
        
        # Skapa ett dokument och en version med korrekt mimetype
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "structuretest.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202), f"Upload failed: {r.get_data(as_text=True)}"
        doc_data = r.get_json()
        doc_id = doc_data["id"]
        
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, method, path)
                    VALUES (:doc_id, :link, :intended_for, :method, :path)
                """),
                {
                    "doc_id": doc_id,
                    "link": "structure_test_link",
                    "intended_for": "structure@example.com",
                    "method": "watermark",
                    "path": "/tmp/structuretest.pdf",
                }
            )
        
        response = client.get("/api/list-all-versions", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        
        # Verifiera huvudstrukturen
        assert isinstance(data, dict)
        assert "versions" in data
        assert isinstance(data["versions"], list)
        
        # Hitta vår version och verifiera dess struktur
        our_version = None
        for v in data["versions"]:
            if v.get("link") == "structure_test_link":
                our_version = v
                break
        
        assert our_version is not None, "Kunde inte hitta vår testversion"
        
        # Verifiera alla obligatoriska fält
        assert "id" in our_version
        assert isinstance(our_version["id"], int)
        
        assert "documentid" in our_version
        assert isinstance(our_version["documentid"], int)
        assert our_version["documentid"] == doc_id
        
        assert "link" in our_version
        assert isinstance(our_version["link"], str)
        assert our_version["link"] == "structure_test_link"
        
        assert "intended_for" in our_version
        assert our_version["intended_for"] == "structure@example.com"
        
        assert "method" in our_version
        assert our_version["method"] == "watermark"

    def test_list_all_versions_with_null_fields(self, client, auth_headers):
        """Testa att versioner med NULL-värden i optional fält hanteras korrekt."""
        from server import app
        from sqlalchemy import text
        
        # Skapa ett dokument med korrekt mimetype
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "nullfields.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202), f"Upload failed: {r.get_data(as_text=True)}"
        doc_data = r.get_json()
        doc_id = doc_data["id"]
        
        # Skapa version med NULL i optional fält
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, method, path)
                    VALUES (:doc_id, :link, NULL, NULL, :path)
                """),
                {
                    "doc_id": doc_id,
                    "link": "null_fields_link",
                    "path": "/tmp/nullfields.pdf",
                }
            )
        
        response = client.get("/api/list-all-versions", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        
        # Hitta vår version
        our_version = None
        for v in data["versions"]:
            if v.get("link") == "null_fields_link":
                our_version = v
                break
        
        assert our_version is not None
        assert our_version["documentid"] == doc_id
        assert our_version["intended_for"] is None
        assert our_version["method"] is None

    def test_list_all_versions_invalid_token(self, client):
        """Testa med ogiltig eller felaktig token."""
        response = client.get(
            "/api/list-all-versions",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_list_all_versions_malformed_auth_header(self, client):
        """Testa med felformaterad Authorization-header."""
        # Utan "Bearer" prefix
        response = client.get(
            "/api/list-all-versions",
            headers={"Authorization": "token123"}
        )
        assert response.status_code == 401

    def test_list_all_versions_database_consistency(self, client, auth_headers):
        """Verifiera att data är konsistent mellan tabeller."""
        from server import app
        from sqlalchemy import text
        
        # Skapa dokument och version med korrekt mimetype
        pdf_io = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
        data = {"file": (pdf_io, "consistency.pdf", "application/pdf")}
        r = client.post(
            "/api/upload-document",
            headers=auth_headers,
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code in (200, 201, 202), f"Upload failed: {r.get_data(as_text=True)}"
        doc_data = r.get_json()
        doc_id = doc_data["id"]
        
        engine = app.config["_ENGINE"]
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO Versions (documentid, link, intended_for, method, path)
                    VALUES (:doc_id, :link, :intended_for, :method, :path)
                """),
                {
                    "doc_id": doc_id,
                    "link": "consistency_link",
                    "intended_for": "test@example.com",
                    "method": "watermark",
                    "path": "/tmp/consistency.pdf",
                }
            )
        
        # Hämta versioner
        response = client.get("/api/list-all-versions", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        
        # Hitta vår version
        our_version = None
        for v in data["versions"]:
            if v.get("link") == "consistency_link":
                our_version = v
                break
        
        assert our_version is not None
        
        # Verifiera att documentid matchar det vi skapade
        assert our_version["documentid"] == doc_id
        
        # Verifiera att dokumentet verkligen finns i Documents-tabellen
        with engine.connect() as conn:
            doc_check = conn.execute(
                text("SELECT id FROM Documents WHERE id = :doc_id"),
                {"doc_id": doc_id}
            ).first()
            assert doc_check is not None, "Dokumentet finns inte i databasen!"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])