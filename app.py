from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from database import Database
from config import Config
import hashlib
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Inicializar banco de dados
db = Database()

# Função de hash (mantenha esta função no app.py)
def hash_password(senha, salt=None):
    """Gera hash da senha usando salt"""
    if salt is None:
        salt = secrets.token_hex(16)
    
    senha_salt = senha + salt
    senha_hash = hashlib.sha256(senha_salt.encode()).hexdigest()
    return senha_hash, salt




# ====================
# ROTAS DE AUTENTICAÇÃO
# ====================

@app.route('/')
def index():
    """Página inicial - redireciona para login ou dashboard"""
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    # Se já está logado, redireciona para dashboard
    if 'usuario_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        if not email or not senha:
            flash('Por favor, preencha todos os campos.', 'danger')
            return render_template('login.html')
        
        # Verificar usuário no banco
        usuario = db.verificar_usuario(email, senha)
        
        if usuario:
            # Login bem-sucedido
            session['usuario_id'] = usuario['id']
            session['usuario_nome'] = usuario['nome']
            session['usuario_email'] = usuario['email']
            session['usuario_tipo'] = usuario['tipo']
            
            flash(f'Bem-vindo, {usuario["nome"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Email ou senha incorretos.', 'danger')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard principal após login"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return render_template('dashboard.html', 
                             usuario=session,
                             localizacoes=[],
                             stats={})
    
    try:
        with conn.cursor() as cursor:
            usuario_id = session['usuario_id']
            usuario_tipo = session['usuario_tipo']
            
            # Buscar estatísticas baseadas no tipo de usuário
            if usuario_tipo == 'admin':
                # Admin vê estatísticas de todo o sistema
                
                # Total de localizações
                cursor.execute("SELECT COUNT(*) FROM localizacoes")
                total_localizacoes = cursor.fetchone()[0]
                
                # Total de equipamentos
                cursor.execute("SELECT COUNT(*) FROM dispositivos")
                total_equipamentos = cursor.fetchone()[0]
                
                # Equipamentos online
                cursor.execute("SELECT COUNT(*) FROM dispositivos WHERE online = true")
                equipamentos_online = cursor.fetchone()[0]
                
                # Total de usuários
                cursor.execute("SELECT COUNT(*) FROM usuarios WHERE ativo = true")
                total_usuarios = cursor.fetchone()[0]
                
                # Total de alimentadores
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM alimentadores a 
                    JOIN dispositivos d ON a.dispositivo_id = d.id
                """)
                total_alimentadores = cursor.fetchone()[0]
                
                # Total de dataloggers
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM dataloggers dl 
                    JOIN dispositivos d ON dl.dispositivo_id = d.id
                """)
                total_dataloggers = cursor.fetchone()[0]
                
                # Últimos equipamentos cadastrados
                cursor.execute("""
                    SELECT d.id, d.nome, d.tipo, d.online, l.nome as localizacao_nome,
                           CASE 
                               WHEN a.id IS NOT NULL THEN 'alimentador'
                               WHEN dl.id IS NOT NULL THEN 'datalogger'
                               ELSE 'dispositivo'
                           END as tipo_especifico
                    FROM dispositivos d
                    LEFT JOIN localizacoes l ON d.localizacao_id = l.id
                    LEFT JOIN alimentadores a ON d.id = a.dispositivo_id
                    LEFT JOIN dataloggers dl ON d.id = dl.dispositivo_id
                    ORDER BY d.created_at DESC
                    LIMIT 5
                """)
                ultimos_equipamentos = cursor.fetchall()
                
            else:
                # Usuário normal vê apenas suas estatísticas
                
                # Total de localizações do usuário
                cursor.execute("""
                    SELECT COUNT(DISTINCT l.id) 
                    FROM localizacoes l
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    WHERE ul.usuario_id = %s
                """, (usuario_id,))
                total_localizacoes = cursor.fetchone()[0]
                
                # Total de equipamentos do usuário
                cursor.execute("""
                    SELECT COUNT(DISTINCT d.id)
                    FROM dispositivos d
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    WHERE ul.usuario_id = %s
                """, (usuario_id,))
                total_equipamentos = cursor.fetchone()[0]
                
                # Equipamentos online do usuário
                cursor.execute("""
                    SELECT COUNT(DISTINCT d.id)
                    FROM dispositivos d
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    WHERE ul.usuario_id = %s AND d.online = true
                """, (usuario_id,))
                equipamentos_online = cursor.fetchone()[0]
                
                # Total de usuários (apenas o próprio para usuários normais)
                total_usuarios = 1
                
                # Total de alimentadores do usuário
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM alimentadores a
                    JOIN dispositivos d ON a.dispositivo_id = d.id
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    WHERE ul.usuario_id = %s
                """, (usuario_id,))
                total_alimentadores = cursor.fetchone()[0]
                
                # Total de dataloggers do usuário
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM dataloggers dl
                    JOIN dispositivos d ON dl.dispositivo_id = d.id
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    WHERE ul.usuario_id = %s
                """, (usuario_id,))
                total_dataloggers = cursor.fetchone()[0]
                
                # Últimos equipamentos do usuário
                cursor.execute("""
                    SELECT d.id, d.nome, d.tipo, d.online, l.nome as localizacao_nome,
                           CASE 
                               WHEN a.id IS NOT NULL THEN 'alimentador'
                               WHEN dl.id IS NOT NULL THEN 'datalogger'
                               ELSE 'dispositivo'
                           END as tipo_especifico
                    FROM dispositivos d
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    LEFT JOIN alimentadores a ON d.id = a.dispositivo_id
                    LEFT JOIN dataloggers dl ON d.id = dl.dispositivo_id
                    WHERE ul.usuario_id = %s
                    ORDER BY d.created_at DESC
                    LIMIT 5
                """, (usuario_id,))
                ultimos_equipamentos = cursor.fetchall()
            
            # Calcular porcentagem de equipamentos online
            porcentagem_online = 0
            if total_equipamentos > 0:
                porcentagem_online = (equipamentos_online / total_equipamentos) * 100
            
            # Preparar estatísticas para o template
            stats = {
                'total_localizacoes': total_localizacoes,
                'total_equipamentos': total_equipamentos,
                'equipamentos_online': equipamentos_online,
                'porcentagem_online': round(porcentagem_online, 1),
                'total_usuarios': total_usuarios,
                'total_alimentadores': total_alimentadores,
                'total_dataloggers': total_dataloggers,
                'ultimos_equipamentos': ultimos_equipamentos
            }
            
            # Obter localizações do usuário (para o card de localizações)
            localizacoes = db.obter_localizacoes_usuario(usuario_id)
            
    except Exception as e:
        print(f"❌ Erro ao buscar estatísticas do dashboard: {e}")
        stats = {
            'total_localizacoes': 0,
            'total_equipamentos': 0,
            'equipamentos_online': 0,
            'porcentagem_online': 0,
            'total_usuarios': 0,
            'total_alimentadores': 0,
            'total_dataloggers': 0,
            'ultimos_equipamentos': []
        }
        localizacoes = []
    finally:
        conn.close()
    
    return render_template('dashboard.html', 
                         usuario=session,
                         localizacoes=localizacoes,
                         stats=stats)


@app.route('/logout')
def logout():
    """Faz logout do usuário"""
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

