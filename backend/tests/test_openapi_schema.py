"""
OpenAPI contract regression tests.

These assertions guard the API's public contract: they ensure every Pydantic
request model moved into backend/services/models.py is still registered with
FastAPI and that endpoints reference the correct request-body schemas. No
database and no HTTP client are required.
"""
from backend.services import models
from backend.services.api import app

EXPECTED_MODELS = [
    "PatternCreate", "PatternUpdate",
    "CardCreate", "CardUpdate",
    "PathNode", "PathEdge", "PathCreate", "PathUpdate",
    "ThreatCreate", "ThreatUpdate",
    "ModelCreate", "ModelUpdate",
    "AssetCreate", "AssetUpdate",
    "VulnerabilityCreate", "VulnerabilityUpdate",
    "CountermeasureCreate", "CountermeasureUpdate",
    "ProductCreate", "ProductUpdate",
]


def _schema():
    return app.openapi()


def test_all_models_registered_in_openapi():
    schemas = _schema()["components"]["schemas"]
    missing = [name for name in EXPECTED_MODELS if name not in schemas]
    assert not missing, f"Models missing from OpenAPI: {missing}"


def test_expected_paths_present():
    paths = _schema()["paths"]
    expected = [
        "/",
        "/patterns", "/patterns/search", "/patterns/{pattern_id}",
        "/cards", "/cards/{card_id}", "/cards/{card_id}/story",
        "/patterns/{pattern_id}/cards",
        "/paths", "/paths/{path_id}",
        "/threats", "/threats/search", "/threats/{threat_id}",
        "/models", "/models/{model_id}", "/models/{model_id}/activate",
        "/active-model",
        "/assets", "/assets/{asset_id}",
        "/vulnerabilities", "/vulnerabilities/{vulnerability_id}",
        "/countermeasures", "/countermeasures/{countermeasure_id}",
        "/products", "/products/{product_id}",
        "/views", "/query/{table}", "/log",
    ]
    missing = [p for p in expected if p not in paths]
    assert not missing, f"Paths missing from OpenAPI: {missing}"


def test_pattern_create_fields_and_required():
    s = _schema()["components"]["schemas"]["PatternCreate"]
    assert set(s.get("required", [])) == {"name", "description", "kind"}
    assert {"name", "description", "kind", "story", "taxonomy"} <= set(s["properties"])


def test_product_create_required_fields():
    s = _schema()["components"]["schemas"]["ProductCreate"]
    assert set(s.get("required", [])) == {"submission_number", "device"}


def test_post_patterns_references_pattern_create():
    body = _schema()["paths"]["/patterns"]["post"]["requestBody"]
    ref = body["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/PatternCreate")


def test_put_threats_references_threat_update():
    body = _schema()["paths"]["/threats/{threat_id}"]["put"]["requestBody"]
    ref = body["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/ThreatUpdate")


def test_model_classes_are_pydantic_basemodels():
    from pydantic import BaseModel
    for name in EXPECTED_MODELS:
        cls = getattr(models, name, None)
        assert cls is not None, f"{name} missing from backend.services.models"
        assert issubclass(cls, BaseModel), f"{name} is not a pydantic BaseModel"
