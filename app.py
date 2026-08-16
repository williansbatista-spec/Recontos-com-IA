import streamlit as st
import pandas as pd
import random
import requests

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E ESTADO
# ==========================================
st.set_page_config(
    page_title="RPG: O Multiverso da Leitura",
    page_icon="📚",
    layout="wide"
)

# Obter API Key dos Secrets do Streamlit
TOGETHER_API_KEY = st.secrets.get("TOGETHER_API_KEY", "")

if "history" not in st.session_state:
    st.session_state.history = []
if "frozen_players" not in st.session_state:
    st.session_state.frozen_players = []
if "potions" not in st.session_state:
    st.session_state.potions = 3
if "current_scene" not in st.session_state:
    st.session_state.current_scene = "A aventura está prestes a começar! Aguardando a primeira decisão do Mestre..."
if "current_image" not in st.session_state:
    st.session_state.current_image = None
if "current_quiz" not in st.session_state:
    st.session_state.current_quiz = None
if "current_gabarito" not in st.session_state:
    st.session_state.current_gabarito = None

# ==========================================
# 2. SIDEBAR - TURMA E STATUS
# ==========================================
st.sidebar.title("⚙️ Painel de Controle do Mestre")

# Checagem da chave nos Secrets
if TOGETHER_API_KEY:
    st.sidebar.success("🔑 Chave Together AI carregada via Secrets!")
else:
    st.sidebar.error("⚠️ TOGETHER_API_KEY não encontrada em st.secrets.")

st.sidebar.divider()
st.sidebar.subheader("📋 Chamada da Turma")
csv_file = st.sidebar.file_uploader("Carregar CSV da Turma", type=["csv"])

players_df = None
name_col = None

if csv_file:
    try:
        # Tenta separador ';' e faz fallback para ','
        players_df = pd.read_csv(csv_file, sep=";")
        if len(players_df.columns) <= 1:
            csv_file.seek(0)
            players_df = pd.read_csv(csv_file, sep=",")
        
        # Limpa espaços em branco ocultos nos cabeçalhos
        players_df.columns = players_df.columns.astype(str).str.strip()
        
        # Identificação inteligente da coluna com o nome dos alunos
        possible_matches = ['nome', 'aluno', 'estudante', 'student', 'name']
        for col in players_df.columns:
            if col.lower() in possible_matches:
                name_col = col
                break
        
        # Se não encontrou palavra-chave, utiliza a primeira coluna do arquivo
        if not name_col and len(players_df.columns) > 0:
            name_col = players_df.columns[0]
        
        st.sidebar.success(f"Carregados {len(players_df)} alunos com sucesso!")
        st.sidebar.caption(f"📌 Coluna de alunos: **{name_col}**")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler CSV: {e}")

# ==========================================
# 3. FUNÇÕES DE INTEGRAÇÃO COM IA (TOGETHER AI)
# ==========================================
def generate_narrative_and_quiz_llama(prompt, api_key):
    """Gera a história e o quiz usando o Llama 3.3 via Together AI."""
    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """Você é o Mestre de um RPG pedagógico escolar chamado 'O Multiverso da Leitura'.
Com base na ação escolhida pelos alunos, continue a história de forma envolvente e educativa.

Forneça a resposta dividida EXATAMENTE nestas três seções marcadas:

[HISTORIA]
(Escreva a narrativa pedagógica e envolvente aqui)

[QUIZ]
(Crie 1 pergunta de múltipla escolha sobre a história/tema com opções A, B, C, D)

[GABARITO]
(Indique a alternativa correta e uma breve explicação pedagógica exclusiva para o professor)
"""

    payload = {
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Ação escolhida pela turma: {prompt}"}
        ],
        "temperature": 0.7,
        "max_tokens": 1200
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=25)
        if res.status_code == 200:
            return res.json()['choices'][0]['message']['content']
        else:
            return f"Erro Llama ({res.status_code}): {res.text}"
    except Exception as e:
        return f"Falha na requisição do Llama: {e}"

def generate_image_flux(prompt, api_key):
    """Gera imagem via API Together AI usando FLUX.1-schnell."""
    url = "https://api.together.xyz/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "black-forest-labs/FLUX.1-schnell",
        "prompt": f"Digital fantasy RPG illustration, book style, adventure scene: {prompt}",
        "width": 1024,
        "height": 768,
        "steps": 4,
        "n": 1
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            return res.json()['data'][0]['url']
        else:
            st.sidebar.error(f"Erro Imagem ({res.status_code}): {res.text}")
            return None
    except Exception as e:
        st.sidebar.error(f"Falha na requisição de imagem: {e}")
        return None

# ==========================================
# 4. NAVEGAÇÃO ENTRE MODOS
# ==========================================
mode = st.radio("Selecione o Modo:", ["Modo Projetor (Turma)", "Painel Oculto (Mestre)"], horizontal=True)

# ------------------------------------------
# MODO PROJETOR (EXIBIÇÃO PARA OS ALUNOS)
# ------------------------------------------
if mode == "Modo Projetor (Turma)":
    st.title("📚 RPG: O Multiverso da Leitura")
    st.markdown("---")
    
    if st.session_state.current_image:
        st.image(st.session_state.current_image, use_container_width=True)
    
    st.subheader("📖 A Narrativa")
    st.write(st.session_state.current_scene)
    
    if st.session_state.current_quiz:
        st.info(f"❓ **Desafio Pedagógico:**\n\n{st.session_state.current_quiz}")

