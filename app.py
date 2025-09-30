from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import psycopg
import pandas as pd
import plotly.express as px
import plotly.utils
import json
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'  # Necessário para flash messages

# Configurações do banco de dados
DB_CONFIG = {
    'host': 'englifeinfor.ddns.net',
    'dbname': 'englife_db',
    'user': 'englife',
    'password': '449140',
    'port': 4491,
    'connect_timeout': 5
}

def get_db_connection():
    """Estabelece conexão com o banco de dados"""
    try:
        conn = psycopg.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Erro na conexão: {e}")
        return None

@app.route('/')
def index():
    """Página inicial - redireciona para dashboard"""
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    """Dashboard principal com estatísticas"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Erro de conexão com o banco de dados"), 500
    
    try:
        cursor = conn.cursor()
        
        # Estatísticas gerais
        stats = {}
        
        # Contagem de dispositivos
        cursor.execute("SELECT COUNT(*) FROM dispositivos")
        stats['total_dispositivos'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dispositivos WHERE tipo = 'alimentador'")
        stats['total_alimentadores'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dispositivos WHERE tipo = 'datalogger'")
        stats['total_dataloggers'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dispositivos WHERE online = true")
        stats['dispositivos_online'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM localizacoes")
        stats['total_localizacoes'] = cursor.fetchone()[0]
        
        # Últimas leituras
        cursor.execute("""
            SELECT l.nome as localizacao, s.posicao, ls.valor, ls.timestamp
            FROM leituras_sensores ls
            JOIN sensores s ON ls.sensor_id = s.id
            JOIN dataloggers d ON s.datalogger_id = d.id
            JOIN dispositivos dev ON d.dispositivo_id = dev.id
            JOIN localizacoes l ON dev.localizacao_id = l.id
            WHERE ls.timestamp >= NOW() - INTERVAL '1 hour'
            ORDER BY ls.timestamp DESC
            LIMIT 10
        """)
        ultimas_leituras = cursor.fetchall()
        
        # Alertas ativos
        cursor.execute("""
            SELECT tipo, mensagem, timestamp, severidade
            FROM alertas 
            WHERE resolvido = false
            ORDER BY timestamp DESC
            LIMIT 5
        """)
        alertas_ativos = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('dashboard.html', 
                             stats=stats, 
                             ultimas_leituras=ultimas_leituras,
                             alertas_ativos=alertas_ativos)
    
    except Exception as e:
        return render_template('error.html', message=f"Erro ao carregar dashboard: {e}"), 500

@app.route('/dispositivos')
def dispositivos():
    """Lista todos os dispositivos"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Erro de conexão com o banco de dados"), 500
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT d.id, d.nome, d.tipo, d.mac_address, d.ip_address, 
                   d.online, d.ultima_comunicacao, l.nome as localizacao
            FROM dispositivos d
            LEFT JOIN localizacoes l ON d.localizacao_id = l.id
            ORDER BY d.tipo, d.nome
        """)
        
        dispositivos = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template('dispositivos.html', dispositivos=dispositivos)
    
    except Exception as e:
        return render_template('error.html', message=f"Erro ao carregar dispositivos: {e}"), 500

@app.route('/alimentadores')
def alimentadores():
    """Página de alimentadores"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Erro de conexão com o banco de dados"), 500
    
    try:
        cursor = conn.cursor()
        
        # Alimentadores com informações completas
        cursor.execute("""
            SELECT 
                a.id, dev.nome, l.nome as localizacao, 
                a.capacidade_racao, a.vazao_media, a.motor_ligado,
                dev.online, c.ativa as config_ativa, c.peso_diario
            FROM alimentadores a
            JOIN dispositivos dev ON a.dispositivo_id = dev.id
            JOIN localizacoes l ON dev.localizacao_id = l.id
            LEFT JOIN config_alimentadores c ON a.id = c.alimentador_id
            ORDER BY dev.nome
        """)
        
        alimentadores = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('alimentadores.html', alimentadores=alimentadores)
    
    except Exception as e:
        return render_template('error.html', message=f"Erro ao carregar alimentadores: {e}"), 500

