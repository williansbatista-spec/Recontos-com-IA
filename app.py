import os
import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import io
from huggingface_hub import InferenceClient

# ---------------------------------------------------------------------------
# 1. CONFIGURAÇÃO INICIAL DA PÁGINA E ESTILOS
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="RPG Educativo Interativo",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🎭 RPG Educativo Interativo")
st.markdown("Uma aventura interativa guiada por Inteligência Artificial para a sala de aula.")

# ---------------------------------------------------------------------------
# 2. DICIONÁRIOS DE CONFIGURAÇÃO (FAIXAS ETÁRIAS E ESTILOS VISUAIS)
# ---------------------------------------------------------------------------
FAIXAS_ETARIAS = {
    "Ensino Fundamental I (6 a 10 anos)": (
        "Linguagem simples, lúdica, tom pedagógico, educativa, sem violência ou temas maduros. "
        "Foque na empatia, curiosidade e amizade."
    ),
    "Ensino Fundamental II (11 a 14 anos)": (
        "Linguagem dinâmica, desafios reflexivos, dilemas éticos simples, elementos de aventura e exploração do contexto histórico."
    ),
    "Ensino Médio (15 a 18 anos)": (
        "Linguagem madura, dilemas éticos complexos, contexto histórico profundo, pensamento crítico e tomada de decisão estratégica."
    ),
    "Livre / Geral": (
        "Tom equilibrado, acessível, envolvente e focado na imersão e no aprendizado prático."
    )
}

ESTILOS = {
    "Anime / Manga": "anime digital art style, vibrant colors, detailed lineart, studio ghibli inspired",
    "Pixel Art": "16-bit pixel art style, retro game aesthetic, detailed sprite art",
    "Massinha de Modelar (Claymation)": "claymation style, stop-motion aesthetic, textured plasticine figures, soft lighting",
    "Aquarela (Watercolor)": "soft watercolor painting style, artistic brush strokes, gentle pastel colors, storybook illustration",
    "História em Quadrinhos (Comic Book)": "comic book illustration style, bold outlines, pop art aesthetic, dynamic shading",
    "Fotorealista": "cinematic realistic photography, 8k, detailed textures, natural lighting"
}

# ---------------------------------------------------------------------------
# 3. BARRA LATERAL: CONFIGURAÇÕES DA SALA E APENAS STATUS DAS CHAVES
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Configurações da Aula")
    
    # Carregamento silencioso via Secrets ou Fallback seguro
    gemini_key = st.secrets.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")
    hf_token = st.secrets.get("HF_TOKEN") or st.text_input("Hugging Face Token", type="password")
    
    if gemini_key and hf_token:
        st.success("🟢 Sistema Conectado")
    else:
        st.warning("⚠️ Insira as chaves nos Secrets para iniciar.")

    st.divider()
    st.header("🏫 Perfil da Turma")
    faixa_selecionada = st.selectbox(
        "Faixa Etária / Ano Escolar:",
        options=list(FAIXAS_ETARIAS.keys()),
        index=1
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
    if st.button("🔄 Reiniciar Aventura"):
        st.session_state.clear()
        st.rerun()

# ---------------------------------------------------------------------------
# 4. INICIALIZAÇÃO DO ESTADO DA SESSÃO
# ---------------------------------------------------------------------------
if "historico" not in st.session_state:
    st.session_state.historico = []

if "imagem_atual" not in st.session_state:
    st.session_state.imagem_atual = None

if "jogo_iniciado" not in st.session_state:
    st.session_state.jogo_iniciado = False

# ---------------------------------------------------------------------------
# 5. FUNÇÕES DE IA (GEMINI E FLUX.1)
# ---------------------------------------------------------------------------
def gerar_texto_gemini(prompt_usuario, api_key):
    try:
        client = genai.Client(api_key=api_key)
        
        system_instruction = (
            "Você é um Mestre de RPG Educativo em sala de aula.\n"
            f"Diretriz de adequação etária: {orientacao_etaria}\n\n"
            "Mantenha a consistência histórica e comportamental dos personagens envolvidos.\n"
            "Para cada turno da história, forneça:\n"
            "1. Uma narrativa envolvente e curta (2 a 3 parágrafos).\n"
            "2. Uma descrição visual detalhada para gerar uma imagem da cena no formato: [CENA: descrição da cena em inglês].\n"
            "3. Exatamente 3 opções de escolha numeradas para os alunos votarem (Opção 1, Opção 2, Opção 3)."
        )
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_usuario,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7
            )
        )
        return response.text
    except Exception as e:
        st.error(f"Erro na geração de texto (Gemini): {e}")
        return None

def gerar_imagem_hf(prompt_cena, token):
    try:
        client = InferenceClient(api_key=token)
        prompt_final = f"{prompt_cena}, {prompt_estilo_base}"
        
        image = client.text_to_image(
            prompt_final,
            model="black-forest-labs/FLUX.1-schnell"
        )
        return image
    except Exception as e:
        st.warning(f"Não foi possível gerar a imagem no momento: {e}")
        return None

