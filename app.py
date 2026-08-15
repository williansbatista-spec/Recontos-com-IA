import os
import random
import io
import time
import streamlit as st
from google import genai
from huggingface_hub import InferenceClient
from PIL import Image

# ---------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA STREAMLIT
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="RPG Escolar Interativo",
    page_icon="🎲",
    layout="wide"
)

st.title("🎲 RPG Escolar Multimodal")
st.subheader("Crie histórias e quadrinhos em tempo real para a sala de aula!")

# ---------------------------------------------------------------------------
# 2. DICIONÁRIOS DE CONFIGURAÇÃO
# ---------------------------------------------------------------------------
ESTILOS = {
    "Desenho Animado 2D": "Children's book illustration, 2D flat cartoon style, vibrant colors",
    "História em Quadrinhos (HQ)": "Comic book panel, vibrant comic book illustration, bold lines",
    "Aquarela Infantil": "Watercolor painting for children's book, soft warm colors, whimsical style",
    "Pixel Art (16-Bit)": "16-bit retro pixel art style, detailed video game scene, vibrant color palette"
}

FAIXAS_ETARIAS = {
    "Educação Infantil (3 a 5 anos)": "Linguagem extremamente simples, lúdica, repetitiva, com rimas leves e tom acolhedor. Opções muito diretas.",
    "Ensino Fundamental I - 1º ao 3º ano (6 a 8 anos)": "Linguagem simples, narrativa de aventura leve, vocabulário claro e frases curtas. Desafios intuitivos.",
    "Ensino Fundamental I - 4º e 5º ano (9 a 10 anos)": "Linguagem dinâmica, aventura investigativa com enigmas simples de lógica/matemática e trabalho em equipe.",
    "Ensino Fundamental II (11 a 14 anos)": "Tom mais épico e misterioso, vocabulário rico, dilemas éticos/estratégicos e desafios intelectuais mais elaborados."
}

# ---------------------------------------------------------------------------
# 3. BARRA LATERAL: CONFIGURAÇÕES E CHAVES DE API
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🔑 Configurações de API")
    
    # Tenta obter as chaves dos Secrets primeiro e limpa espaços vazios
    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
    hf_token = st.secrets.get("HF_TOKEN", "").strip()

    # Se não encontrar nos Secrets, exibe os campos manuais
    if not gemini_key:
        gemini_key = st.text_input("Gemini API Key", type="password")
    if not hf_token:
        hf_token = st.text_input("Hugging Face Token", type="password")
        
    if gemini_key and hf_token:
        st.success("🟢 Chaves de API Ativas!")
    else:
        st.warning("⚠️ Insira as chaves nos Secrets ou nos campos acima.")
    
    st.divider()
    st.header("🏫 Perfil da Turma")
    faixa_selecionada = st.selectbox(
        "Faixa Etária / Ano Escolar:",
        options=list(FAIXAS_ETARIAS.keys()),
        index=2
    )
    orientacao_etaria = FAIXAS_ETARIAS[faixa_selecionada]

    st.header("🎨 Estilo Visual")
    estilo_selecionado = st.selectbox(
        "Estilo das ilustrações:",
        options=list(ESTILOS.keys()),
        index=0
    )
    prompt_estilo_base = ESTILOS[estilo_selecionado]
    
    st.divider()
    st.caption("Geração de imagens via Hugging Face (FLUX.1-schnell).")

# ---------------------------------------------------------------------------
# 4. GERENCIAMENTO DE ESTADO (SESSÃO)
# ---------------------------------------------------------------------------
if "historico" not in st.session_state:
    st.session_state.historico = []

if "votos_op1" not in st.session_state:
    st.session_state.votos_op1 = 0

if "votos_op2" not in st.session_state:
    st.session_state.votos_op2 = 0

