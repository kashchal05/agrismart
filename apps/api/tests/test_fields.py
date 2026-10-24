from tests.conftest import auth_headers, register


def test_create_field_computes_area_centroid_county(client, square_geometry):
    token = register(client, "a@farm.com")
    # ~0.008deg square near Plainview, TX -> roughly 65 ha.
    geom = square_geometry(-101.78, 34.12)
    resp = client.post(
        "/fields", json={"name": "North 80", "geometry": geom}, headers=auth_headers(token)
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "North 80"
    assert 50 < body["area_ha"] < 80            # geodesic area sanity
    assert abs(body["centroid_lat"] - 34.12) < 1e-6
    assert body["county"] == "Hale" and body["state"] == "TX"
    assert body["geometry"]["type"] == "Polygon"


def test_draw_three_fields_then_list(client, square_geometry):
    token = register(client, "a@farm.com")
    for i in range(3):
        geom = square_geometry(-101.78 + i * 0.02, 34.12)
        r = client.post(
            "/fields", json={"name": f"Field {i}", "geometry": geom}, headers=auth_headers(token)
        )
        assert r.status_code == 201
    listed = client.get("/fields", headers=auth_headers(token))
    assert listed.status_code == 200
    assert len(listed.json()) == 3


def test_invalid_polygon_rejected(client):
    token = register(client, "a@farm.com")
    bad = {"type": "Polygon", "coordinates": [[[-101.0, 34.0], [-100.0, 34.0]]]}  # <4 points
    resp = client.post(
        "/fields", json={"name": "bad", "geometry": bad}, headers=auth_headers(token)
    )
    assert resp.status_code == 422


def test_fields_require_auth(client):
    assert client.get("/fields").status_code == 403


# ---- the important one: multi-tenant isolation ----
def test_tenant_cannot_see_or_delete_others_field(client, square_geometry):
    alice = register(client, "alice@farm.com")
    bob = register(client, "bob@farm.com")

    created = client.post(
        "/fields",
        json={"name": "Alice secret field", "geometry": square_geometry(-101.78, 34.12)},
        headers=auth_headers(alice),
    )
    field_id = created.json()["id"]

    # Bob's list is empty.
    assert client.get("/fields", headers=auth_headers(bob)).json() == []
    # Bob cannot fetch Alice's field by id.
    assert client.get(f"/fields/{field_id}", headers=auth_headers(bob)).status_code == 404
    # Bob cannot delete Alice's field.
    assert client.delete(f"/fields/{field_id}", headers=auth_headers(bob)).status_code == 404
    # Alice still has it.
    assert client.get(f"/fields/{field_id}", headers=auth_headers(alice)).status_code == 200


def test_owner_can_delete(client, square_geometry):
    token = register(client, "a@farm.com")
    created = client.post(
        "/fields",
        json={"name": "del", "geometry": square_geometry(-101.78, 34.12)},
        headers=auth_headers(token),
    )
    fid = created.json()["id"]
    assert client.delete(f"/fields/{fid}", headers=auth_headers(token)).status_code == 204
    assert client.get(f"/fields/{fid}", headers=auth_headers(token)).status_code == 404