# ====================
# ROTA DE SAÚDE
# ====================

@app.route('/health')
def health_check():
    """Verifica se a aplicação e banco estão funcionando"""
    try:
        # Testar conexão com banco tentando buscar um usuário
        usuario = db.verificar_usuario('admin@englife.com', 'teste')
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'message': 'Sistema de autenticação funcionando',
            'session_active': 'usuario_id' in session
        }), 200
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ====================
# MIDDLEWARE - Verificar autenticação
# ====================

@app.before_request
def check_authentication():
    """Verifica autenticação para rotas protegidas"""
    # Rotas que não precisam de autenticação
    public_routes = ['login', 'logout', 'health', 'static']
    
    if request.endpoint and request.endpoint not in public_routes:
        if 'usuario_id' not in session:
            if request.endpoint != 'index':
                flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))


# ====================
# ROTAS DE CADASTRO DE EQUIPAMENTOS
# ====================

@app.route('/equipamentos')
def equipamentos():
    """Página principal de equipamentos"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return render_template('equipamentos.html', dispositivos=[])
    
    try:
        with conn.cursor() as cursor:
            if session['usuario_tipo'] == 'admin':
                # Admin vê todos os dispositivos
                cursor.execute("""
                    SELECT DISTINCT d.*, l.nome as localizacao_nome,
                           CASE 
                               WHEN a.id IS NOT NULL THEN 'alimentador'
                               WHEN dl.id IS NOT NULL THEN 'datalogger'
                               ELSE 'dispositivo'
                           END as tipo_especifico
                    FROM dispositivos d
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    LEFT JOIN alimentadores a ON d.id = a.dispositivo_id
                    LEFT JOIN dataloggers dl ON d.id = dl.dispositivo_id
                    ORDER BY d.nome
                """)
            else:
                # Usuário normal vê apenas dispositivos das suas localizações
                cursor.execute("""
                    SELECT DISTINCT d.*, l.nome as localizacao_nome,
                           CASE 
                               WHEN a.id IS NOT NULL THEN 'alimentador'
                               WHEN dl.id IS NOT NULL THEN 'datalogger'
                               ELSE 'dispositivo'
                           END as tipo_especifico
                    FROM dispositivos d
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    LEFT JOIN alimentadores a ON d.id = a.dispositivo_id
                    LEFT JOIN dataloggers dl ON d.id = dl.dispositivo_id
                    WHERE ul.usuario_id = %s
                    ORDER BY d.nome
                """, (session['usuario_id'],))
            
            dispositivos = cursor.fetchall()
            
            # Converter para lista de dicionários
            colunas = ['id', 'localizacao_id', 'nome', 'descricao', 'mac_address', 
                      'ip_address', 'tipo', 'modelo', 'online', 'ultima_comunicacao',
                      'created_at', 'updated_at', 'localizacao_nome', 'tipo_especifico']
            
            dispositivos_dict = [dict(zip(colunas, dispositivo)) for dispositivo in dispositivos]
            
    except Exception as e:
        print(f"❌ Erro ao buscar dispositivos: {e}")
        dispositivos_dict = []
    finally:
        conn.close()
    
    return render_template('equipamentos.html', dispositivos=dispositivos_dict)


@app.route('/equipamentos/cadastrar')
def cadastrar_equipamento():
    """Formulário para cadastrar novo equipamento"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return redirect(url_for('equipamentos'))
    
    try:
        with conn.cursor() as cursor:
            if session['usuario_tipo'] == 'admin':
                # Admin vê todas as localizações
                cursor.execute("""
                    SELECT id, nome, descricao, tipo 
                    FROM localizacoes 
                    ORDER BY nome
                """)
            else:
                # Usuário normal vê apenas suas localizações
                cursor.execute("""
                    SELECT l.id, l.nome, l.descricao, l.tipo
                    FROM localizacoes l
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    WHERE ul.usuario_id = %s
                    ORDER BY l.nome
                """, (session['usuario_id'],))
            
            localizacoes = cursor.fetchall()
            
            localizacoes_dict = [
                {
                    'id': loc[0],
                    'nome': loc[1],
                    'descricao': loc[2],
                    'tipo': loc[3]
                }
                for loc in localizacoes
            ]
            
    except Exception as e:
        print(f"❌ Erro ao buscar localizações: {e}")
        localizacoes_dict = []
    finally:
        conn.close()
    
    return render_template('cadastrar_equipamento.html', localizacoes=localizacoes_dict)



@app.route('/equipamentos/salvar', methods=['POST'])
def salvar_equipamento():
    """Salva um novo equipamento"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    try:
        nome = request.form['nome']
        descricao = request.form.get('descricao', '')
        mac_address = request.form['mac_address']
        ip_address = request.form.get('ip_address', '')
        tipo = request.form['tipo']
        modelo = request.form.get('modelo', '')
        localizacao_id = request.form['localizacao_id']  # Agora obrigatório
        
        # Validar campos obrigatórios
        if not localizacao_id:
            flash('A localização é obrigatória.', 'danger')
            return redirect(url_for('cadastrar_equipamento'))
        
        conn = db.get_connection()
        if not conn:
            flash('Erro de conexão com o banco de dados', 'danger')
            return redirect(url_for('cadastrar_equipamento'))
        
        with conn.cursor() as cursor:
            # Verificar se o usuário tem acesso à localização
            if session['usuario_tipo'] != 'admin':
                # Para usuários não-admin, verificar se a localização pertence ao usuário
                cursor.execute("""
                    SELECT 1 FROM usuario_localizacao 
                    WHERE usuario_id = %s AND localizacao_id = %s
                """, (session['usuario_id'], localizacao_id))
                
                if not cursor.fetchone():
                    flash('Você não tem acesso a esta localização.', 'danger')
                    return redirect(url_for('cadastrar_equipamento'))
            
            # Verificar se MAC Address já existe
            cursor.execute("SELECT id FROM dispositivos WHERE mac_address = %s", (mac_address,))
            if cursor.fetchone():
                flash('MAC Address já está em uso. Por favor, use um endereço único.', 'danger')
                return redirect(url_for('cadastrar_equipamento'))
            
            # Inserir dispositivo
            cursor.execute("""
                INSERT INTO dispositivos (localizacao_id, nome, descricao, mac_address, ip_address, tipo, modelo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (localizacao_id, nome, descricao, mac_address, ip_address, tipo, modelo))
            
            dispositivo_id = cursor.fetchone()[0]
            
            # Criar registro específico baseado no tipo
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
                
                flash('Alimentador cadastrado com sucesso!', 'success')
                
            elif tipo == 'datalogger':
                cursor.execute("""
                    INSERT INTO dataloggers (dispositivo_id, quantidade_sensores, intervalo_leitura)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (dispositivo_id, 3, 60))
                
                datalogger_id = cursor.fetchone()[0]
                
                # Criar sensores automáticos apenas para dataloggers
                sensores_base = [
                    ('Sensor Água', 'temperatura', '°C', 'agua'),
                    ('Sensor Estufa', 'temperatura', '°C', 'estufa'),
                    ('Sensor Externa', 'temperatura', '°C', 'externa')
                ]
                
                for nome_sensor, tipo_sensor, unidade, posicao in sensores_base:
                    endereco = f"DS18B20_{datalogger_id}_{posicao}"
                    cursor.execute("""
                        INSERT INTO sensores (datalogger_id, nome, tipo, unidade, posicao, endereco)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (datalogger_id, nome_sensor, tipo_sensor, unidade, posicao, endereco))
                
                flash('Datalogger cadastrado com sucesso! 3 sensores de temperatura criados automaticamente.', 'success')
            
            conn.commit()
            
    except Exception as e:
        print(f"❌ Erro ao salvar equipamento: {e}")
        flash(f'Erro ao cadastrar equipamento: {str(e)}', 'danger')
        return redirect(url_for('cadastrar_equipamento'))
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('equipamentos'))

