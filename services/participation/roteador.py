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

def formatarpagina(total: int, page: int = 0, size: int = 20):
    return {
        "page": page,
        "size": size,
        "totalElements": total,
        "totalPages": 1
    }


def formatarcota(cota: dict):
    return {
        "id": cota["id"],
        "name": cota["name"],
        "condition": cota["condition"],
        "items": cota["items"],
        "amount": cota["amount"],
        "status": cota["status"],
        "createdBy": cota.get("createdby"),
        "createdAt": cota.get("createdat")
    }


def formatarparticipacao(part: dict):
    resposta = {
        "id": part["id"],
        "userId": part["userid"],
        "quotaId": part["quotaid"],
        "status": part["status"],
        "startCycle": part.get("startcycle"),
        "quotaSnapshot": part.get("quotasnapshot"),
        "createdAt": part.get("createdat"),
        "cancelledAt": part.get("cancelledat"),
        "cancelReason": part.get("cancelreason"),
        "cancelRequestedBy": part.get("cancelrequestedby"),
        "effectiveCycle": part.get("effectivecycle")
    }

    return {chave: valor for chave, valor in resposta.items() if valor is not None}

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

def exigirautenticacao(credenciais: HTTPAuthorizationCredentials = fastapi.Depends(seguranca)):
    try:
        payload = jwt.decode(
            credenciais.credentials,
            options={"verify_signature": False, "verify_exp": False},
            algorithms=["RS256"]
        )
    except Exception:
        raise fastapi.HTTPException(status_code=401, detail="credencial invalida")

    return payload

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
    return formatarcota(bancocotas[idgerado])

@roteador.get("/quotas")
async def listarcotas(
    active: bool | None = None,
    condition: str | None = None,
    items: str | None = None
):
    cotas = list(bancocotas.values())

    if active is not None:
        statusesperado = "ACTIVE" if active else "INACTIVE"
        cotas = [cota for cota in cotas if cota["status"] == statusesperado]

    if condition is not None:
        cotas = [cota for cota in cotas if cota["condition"] == condition]

    if items is not None:
        cotas = [cota for cota in cotas if cota["items"] == items]

    return {
    "items": [formatarcota(cota) for cota in cotas],
    "page": formatarpagina(len(cotas))
}
@roteador.get("/quotas/{quotaid}")
async def obtercota(quotaid: str):
    if quotaid not in bancocotas:
        raise fastapi.HTTPException(status_code=404, detail="cota inexistente")
    return formatarcota(bancocotas[quotaid])

@roteador.patch("/quotas/{quotaid}")
async def atualizarcota(quotaid: str, dados: requestatualizarcota, token=fastapi.Depends(exigirpapel("MANAGER"))):
    if quotaid not in bancocotas:
        raise fastapi.HTTPException(status_code=404, detail="cota inexistente")
    cota = bancocotas[quotaid]
    if dados.name: cota["name"] = dados.name
    if dados.amount is not None: cota["amount"] = dados.amount
    if dados.active is not None: cota["status"] = "ACTIVE" if dados.active else "INACTIVE"
    return formatarcota(cota)

@roteador.delete("/quotas/{quotaid}")
async def desativarcota(quotaid: str, token=fastapi.Depends(exigirpapel("MANAGER"))):
    if quotaid not in bancocotas:
        raise fastapi.HTTPException(status_code=404, detail="cota inexistente")
    for part in bancoparticipacoes.values():
        if part["quotaid"] == quotaid and part["status"] == "ACTIVE":
            raise fastapi.HTTPException(status_code=409, detail="cota possui participacoes ativas")
    bancocotas[quotaid]["status"] = "INACTIVE"
    return formatarcota(bancocotas[quotaid])

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
    "eventId": f"evt_{uuid.uuid4().hex[:12]}",
    "eventType": "FinancialPendencyCreated",
    "occurredAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "version": "1.0",
    "payload": {
        "pendencyId": f"pend_{uuid.uuid4().hex[:6]}",
        "source": "MONTHLY_PARTICIPATION",
        "sourceId": idparticipacao,
        "userId": dados.userid,
        "cycle": dados.startcycle,
        "amount": cotaselecionada["amount"],
        "status": "PENDING"
    }
})

    return formatarparticipacao(bancoparticipacoes[idparticipacao])

@roteador.get("/participations")
async def listarparticipacoes(
    userid: str | None = fastapi.Query(None, alias="userId"),
    quotaid: str | None = fastapi.Query(None, alias="quotaId"),
    status: str | None = None,
    cycle: str | None = None
):
    participacoes = list(bancoparticipacoes.values())

    if userid is not None:
        participacoes = [part for part in participacoes if part["userid"] == userid]

    if quotaid is not None:
        participacoes = [part for part in participacoes if part["quotaid"] == quotaid]

    if status is not None:
        participacoes = [part for part in participacoes if part["status"] == status]

    if cycle is not None:
        participacoes = [part for part in participacoes if part.get("startcycle") == cycle]

    return {
    "items": [formatarparticipacao(part) for part in participacoes],
    "page": formatarpagina(len(participacoes))
}
    

@roteador.get("/participations/{partid}")
async def obterparticipacao(partid: str):
    if partid not in bancoparticipacoes:
        raise fastapi.HTTPException(status_code=404, detail="participacao inexistente")
    return formatarparticipacao(bancoparticipacoes[partid])
@roteador.patch("/participations/{partid}")
async def cancelarparticipacao(
    partid: str,
    dados: requestcancelamento,
    token=fastapi.Depends(exigirautenticacao)
):
    if partid not in bancoparticipacoes:
        raise fastapi.HTTPException(status_code=404, detail="participacao inexistente")

    part = bancoparticipacoes[partid]
    papeis = extrairpapeis(token)

    eh_manager = "MANAGER" in papeis
    eh_dono = dados.requestedby == part["userid"]

    if not eh_manager and not eh_dono:
        raise fastapi.HTTPException(
            status_code=403,
            detail="cancelamento permitido apenas para gestor ou titular da participacao"
        )

    part["status"] = "CANCELLED"
    part["cancelledat"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    part["cancelreason"] = dados.reason
    part["cancelrequestedby"] = dados.requestedby

    if dados.effectivecycle is not None:
        part["effectivecycle"] = dados.effectivecycle

    return formatarparticipacao(part)