# ------------------------------------------
# PAINEL OCULTO (EXCLUSIVO DO PROFESSOR)
# ------------------------------------------
else:
    st.title("🧙‍♂️ Controle do Mestre")
    
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        st.subheader("🎲 Mecânicas da Turma")
        
        # Sorteio de Herói
        if players_df is not None and name_col:
            active_df = players_df[~players_df[name_col].isin(st.session_state.frozen_players)]
            if st.button("🎲 Sortear Herói Ativo"):
                if not active_df.empty:
                    chosen = random.choice(active_df[name_col].tolist())
                    st.success(f"Herói Escolhido: **{chosen}**!")
                else:
                    st.warning("Todos os alunos ativos estão congelados!")
        else:
            st.caption("Suba o arquivo CSV para habilitar o sorteio de alunos.")

        # Rolo de Dado D20
        if st.button("🎰 Rolar Dado D20"):
            d20 = random.randint(1, 20)
            if d20 == 1:
                st.error(f"Rolagem: {d20} — **Falha Crítica!** (O herói foi congelado!)")
            elif d20 == 20:
                st.balloons()
                st.success(f"Rolagem: {d20} — **Sucesso Crítico!**")
            else:
                st.info(f"Rolagem: {d20}")

        # Poção de Resgate
        st.divider()
        st.subheader("🧪 Poção de Resgate")
        st.write(f"Poções Restantes: **{st.session_state.potions}**")
        
        # Congelar/Descongelar Manual
        if players_df is not None and name_col:
            student_to_freeze = st.selectbox("Congelar Aluno (Fail Forward):", players_df[name_col].tolist())
            if st.button("Congelar Aluno"):
                if student_to_freeze not in st.session_state.frozen_players:
                    st.session_state.frozen_players.append(student_to_freeze)
                    st.warning(f"{student_to_freeze} foi congelado.")

        if st.session_state.frozen_players:
            student_to_rescue = st.selectbox("Aluno Congelado:", st.session_state.frozen_players)
            if st.button("Usar Poção de Resgate"):
                if st.session_state.potions > 0:
                    st.session_state.potions -= 1
                    st.session_state.frozen_players.remove(student_to_rescue)
                    st.success(f"{student_to_rescue} foi descongelado com sucesso!")
                    st.rerun()
                else:
                    st.error("Sem poções restantes!")

    with col_right:
        st.subheader("✍️ Avançar Aventura")
        action_text = st.text_area("Decisão da Turma / Ação do Mestre:", placeholder="Ex: A turma decide examinar os pergaminhos antigos no altar...")
        
        if st.button("🚀 Gerar Próxima Cena"):
            if not TOGETHER_API_KEY:
                st.error("Configure a variável TOGETHER_API_KEY nos secrets do Streamlit.")
            elif not action_text:
                st.warning("Escreva a decisão antes de avançar.")
            else:
                with st.spinner("Consultando Llama 3 e gerando ilustração FLUX..."):
                    raw_res = generate_narrative_and_quiz_llama(action_text, TOGETHER_API_KEY)
                    
                    # Parse das seções
                    historia = raw_res
                    quiz = ""
                    gabarito = ""
                    
                    if "[HISTORIA]" in raw_res:
                        parts = raw_res.split("[HISTORIA]")
                        rest = parts[1]
                        if "[QUIZ]" in rest:
                            historia, rest2 = rest.split("[QUIZ]")
                            if "[GABARITO]" in rest2:
                                quiz, gabarito = rest2.split("[GABARITO]")
                            else:
                                quiz = rest2
                        else:
                            historia = rest

                    st.session_state.current_scene = historia.strip()
                    st.session_state.current_quiz = quiz.strip()
                    st.session_state.current_gabarito = gabarito.strip()
                    
                    # Salva histórico
                    st.session_state.history.append({
                        "acao": action_text,
                        "cena": historia.strip(),
                        "gabarito": gabarito.strip()
                    })

                    # Gerar Imagem FLUX
                    img_url = generate_image_flux(action_text, TOGETHER_API_KEY)
                    st.session_state.current_image = img_url

                    st.success("Nova cena gerada com sucesso!")
                    st.rerun()

        # Gabarito Exclusivo
        if st.session_state.current_gabarito:
            st.warning("🔒 **Gabarito do Mestre (Oculto dos Alunos):**")
            st.write(st.session_state.current_gabarito)

    # Exportar Roteiro
    st.divider()
    st.subheader("📄 Exportar Roteiro da Aula")
    if st.button("Gerar Arquivo de Texto"):
        full_text = "--- ROTEIRO DA AVENTURA ---\n\n"
        for idx, item in enumerate(st.session_state.history, 1):
            full_text += f"--- CENA {idx} ---\nDecisão: {item['acao']}\n\nHistória:\n{item['cena']}\n\nGabarito:\n{item['gabarito']}\n\n"
        
        st.download_button(
            label="💾 Baixar Roteiro (.txt)",
            data=full_text,
            file_name="roteiro_rpg_aula.txt",
            mime="text/plain"
        )