@app.route('/equipamentos/<int:dispositivo_id>')
def ver_equipamento(dispositivo_id):
    """Visualizar detalhes de um equipamento"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return redirect(url_for('equipamentos'))
    
    try:
        with conn.cursor() as cursor:
            if session['usuario_tipo'] == 'admin':
                # Admin pode ver qualquer dispositivo
                cursor.execute("""
                    SELECT d.*, l.nome as localizacao_nome,
                           CASE 
                               WHEN a.id IS NOT NULL THEN 'alimentador'
                               WHEN dl.id IS NOT NULL THEN 'datalogger'
                               ELSE 'dispositivo'
                           END as tipo_especifico,
                           a.id as alimentador_id,
                           dl.id as datalogger_id
                    FROM dispositivos d
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    LEFT JOIN alimentadores a ON d.id = a.dispositivo_id
                    LEFT JOIN dataloggers dl ON d.id = dl.dispositivo_id
                    WHERE d.id = %s
                """, (dispositivo_id,))
            else:
                # Usuário normal só vê dispositivos das suas localizações
                cursor.execute("""
                    SELECT d.*, l.nome as localizacao_nome,
                           CASE 
                               WHEN a.id IS NOT NULL THEN 'alimentador'
                               WHEN dl.id IS NOT NULL THEN 'datalogger'
                               ELSE 'dispositivo'
                           END as tipo_especifico,
                           a.id as alimentador_id,
                           dl.id as datalogger_id
                    FROM dispositivos d
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    LEFT JOIN alimentadores a ON d.id = a.dispositivo_id
                    LEFT JOIN dataloggers dl ON d.id = dl.dispositivo_id
                    WHERE d.id = %s AND ul.usuario_id = %s
                """, (dispositivo_id, session['usuario_id']))
            
            dispositivo = cursor.fetchone()
            
            if not dispositivo:
                flash('Equipamento não encontrado ou acesso negado.', 'danger')
                return redirect(url_for('equipamentos'))
            
            # Resto do código permanece igual...
            # Converter para dicionário
            colunas = ['id', 'localizacao_id', 'nome', 'descricao', 'mac_address', 
                      'ip_address', 'tipo', 'modelo', 'online', 'ultima_comunicacao',
                      'created_at', 'updated_at', 'localizacao_nome', 'tipo_especifico',
                      'alimentador_id', 'datalogger_id']
            
            dispositivo_dict = dict(zip(colunas, dispositivo))
            
            # Buscar sensores se for datalogger
            sensores = []
            if dispositivo_dict['tipo_especifico'] == 'datalogger':
                cursor.execute("""
                    SELECT id, nome, tipo, unidade, posicao, endereco, ativo
                    FROM sensores 
                    WHERE datalogger_id = %s
                    ORDER BY posicao
                """, (dispositivo_dict['datalogger_id'],))
                
                sensores = cursor.fetchall()
            
    except Exception as e:
        print(f"❌ Erro ao buscar equipamento: {e}")
        flash('Erro ao carregar equipamento.', 'danger')
        return redirect(url_for('equipamentos'))
    finally:
        conn.close()
    
    return render_template('ver_equipamento.html', 
                         dispositivo=dispositivo_dict, 
                         sensores=sensores)


@app.route('/equipamentos/<int:dispositivo_id>/adicionar-sensor', methods=['POST'])
def adicionar_sensor(dispositivo_id):
    """Adiciona um sensor a um datalogger"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    try:
        nome = request.form['nome']
        tipo = request.form['tipo']
        unidade = request.form['unidade']
        posicao = request.form['posicao']
        endereco = request.form.get('endereco', '')
        
        conn = db.get_connection()
        if not conn:
            flash('Erro de conexão com o banco de dados', 'danger')
            return redirect(url_for('ver_equipamento', dispositivo_id=dispositivo_id))
        
        with conn.cursor() as cursor:
            # Verificar se é um datalogger e se o usuário tem acesso
            cursor.execute("""
                SELECT dl.id
                FROM dispositivos d
                JOIN dataloggers dl ON d.id = dl.dispositivo_id
                JOIN localizacoes l ON d.localizacao_id = l.id
                JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                WHERE d.id = %s AND ul.usuario_id = %s AND d.tipo = 'datalogger'
            """, (dispositivo_id, session['usuario_id']))
            
            datalogger = cursor.fetchone()
            
            if not datalogger:
                flash('Datalogger não encontrado ou acesso negado.', 'danger')
                return redirect(url_for('equipamentos'))
            
            datalogger_id = datalogger[0]
            
            # Inserir sensor
            cursor.execute("""
                INSERT INTO sensores (datalogger_id, nome, tipo, unidade, posicao, endereco)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (datalogger_id, nome, tipo, unidade, posicao, endereco))
            
            conn.commit()
            flash('Sensor adicionado com sucesso!', 'success')
            
    except Exception as e:
        print(f"❌ Erro ao adicionar sensor: {e}")
        flash(f'Erro ao adicionar sensor: {str(e)}', 'danger')
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('ver_equipamento', dispositivo_id=dispositivo_id))

@app.route('/equipamentos/<int:dispositivo_id>/excluir', methods=['POST'])
def excluir_equipamento(dispositivo_id):
    """Exclui um equipamento e todos os dados relacionados"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return redirect(url_for('equipamentos'))
    
    try:
        with conn.cursor() as cursor:
            # Verificar se o usuário tem permissão para excluir este equipamento
            if session['usuario_tipo'] == 'admin':
                # Admin pode excluir qualquer dispositivo
                cursor.execute("""
                    SELECT d.id, d.nome, d.tipo, l.nome as localizacao_nome
                    FROM dispositivos d
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    WHERE d.id = %s
                """, (dispositivo_id,))
            else:
                # Usuário normal só pode excluir dispositivos das suas localizações
                cursor.execute("""
                    SELECT d.id, d.nome, d.tipo, l.nome as localizacao_nome
                    FROM dispositivos d
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    WHERE d.id = %s AND ul.usuario_id = %s
                """, (dispositivo_id, session['usuario_id']))
            
            dispositivo = cursor.fetchone()
            
            if not dispositivo:
                flash('Equipamento não encontrado ou acesso negado.', 'danger')
                return redirect(url_for('equipamentos'))
            
            dispositivo_id, dispositivo_nome, dispositivo_tipo, localizacao_nome = dispositivo
            
            # Excluir o dispositivo (as relações em cascata cuidarão do resto)
            cursor.execute("DELETE FROM dispositivos WHERE id = %s", (dispositivo_id,))
            
            conn.commit()
            
            flash(f'Equipamento "{dispositivo_nome}" excluído com sucesso!', 'success')
            
    except Exception as e:
        print(f"❌ Erro ao excluir equipamento: {e}")
        conn.rollback()
        flash(f'Erro ao excluir equipamento: {str(e)}', 'danger')
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('equipamentos'))


