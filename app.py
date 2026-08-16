import streamlit as st
import requests
import json
import random
import io
from PIL import Image

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="RPG Pedagógico - Mestre IA",
    page_icon="⚔️",
    layout="wide"
)

# --- ESTILIZAÇÃO CUSTOMIZADA ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    .hero-card { background-color: #1f2937; padding: 15px; border-radius: 10px; border: 1px solid #374151; }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DO ESTADO DA SESSÃO ---
if "game_started" not in st.session_state:
    st.session_state.game_started = False
if "historico" not in st.session_state:
    st.session_state.historico = []
if "rodada" not in st.session_state:
    st.session_state.rodada = 0
if "herois" not in st.session_state:
    st.session_state.herois = []
if "imagem_atual" not in st.session_state:
    st.session_state.imagem_atual = None

# --- BARRA LATERAL: CONFIGURAÇÕES E CHAVE ---
with st.sidebar:
    st.title("⚙️ Painel do Mestre")
    
    # Tenta puxar dos secrets do Streamlit ou pede ao usuário
    api_key_default = st.secrets.get("TOGETHER_API_KEY", "") if "TOGETHER_API_KEY" in st.secrets else ""
    together_key = st.text_input("Together AI API Key", value=api_key_default, type="password")
    
    st.divider()
    
    st.session_state.mundo_mestre = st.text_input("Livro/Mundo da Aventura", "O Pequeno Príncipe")
    st.session_state.faixa_etaria = st.selectbox("Faixa Etária", ["Ensino Fundamental I", "Ensino Fundamental II", "Ensino Médio"])
    st.session_state.estilo_arte = st.selectbox(
        "Estilo Visual", 
        ["vibrant children storybook illustration", "epic fantasy digital painting", "watercolor fairytale art", "cinematic 3d render"]
    )

# --- FUNÇÃO 1: GERAR TEXTO VIA LLAMA 3.3 70B ---
def chamar_llama(prompt_system, prompt_user, api_key):
    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "messages": [
            {"role": "system", "content": prompt_system},
            {"role": "user", "content": prompt_user}
        ],
        "temperature": 0.7,
        "max_tokens": 700
    }
    
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        st.error(f"🚨 Erro no Llama ({response.status_code}): {response.text}")
        st.stop()

# --- FUNÇÃO 2: GERAR IMAGEM VIA FLUX.1-SCHNELL ---
def gerar_imagem_flux(prompt_text, api_key):
    url = "https://api.together.xyz/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "black-forest-labs/FLUX.1-schnell",
        "prompt": f"{prompt_text}, {st.session_state.estilo_arte}, highly detailed, sharp focus",
        "width": 1024,
        "height": 768,
        "steps": 4,
        "n": 1
    }
    
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    if response.status_code == 200:
        img_url = response.json()["data"][0]["url"]
        img_data = requests.get(img_url).content
        return Image.open(io.BytesIO(img_data))
    else:
        st.error(f"🚨 Erro no FLUX ({response.status_code}): {response.text}")
        st.stop()

# --- FUNÇÃO DE NARRATIVA COMBINADA ---
def gerar_rodada_rpg(prompt_acao, api_key, heroi_ativo=None, is_intro=False):
    system_prompt = f"""
    Você é o Mestre de um RPG pedagógico baseado no livro '{st.session_state.mundo_mestre}' para {st.session_state.faixa_etaria}.
    REGRAS RÍGIDAS:
    1. Nunca use violência explícita ou morte. Personagens derrotados apenas são congelados ou recuam.
    2. A narrativa deve ser envolvente e pedagógica.
    3. Retorne a resposta ESTRITAMENTE em duas partes separadas por '---':
       Parte 1: A narrativa em português (máximo 2 parágrafos).
       Parte 2: Um prompt em INGLÊS curto para a imagem da cena.
    """
    
    if is_intro:
        user_prompt = "Narre o início da jornada da comitiva de alunos e apresente o primeiro grande desafio no mundo do livro!"
    else:
        user_prompt = f"O herói {heroi_ativo['personagem']} realizou a seguinte ação: {prompt_acao}. Narre a consequência dessa ação!"

    resposta = chamar_llama(system_prompt, user_prompt, api_key)
    
    if "---" in resposta:
        narrativa, prompt_img = resposta.split("---", 1)
    else:
        narrativa, prompt_img = resposta, "fantasy adventure scene"
        
    imagem = gerar_imagem_flux(prompt_img.strip(), api_key)
    return narrativa.strip(), imagem

