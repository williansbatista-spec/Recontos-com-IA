import os
import random
import time
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from huggingface_hub import InferenceClient

# ---------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="RPG Escolar - Mestre de Aventura",
    page_icon="🎲",
    layout="wide"
)

st.title("🎲 RPG Escolar: O Multiverso da Leitura")
st.caption("Aventura Interativa Pedagógica com Registro de Roteiro para HQ/Vídeo")

# ---------------------------------------------------------------------------
# 2. BARRA LATERAL: API & CONFIGURAÇÕES
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🔑 Configurações de API")
    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
    hf_token = st.secrets.get("HF_TOKEN", "").strip()

    if not gemini_key:
        gemini_key = st.text_input("Gemini API Key", type="password")
    if not hf_token:
        hf_token = st.text_input("Hugging Face Token", type="password")

    if gemini_key and hf_token:
        st.success("🟢 APIs Conectadas!")
    else:
        st.warning("⚠️ Insira as chaves necessárias.")

    st.divider()
    st.header("⚙️ Parâmetros da Partida")
    total_rodadas = st.slider("Duração (Número de Rodadas):", min_value=5, max_value=35, value=20)
    faixa_etaria = st.selectbox(
        "Faixa Etária:",
        ["Ensino Fundamental I (1º ao 3º ano)", "Ensino Fundamental I (4º e 5º ano)", "Ensino Fundamental II"]
    )

# ---------------------------------------------------------------------------
# 3. ESTADO DA SESSÃO (SESSION STATE)
# ---------------------------------------------------------------------------
if "partida_iniciada" not in st.session_state:
    st.session_state.partida_iniciada = False
if "jogadores" not in st.session_state:
    st.session_state.jogadores = []
if "mundo_mestre" not in st.session_state:
    st.session_state.mundo_mestre = ""
if "rodada_atual" not in st.session_state:
    st.session_state.rodada_atual = 1
if "historico" not in st.session_state:
    st.session_state.historico = []
if "roteiro_hq" not in st.session_state:
    st.session_state.roteiro_hq = []

# ---------------------------------------------------------------------------
# 4. FUNÇÕES AUXILIARES & IA
# ---------------------------------------------------------------------------
def rolar_dado():
    return random.randint(1, 20)

def inicializar_cliente_gemini(key):
    return genai.Client(api_key=key)

def gerar_narrativa_rpg(g_key, prompt_contexto, is_final=False):
    client = inicializar_cliente_gemini(g_key)
    
    instrucao_mestre = f"""
    Você é o Mestre de um RPG pedagógico infantil para a faixa etária: {faixa_etaria}.
    REGRAS RÍGIDAS:
    1. Jamais use termos de morte ou violência real. Alunos derrotados são apenas 'congelados', 'capturados' ou 'expulsos da área'.
    2. Responda ESTRITAMENTE em duas partes separadas por '---':
    Parte 1: A narrativa em até 2 parágrafos envolventes.
    Parte 2: O prompt em inglês detalhado para a imagem da cena.
    """
    
    if is_final:
        prompt_contexto += " ESTA É A RODADA FINAL! Narre a grande vitória vitoriosa e épica da turma contra o desafio principal."

    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt_contexto,
            config=types.GenerateContentConfig(system_instruction=instrucao_mestre)
        )
        texto = response.text
        if "---" in texto:
            narrativa, prompt_img = texto.split("---", 1)
        else:
            narrativa = texto
            prompt_img = "epic fantasy adventure scene for children's storybook"
        return narrativa.strip(), prompt_img.strip()
    except Exception as e:
        return f"Erro na narrativa: {e}", "fantasy adventure scene"

def gerar_imagem(prompt_text, is_final, token):
    try:
        client = InferenceClient(api_key=token)
        if is_final:
            prompt_completo = "16-bit retro video game ending screen, pixel art, group of diverse young heroes posing victoriously, vibrant colors"
        else:
            prompt_completo = f"{prompt_text}, vibrant children storybook style, high quality"
        
        image = client.text_to_image(prompt_completo, model="black-forest-labs/FLUX.1-schnell")
        return image
    except Exception:
        return None

def gerar_pergunta_livro(g_key, livro, faixa):
    client = inicializar_cliente_gemini(g_key)
    prompt = f"Gere uma pergunta simples de múltipla escolha sobre o livro '{livro}' adequada para {faixa}. Forneça a pergunta e a resposta correta no final."
    try:
        response = client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        return f"Erro ao gerar pergunta: {e}"