# ====================
# ROTAS DE LOCALIZAÇÕES
# ====================

@app.route('/localizacoes')
def localizacoes():
    """Página principal de localizações"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return render_template('localizacoes.html', localizacoes=[])
    
    try:
        with conn.cursor() as cursor:
            if session['usuario_tipo'] == 'admin':
                # Admin vê todas as localizações
                cursor.execute("""
                    SELECT l.*, 
                           COUNT(DISTINCT d.id) as total_equipamentos,
                           COUNT(DISTINCT u.id) as total_usuarios
                    FROM localizacoes l
                    LEFT JOIN dispositivos d ON l.id = d.localizacao_id
                    LEFT JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    LEFT JOIN usuarios u ON ul.usuario_id = u.id
                    GROUP BY l.id
                    ORDER BY l.nome
                """)
            else:
                # Usuário normal vê apenas suas localizações
                cursor.execute("""
                    SELECT l.*, 
                           COUNT(DISTINCT d.id) as total_equipamentos,
                           COUNT(DISTINCT u.id) as total_usuarios
                    FROM localizacoes l
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    LEFT JOIN dispositivos d ON l.id = d.localizacao_id
                    LEFT JOIN usuario_localizacao ul2 ON l.id = ul2.localizacao_id
                    LEFT JOIN usuarios u ON ul2.usuario_id = u.id
                    WHERE ul.usuario_id = %s
                    GROUP BY l.id
                    ORDER BY l.nome
                """, (session['usuario_id'],))
            
            localizacoes = cursor.fetchall()
            
            # Converter para lista de dicionários
            colunas = ['id', 'nome', 'descricao', 'tipo', 'created_at', 'total_equipamentos', 'total_usuarios']
            localizacoes_dict = [dict(zip(colunas, localizacao)) for localizacao in localizacoes]
            
    except Exception as e:
        print(f"❌ Erro ao buscar localizações: {e}")
        localizacoes_dict = []
    finally:
        conn.close()
    
    return render_template('localizacoes.html', localizacoes=localizacoes_dict)

@app.route('/localizacoes/cadastrar')
def cadastrar_localizacao():
    """Formulário para cadastrar nova localização"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    return render_template('cadastrar_localizacao.html')

@app.route('/localizacoes/salvar', methods=['POST'])
def salvar_localizacao():
    """Salva uma nova localização"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    try:
        nome = request.form['nome']
        descricao = request.form.get('descricao', '')
        tipo = request.form['tipo']
        
        conn = db.get_connection()
        if not conn:
            flash('Erro de conexão com o banco de dados', 'danger')
            return redirect(url_for('cadastrar_localizacao'))
        
        with conn.cursor() as cursor:
            # Verificar se já existe uma localização com o mesmo nome
            cursor.execute("SELECT id FROM localizacoes WHERE nome = %s", (nome,))
            if cursor.fetchone():
                flash('Já existe uma localização com este nome.', 'danger')
                return redirect(url_for('cadastrar_localizacao'))
            
            # Inserir nova localização
            cursor.execute("""
                INSERT INTO localizacoes (nome, descricao, tipo)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (nome, descricao, tipo))
            
            localizacao_id = cursor.fetchone()[0]
            
            # Se for admin, associar automaticamente a todos os usuários
            if session['usuario_tipo'] == 'admin':
                cursor.execute("SELECT id FROM usuarios")
                usuarios = cursor.fetchall()
                
                for usuario in usuarios:
                    cursor.execute("""
                        INSERT INTO usuario_localizacao (usuario_id, localizacao_id)
                        VALUES (%s, %s)
                        ON CONFLICT (usuario_id, localizacao_id) DO NOTHING
                    """, (usuario[0], localizacao_id))
            else:
                # Usuário normal: associar apenas a si mesmo
                cursor.execute("""
                    INSERT INTO usuario_localizacao (usuario_id, localizacao_id)
                    VALUES (%s, %s)
                """, (session['usuario_id'], localizacao_id))
            
            conn.commit()
            flash('Localização cadastrada com sucesso!', 'success')
            
    except Exception as e:
        print(f"❌ Erro ao salvar localização: {e}")
        flash(f'Erro ao cadastrar localização: {str(e)}', 'danger')
        return redirect(url_for('cadastrar_localizacao'))
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('localizacoes'))

@app.route('/localizacoes/<int:localizacao_id>')
def ver_localizacao(localizacao_id):
    """Visualizar detalhes de uma localização"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return redirect(url_for('localizacoes'))
    
    try:
        with conn.cursor() as cursor:
            if session['usuario_tipo'] == 'admin':
                # Admin pode ver qualquer localização
                cursor.execute("""
                    SELECT l.*,
                           COUNT(DISTINCT d.id) as total_equipamentos,
                           COUNT(DISTINCT u.id) as total_usuarios
                    FROM localizacoes l
                    LEFT JOIN dispositivos d ON l.id = d.localizacao_id
                    LEFT JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    LEFT JOIN usuarios u ON ul.usuario_id = u.id
                    WHERE l.id = %s
                    GROUP BY l.id
                """, (localizacao_id,))
            else:
                # Usuário normal só pode ver localizações que tem acesso
                cursor.execute("""
                    SELECT l.*,
                           COUNT(DISTINCT d.id) as total_equipamentos,
                           COUNT(DISTINCT u.id) as total_usuarios
                    FROM localizacoes l
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    LEFT JOIN dispositivos d ON l.id = d.localizacao_id
                    LEFT JOIN usuario_localizacao ul2 ON l.id = ul2.localizacao_id
                    LEFT JOIN usuarios u ON ul2.usuario_id = u.id
                    WHERE l.id = %s AND ul.usuario_id = %s
                    GROUP BY l.id
                """, (localizacao_id, session['usuario_id']))
            
            localizacao = cursor.fetchone()
            
            if not localizacao:
                flash('Localização não encontrada ou acesso negado.', 'danger')
                return redirect(url_for('localizacoes'))
            
            # Converter para dicionário
            colunas = ['id', 'nome', 'descricao', 'tipo', 'created_at', 'total_equipamentos', 'total_usuarios']
            localizacao_dict = dict(zip(colunas, localizacao))
            
            # Buscar equipamentos da localização
            cursor.execute("""
                SELECT d.*,
                       CASE 
                           WHEN a.id IS NOT NULL THEN 'alimentador'
                           WHEN dl.id IS NOT NULL THEN 'datalogger'
                           ELSE 'dispositivo'
                       END as tipo_especifico
                FROM dispositivos d
                LEFT JOIN alimentadores a ON d.id = a.dispositivo_id
                LEFT JOIN dataloggers dl ON d.id = dl.dispositivo_id
                WHERE d.localizacao_id = %s
                ORDER BY d.nome
            """, (localizacao_id,))
            
            equipamentos = cursor.fetchall()
            colunas_equip = ['id', 'localizacao_id', 'nome', 'descricao', 'mac_address', 
                            'ip_address', 'tipo', 'modelo', 'online', 'ultima_comunicacao',
                            'created_at', 'updated_at', 'tipo_especifico']
            equipamentos_dict = [dict(zip(colunas_equip, equipamento)) for equipamento in equipamentos]
            
    except Exception as e:
        print(f"❌ Erro ao buscar localização: {e}")
        flash('Erro ao carregar localização.', 'danger')
        return redirect(url_for('localizacoes'))
    finally:
        conn.close()
    
    return render_template('ver_localizacao.html', 
                         localizacao=localizacao_dict, 
                         equipamentos=equipamentos_dict)

# ====================
# ROTAS DE USUÁRIOS (APENAS ADMIN)
# ====================

@app.route('/usuarios')
def usuarios():
    """Página de gerenciamento de usuários (apenas admin)"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    # Verificar se é admin
    if session['usuario_tipo'] != 'admin':
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return render_template('usuarios.html', usuarios=[])
    
    try:
        with conn.cursor() as cursor:
            # Buscar todos os usuários
            cursor.execute("""
                SELECT id, nome, email, tipo, ativo, created_at
                FROM usuarios
                ORDER BY nome
            """)
            
            usuarios = cursor.fetchall()
            
            # Converter para lista de dicionários
            colunas = ['id', 'nome', 'email', 'tipo', 'ativo', 'created_at']
            usuarios_dict = [dict(zip(colunas, usuario)) for usuario in usuarios]
            
    except Exception as e:
        print(f"❌ Erro ao buscar usuários: {e}")
        usuarios_dict = []
    finally:
        conn.close()
    
    return render_template('usuarios.html', usuarios=usuarios_dict)