# ---------------------------------------------------------------------------
# 5. FUNÇÕES DE SUPORTE E IA
# ---------------------------------------------------------------------------
def extrair_opcoes(texto_narrativa: str):
    """ Extrai 2 opções do texto gerado pelo Gemini """
    linhas = [l.strip() for l in texto_narrativa.split("\n") if l.strip()]
    op1, op2 = "Opção 1: Avançar com cuidado", "Opção 2: Procurar uma pista"
    
    opcoes_encontradas = []
    for linha in linhas:
        if linha.startswith("1.") or linha.startswith("1-") or "1)" in linha or "Opção 1" in linha:
            opcoes_encontradas.append(linha)
        elif linha.startswith("2.") or linha.startswith("2-") or "2)" in linha or "Opção 2" in linha:
            opcoes_encontradas.append(linha)
            
    if len(opcoes_encontradas) >= 2:
        return opcoes_encontradas[0], opcoes_encontradas[1]
    return op1, op2

def gerar_narrativa(prompt_usuario: str, g_key: str, estilo_prefixo: str, orientacao_idade: str):
    client = genai.Client(api_key=g_key)
    
    system_instruction = f"""
    Você é o Mestre de um RPG pedagógico infantil.
    
    DIRETRIZ DE PÚBLICO-ALVO:
    {orientacao_idade}
    
    Responda em duas partes estritamente divididas por '---':
    Parte 1: A narrativa da história em até 2 parágrafos curtos. Termine SEMPRE com 2 opções bem claras numeradas para os alunos escolherem:
    1. [Descrição da Opção 1]
    2. [Descrição da Opção 2]
    ---
    Parte 2: Escreva APENAS o prompt em inglês para o gerador de imagens, sem nenhum rótulo como 'Parte 2:'.
    Exemplo do formato esperado:
    {estilo_prefixo}: [descrição detalhada e colorida da cena visualmente, sem texto na imagem]
    """
    
    max_tentativas = 3
    for tentativa in range(max_tentativas):
        try:
            # Força o uso do modelo estável que possui maior cota gratuita
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"{system_instruction}\n\nAção/Contexto: {prompt_usuario}"
            )
            
            texto = response.text
            if "---" in texto:
                narrativa, prompt_img = texto.split("---", 1)
            else:
                narrativa = texto
                prompt_img = f"{estilo_prefixo}: storybook magical scene"
                
            return narrativa.strip(), prompt_img.strip()

        except Exception as e:
            # Trata erro de limite (429 RESOURCE_EXHAUSTED). Espera 10s e tenta de novo.
            if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and tentativa < max_tentativas - 1:
                time.sleep(10)
                continue
            else:
                raise e

def gerar_imagem_hf(prompt_img: str, estilo_prefixo: str, token: str):
    """ Gera imagem via Hugging Face Serverless Inference (FLUX.1) """
    try:
        client = InferenceClient(api_key=token)
        prompt_completo = f"{prompt_img}, {estilo_prefixo}"
        
        image = client.text_to_image(
            prompt_completo,
            model="black-forest-labs/FLUX.1-schnell"
        )
        return image
    except Exception as e:
        st.warning(f"Não foi possível gerar a imagem no Hugging Face: {e}")
        return None

def executar_rodada(acao_texto: str):
    if not gemini_key or not gemini_key.strip():
        st.error("Por favor, insira a chave de API do Gemini.")
        return
    if not hf_token or not hf_token.strip():
        st.error("Por favor, insira o token da Hugging Face.")
        return

    with st.spinner("🧠 O Mestre está escrevendo a história e desenhando a cena..."):
        try:
            narrativa, prompt_img = gerar_narrativa(
                acao_texto, 
                gemini_key.strip(), 
                prompt_estilo_base, 
                orientacao_etaria
            )
            img_gerada = gerar_imagem_hf(prompt_img, prompt_estilo_base, hf_token.strip())
            
            # Salva a nova rodada no histórico
            st.session_state.historico.append({
                "acao": acao_texto,
                "narrativa": narrativa,
                "imagem": img_gerada,
                "estilo": estilo_selecionado,
                "faixa": faixa_selecionada
            })
            
            # Reseta o placar de votos para a nova etapa
            st.session_state.votos_op1 = 0
            st.session_state.votos_op2 = 0
            
            st.success("Rodada gerada com sucesso!")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao processar a rodada: {e}")

# ---------------------------------------------------------------------------
# 6. PAINEL PRINCIPAL: JOGO & VOTAÇÃO
# ---------------------------------------------------------------------------