# --- TELA 1: SETUP DA TURMA ---
if not st.session_state.game_started:
    st.title("⚔️ RPG Pedagógico em Sala de Aula")
    st.subheader("Configuração da Turma")
    
    num_alunos = st.number_input("Quantidade de Alunos/Grupos", min_value=1, max_value=40, value=5)
    
    col1, col2 = st.columns(2)
    herois_temp = []
    
    for i in range(num_alunos):
        with col1 if i % 2 == 0 else col2:
            st.markdown(f"##### Aluno/Grupo {i+1}")
            nome_aluno = st.text_input(f"Nome do Aluno {i+1}", f"Aluno {i+1}", key=f"aluno_{i}")
            nome_heroi = st.text_input(f"Nome do Personagem {i+1}", f"Herói {i+1}", key=f"heroi_{i}")
            herois_temp.append({"aluno": nome_aluno, "personagem": nome_heroi, "status": "Ativo"})

    if st.button("🚀 Iniciar Aventura!", type="primary"):
        if not together_key:
            st.error("Insira a chave da Together AI na barra lateral para começar!")
        else:
            st.session_state.herois = herois_temp
            with st.spinner("Criando o universo e gerando o cenário inicial..."):
                narrativa_intro, img_intro = gerar_rodada_rpg("", together_key, is_intro=True)
                st.session_state.historico.append({"tipo": "mestre", "texto": narrativa_intro})
                st.session_state.imagem_atual = img_intro
                st.session_state.game_started = True
                st.rerun()

# --- TELA 2: O JOGO EM EXECUÇÃO ---
else:
    st.title(f"📖 Aventura em {st.session_state.mundo_mestre}")
    
    # Exibe a Imagem da Cena Atual na Tela de 85"
    if st.session_state.imagem_atual:
        st.image(st.session_state.imagem_atual, use_container_width=True)
    
    # Layout em Colunas: História vs Painel dos Alunos
    col_hist, col_controlo = st.columns([2, 1])
    
    with col_hist:
        st.subheader("📜 Diário da Aventura")
        for item in reversed(st.session_state.historico):
            if item["tipo"] == "mestre":
                st.info(item["texto"])
            else:
                st.success(f"**{item['heroi']}:** {item['texto']}")

    with col_controlo:
        st.subheader("🎯 Vez do Jogador")
        
        # Qual aluno joga nesta rodada
        idx_heroi = st.session_state.rodada % len(st.session_state.herois)
        heroi_atual = st.session_state.herois[idx_heroi]
        
        st.markdown(f"""
        <div class="hero-card">
            <h4>Vez de: {heroi_atual['aluno']}</h4>
            <p><strong>Personagem:</strong> {heroi_atual['personagem']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        acao_aluno = st.text_area("O que o seu personagem decide fazer?", placeholder="Ex: Tento conversar com o sábio e decifrar o enigma...")
        
        if st.button("✨ Executar Ação", type="primary"):
            if acao_aluno and together_key:
                with st.spinner("O Mestre está calculando o resultado e pintando a cena..."):
                    # Registra ação do aluno
                    st.session_state.historico.append({
                        "tipo": "aluno", 
                        "heroi": heroi_atual["personagem"], 
                        "texto": acao_aluno
                    })
                    
                    # Gera resposta do Mestre + Imagem
                    narrativa, nova_img = gerar_rodada_rpg(acao_aluno, together_key, heroi_ativo=heroi_atual)
                    
                    st.session_state.historico.append({"tipo": "mestre", "texto": narrativa})
                    st.session_state.imagem_atual = nova_img
                    st.session_state.rodada += 1
                    st.rerun()