@app.route('/usuarios/cadastrar')
def cadastrar_usuario():
    """Formulário para cadastrar novo usuário (apenas admin)"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    # Verificar se é admin
    if session['usuario_tipo'] != 'admin':
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Buscar localizações para associar ao usuário
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return render_template('cadastrar_usuario.html', localizacoes=[])
    
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, nome, tipo, descricao
                FROM localizacoes
                ORDER BY nome
            """)
            localizacoes = cursor.fetchall()
            
            localizacoes_dict = [
                {
                    'id': loc[0],
                    'nome': loc[1],
                    'tipo': loc[2],
                    'descricao': loc[3]
                }
                for loc in localizacoes
            ]
            
    except Exception as e:
        print(f"❌ Erro ao buscar localizações: {e}")
        localizacoes_dict = []
    finally:
        conn.close()
    
    return render_template('cadastrar_usuario.html', localizacoes=localizacoes_dict)

@app.route('/usuarios/salvar', methods=['POST'])
def salvar_usuario():
    """Salva um novo usuário (apenas admin)"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    # Verificar se é admin
    if session['usuario_tipo'] != 'admin':
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        tipo = request.form['tipo']
        localizacoes = request.form.getlist('localizacoes')  # Lista de localizações selecionadas
        
        # Validar senha
        if len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
            return redirect(url_for('cadastrar_usuario'))
        
        # Gerar hash da senha
        senha_hash, salt = hash_password(senha)
        
        conn = db.get_connection()
        if not conn:
            flash('Erro de conexão com o banco de dados', 'danger')
            return redirect(url_for('cadastrar_usuario'))
        
        with conn.cursor() as cursor:
            # Verificar se email já existe
            cursor.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('Já existe um usuário com este email.', 'danger')
                return redirect(url_for('cadastrar_usuario'))
            
            # Inserir novo usuário
            cursor.execute("""
                INSERT INTO usuarios (nome, email, senha_hash, salt, tipo)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (nome, email, senha_hash, salt, tipo))
            
            usuario_id = cursor.fetchone()[0]
            
            # Associar localizações ao usuário
            for localizacao_id in localizacoes:
                cursor.execute("""
                    INSERT INTO usuario_localizacao (usuario_id, localizacao_id)
                    VALUES (%s, %s)
                """, (usuario_id, localizacao_id))
            
            conn.commit()
            flash('Usuário cadastrado com sucesso!', 'success')
            
    except Exception as e:
        print(f"❌ Erro ao salvar usuário: {e}")
        flash(f'Erro ao cadastrar usuário: {str(e)}', 'danger')
        return redirect(url_for('cadastrar_usuario'))
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('usuarios'))

# Atualize a rota atualizar_usuario para não modificar a senha
@app.route('/usuarios/<int:usuario_id>/atualizar', methods=['POST'])
def atualizar_usuario(usuario_id):
    """Atualiza dados do usuário (apenas admin)"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    # Verificar se é admin
    if session['usuario_tipo'] != 'admin':
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        nome = request.form['nome']
        email = request.form['email']
        tipo = request.form['tipo']
        ativo = 'ativo' in request.form  # Checkbox
        localizacoes = request.form.getlist('localizacoes')
        
        conn = db.get_connection()
        if not conn:
            flash('Erro de conexão com o banco de dados', 'danger')
            return redirect(url_for('editar_usuario', usuario_id=usuario_id))
        
        with conn.cursor() as cursor:
            # Verificar se email já existe em outro usuário
            cursor.execute("SELECT id FROM usuarios WHERE email = %s AND id != %s", (email, usuario_id))
            if cursor.fetchone():
                flash('Já existe outro usuário com este email.', 'danger')
                return redirect(url_for('editar_usuario', usuario_id=usuario_id))
            
            # Atualizar dados do usuário (sem modificar a senha)
            cursor.execute("""
                UPDATE usuarios 
                SET nome = %s, email = %s, tipo = %s, ativo = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (nome, email, tipo, ativo, usuario_id))
            
            # Atualizar localizações do usuário
            # Primeiro remover todas as associações
            cursor.execute("DELETE FROM usuario_localizacao WHERE usuario_id = %s", (usuario_id,))
            
            # Depois adicionar as novas
            for localizacao_id in localizacoes:
                cursor.execute("""
                    INSERT INTO usuario_localizacao (usuario_id, localizacao_id)
                    VALUES (%s, %s)
                """, (usuario_id, localizacao_id))
            
            conn.commit()
            flash('Usuário atualizado com sucesso!', 'success')
            
    except Exception as e:
        print(f"❌ Erro ao atualizar usuário: {e}")
        flash(f'Erro ao atualizar usuário: {str(e)}', 'danger')
        return redirect(url_for('editar_usuario', usuario_id=usuario_id))
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('usuarios'))

# Adicione uma rota para redefinir senha (opcional)
@app.route('/usuarios/<int:usuario_id>/redefinir-senha', methods=['POST'])
def redefinir_senha_usuario(usuario_id):
    """Redefine a senha de um usuário (apenas admin)"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    # Verificar se é admin
    if session['usuario_tipo'] != 'admin':
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
        return redirect(url_for('dashboard'))
    
    try:
        nova_senha = request.form['nova_senha']
        confirmar_senha = request.form['confirmar_senha']
        
        # Validar senhas
        if len(nova_senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
            return redirect(url_for('editar_usuario', usuario_id=usuario_id))
        
        if nova_senha != confirmar_senha:
            flash('As senhas não coincidem.', 'danger')
            return redirect(url_for('editar_usuario', usuario_id=usuario_id))
        
        # Gerar novo hash da senha
        senha_hash, salt = hash_password(nova_senha)
        
        conn = db.get_connection()
        if not conn:
            flash('Erro de conexão com o banco de dados', 'danger')
            return redirect(url_for('editar_usuario', usuario_id=usuario_id))
        
        with conn.cursor() as cursor:
            # Atualizar senha
            cursor.execute("""
                UPDATE usuarios 
                SET senha_hash = %s, salt = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (senha_hash, salt, usuario_id))
            
            conn.commit()
            flash('Senha redefinida com sucesso!', 'success')
            
    except Exception as e:
        print(f"❌ Erro ao redefinir senha: {e}")
        flash(f'Erro ao redefinir senha: {str(e)}', 'danger')
        return redirect(url_for('editar_usuario', usuario_id=usuario_id))
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('editar_usuario', usuario_id=usuario_id))