# CASO 1: AINDA NÃO HÁ HISTÓRICO (INÍCIO DO JOGO)
if not st.session_state.historico:
    st.info("👋 **Bem-vindo ao RPG Escolar!** Digite abaixo o tema ou o começo da história para iniciar a aventura.")
    
    with st.form("form_inicio"):
        contexto_inicial = st.text_area(
            "Qual é o ponto de partida da aventura?",
            placeholder="Ex: A turma de alunos encontrou um portal mágico escondido atrás do quadro negro da sala de aula..."
        )
        btn_iniciar = st.form_submit_button("🚀 Começar Aventura", use_container_width=True)
        
        if btn_iniciar:
            if not contexto_inicial.strip():
                st.warning("Escreva uma introdução para começar!")
            else:
                executar_rodada(contexto_inicial)

# CASO 2: O JOGO JÁ COMEÇOU (SISTEMA DE VOTAÇÃO ATIVO)
else:
    # Recupera as opções da ÚLTIMA narrativa do histórico
    ultima_narrativa = st.session_state.historico[-1]["narrativa"]
    op1_texto, op2_texto = extrair_opcoes(ultima_narrativa)

    st.markdown("### 🗳️ Votação para a Próxima Ação")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"**{op1_texto}**")
        if st.button("👍 Votar na Opção 1", key="btn_voto_1", use_container_width=True):
            st.session_state.votos_op1 += 1
            st.rerun()
        st.metric("Total de Votos", st.session_state.votos_op1)

    with col2:
        st.warning(f"**{op2_texto}**")
        if st.button("👍 Votar na Opção 2", key="btn_voto_2", use_container_width=True):
            st.session_state.votos_op2 += 1
            st.rerun()
        st.metric("Total de Votos", st.session_state.votos_op2)

    st.divider()

    # Botões de Ação da Votação
    col_enviar, col_limpar = st.columns([3, 1])

    with col_enviar:
        if st.button("🏆 Finalizar Votação e Avançar História", type="primary", use_container_width=True):
            v1 = st.session_state.votos_op1
            v2 = st.session_state.votos_op2
            
            if v1 > v2:
                escolha = f"A maioria da turma escolheu a Opção 1: {op1_texto}"
            elif v2 > v1:
                escolha = f"A maioria da turma escolheu a Opção 2: {op2_texto}"
            else:
                escolha = f"Houve empate nos votos! O Mestre decidiu seguir com a Opção 1: {op1_texto}"
                
            executar_rodada(escolha)

    with col_limpar:
        if st.button("🔄 Zerar Placar", use_container_width=True):
            st.session_state.votos_op1 = 0
            st.session_state.votos_op2 = 0
            st.rerun()

    # Opção alternativa para o professor digitar uma ação livre
    with st.expander("✍️ Ou digite uma ação personalizada (Ação Livre)"):
        with st.form("form_livre"):
            acao_custom = st.text_input("Ação customizada da turma:")
            btn_custom = st.form_submit_button("🎮 Enviar Ação Livre")
            if btn_custom and acao_custom.strip():
                executar_rodada(acao_custom)

# ---------------------------------------------------------------------------
# 7. EXIBIÇÃO DO HISTÓRICO DA HISTÓRIA
# ---------------------------------------------------------------------------
if st.session_state.historico:
    st.divider()
    st.header("📖 Linha do Tempo da Aventura")
    
    for i, rodada in enumerate(reversed(st.session_state.historico)):
        num_rodada = len(st.session_state.historico) - i
        with st.container():
            st.markdown(f"### 📍 Rodada {num_rodada}")
            c1, c2 = st.columns([1, 1])
            
            with c1:
                st.markdown(f"**Ação decidida:** _{rodada['acao']}_")
                st.markdown(rodada["narrativa"])
            
            with c2:
                if rodada["imagem"]:
                    st.image(
                        rodada["imagem"], 
                        caption=f"Cena {num_rodada} | Estilo: {rodada.get('estilo', 'Visual')}", 
                        use_container_width=True
                    )
                else:
                    st.info("🖼️ Imagem indisponível nesta rodada.")
            
            st.divider()