# ---------------------------------------------------------------------------
# 6. INTERFACE E FLUXO PRINCIPAL DO JOGO
# ---------------------------------------------------------------------------
if not gemini_key or not hf_token:
    st.info("👈 Por favor, certifique-se de que as chaves de API estão cadastradas nos Secrets do Streamlit.")
else:
    # TELA DE SELEÇÃO INICIAL
    if not st.session_state.jogo_iniciado:
        st.subheader("🚀 Escolha o Cenário Pedagógico")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🪵 As Aventuras de Tom Sawyer")
            st.write("Explore o Rio Mississippi no século XIX com Tom Sawyer e Huck Finn. Foco em literatura e história.")
            if st.button("Iniciar Tom Sawyer", type="primary"):
                st.session_state.personagem = "Tom Sawyer"
                st.session_state.contexto = "Tom Sawyer e seu amigo Huck Finn nas margens do Rio Mississippi no século XIX."
                st.session_state.jogo_iniciado = True
                prompt_inicial = f"Inicie a história com {st.session_state.contexto}. Crie o primeiro capítulo e as 3 opções de escolha."
                
                with st.spinner("Criando a primeira cena..."):
                    resposta = gerar_texto_gemini(prompt_inicial, gemini_key)
                    if resposta:
                        st.session_state.historico.append({"role": "mestre", "content": resposta})
                st.rerun()

        with col2:
            st.markdown("### 📖 O Diário de Anne Frank")
            st.write("Acompanhe o contexto histórico da Segunda Guerra Mundial com empatia, respeito e consciência reflexiva.")
            if st.button("Iniciar Anne Frank", type="primary"):
                st.session_state.personagem = "Anne Frank"
                st.session_state.contexto = "Anne Frank e o contexto do Anexo Secreto em Amsterdã durante a Segunda Guerra Mundial."
                st.session_state.jogo_iniciado = True
                prompt_inicial = f"Inicie a história com {st.session_state.contexto}. Crie o primeiro capítulo reflexivo e as 3 opções de escolha respeitosas."
                
                with st.spinner("Criando a primeira cena..."):
                    resposta = gerar_texto_gemini(prompt_inicial, gemini_key)
                    if resposta:
                        st.session_state.historico.append({"role": "mestre", "content": resposta})
                st.rerun()

    # TELA DE JOGO ATIVA
    else:
        st.subheader(f"📖 Aventura: {st.session_state.get('personagem', 'RPG')}")
        
        # Histórico da História
        for mensagem in st.session_state.historico:
            if mensagem["role"] == "mestre":
                st.markdown(mensagem["content"])
            elif mensagem["role"] == "aluno":
                st.info(f"📍 **Decisão da Turma:** {mensagem['content']}")

        # Extração de prompt para imagem
        if st.session_state.historico:
            ultima_resposta = st.session_state.historico[-1]["content"]
            if "[CENA:" in ultima_resposta:
                inicio = ultima_resposta.find("[CENA:") + 6
                fim = ultima_resposta.find("]", inicio)
                prompt_cena = ultima_resposta[inicio:fim].strip()
                
                col_img1, col_img2 = st.columns([1, 4])
                with col_img1:
                    if st.button("🎨 Ilustrar Cena"):
                        with st.spinner("Gerando ilustração..."):
                            img = gerar_imagem_hf(prompt_cena, hf_token)
                            if img:
                                st.session_state.imagem_atual = img
            
        if st.session_state.imagem_atual:
            st.image(st.session_state.imagem_atual, use_container_width=True)

        st.divider()

        # Entrada para a decisão dos alunos
        st.subheader("🗳️ O que a turma decide fazer?")
        escolha = st.text_input("Digite o número da opção (ex: Opção 1) ou escreva uma ação personalizada:")
        
        if st.button("Enviar Resposta e Avançar ➡️", type="primary"):
            if escolha:
                st.session_state.historico.append({"role": "aluno", "content": escolha})
                st.session_state.imagem_atual = None
                
                # Contexto acumulado
                contexto_completo = f"Contexto original: {st.session_state.contexto}\n\nHistórico:\n"
                for msg in st.session_state.historico:
                    contexto_completo += f"{msg['role']}: {msg['content']}\n"
                
                prompt_proximo = f"{contexto_completo}\n\nA turma escolheu: '{escolha}'. Continue a narrativa, forneça [CENA: ...] em inglês e 3 novas opções."
                
                with st.spinner("O Mestre está criando o próximo capítulo..."):
                    resposta = gerar_texto_gemini(prompt_proximo, gemini_key)
                    if resposta:
                        st.session_state.historico.append({"role": "mestre", "content": resposta})
                st.rerun()
            else:
                st.warning("Por favor, digite uma opção antes de avançar.")