@app.route('/usuarios/<int:usuario_id>/editar')
def editar_usuario(usuario_id):
    """Formulário para editar usuário (apenas admin)"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    # Verificar se é admin
    if session['usuario_tipo'] != 'admin':
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return redirect(url_for('usuarios'))
    
    try:
        with conn.cursor() as cursor:
            # Buscar dados do usuário
            cursor.execute("""
                SELECT id, nome, email, tipo, ativo
                FROM usuarios
                WHERE id = %s
            """, (usuario_id,))
            
            usuario = cursor.fetchone()
            
            if not usuario:
                flash('Usuário não encontrado.', 'danger')
                return redirect(url_for('usuarios'))
            
            usuario_dict = {
                'id': usuario[0],
                'nome': usuario[1],
                'email': usuario[2],
                'tipo': usuario[3],
                'ativo': usuario[4]
            }
            
            # Buscar todas as localizações
            cursor.execute("""
                SELECT id, nome, tipo, descricao
                FROM localizacoes
                ORDER BY nome
            """)
            todas_localizacoes = cursor.fetchall()
            
            # Buscar localizações do usuário
            cursor.execute("""
                SELECT localizacao_id
                FROM usuario_localizacao
                WHERE usuario_id = %s
            """, (usuario_id,))
            
            localizacoes_usuario = [row[0] for row in cursor.fetchall()]
            
            localizacoes_dict = [
                {
                    'id': loc[0],
                    'nome': loc[1],
                    'tipo': loc[2],
                    'descricao': loc[3],
                    'selecionada': loc[0] in localizacoes_usuario
                }
                for loc in todas_localizacoes
            ]
            
    except Exception as e:
        print(f"❌ Erro ao buscar usuário: {e}")
        flash('Erro ao carregar usuário.', 'danger')
        return redirect(url_for('usuarios'))
    finally:
        conn.close()
    
    return render_template('editar_usuario.html', 
                         usuario=usuario_dict, 
                         localizacoes=localizacoes_dict)



@app.route('/usuarios/<int:usuario_id>/excluir', methods=['POST'])
def excluir_usuario(usuario_id):
    """Exclui um usuário (apenas admin)"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    # Verificar se é admin
    if session['usuario_tipo'] != 'admin':
        flash('Acesso negado. Apenas administradores podem acessar esta página.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Não permitir excluir a si mesmo
    if usuario_id == session['usuario_id']:
        flash('Você não pode excluir sua própria conta.', 'danger')
        return redirect(url_for('usuarios'))
    
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return redirect(url_for('usuarios'))
    
    try:
        with conn.cursor() as cursor:
            # Buscar nome do usuário para mensagem
            cursor.execute("SELECT nome FROM usuarios WHERE id = %s", (usuario_id,))
            usuario = cursor.fetchone()
            
            if not usuario:
                flash('Usuário não encontrado.', 'danger')
                return redirect(url_for('usuarios'))
            
            usuario_nome = usuario[0]
            
            # Excluir usuário (as relações em cascata cuidarão das associações)
            cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
            
            conn.commit()
            flash(f'Usuário "{usuario_nome}" excluído com sucesso!', 'success')
            
    except Exception as e:
        print(f"❌ Erro ao excluir usuário: {e}")
        conn.rollback()
        flash(f'Erro ao excluir usuário: {str(e)}', 'danger')
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('usuarios'))


# ====================
# ROTAS DE RELATÓRIOS
# ====================

@app.route('/relatorios')
def relatorios():
    """Página principal de relatórios"""
    if 'usuario_id' not in session:
        flash('Por favor, faça login para acessar esta página.', 'warning')
        return redirect(url_for('login'))
    
    conn = db.get_connection()
    if not conn:
        flash('Erro de conexão com o banco de dados', 'danger')
        return render_template('relatorios.html', dataloggers=[], dados={})
    
    try:
        with conn.cursor() as cursor:
            if session['usuario_tipo'] == 'admin':
                # Admin vê todos os dataloggers
                cursor.execute("""
                    SELECT d.id, d.nome, l.nome as localizacao_nome, dl.quantidade_sensores
                    FROM dispositivos d
                    JOIN dataloggers dl ON d.id = dl.dispositivo_id
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    WHERE d.tipo = 'datalogger'
                    ORDER BY d.nome
                """)
            else:
                # Usuário normal vê apenas dataloggers das suas localizações
                cursor.execute("""
                    SELECT d.id, d.nome, l.nome as localizacao_nome, dl.quantidade_sensores
                    FROM dispositivos d
                    JOIN dataloggers dl ON d.id = dl.dispositivo_id
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    WHERE d.tipo = 'datalogger' AND ul.usuario_id = %s
                    ORDER BY d.nome
                """, (session['usuario_id'],))
            
            dataloggers = cursor.fetchall()
            
            # Converter para lista de dicionários
            colunas = ['id', 'nome', 'localizacao_nome', 'quantidade_sensores']
            dataloggers_dict = [dict(zip(colunas, datalogger)) for datalogger in dataloggers]
            
    except Exception as e:
        print(f"❌ Erro ao buscar dataloggers: {e}")
        dataloggers_dict = []
    finally:
        conn.close()
    
    return render_template('relatorios.html', 
                         dataloggers=dataloggers_dict, 
                         dados={})

@app.route('/relatorios/dados', methods=['POST'])
def obter_dados_relatorio():
    """Obtém dados para o relatório baseado nos filtros"""
    if 'usuario_id' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
    
    try:
        datalogger_id = request.form.get('datalogger_id')
        data_inicio = request.form.get('data_inicio')
        data_fim = request.form.get('data_fim')
        
        if not datalogger_id:
            return jsonify({'error': 'Selecione um datalogger'}), 400
        
        conn = db.get_connection()
        if not conn:
            return jsonify({'error': 'Erro de conexão com o banco'}), 500
        
        with conn.cursor() as cursor:
            # Verificar se o usuário tem acesso a este datalogger
            if session['usuario_tipo'] != 'admin':
                cursor.execute("""
                    SELECT 1 
                    FROM dispositivos d
                    JOIN localizacoes l ON d.localizacao_id = l.id
                    JOIN usuario_localizacao ul ON l.id = ul.localizacao_id
                    WHERE d.id = %s AND ul.usuario_id = %s AND d.tipo = 'datalogger'
                """, (datalogger_id, session['usuario_id']))
                
                if not cursor.fetchone():
                    return jsonify({'error': 'Acesso negado a este datalogger'}), 403
            
            # Buscar dados dos sensores
            cursor.execute("""
                SELECT 
                    s.id as sensor_id,
                    s.nome as sensor_nome,
                    s.posicao,
                    s.unidade,
                    ls.valor,
                    ls.timestamp
                FROM sensores s
                JOIN leituras_sensores ls ON s.id = ls.sensor_id
                WHERE s.datalogger_id = (
                    SELECT dl.id 
                    FROM dataloggers dl 
                    WHERE dl.dispositivo_id = %s
                )
                AND ls.timestamp BETWEEN %s AND %s
                ORDER BY ls.timestamp, s.posicao
            """, (datalogger_id, data_inicio, data_fim))
            
            dados = cursor.fetchall()
            
            # Processar dados para o gráfico
            dados_processados = processar_dados_grafico(dados)
            
            # Estatísticas básicas
            estatisticas = calcular_estatisticas(dados)
            
        conn.close()
        
        return jsonify({
            'success': True,
            'dados': dados_processados,
            'estatisticas': estatisticas
        })
        
    except Exception as e:
        print(f"❌ Erro ao buscar dados do relatório: {e}")
        return jsonify({'error': str(e)}), 500