@app.route('/dataloggers')
def dataloggers():
    """Página de dataloggers"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Erro de conexão com o banco de dados"), 500
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                d.id, dev.nome, l.nome as localizacao, 
                d.quantidade_sensores, d.intervalo_leitura,
                dev.online, dev.ultima_comunicacao
            FROM dataloggers d
            JOIN dispositivos dev ON d.dispositivo_id = dev.id
            JOIN localizacoes l ON dev.localizacao_id = l.id
            ORDER BY dev.nome
        """)
        
        dataloggers = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('dataloggers.html', dataloggers=dataloggers)
    
    except Exception as e:
        return render_template('error.html', message=f"Erro ao carregar dataloggers: {e}"), 500

@app.route('/leituras')
def leituras():
    """Página de leituras dos sensores"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Erro de conexão com o banco de dados"), 500
    
    try:
        cursor = conn.cursor()
        
        # Filtros
        localizacao = request.args.get('localizacao', '')
        sensor_type = request.args.get('tipo', '')
        horas = request.args.get('horas', '24')
        
        query = """
            SELECT 
                l.nome as localizacao,
                s.posicao as tipo_sensor,
                ls.valor,
                ls.timestamp,
                dev.nome as datalogger
            FROM leituras_sensores ls
            JOIN sensores s ON ls.sensor_id = s.id
            JOIN dataloggers d ON s.datalogger_id = d.id
            JOIN dispositivos dev ON d.dispositivo_id = dev.id
            JOIN localizacoes l ON dev.localizacao_id = l.id
            WHERE ls.timestamp >= NOW() - INTERVAL %s hours
        """
        params = [horas]
        
        if localizacao:
            query += " AND l.nome = %s"
            params.append(localizacao)
        
        if sensor_type:
            query += " AND s.posicao = %s"
            params.append(sensor_type)
        
        query += " ORDER BY ls.timestamp DESC LIMIT 1000"
        
        cursor.execute(query, params)
        leituras = cursor.fetchall()
        
        # Localizações para o filtro
        cursor.execute("SELECT DISTINCT nome FROM localizacoes ORDER BY nome")
        localizacoes = [row[0] for row in cursor.fetchall()]
        
        # Tipos de sensor para o filtro
        cursor.execute("SELECT DISTINCT posicao FROM sensores ORDER BY posicao")
        tipos_sensor = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return render_template('leituras.html', 
                             leituras=leituras,
                             localizacoes=localizacoes,
                             tipos_sensor=tipos_sensor,
                             filtros=request.args)
    
    except Exception as e:
        return render_template('error.html', message=f"Erro ao carregar leituras: {e}"), 500

@app.route('/graficos')
def graficos():
    """Página com gráficos das leituras"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Erro de conexão com o banco de dados"), 500
    
    try:
        cursor = conn.cursor()
        
        # Dados para gráficos - últimas 24 horas
        cursor.execute("""
            SELECT 
                l.nome as localizacao,
                s.posicao as tipo_sensor,
                ls.valor,
                ls.timestamp
            FROM leituras_sensores ls
            JOIN sensores s ON ls.sensor_id = s.id
            JOIN dataloggers d ON s.datalogger_id = d.id
            JOIN dispositivos dev ON d.dispositivo_id = dev.id
            JOIN localizacoes l ON dev.localizacao_id = l.id
            WHERE ls.timestamp >= NOW() - INTERVAL '24 hours'
            ORDER BY ls.timestamp
        """)
        
        dados = cursor.fetchall()
        
        graphs = []
        
        if dados:
            # Converter para DataFrame
            df = pd.DataFrame(dados, columns=['localizacao', 'tipo_sensor', 'valor', 'timestamp'])
            
            # Criar gráficos
            if not df.empty:
                # Gráfico de linhas por localização e tipo de sensor
                fig = px.line(df, x='timestamp', y='valor', color='localizacao', 
                             line_group='tipo_sensor', title='Temperaturas por Localização')
                graphs.append(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder))
                
                # Gráfico de boxplot por tipo de sensor
                fig2 = px.box(df, x='tipo_sensor', y='valor', 
                             title='Distribuição de Temperaturas por Tipo de Sensor')
                graphs.append(json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder))
        
        cursor.close()
        conn.close()
        
        return render_template('graficos.html', graphs=graphs)
    
    except Exception as e:
        return render_template('error.html', message=f"Erro ao carregar gráficos: {e}"), 500

# =============================================
# ROTAS DE CADASTRO
# =============================================

@app.route('/cadastros')
def cadastros():
    """Página principal de cadastros"""
    return render_template('cadastros.html')

