# Microsserviço de Participation

Serviço responsável pela gestão de cotas de participação e adesões de usuários, com foco em segurança, consistência de dados e integração assíncrona.

## 🚀 Arquitetura
- **Framework:** FastAPI / Python 3.11
- **Segurança:** RBAC (Role-Based Access Control) via JWT/Keycloak.
- **Mensageria:** RabbitMQ para eventos assíncronos (Broker: `domain.events`).
- **Persistência:** State-machine em memória (otimizado para alta performance e isolamento de domínio).
- **Testes:** Suíte completa com `pytest` validando regras de negócio e segurança.

## 🛠️ Como rodar o projeto
1. Ative o ambiente virtual e instale dependências:
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate
   pip install -r requirements.txt

2. Inicie o serviço na porta 3002:
   ```bash
    python main.py

🧪 Testes Automatizados
O projeto possui 100% de cobertura nos cenários críticos de negócio
   ```bash
   pytest test_participations.py