def processar_dados_grafico(dados):
    """Processa os dados para formato adequado para gráficos"""
    if not dados:
        return {}
    
    # Agrupar dados por sensor
    dados_por_sensor = {}
    
    for sensor_id, sensor_nome, posicao, unidade, valor, timestamp in dados:
        if posicao not in dados_por_sensor:
            dados_por_sensor[posicao] = {
                'nome': sensor_nome,
                'unidade': unidade,
                'dados': []
            }
        
        dados_por_sensor[posicao]['dados'].append({
            'x': timestamp.isoformat(),
            'y': float(valor)
        })
    
    return dados_por_sensor

def calcular_estatisticas(dados):
    """Calcula estatísticas básicas dos dados"""
    if not dados:
        return {}
    
    estatisticas = {}
    
    # Agrupar por sensor
    dados_por_sensor = {}
    for sensor_id, sensor_nome, posicao, unidade, valor, timestamp in dados:
        if posicao not in dados_por_sensor:
            dados_por_sensor[posicao] = {
                'nome': sensor_nome,
                'unidade': unidade,
                'valores': []
            }
        dados_por_sensor[posicao]['valores'].append(float(valor))
    
    # Calcular estatísticas para cada sensor
    for posicao, info in dados_por_sensor.items():
        valores = info['valores']
        if valores:
            estatisticas[posicao] = {
                'nome': info['nome'],
                'unidade': info['unidade'],
                'media': round(sum(valores) / len(valores), 2),
                'maxima': round(max(valores), 2),
                'minima': round(min(valores), 2),
                'total_leituras': len(valores)
            }
    
    return estatisticas


# ====================
# ROTAS PARA RECEBER DADOS DOS DATALOGGERS
# ====================

@app.route('/api/datalogger/leitura', methods=['POST'])
def receber_leitura_datalogger():
    """
    Rota para receber leituras de sensores dos dataloggers
    Formato esperado do JSON:
    {
        "mac_address": "AA:BB:CC:DD:EE:01",
        "leituras": [
            {
                "endereco_sensor": "DS18B20_1_agua",
                "valor": 25.5,
                "timestamp": "2025-01-15 10:30:00"
            },
            {
                "endereco_sensor": "DS18B20_1_estufa", 
                "valor": 28.3,
                "timestamp": "2025-01-15 10:30:00"
            }
        ]
    }
    """
    try:
        # Verificar se é uma requisição JSON
        if not request.is_json:
            return jsonify({
                'status': 'erro',
                'mensagem': 'Content-Type deve ser application/json'
            }), 400
        
        data = request.get_json()
        
        # Validar campos obrigatórios
        if not data or 'mac_address' not in data or 'leituras' not in data:
            return jsonify({
                'status': 'erro',
                'mensagem': 'Campos obrigatórios: mac_address e leituras'
            }), 400
        
        mac_address = data['mac_address'].strip().upper()
        leituras = data['leituras']
        
        if not leituras:
            return jsonify({
                'status': 'erro', 
                'mensagem': 'Lista de leituras vazia'
            }), 400
        
        conn = db.get_connection()
        if not conn:
            return jsonify({
                'status': 'erro',
                'mensagem': 'Erro de conexão com o banco de dados'
            }), 500
        
        with conn.cursor() as cursor:
            # Verificar se o datalogger existe e está ativo
            cursor.execute("""
                SELECT d.id, d.nome, dl.id as datalogger_id, d.localizacao_id
                FROM dispositivos d
                JOIN dataloggers dl ON d.id = dl.dispositivo_id
                WHERE d.mac_address = %s AND d.tipo = 'datalogger' AND d.online = true
            """, (mac_address,))
            
            datalogger = cursor.fetchone()
            
            if not datalogger:
                return jsonify({
                    'status': 'erro',
                    'mensagem': 'Datalogger não encontrado ou inativo'
                }), 404
            
            dispositivo_id, dispositivo_nome, datalogger_id, localizacao_id = datalogger
            
            leituras_processadas = 0
            leituras_com_erro = []
            
            # Processar cada leitura
            for leitura in leituras:
                try:
                    endereco_sensor = leitura.get('endereco_sensor', '').strip()
                    valor = leitura.get('valor')
                    timestamp_str = leitura.get('timestamp')
                    
                    # Validar leitura
                    if not endereco_sensor or valor is None:
                        leituras_com_erro.append({
                            'endereco_sensor': endereco_sensor,
                            'erro': 'Campos endereco_sensor e valor são obrigatórios'
                        })
                        continue
                    
                    # Buscar sensor pelo endereço
                    cursor.execute("""
                        SELECT id, nome, tipo, unidade, ativo
                        FROM sensores 
                        WHERE endereco = %s AND datalogger_id = %s
                    """, (endereco_sensor, datalogger_id))
                    
                    sensor = cursor.fetchone()
                    
                    if not sensor:
                        leituras_com_erro.append({
                            'endereco_sensor': endereco_sensor,
                            'erro': 'Sensor não encontrado para este datalogger'
                        })
                        continue
                    
                    sensor_id, sensor_nome, sensor_tipo, unidade, ativo = sensor
                    
                    if not ativo:
                        leituras_com_erro.append({
                            'endereco_sensor': endereco_sensor,
                            'erro': 'Sensor inativo'
                        })
                        continue
                    
                    # Converter timestamp
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except ValueError:
                            timestamp = datetime.now()
                    else:
                        timestamp = datetime.now()
                    
                    # Inserir leitura
                    cursor.execute("""
                        INSERT INTO leituras_sensores (sensor_id, valor, timestamp)
                        VALUES (%s, %s, %s)
                    """, (sensor_id, float(valor), timestamp))
                    
                    leituras_processadas += 1
                    
                    # Verificar limites de temperatura e gerar alertas se necessário
                    if sensor_tipo == 'temperatura':
                        verificar_limites_temperatura(
                            cursor, 
                            localizacao_id, 
                            sensor_id, 
                            float(valor), 
                            sensor_nome,
                            timestamp
                        )
                        
                except Exception as e:
                    leituras_com_erro.append({
                        'endereco_sensor': leitura.get('endereco_sensor', 'desconhecido'),
                        'erro': str(e)
                    })
                    continue
            
            # Atualizar última comunicação do dispositivo
            cursor.execute("""
                UPDATE dispositivos 
                SET ultima_comunicacao = %s, online = true
                WHERE id = %s
            """, (datetime.now(), dispositivo_id))
            
            conn.commit()
            
            # Preparar resposta
            resposta = {
                'status': 'sucesso',
                'mensagem': f'{leituras_processadas} leitura(s) processada(s) com sucesso',
                'datalogger': dispositivo_nome,
                'leituras_processadas': leituras_processadas,
                'leituras_com_erro': len(leituras_com_erro)
            }
            
            if leituras_com_erro:
                resposta['erros_detalhados'] = leituras_com_erro
            
            return jsonify(resposta), 200
            
    except Exception as e:
        print(f"❌ Erro ao processar leituras do datalogger: {e}")
        if conn:
            conn.rollback()
        
        return jsonify({
            'status': 'erro',
            'mensagem': f'Erro interno do servidor: {str(e)}'
        }), 500
    finally:
        if conn:
            conn.close()