# CADASTRO DE LOCALIZAÇÕES
@app.route('/cadastros/localizacoes')
def cadastrar_localizacao():
    """Formulário para cadastrar localização"""
    return render_template('cadastros/localizacao.html')

@app.route('/cadastros/localizacoes/salvar', methods=['POST'])
def salvar_localizacao():
    """Salva uma nova localização"""
    try:
        nome = request.form['nome']
        descricao = request.form['descricao']
        tipo = request.form['tipo']
        
        conn = get_db_connection()
        if not conn:
            flash('Erro de conexão com o banco de dados', 'error')
            return redirect(url_for('cadastrar_localizacao'))
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO localizacoes (nome, descricao, tipo)
            VALUES (%s, %s, %s)
        """, (nome, descricao, tipo))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Localização cadastrada com sucesso!', 'success')
        return redirect(url_for('cadastros'))
    
    except Exception as e:
        flash(f'Erro ao cadastrar localização: {str(e)}', 'error')
        return redirect(url_for('cadastrar_localizacao'))

# CADASTRO DE DISPOSITIVOS
@app.route('/cadastros/dispositivos')
def cadastrar_dispositivo():
    """Formulário para cadastrar dispositivo"""
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'error')
        return redirect(url_for('cadastros'))
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome FROM localizacoes ORDER BY nome")
    localizacoes = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('cadastros/dispositivo.html', localizacoes=localizacoes)

@app.route('/cadastros/dispositivos/salvar', methods=['POST'])
def salvar_dispositivo():
    """Salva um novo dispositivo"""
    try:
        nome = request.form['nome']
        descricao = request.form['descricao']
        mac_address = request.form['mac_address']
        ip_address = request.form.get('ip_address', '')
        tipo = request.form['tipo']
        modelo = request.form.get('modelo', '')
        localizacao_id = request.form.get('localizacao_id') or None
        
        conn = get_db_connection()
        if not conn:
            flash('Erro de conexão com o banco de dados', 'error')
            return redirect(url_for('cadastrar_dispositivo'))
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dispositivos (localizacao_id, nome, descricao, mac_address, ip_address, tipo, modelo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (localizacao_id, nome, descricao, mac_address, ip_address, tipo, modelo))
        
        # Obter o ID do dispositivo inserido
        dispositivo_id = cursor.fetchone()[0]
        
        # Se for alimentador ou datalogger, criar registro na tabela específica
        if tipo == 'alimentador':
            cursor.execute("""
                INSERT INTO alimentadores (dispositivo_id, capacidade_racao, vazao_media)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (dispositivo_id, 0, 0))
            
            alimentador_id = cursor.fetchone()[0]
            
            # Criar configuração padrão
            cursor.execute("""
                INSERT INTO config_alimentadores (alimentador_id, ativa)
                VALUES (%s, false)
            """, (alimentador_id,))
            
            # Criar calibração padrão
            cursor.execute("""
                INSERT INTO calibracao_alimentadores (alimentador_id)
                VALUES (%s)
            """, (alimentador_id,))
            
        elif tipo == 'datalogger':
            cursor.execute("""
                INSERT INTO dataloggers (dispositivo_id)
                VALUES (%s)
            """, (dispositivo_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Dispositivo cadastrado com sucesso!', 'success')
        return redirect(url_for('cadastros'))
    
    except Exception as e:
        flash(f'Erro ao cadastrar dispositivo: {str(e)}', 'error')
        return redirect(url_for('cadastrar_dispositivo'))

# CADASTRO DE SENSORES
@app.route('/cadastros/sensores')
def cadastrar_sensor():
    """Formulário para cadastrar sensor"""
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'error')
        return redirect(url_for('cadastros'))
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, dev.nome, l.nome 
        FROM dataloggers d
        JOIN dispositivos dev ON d.dispositivo_id = dev.id
        JOIN localizacoes l ON dev.localizacao_id = l.id
        ORDER BY dev.nome
    """)
    dataloggers = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('cadastros/sensor.html', dataloggers=dataloggers)

@app.route('/cadastros/sensores/salvar', methods=['POST'])
def salvar_sensor():
    """Salva um novo sensor"""
    try:
        datalogger_id = request.form['datalogger_id']
        nome = request.form['nome']
        tipo = request.form['tipo']
        unidade = request.form['unidade']
        posicao = request.form['posicao']
        endereco = request.form.get('endereco', '')
        
        conn = get_db_connection()
        if not conn:
            flash('Erro de conexão com o banco de dados', 'error')
            return redirect(url_for('cadastrar_sensor'))
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sensores (datalogger_id, nome, tipo, unidade, posicao, endereco)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (datalogger_id, nome, tipo, unidade, posicao, endereco))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Sensor cadastrado com sucesso!', 'success')
        return redirect(url_for('cadastros'))
    
    except Exception as e:
        flash(f'Erro ao cadastrar sensor: {str(e)}', 'error')
        return redirect(url_for('cadastrar_sensor'))

# CADASTRO DE CONFIGURAÇÕES DE ALIMENTADOR
@app.route('/cadastros/config-alimentador')
def cadastrar_config_alimentador():
    """Formulário para configurar alimentador"""
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'error')
        return redirect(url_for('cadastros'))
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, dev.nome, l.nome 
        FROM alimentadores a
        JOIN dispositivos dev ON a.dispositivo_id = dev.id
        JOIN localizacoes l ON dev.localizacao_id = l.id
        ORDER BY dev.nome
    """)
    alimentadores = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('cadastros/config_alimentador.html', alimentadores=alimentadores)