# ---------------------------------------------------------------------------
# 5. TELA DE CARREGAMENTO (IMPORTAÇÃO DO CSV)
# ---------------------------------------------------------------------------
if not st.session_state.partida_iniciada:
    st.header("📂 1. Carregar Ficha da Turma (CSV)")
    st.markdown("""
    Envie um arquivo CSV contendo as colunas: **Nome do Aluno**, **Livro Lido**, **Nome do Personagem**, **Habilidade**, **Item Mágico**.
    """)
    
    csv_file = st.file_uploader("Escolha o arquivo CSV", type=["csv"])
    
    if csv_file:
        try:
            # Tenta ler com vírgula; se falhar, tenta com ponto e vírgula
            try:
                df = pd.read_csv(csv_file)
                if len(df.columns) <= 1:
                    csv_file.seek(0)
                    df = pd.read_csv(csv_file, sep=';')
            except Exception:
                csv_file.seek(0)
                df = pd.read_csv(csv_file, sep=';')

            # Limpa espaços invisíveis nos cabeçalhos
            df.columns = df.columns.str.strip()

            st.dataframe(df.head(), use_container_width=True)
            
            # Mapeamento flexível de colunas
            col_map = {col.lower(): col for col in df.columns}
            
            c_aluno = col_map.get("nome do aluno") or col_map.get("aluno") or col_map.get("nome")
            c_livro = col_map.get("livro lido") or col_map.get("livro")
            c_personagem = col_map.get("nome do personagem") or col_map.get("personagem")
            c_habilidade = col_map.get("habilidade")
            c_item = col_map.get("item mágico") or col_map.get("item magico") or col_map.get("item")

            if not all([c_aluno, c_livro, c_personagem, c_habilidade, c_item]):
                st.error("⚠️ Não encontramos todas as colunas necessárias! Certifique-se de que seu arquivo possui: 'Nome do Aluno', 'Livro Lido', 'Nome do Personagem', 'Habilidade' e 'Item Mágico'.")
            else:
                if st.button("🚀 Iniciar Aventura!", type="primary"):
                    jogadores = []
                    for _, row in df.iterrows():
                        jogadores.append({
                            "aluno": str(row[c_aluno]),
                            "livro": str(row[c_livro]),
                            "personagem": str(row[c_personagem]),
                            "habilidade": str(row[c_habilidade]),
                            "item": str(row[c_item]),
                            "status": "VIVO",
                            "item_resgate": False
                        })
                    
                    st.session_state.jogadores = jogadores
                    livros_disponiveis = list(set([j["livro"] for j in jogadores]))
                    st.session_state.mundo_mestre = random.choice(livros_disponiveis)
                    st.session_state.partida_iniciada = True
                    st.rerun()

        except Exception as e:
            st.error(f"Erro ao processar o arquivo CSV: {e}")