def verificar_limites_temperatura(cursor, localizacao_id, sensor_id, valor, sensor_nome, timestamp):
    """
    Verifica se a temperatura está dentro dos limites e gera alertas se necessário
    """
    try:
        # Buscar limites para esta localização e tipo de sensor
        cursor.execute("""
            SELECT lt.maximo, lt.minimo, s.posicao
            FROM limites_temperatura lt
            JOIN sensores s ON s.id = %s
            WHERE lt.localizacao_id = %s AND lt.tipo_sensor = s.posicao
        """, (sensor_id, localizacao_id))
        
        limite = cursor.fetchone()
        
        if not limite:
            return
        
        maximo, minimo, posicao = limite
        
        # Verificar se está fora dos limites
        if valor > maximo or valor < minimo:
            tipo_alerta = "TEMPERATURA_ALTA" if valor > maximo else "TEMPERATURA_BAIXA"
            severidade = "ALTA" if abs(valor - (maximo if valor > maximo else minimo)) > 5 else "MEDIA"
            
            mensagem = (
                f"Temperatura {posicao}: {valor:.1f}°C "
                f"{'acima' if valor > maximo else 'abaixo'} do limite "
                f"({maximo if valor > maximo else minimo}°C)"
            )
            
            # Inserir alerta
            cursor.execute("""
                INSERT INTO alertas (localizacao_id, tipo, severidade, mensagem, timestamp)
                VALUES (%s, %s, %s, %s, %s)
            """, (localizacao_id, tipo_alerta, severidade, mensagem, timestamp))
            
    except Exception as e:
        print(f"❌ Erro ao verificar limites de temperatura: {e}")


@app.route('/api/datalogger/status', methods=['POST'])
def atualizar_status_datalogger():
    """
    Rota para atualizar status do datalogger (heartbeat)
    Formato esperado:
    {
        "mac_address": "AA:BB:CC:DD:EE:01",
        "status": "online",
        "versao_firmware": "1.2.3",
        "sensores_ativos": 3
    }
    """
    try:
        if not request.is_json:
            return jsonify({'status': 'erro', 'mensagem': 'Content-Type deve ser application/json'}), 400
        
        data = request.get_json()
        mac_address = data.get('mac_address', '').strip().upper()
        status = data.get('status', 'online')
        versao_firmware = data.get('versao_firmware', '')
        sensores_ativos = data.get('sensores_ativos')
        
        if not mac_address:
            return jsonify({'status': 'erro', 'mensagem': 'mac_address é obrigatório'}), 400
        
        conn = db.get_connection()
        if not conn:
            return jsonify({'status': 'erro', 'mensagem': 'Erro de conexão com o banco'}), 500
        
        with conn.cursor() as cursor:
            # Verificar se dispositivo existe
            cursor.execute("""
                SELECT id FROM dispositivos 
                WHERE mac_address = %s AND tipo = 'datalogger'
            """, (mac_address,))
            
            dispositivo = cursor.fetchone()
            
            if not dispositivo:
                return jsonify({'status': 'erro', 'mensagem': 'Datalogger não encontrado'}), 404
            
            dispositivo_id = dispositivo[0]
            
            # Atualizar status
            cursor.execute("""
                UPDATE dispositivos 
                SET online = %s, ultima_comunicacao = %s, versao_firmware = %s
                WHERE id = %s
            """, (status == 'online', datetime.now(), versao_firmware, dispositivo_id))
            
            # Atualizar contagem de sensores se fornecida
            if sensores_ativos is not None:
                cursor.execute("""
                    UPDATE dataloggers 
                    SET quantidade_sensores = %s
                    WHERE dispositivo_id = %s
                """, (sensores_ativos, dispositivo_id))
            
            conn.commit()
            
            return jsonify({
                'status': 'sucesso',
                'mensagem': 'Status atualizado com sucesso'
            }), 200
            
    except Exception as e:
        print(f"❌ Erro ao atualizar status do datalogger: {e}")
        if conn:
            conn.rollback()
        return jsonify({'status': 'erro', 'mensagem': str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/datalogger/config', methods=['GET'])
def obter_config_datalogger():
    """
    Rota para o datalogger obter sua configuração
    Parâmetros: mac_address
    """
    try:
        mac_address = request.args.get('mac_address', '').strip().upper()
        
        if not mac_address:
            return jsonify({'status': 'erro', 'mensagem': 'mac_address é obrigatório'}), 400
        
        conn = db.get_connection()
        if not conn:
            return jsonify({'status': 'erro', 'mensagem': 'Erro de conexão com o banco'}), 500
        
        with conn.cursor() as cursor:
            # Buscar configuração do datalogger
            cursor.execute("""
                SELECT dl.intervalo_leitura, d.nome
                FROM dispositivos d
                JOIN dataloggers dl ON d.id = dl.dispositivo_id
                WHERE d.mac_address = %s AND d.tipo = 'datalogger'
            """, (mac_address,))
            
            datalogger = cursor.fetchone()
            
            if not datalogger:
                return jsonify({'status': 'erro', 'mensagem': 'Datalogger não encontrado'}), 404
            
            intervalo_leitura, nome = datalogger
            
            # Buscar sensores ativos
            cursor.execute("""
                SELECT endereco, nome, tipo, unidade, posicao
                FROM sensores 
                WHERE datalogger_id = (
                    SELECT dl.id FROM dataloggers dl
                    JOIN dispositivos d ON dl.dispositivo_id = d.id
                    WHERE d.mac_address = %s
                ) AND ativo = true
            """, (mac_address,))
            
            sensores = cursor.fetchall()
            
            sensores_config = []
            for sensor in sensores:
                sensores_config.append({
                    'endereco': sensor[0],
                    'nome': sensor[1],
                    'tipo': sensor[2],
                    'unidade': sensor[3],
                    'posicao': sensor[4]
                })
            
            return jsonify({
                'status': 'sucesso',
                'datalogger': nome,
                'config': {
                    'intervalo_leitura': intervalo_leitura,
                    'sensores': sensores_config
                }
            }), 200
            
    except Exception as e:
        print(f"❌ Erro ao obter configuração do datalogger: {e}")
        return jsonify({'status': 'erro', 'mensagem': str(e)}), 500
    finally:
        if conn:
            conn.close()




if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)