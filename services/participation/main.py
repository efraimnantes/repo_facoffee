import fastapi
import uvicorn
import threading
import pika
import json
import os
from roteador import roteador, bancoparticipacoes

app = fastapi.FastAPI()
app.include_router(roteador, prefix="/api/participation")

def consumirfila():
    parametros = pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST", "localhost"),
        port=int(os.getenv("RABBITMQ_PORT", "5672")),
        virtual_host="/",
        credentials=pika.PlainCredentials("facoffee", "facoffee")
    )
    conexao = pika.BlockingConnection(parametros)
    canal = conexao.channel()
    
    def processarmensagem(ch, method, properties, body):
        try:
            payload = json.loads(body.decode("utf-8"))
            if payload.get("eventType") == "UserDeactivated":
                userid = payload.get("payload", {}).get("userId")
                for part in bancoparticipacoes.values():
                    if part["userid"] == userid and part["status"] == "ACTIVE":
                        part["status"] = "CANCELLED"
                        print(f"participacao de {userid} cancelada por evento assincrono")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(f"erro ao processar evento: {e}")

    canal.basic_consume(queue="participation.user-deactivated", on_message_callback=processarmensagem)
    canal.start_consuming()

if __name__ == "__main__":
    threadconsumidor = threading.Thread(target=consumirfila, daemon=True)
    threadconsumidor.start()
    uvicorn.run(app, host="0.0.0.0", port=3002)