@app.route('/cadastros/config-alimentador/salvar', methods=['POST'])
def salvar_config_alimentador():
    """Salva configuração do alimentador"""
    try:
        alimentador_id = request.form['alimentador_id']
        horario_inicio = request.form['horario_inicio']
        horario_fim = request.form['horario_fim']
        intervalo = request.form['intervalo']
        peso_diario = request.form['peso_diario']
        porcoes = request.form['porcoes']
        ativa = 'ativa' in request.form
        
        conn = get_db_connection()
        if not conn:
            flash('Erro de conexão com o banco de dados', 'error')
            return redirect(url_for('cadastrar_config_alimentador'))
        
        cursor = conn.cursor()
        
        # Verificar se já existe configuração
        cursor.execute("SELECT id FROM config_alimentadores WHERE alimentador_id = %s", (alimentador_id,))
        existing_config = cursor.fetchone()
        
        if existing_config:
            # Atualizar configuração existente
            cursor.execute("""
                UPDATE config_alimentadores 
                SET horario_inicio = %s, horario_fim = %s, intervalo = %s, 
                    peso_diario = %s, porcoes = %s, ativa = %s, updated_at = CURRENT_TIMESTAMP
                WHERE alimentador_id = %s
            """, (horario_inicio, horario_fim, intervalo, peso_diario, porcoes, ativa, alimentador_id))
        else:
            # Inserir nova configuração
            cursor.execute("""
                INSERT INTO config_alimentadores 
                (alimentador_id, horario_inicio, horario_fim, intervalo, peso_diario, porcoes, ativa)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (alimentador_id, horario_inicio, horario_fim, intervalo, peso_diario, porcoes, ativa))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Configuração do alimentador salva com sucesso!', 'success')
        return redirect(url_for('cadastros'))
    
    except Exception as e:
        flash(f'Erro ao salvar configuração: {str(e)}', 'error')
        return redirect(url_for('cadastrar_config_alimentador'))

# CADASTRO DE LIMITES DE TEMPERATURA
@app.route('/cadastros/limites-temperatura')
def cadastrar_limites_temperatura():
    """Formulário para cadastrar limites de temperatura"""
    conn = get_db_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'error')
        return redirect(url_for('cadastros'))
    
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome FROM localizacoes ORDER BY nome")
    localizacoes = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('cadastros/limites_temperatura.html', localizacoes=localizacoes)

@app.route('/cadastros/limites-temperatura/salvar', methods=['POST'])
def salvar_limites_temperatura():
    """Salva limites de temperatura"""
    try:
        localizacao_id = request.form['localizacao_id']
        tipo_sensor = request.form['tipo_sensor']
        maximo = float(request.form['maximo'])
        minimo = float(request.form['minimo'])
        
        conn = get_db_connection()
        if not conn:
            flash('Erro de conexão com o banco de dados', 'error')
            return redirect(url_for('cadastrar_limites_temperatura'))
        
        cursor = conn.cursor()
        
        # Verificar se já existe limite para esta localização e tipo
        cursor.execute("""
            SELECT id FROM limites_temperatura 
            WHERE localizacao_id = %s AND tipo_sensor = %s
        """, (localizacao_id, tipo_sensor))
        
        existing_limit = cursor.fetchone()
        
        if existing_limit:
            # Atualizar limite existente
            cursor.execute("""
                UPDATE limites_temperatura 
                SET maximo = %s, minimo = %s, updated_at = CURRENT_TIMESTAMP
                WHERE localizacao_id = %s AND tipo_sensor = %s
            """, (maximo, minimo, localizacao_id, tipo_sensor))
        else:
            # Inserir novo limite
            cursor.execute("""
                INSERT INTO limites_temperatura (localizacao_id, tipo_sensor, maximo, minimo)
                VALUES (%s, %s, %s, %s)
            """, (localizacao_id, tipo_sensor, maximo, minimo))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        flash('Limites de temperatura salvos com sucesso!', 'success')
        return redirect(url_for('cadastros'))
    
    except Exception as e:
        flash(f'Erro ao salvar limites: {str(e)}', 'error')
        return redirect(url_for('cadastrar_limites_temperatura'))

# ROTA PARA LISTAR TODOS OS CADASTROS
@app.route('/cadastros/lista')
def lista_cadastros():
    """Lista todos os cadastros"""
    conn = get_db_connection()
    if not conn:
        return render_template('error.html', message="Erro de conexão com o banco de dados"), 500
    
    try:
        cursor = conn.cursor()
        
        # Localizações
        cursor.execute("SELECT id, nome, tipo, descricao FROM localizacoes ORDER BY nome")
        localizacoes = cursor.fetchall()
        
        # Dispositivos
        cursor.execute("""
            SELECT d.id, d.nome, d.tipo, d.mac_address, l.nome 
            FROM dispositivos d 
            LEFT JOIN localizacoes l ON d.localizacao_id = l.id 
            ORDER BY d.tipo, d.nome
        """)
        dispositivos = cursor.fetchall()
        
        # Sensores
        cursor.execute("""
            SELECT s.id, s.nome, s.tipo, s.posicao, dev.nome 
            FROM sensores s
            JOIN dataloggers d ON s.datalogger_id = d.id
            JOIN dispositivos dev ON d.dispositivo_id = dev.id
            ORDER BY dev.nome, s.nome
        """)
        sensores = cursor.fetchall()
        
        # Configurações de alimentadores
        cursor.execute("""
            SELECT c.id, dev.nome, c.horario_inicio, c.horario_fim, c.peso_diario, c.ativa
            FROM config_alimentadores c
            JOIN alimentadores a ON c.alimentador_id = a.id
            JOIN dispositivos dev ON a.dispositivo_id = dev.id
            ORDER BY dev.nome
        """)
        configs_alimentadores = cursor.fetchall()
        
        # Limites de temperatura
        cursor.execute("""
            SELECT l.id, loc.nome, l.tipo_sensor, l.maximo, l.minimo
            FROM limites_temperatura l
            JOIN localizacoes loc ON l.localizacao_id = loc.id
            ORDER BY loc.nome, l.tipo_sensor
        """)
        limites_temperatura = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('cadastros/lista.html',
                             localizacoes=localizacoes,
                             dispositivos=dispositivos,
                             sensores=sensores,
                             configs_alimentadores=configs_alimentadores,
                             limites_temperatura=limites_temperatura)
    
    except Exception as e:
        return render_template('error.html', message=f"Erro ao carregar lista: {e}"), 500

@app.route('/api/estatisticas')
def api_estatisticas():
    """API para estatísticas em tempo real"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Erro de conexão'}), 500
    
    try:
        cursor = conn.cursor()
        
        # Dispositivos online
        cursor.execute("SELECT COUNT(*) FROM dispositivos WHERE online = true")
        online = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM dispositivos")
        total = cursor.fetchone()[0]
        
        # Últimas temperaturas
        cursor.execute("""
            SELECT AVG(valor) 
            FROM leituras_sensores 
            WHERE timestamp >= NOW() - INTERVAL '10 minutes'
        """)
        temp_media = cursor.fetchone()[0] or 0
        
        # Alertas ativos
        cursor.execute("SELECT COUNT(*) FROM alertas WHERE resolvido = false")
        alertas = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'dispositivos_online': online,
            'total_dispositivos': total,
            'temperatura_media': round(temp_media, 2),
            'alertas_ativos': alertas
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)