# ---------------------------------------------------------------------------
# 6. PAINEL DO JOGO (PARTIDA ATIVA)
# ---------------------------------------------------------------------------
else:
    # Cabeçalho de Status
    c_head1, c_head2, c_head3 = st.columns(3)
    c_head1.metric("Mundo Mestre Sorteado", st.session_state.mundo_mestre)
    c_head2.metric("Rodada Atual", f"{st.session_state.rodada_atual} / {total_rodadas}")
    
    vivos = sum(1 for j in st.session_state.jogadores if j["status"] == "VIVO")
    c_head3.metric("Alunos Ativos", f"{vivos} / {len(st.session_state.jogadores)}")
    
    st.divider()

    # Checagem de Fim de Jogo
    is_ultima_rodada = st.session_state.rodada_atual >= total_rodadas

    # Painel de Seleção do Herói da Rodada
    if not is_ultima_rodada:
        st.subheader("🎯 Desafio da Rodada")
        
        aluno_selecionado = st.selectbox(
            "Escolha o aluno para enfrentar o desafio:",
            options=[j for j in st.session_state.jogadores if j["status"] == "VIVO"],
            format_func=lambda j: f"{j['aluno']} ({j['personagem']}) - Item: {j['item']}"
        )
        
        if aluno_selecionado:
            st.info(f"👉 **Personagem:** {aluno_selecionado['personagem']} | **Habilidade:** {aluno_selecionado['habilidade']} | **Item:** {aluno_selecionado['item']}")
            
            col_dado, col_pergunta = st.columns(2)
            
            with col_dado:
                st.markdown("#### 🎲 Opção A: Teste de Sorte (Dado Virtual)")
                if st.button("🎲 Rolar D20"):
                    resultado_dado = rolar_dado()
                    st.session_state["ultimo_dado"] = resultado_dado
                if "ultimo_dado" in st.session_state:
                    res = st.session_state["ultimo_dado"]
                    st.metric("Resultado do Dado", res)
                    if res >= 10:
                        st.success("SUCESSO NO DADO!")
                    else:
                        st.error("FALHA NO DADO!")

            with col_pergunta:
                st.markdown("#### 📖 Opção B: Desafio do Livro")
                if st.button("❓ Gerar Pergunta sobre o Livro"):
                    with st.spinner("Gerando pergunta..."):
                        q = gerar_pergunta_livro(gemini_key, aluno_selecionado['livro'], faixa_etaria)
                        st.session_state["pergunta_atual"] = q
                
                if "pergunta_atual" in st.session_state:
                    st.write(st.session_state["pergunta_atual"])

            st.divider()
            
            # Resolução da Rodada
            st.markdown("#### 📝 Decisão do Mestre:")
            c_res1, c_res2 = st.columns(2)
            
            if c_res1.button("✅ O Aluno TEVE SUCESSO!", type="primary", use_container_width=True):
                contexto = (
                    f"Mundo da história: {st.session_state.mundo_mestre}. Rodada {st.session_state.rodada_atual}. "
                    f"O herói {aluno_selecionado['personagem']} (aluno {aluno_selecionado['aluno']}) usou seu item '{aluno_selecionado['item']}' "
                    f"e sua habilidade '{aluno_selecionado['habilidade']}' para superar o obstáculo com SUCESSO!"
                )
                
                with st.spinner("Narrações e imagens sendo geradas..."):
                    narrativa, p_img = gerar_narrativa_rpg(gemini_key, contexto)
                    img = gerar_imagem(p_img, False, hf_token)
                    
                    st.session_state.roteiro_hq.append(f"CENA {st.session_state.rodada_atual}: [SUCESSO] Herói {aluno_selecionado['personagem']} usa {aluno_selecionado['item']}. Narrativa: {narrativa}")
                    st.session_state.historico.append({"texto": narrativa, "img": img, "heroi": aluno_selecionado["personagem"]})
                    
                    st.session_state.rodada_atual += 1
                    st.rerun()

            if c_res2.button("❌ O Aluno FALHOU!", use_container_width=True):
                for j in st.session_state.jogadores:
                    if j["aluno"] == aluno_selecionado["aluno"]:
                        j["status"] = "CONGELADO"
                
                contexto = (
                    f"Mundo da história: {st.session_state.mundo_mestre}. Rodada {st.session_state.rodada_atual}. "
                    f"O herói {aluno_selecionado['personagem']} tentou usar o item '{aluno_selecionado['item']}', mas FALHOU! "
                    f"Narre como ele foi congelado/capturado de forma mágica e sem violência."
                )
                
                with st.spinner("Narrações e imagens sendo geradas..."):
                    narrativa, p_img = gerar_narrativa_rpg(gemini_key, contexto)
                    img = gerar_imagem(p_img, False, hf_token)
                    
                    st.session_state.roteiro_hq.append(f"CENA {st.session_state.rodada_atual}: [FALHA] Herói {aluno_selecionado['personagem']} foi congelado. Narrativa: {narrativa}")
                    st.session_state.historico.append({"texto": narrativa, "img": img, "heroi": aluno_selecionado["personagem"]})
                    
                    st.session_state.rodada_atual += 1
                    st.rerun()

    else:
        # Batalha Final / Conclusão
        st.balloons()
        st.header("🏆 BATALHA FINAL E CONCLUSÃO!")
        
        if st.button("🎬 Gerar Gran Finale em Pixel Art 16-bits!", type="primary"):
            contexto = f"Mundo da história: {st.session_state.mundo_mestre}. Esta é a vitória final de todos os heróis reunidos!"
            with st.spinner("Criando a tela de vitória final..."):
                narrativa, p_img = gerar_narrativa_rpg(gemini_key, contexto, is_final=True)
                img_final = gerar_imagem(p_img, is_final=True, token=hf_token)
                
                st.session_state.historico.append({"texto": narrativa, "img": img_final, "heroi": "TODOS"})
                st.session_state.roteiro_hq.append(f"CENA FINAL: Vitória Épica do Grupo. {narrativa}")
                st.rerun()

    # ---------------------------------------------------------------------------
    # 7. EXIBIÇÃO DA HISTÓRIA E ROTEIRO EXPORTÁVEL
    # ---------------------------------------------------------------------------
    st.divider()
    st.subheader("📖 Linha do Tempo e Roteiro da Aula")
    
    texto_roteiro = "\n\n".join(st.session_state.roteiro_hq)
    st.download_button(
        label="📥 Baixar Roteiro para HQ / Vídeo (TXT)",
        data=texto_roteiro,
        file_name="roteiro_hq_animacao.txt",
        mime="text/plain"
    )

    for h in reversed(st.session_state.historico):
        with st.container():
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"**Destaque:** {h['heroi']}")
                st.write(h["texto"])
            with col2:
                if h["img"]:
                    st.image(h["img"], use_container_width=True)
            st.divider()
