import streamlit as st
import requests
import io
from PIL import Image

# --- CONFIGURAÇÃO DA PÁGINA E ESTILOS ---
st.set_page_config(
    page_title="RPG Pedagógico",
    page_icon="⚔️",
    layout="wide"
)

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    .card-heroi { background-color: #1f2937; padding: 15px; border-radius: 10px; border: 1px solid #374151; }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DO ESTADO DO JOGO ---
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

# --- BARRA LATERAL (CONFIGURAÇÕES DO MESTRE) ---
with st.sidebar:
    st.title("⚙️ Painel do Mestre")
    
    # Tenta carregar a chave dos secrets do Streamlit, se existir
    default_key = st.secrets.get("TOGETHER_API_KEY", "") if "TOGETHER_API_KEY" in st.secrets else ""
    chave_together = st.text_input("TOGETHER_API_KEY", value=default_key, type="password")
    
    st.divider()
    
    st.session_state.mundo_mestre = st.text_input("Livro/Mundo Base", "O Pequeno Príncipe")
    st.session_state.faixa_etaria = st.selectbox(
        "Faixa Etária", 
        ["Ensino Fundamental I", "Ensino Fundamental II", "Ensino Médio"]
    )
    st.session_state.estilo_arte = st.selectbox(
        "Estilo Visual das Imagens", 
        [
            "vibrant children storybook illustration", 
            "epic fantasy digital painting", 
            "watercolor fairytale art", 
            "cinematic 3d render"
        ]
    )

# --- FUNÇÃO DE NARRATIVA (LLAMA 3.3 70B VIA TOGETHER AI) ---
def gerar_narrativa_rpg(prompt_contexto, chave_api, is_intro=False, is_final=False, herois_vivos=None, heroi_ativo=None):
    faixa = st.session_state.get("faixa_etaria", "Ensino Fundamental I")
    estilo = st.session_state.get("estilo_arte", "vibrant children storybook illustration")
    
    lista_observadores = ""
    if herois_vivos:
        nomes = [h['personagem'] for h in herois_vivos if h != heroi_ativo]
        if nomes:
            lista_observadores = f"In the background, observing or reacting, are other diverse young heroes: {', '.join(nomes)}."

    instrucao_mestre = f"""
    Você é o Mestre de um RPG pedagógico infantil para a faixa etária: {faixa}.
    
    REGRAS RÍGIDAS DE NARRATIVA:
    1. Jamais use termos de morte ou violência real. Alunos derrotados são apenas 'congelados', 'capturados' ou 'expulsos da área'.
    2. Mantenha a ambientação estritamente ligada ao livro base do mundo: '{st.session_state.get('mundo_mestre', '')}'.
    
    FORMATO DE RESPOSTA (ESTRITO):
    Responda ESTRITAMENTE em duas partes separadas por '---':
    Parte 1: A narrativa da cena (até 2 parágrafos em português).
    Parte 2: O prompt em INGLÊS muito detalhado para gerar a imagem. 
    OBRIGATÓRIO na Parte 2:
    - O estilo visual DEVE SER EXACTAMENTE este: "{estilo}".
    - {f"O foco central da imagem deve ser o herói em ação ({heroi_ativo['personagem']})." if heroi_ativo else "A imagem deve mostrar o grupo de heróis."}
    - {lista_observadores}
    """
    
    if is_intro:
        prompt_contexto = f"INTRODUÇÃO DA AVENTURA: Apresente o reino fantástico do livro '{st.session_state.get('mundo_mestre', '')}'. Descreva como a comitiva de heróis chegou e o primeiro desafio!"
    elif is_final:
        prompt_contexto += " ESTA É A RODADA FINAL! Narre a grande vitória vitoriosa e épica da turma contra o desafio principal."

    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {chave_api}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "messages": [
            {"role": "system", "content": instrucao_mestre},
            {"role": "user", "content": prompt_contexto}
        ],
        "temperature": 0.7,
        "max_tokens": 800
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            texto = response.json()["choices"][0]["message"]["content"]
        else:
            st.error(f"🚨 ERRO TEXTO TOGETHER: {response.status_code} - {response.text}")
            st.stop()
    except Exception as e:
        st.error(f"🚨 ERRO CONEXÃO LLAMA: {e}")
        st.stop()

    if "---" in texto:
        narrativa, prompt_img = texto.split("---", 1)
    else:
        narrativa = texto
        prompt_img = f"epic scene, {estilo}"
    
    return narrativa.strip(), prompt_img.strip()

# --- FUNÇÃO DE IMAGEM (FLUX.1-SCHNELL VIA TOGETHER AI) ---
def gerar_imagem(prompt_text, chave_api):
    if not chave_api:
        st.error("🚨 ERRO: A chave da Together AI não foi configurada!")
        st.stop()

    url = "https://api.together.xyz/v1/images/generations"
    headers = {
        "Authorization": f"Bearer {chave_api}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "black-forest-labs/FLUX.1-schnell",
        "prompt": prompt_text,
        "width": 1024,
        "height": 768,
        "steps": 4,
        "n": 1
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            img_url = response.json()["data"][0]["url"]
            img_res = requests.get(img_url)
            return Image.open(io.BytesIO(img_res.content))
        else:
            st.error(f"🚨 ERRO IMAGEM TOGETHER: {response.status_code} - {response.text}")
            st.stop()

    except Exception as e:
        st.error(f"🚨 ERRO CONEXÃO FLUX: {e}")
        st.stop()

# ==============================================================================
# FLUXO DA INTERFACE GRÁFICA DO STREAMLIT
# ==============================================================================

# --- TELA 1: CADASTRO DOS ALUNOS E MONTAGEM DA TURMA ---
if not st.session_state.game_started:
    st.title("⚔️ RPG Pedagógico - Aventura Interativa")
    st.subheader("Configurar Jogadores da Turma")
    
    num_alunos = st.number_input("Número de Grupos/Alunos", min_value=1, max_value=40, value=5)
    
    col1, col2 = st.columns(2)
    herois_temp = []
    
    for i in range(num_alunos):
        with col1 if i % 2 == 0 else col2:
            st.markdown(f"##### Jogador/Grupo {i+1}")
            nome_aluno = st.text_input(f"Nome do Aluno/Grupo {i+1}", f"Grupo {i+1}", key=f"aluno_{i}")
            nome_heroi = st.text_input(f"Nome do Personagem {i+1}", f"Herói {i+1}", key=f"heroi_{i}")
            herois_temp.append({"aluno": nome_aluno, "personagem": nome_heroi, "status": "Ativo"})

    st.write("")
    if st.button("🚀 Iniciar Partida", type="primary"):
        if not chave_together:
            st.error("Por favor, cole sua TOGETHER_API_KEY na barra lateral antes de iniciar!")
        else:
            st.session_state.herois = herois_temp
            with st.spinner("O Mestre está criando o mundo e pintando o cenário inicial..."):
                # Gerar introdução e imagem inicial
                narrativa_intro, prompt_img_intro = gerar_narrativa_rpg("", chave_together, is_intro=True)
                img_intro = gerar_imagem(prompt_img_intro, chave_together)
                
                st.session_state.historico.append({"tipo": "mestre", "texto": narrativa_intro})
                st.session_state.imagem_atual = img_intro
                st.session_state.game_started = True
                st.rerun()

# --- TELA 2: EXECUÇÃO DO JOGO EM SALA DE AULA ---
else:
    st.title(f"📖 Aventura: {st.session_state.mundo_mestre}")
    
    # Exibição Visual Principal (Otimizada para Projetor / TV 85")
    if st.session_state.imagem_atual:
        st.image(st.session_state.imagem_atual, use_container_width=True)
    
    col_esquerda, col_direita = st.columns([2, 1])
    
    with col_esquerda:
        st.subheader("📜 Diário da Jornada")
        for item in reversed(st.session_state.historico):
            if item["tipo"] == "mestre":
                st.info(f"🧙‍♂️ **Mestre:** {item['texto']}")
            else:
                st.success(f"⚔️ **{item['heroi']} ({item['aluno']}):** {item['texto']}")

    with col_direita:
        st.subheader("🎲 Vez do Jogador")
        
        # Identifica de quem é o turno atual
        idx_heroi = st.session_state.rodada % len(st.session_state.herois)
        heroi_atual = st.session_state.herois[idx_heroi]
        
        st.markdown(f"""
        <div class="card-heroi">
            <h4>É a vez de: {heroi_atual['aluno']}</h4>
            <p><strong>Personagem:</strong> {heroi_atual['personagem']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        acao = st.text_area("O que você faz diante deste desafio?", placeholder="Descreva sua ação aqui...")
        
        if st.button("✨ Executar Ação", type="primary"):
            if acao and chave_together:
                with st.spinner("O Mestre está calculando os resultados e gerando a nova imagem..."):
                    # Salva a ação no histórico
                    st.session_state.historico.append({
                        "tipo": "aluno", 
                        "aluno": heroi_atual["aluno"],
                        "heroi": heroi_atual["personagem"], 
                        "texto": acao
                    })
                    
                    # Gera resposta da IA
                    narrativa, prompt_img = gerar_narrativa_rpg(
                        prompt_contexto=acao, 
                        chave_api=chave_together, 
                        heroi_ativo=heroi_atual,
                        herois_vivos=st.session_state.herois
                    )
                    
                    nova_img = gerar_imagem(prompt_img, chave_together)
                    
                    # Atualiza o estado da partida
                    st.session_state.historico.append({"tipo": "mestre", "texto": narrativa})
                    st.session_state.imagem_atual = nova_img
                    st.session_state.rodada += 1
                    st.rerun()
