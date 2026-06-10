from fastapi.testclient import TestClient
from main import app
from roteador import bancocotas, bancoparticipacoes
import pytest
import jwt

cliente = TestClient(app)

@pytest.fixture(autouse=True)
def limparbanco():
    bancocotas.clear()
    bancoparticipacoes.clear()
    yield

def test_criacaocota_sucesso(monkeypatch):
    monkeypatch.setattr(jwt, "decode", lambda *args, **kwargs: {"realm_access": {"roles": ["MANAGER"]}, "preferred_username": "admin"})
    
    resposta = cliente.post("/api/participation/quotas", json={
        "name": "cota automatizada", "condition": "DAILY", 
        "items": "ALL", "amount": 50.0, "active": True
    }, headers={"Authorization": "Bearer token_falso"})
    
    assert resposta.status_code == 201
    assert "id" in resposta.json()

def test_valornegativo_rejeitado(monkeypatch):
    monkeypatch.setattr(jwt, "decode", lambda *args, **kwargs: {"realm_access": {"roles": ["MANAGER"]}})
    
    resposta = cliente.post("/api/participation/quotas", json={
        "name": "cota invalida", "condition": "DAILY", 
        "items": "ALL", "amount": -10.0, "active": True
    }, headers={"Authorization": "Bearer token_falso"})
    
    assert resposta.status_code == 422 

def test_adesaoduplicada_bloqueada(monkeypatch):
    monkeypatch.setattr(jwt, "decode", lambda *args, **kwargs: {"realm_access": {"roles": ["PARTICIPANT"]}})
    
    bancocotas["quota_test_01"] = {"id": "quota_test_01", "status": "ACTIVE", "name": "teste", "condition": "DAILY", "items": "ALL", "amount": 10.0}
    bancoparticipacoes["part_test_01"] = {"id": "part_test_01", "userid": "usr_999", "quotaid": "quota_test_01", "status": "ACTIVE"}

    resposta = cliente.post("/api/participation/participations", json={
        "userId": "usr_999", "quotaId": "quota_test_01", "startCycle": "2026-06"
    }, headers={"Authorization": "Bearer token_falso"})
    
    assert resposta.status_code == 409
    assert "ja possui cota ativa" in resposta.json()["detail"]

def test_participant_pode_cancelar_propria_participacao(monkeypatch):
    monkeypatch.setattr(jwt, "decode", lambda *args, **kwargs: {"roles": ["PARTICIPANT"]})

    bancoparticipacoes["part_test_01"] = {
        "id": "part_test_01",
        "userid": "usr_999",
        "quotaid": "quota_test_01",
        "status": "ACTIVE"
    }

    resposta = cliente.patch("/api/participation/participations/part_test_01", json={
        "requestedBy": "usr_999",
        "reason": "cancelamento solicitado pelo participante",
        "effectiveCycle": "2026-06"
    }, headers={"Authorization": "Bearer token_falso"})

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "CANCELLED"
    assert resposta.json()["cancelrequestedby"] == "usr_999"


def test_participant_nao_pode_cancelar_participacao_de_outro_usuario(monkeypatch):
    monkeypatch.setattr(jwt, "decode", lambda *args, **kwargs: {"roles": ["PARTICIPANT"]})

    bancoparticipacoes["part_test_01"] = {
        "id": "part_test_01",
        "userid": "usr_999",
        "quotaid": "quota_test_01",
        "status": "ACTIVE"
    }

    resposta = cliente.patch("/api/participation/participations/part_test_01", json={
        "requestedBy": "usr_123",
        "reason": "tentativa indevida",
        "effectiveCycle": "2026-06"
    }, headers={"Authorization": "Bearer token_falso"})

    assert resposta.status_code == 403
    assert "cancelamento permitido apenas" in resposta.json()["detail"]


def test_manager_pode_cancelar_qualquer_participacao(monkeypatch):
    monkeypatch.setattr(jwt, "decode", lambda *args, **kwargs: {"roles": ["MANAGER"]})

    bancoparticipacoes["part_test_01"] = {
        "id": "part_test_01",
        "userid": "usr_999",
        "quotaid": "quota_test_01",
        "status": "ACTIVE"
    }

    resposta = cliente.patch("/api/participation/participations/part_test_01", json={
        "requestedBy": "manager_001",
        "reason": "cancelamento administrativo",
        "effectiveCycle": "2026-06"
    }, headers={"Authorization": "Bearer token_falso"})

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "CANCELLED"
    assert resposta.json()["cancelrequestedby"] == "manager_001"    