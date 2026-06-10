from fastapi.testclient import TestClient
from main import app
from roteador import bancocotas, bancoparticipacoes
import pytest
import roteador
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

def test_listar_cotas_filtrando_por_active():
    bancocotas["quota_ativa"] = {
        "id": "quota_ativa",
        "name": "cota ativa",
        "condition": "DAILY",
        "items": "ALL",
        "amount": 10.0,
        "status": "ACTIVE"
    }

    bancocotas["quota_inativa"] = {
        "id": "quota_inativa",
        "name": "cota inativa",
        "condition": "DAILY",
        "items": "ALL",
        "amount": 20.0,
        "status": "INACTIVE"
    }

    resposta = cliente.get("/api/participation/quotas?active=true")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo["items"]) == 1
    assert corpo["items"][0]["id"] == "quota_ativa"


def test_listar_participacoes_filtrando_por_userid():
    bancoparticipacoes["part_001"] = {
        "id": "part_001",
        "userid": "usr_001",
        "quotaid": "quota_001",
        "status": "ACTIVE",
        "startcycle": "2026-06"
    }

    bancoparticipacoes["part_002"] = {
        "id": "part_002",
        "userid": "usr_002",
        "quotaid": "quota_001",
        "status": "ACTIVE",
        "startcycle": "2026-06"
    }

    resposta = cliente.get("/api/participation/participations?userId=usr_001")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo["items"]) == 1
    assert corpo["items"][0]["userid"] == "usr_001"


def test_participant_nao_pode_criar_cota(monkeypatch):
    monkeypatch.setattr(jwt, "decode", lambda *args, **kwargs: {"roles": ["PARTICIPANT"]})

    resposta = cliente.post("/api/participation/quotas", json={
        "name": "cota bloqueada",
        "condition": "DAILY",
        "items": "ALL",
        "amount": 50.0,
        "active": True
    }, headers={"Authorization": "Bearer token_falso"})

    assert resposta.status_code == 403

def test_registrar_adesao_publica_evento_com_metadados(monkeypatch):
    monkeypatch.setattr(jwt, "decode", lambda *args, **kwargs: {"roles": ["PARTICIPANT"]})

    eventos_publicados = []

    monkeypatch.setattr(roteador, "publicarevento", lambda evento: eventos_publicados.append(evento))

    bancocotas["quota_test_01"] = {
        "id": "quota_test_01",
        "status": "ACTIVE",
        "name": "teste",
        "condition": "DAILY",
        "items": "ALL",
        "amount": 10.0
    }

    resposta = cliente.post("/api/participation/participations", json={
        "userId": "usr_999",
        "quotaId": "quota_test_01",
        "startCycle": "2026-06"
    }, headers={"Authorization": "Bearer token_falso"})

    assert resposta.status_code == 201
    assert len(eventos_publicados) == 1

    evento = eventos_publicados[0]

    assert "eventId" in evento
    assert "occurredAt" in evento
    assert evento["type"] == "FinancialPendencyCreated"
    assert evento["userId"] == "usr_999"
    assert evento["amount"] == 10.0
    assert evento["status"] == "PENDING"