import fastapi
import uuid
import jwt
from datetime import datetime, timezone
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from esquemas import requestadesao, requestcriarcota, requestatualizarcota, requestcancelamento
from mensageria import publicarevento

roteador = fastapi.APIRouter()
seguranca = HTTPBearer()

bancocotas = {}
bancoparticipacoes = {}

def extrairpapeis(payload: dict):
    papeis = payload.get("roles")

    if papeis is None:
        papeis = payload.get("realm_access", {}).get("roles", [])

    return papeis

def exigirpapel(papelnecessario: str):
    def validador(credenciais: HTTPAuthorizationCredentials = fastapi.Depends(seguranca)):
        try:
            payload = jwt.decode(
                credenciais.credentials,
                options={"verify_signature": False, "verify_exp": False},
                algorithms=["RS256"]
            )
        except Exception:
            raise fastapi.HTTPException(status_code=401, detail="credencial invalida")

        papeis = extrairpapeis(payload)

        if papelnecessario not in papeis:
            raise fastapi.HTTPException(status_code=403, detail="acesso negado pelo dominio")

        return payload

    return validador

@roteador.post("/quotas", status_code=201)
async def criarcota(dados: requestcriarcota, token=fastapi.Depends(exigirpapel("MANAGER"))):
    idgerado = f"quota_{uuid.uuid4().hex[:6]}"
    bancocotas[idgerado] = {
        "id": idgerado, "name": dados.name, "condition": dados.condition,
        "items": dados.items, "amount": dados.amount,
        "status": "ACTIVE" if dados.active else "INACTIVE",
        "createdby": token.get("preferred_username", "system"),
        "createdat": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    return bancocotas[idgerado]

@roteador.get("/quotas")
async def listarcotas():
    return {"items": list(bancocotas.values()), "page": {"page": 0, "size": 20, "totalelements": len(bancocotas), "totalpages": 1}}

@roteador.get("/quotas/{quotaid}")
async def obtercota(quotaid: str):
    if quotaid not in bancocotas:
        raise fastapi.HTTPException(status_code=404, detail="cota inexistente")
    return bancocotas[quotaid]

@roteador.patch("/quotas/{quotaid}")
async def atualizarcota(quotaid: str, dados: requestatualizarcota, token=fastapi.Depends(exigirpapel("MANAGER"))):
    if quotaid not in bancocotas:
        raise fastapi.HTTPException(status_code=404, detail="cota inexistente")
    cota = bancocotas[quotaid]
    if dados.name: cota["name"] = dados.name
    if dados.amount is not None: cota["amount"] = dados.amount
    if dados.active is not None: cota["status"] = "ACTIVE" if dados.active else "INACTIVE"
    return cota

@roteador.delete("/quotas/{quotaid}")
async def desativarcota(quotaid: str, token=fastapi.Depends(exigirpapel("MANAGER"))):
    if quotaid not in bancocotas:
        raise fastapi.HTTPException(status_code=404, detail="cota inexistente")
    for part in bancoparticipacoes.values():
        if part["quotaid"] == quotaid and part["status"] == "ACTIVE":
            raise fastapi.HTTPException(status_code=409, detail="cota possui participacoes ativas")
    bancocotas[quotaid]["status"] = "INACTIVE"
    return bancocotas[quotaid]

@roteador.post("/participations", status_code=201)
async def registraradesao(dados: requestadesao, token=fastapi.Depends(exigirpapel("PARTICIPANT"))):
    if dados.quotaid not in bancocotas:
        raise fastapi.HTTPException(status_code=400, detail="cota inexistente")
    cotaselecionada = bancocotas[dados.quotaid]
    if cotaselecionada["status"] != "ACTIVE":
        raise fastapi.HTTPException(status_code=400, detail="cota inativa")
    for part in bancoparticipacoes.values():
        if part["userid"] == dados.userid and part["status"] == "ACTIVE":
            raise fastapi.HTTPException(status_code=409, detail="usuario ja possui cota ativa")
            
    idparticipacao = f"part_{uuid.uuid4().hex[:6]}"
    bancoparticipacoes[idparticipacao] = {
        "id": idparticipacao, "userid": dados.userid, "quotaid": dados.quotaid,
        "status": "ACTIVE", "startcycle": dados.startcycle,
        "quotasnapshot": {
            "quotaid": cotaselecionada["id"], "name": cotaselecionada["name"],
            "condition": cotaselecionada["condition"], "items": cotaselecionada["items"],
            "amount": cotaselecionada["amount"]
        },
        "createdat": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    publicarevento({
        "pendencyId": f"pend_{uuid.uuid4().hex[:6]}", "source": "MONTHLY_PARTICIPATION",
        "sourceId": idparticipacao, "userId": dados.userid, "cycle": dados.startcycle,
        "amount": cotaselecionada["amount"], "status": "PENDING"
    })
    return bancoparticipacoes[idparticipacao]

@roteador.get("/participations")
async def listarparticipacoes():
    return {"items": list(bancoparticipacoes.values()), "page": {"page": 0, "size": 20, "totalelements": len(bancoparticipacoes), "totalpages": 1}}

@roteador.get("/participations/{partid}")
async def obterparticipacao(partid: str):
    if partid not in bancoparticipacoes:
        raise fastapi.HTTPException(status_code=404, detail="participacao inexistente")
    return bancoparticipacoes[partid]

@roteador.patch("/participations/{partid}")
async def cancelarparticipacao(partid: str, dados: requestcancelamento):
    if partid not in bancoparticipacoes:
        raise fastapi.HTTPException(status_code=404, detail="participacao inexistente")
    part = bancoparticipacoes[partid]
    part["status"] = "CANCELLED"
    part["cancelledat"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return part