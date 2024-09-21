import json
import os
import asyncio
import logging
import psycopg2
from psycopg2 import sql
from panoramisk import Manager


manager = Manager(
    loop=asyncio.get_event_loop(),
    host=os.environ['AMI_HOST'],
    port=int(os.environ['AMI_PORT']),
    username=os.environ['AMI_USERNAME'],
    secret=os.environ['AMI_PASSWORD']
)


logger = logging.getLogger('AMI')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

def log(msg, level='info'):
    """Função auxiliar para registrar logs com diferentes níveis."""
    if level == 'info':
        logger.info(msg)
    elif level == 'error':
        logger.error(msg)
    elif level == 'debug':
        logger.debug(msg)
    elif level == 'warning':
        logger.warning(msg)
    else:
        logger.info(msg)

class PostgresDB:
    def __init__(self, host, port, dbname, user, password):
        """Inicializa a conexão com o banco de dados PostgreSQL."""
        try:
            self.connection = psycopg2.connect(
                host=host,
                port=port,
                database=dbname,
                user=user,
                password=password
            )
            self.cursor = self.connection.cursor()
            log("✅ Conectado ao banco de dados PostgreSQL com sucesso.")
        except (Exception, psycopg2.DatabaseError) as error:
            log(f"❌ Erro ao conectar ao PostgreSQL: {error}", level='error')
            self.connection = None

    def insert_agent(self, uniqueid, fila, agente, ramal, logado_desde):
        """Insere um agente na tabela monitoring_agents."""
        if not self.connection:
            log("❌ Sem conexão com o banco de dados.", level='error')
            return

        try:
            insert_query = """
            INSERT INTO monitoring_agents (
                uniqueid, fila, agente, ramal, chamadas, ultima_chamada, status, logado_desde
            ) VALUES (%s, %s, %s, %s, 0, NULL, 1, to_timestamp(%s))
            ON CONFLICT (uniqueid) DO NOTHING;
            """
            self.cursor.execute(insert_query, (uniqueid, fila, agente, ramal, logado_desde))
            self.connection.commit()
            log(f"✅ Agente '{agente}' inserido com sucesso na tabela 'monitoring_agents'.")
        except (Exception, psycopg2.DatabaseError) as error:
            log(f"❌ Erro ao inserir agente: {error}", level='error')
            self.connection.rollback()

    def remove_agent(self, fila, ramal):
        """Remove um agente da tabela monitoring_agents."""
        if not self.connection:
            log("❌ Sem conexão com o banco de dados.", level='error')
            return

        try:
            delete_query = """
            DELETE FROM monitoring_agents WHERE fila = %s AND ramal = %s;
            """
            self.cursor.execute(delete_query, (fila,ramal))
            self.connection.commit()
            log(f"✅ Agente com ramal '{ramal}' removido com sucesso da fila '{fila}'")
        except (Exception, psycopg2.DatabaseError) as error:
            log(f"❌ Erro ao remover agente: {error}", level='error')
            self.connection.rollback()

    def update_agent_status(self, fila, ramal, chamadas, ultima_chamada, status):
        """Atualiza os campos 'chamadas', 'ultima_chamada' e 'status' para um agente existente."""
        if not self.connection:
            log("❌ Sem conexão com o banco de dados.", level='error')
            return

        try:
            update_query = """
            UPDATE monitoring_agents
            SET
                fila = %s,
                chamadas = %s,
                ultima_chamada = to_timestamp(%s),
                status = %s
            WHERE
                fila = %s AND ramal = %s;
            """
            self.cursor.execute(update_query, (fila, chamadas, ultima_chamada, status, fila, ramal))
            if self.cursor.rowcount > 0:
                self.connection.commit()
                log(f"✅ Atualizado status do agente na fila {fila} e ramal {ramal}.")
            else:
                log(f"⚠️ Nenhum agente encontrado na fila {fila} e ramal {ramal} para atualizar.", level='warning')
        except (Exception, psycopg2.DatabaseError) as error:
            log(f"❌ Erro ao atualizar status do agente: {error}", level='error')
            self.connection.rollback()


db = PostgresDB(
    host=os.environ['DB_HOST'],
    port=int(os.environ['DB_PORT']),
    dbname=os.environ['DB_NAME'],
    user=os.environ['DB_USERNAME'],
    password=os.environ['DB_PASSWORD']
)

@manager.register_event('UserEvent')
def handle_user_event(manager, message):
    """Manipulador para eventos UserEvent."""
    data = dict(message.items())
    user_event = data.get('UserEvent', '')

    if user_event == 'AGENTLOGIN':
        uniqueid = data.get('Id')  
        fila = data.get('Fila')
        agente = data.get('Agente')
        ramal = data.get('Ramal')
        logado_desde = data.get('Id')  

        if all([uniqueid, fila, agente, ramal, logado_desde]):
            db.insert_agent(uniqueid, fila, agente, ramal, logado_desde)
        else:
            log(f"⚠️ Dados insuficientes para AGENTLOGIN: {data}", level='warning')

    elif user_event == 'AGENTLOGOFF':
        fila  = data.get('Fila')
        ramal = data.get('Ramal')

        if all([fila,ramal]):
            db.remove_agent(fila, ramal)
        else:
            log(f"⚠️ Dados insuficientes para AGENTLOGOFF: {data}", level='warning')
    else:
        log(f"🔍 Evento UserEvent desconhecido: {user_event}", level='warning')

@manager.register_event('QueueMemberStatus')
def handle_queue_member_status(manager, message):
    """Manipulador para eventos QueueMemberStatus."""
    data = dict(message.items())

    queue = data.get('Queue')
    member_name = data.get('MemberName')
    interface = data.get('Interface')
    calls_taken = data.get('CallsTaken')
    last_call = data.get('LastCall')
    status = data.get('Status')

    if not all([queue, member_name, interface, calls_taken, last_call, status]):
        log(f"⚠️ Dados insuficientes para QueueMemberStatus: {data}", level='warning')
        return

    
    try:
        ramal = interface.split('/')[1].split('@')[0]
    except IndexError:
        log(f"⚠️ Formato inesperado para 'Interface': {interface}", level='warning')
        return

    
    if last_call.isdigit() and int(last_call) > 0:
        ultima_chamada = last_call
    else:
        ultima_chamada = None  

    
    try:
        chamadas = int(calls_taken)
        status_int = int(status)
    except ValueError:
        log(f"⚠️ Valores inválidos para 'CallsTaken' ou 'Status': {data}", level='warning')
        return
    
    db.update_agent_status(queue, ramal, chamadas, ultima_chamada, status_int)
    

def main():
    log("🔄 Iniciando o Manager do AMI...")
    manager.connect()
    try:
        manager.loop.run_forever()
    except KeyboardInterrupt:
        log("⏹️ Encerrando o Manager do AMI...")
    finally:
        manager.loop.close()
        if db.connection:
            db.connection.close()
            log("🔒 Conexão com o banco de dados PostgreSQL encerrada.")

if __name__ == '__main__':
    main()
