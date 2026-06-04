import json
import os
import uuid
from datetime import datetime, timezone
import pika

def publicarevento(payload):
    parametros = pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST", "localhost"),
        port=int(os.getenv("RABBITMQ_PORT", "5672")),
        virtual_host="/",
        credentials=pika.PlainCredentials("facoffee", "facoffee")
    )
    conexao = pika.BlockingConnection(parametros)
    canal = conexao.channel()
    
    evento = {
        "eventId": f"evt_{uuid.uuid4().hex[:8]}",
        "eventType": "FinancialPendencyCreated",
        "occurredAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "version": "1.0",
        "payload": payload
    }
    
    canal.basic_publish(
        exchange="domain.events",
        routing_key="finance.pendency-created",
        body=json.dumps(evento).encode("utf-8")
    )
    conexao.close()