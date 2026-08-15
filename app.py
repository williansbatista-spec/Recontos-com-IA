import os
import math
import random
import time
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import io
import requests
import base64

# ---------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="RPG Escolar - Multiverso da Leitura",
    page_icon="🎲",
    layout="wide"
)

st.title("🎲 RPG Escolar: O Multiverso da Leitura")

# ---------------------------------------------------------------------------
# 2. BARRA LATERAL: CONFIGURAÇÕES E SECRETS
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Parâmetros da Partida")
    
    # 1. Puxando as chaves do arquivo secrets.toml de forma invisível
    gemini_key = st.secrets.get("GEMINI_API_KEY", "").strip()
    together_key = st.secrets.get("TOGETHER_API_KEY", "").strip()

    # 2. Trava de segurança
    if not gemini_key or not together_key:
        st.error("⚠️ Chaves de API não encontradas nas variáveis de ambiente (secrets)!")
        st.stop()
    else:
        st.success("🟢 APIs Conectadas! (Gemini & Together AI)")
    
    st.divider()

    if not st.session_state.get("partida_iniciada", False):
        total_rodadas = st.slider("Duração (Número de Rodadas):", min_value=5, max_value=35, value=20)
        faixa_etaria = st.selectbox(
            "Faixa Etária:",
            ["Ensino Fundamental I (1º ao 3º ano)", "Ensino Fundamental I (4º e 5º ano)", "Ensino Fundamental II"]
        )
        
        estilo_arte = st.selectbox(
            "🎨 Estilo Visual das Imagens:",
            [
                "Children's Storybook Illustration, vibrant colors, flat design",
                "Studio Ghibli Anime Style, magical atmosphere",
                "16-bit Retro Video Game Pixel Art",
                "Soft Watercolor Painting, fantasy children book",
                "3D Pixar CGI Animation style, cute and highly detailed"
            ]
        )
        
        st.session_state["total_rodadas"] = total_rodadas
        st.session_state["faixa_etaria"] = faixa_etaria
        st.session_state["estilo_arte"] = estilo_arte
    else:
        st.info(f"📌 **Rodadas totais:** {st.session_state.get('total_rodadas', 20)}")
        st.info(f"📌 **Faixa etária:** {st.session_state.get('faixa_etaria', 'Ensino Fundamental I')}")
        st.info(f"📖 **Mundo Atual:** {st.session_state.get('mundo_mestre', 'Indefinido')}")
        st.info(f"🎨 **Estilo de Arte:** {st.session_state.get('estilo_arte', '').split(',')[0]}")

        st.divider()
        
        if st.button("🗑️ Encerrar e Reiniciar Jogo", type="primary", use_container_width=True):
            chaves_para_limpar = [
                "partida_iniciada", "jogadores", "mundo_mestre", 
                "rodada_atual", "historico", "roteiro_hq", 
                "aluno_sorteado", "pergunta_atual", "ultimo_dado", "estilo_arte"
            ]
            for chave in chaves_para_limpar:
                if chave in st.session_state:
                    del st.session_state[chave]
            st.rerun()

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
if "aluno_sorteado" not in st.session_state:
    st.session_state.aluno_sorteado = None
if "pergunta_atual" not in st.session_state:
    st.session_state.pergunta_atual = None

# ---------------------------------------------------------------------------
# 4. FUNÇÕES AUXILIARES & IA 
# ---------------------------------------------------------------------------
def rolar_dado():
    return random.randint(1, 20)

def inicializar_cliente_gemini(key):
    return genai.Client(api_key=key)

def obter_primeiro_nome(nome_completo):
    return str(nome_completo).strip().split()[0]

def sortear_proximo_aluno_automatico(aluno_atual=None):
    vivos = [j for j in st.session_state.jogadores if j["status"] == "VIVO" and j.get("presente", True)]
    if not vivos:
        st.session_state.aluno_sorteado = None
        return
    
    if len(vivos) > 1 and aluno_atual:
        opcoes = [j for j in vivos if j["aluno"] != aluno_atual["aluno"]]
        st.session_state.aluno_sorteado = random.choice(opcoes)
    else:
        st.session_state.aluno_sorteado = random.choice(vivos)

def renderizar_painel_jogadores():
    st.markdown("### 🛡️ Painel dos Heróis")
    
    jogadores_presentes = [j for j in st.session_state.jogadores if j.get("presente", True)]
    total = len(jogadores_presentes)
    
    if total == 0:
        st.info("Nenhum aluno cadastrado/presente.")
        return

    cols_por_linha = math.ceil(total / 2)
    
    cols_l1 = st.columns(cols_por_linha)
    for idx in range(cols_por_linha):
        if idx < total:
            exibir_card_compacto(cols_l1[idx], jogadores_presentes[idx])
            
    if total > cols_por_linha:
        cols_l2 = st.columns(cols_por_linha)
        for idx in range(cols_por_linha, total):
            exibir_card_compacto(cols_l2[idx - cols_por_linha], jogadores_presentes[idx])
            
    st.divider()

def exibir_card_compacto(coluna, j):
    primeiro_nome = obter_primeiro_nome(j["aluno"])
    is_ativo = j["status"] == "VIVO"
    status_icon = "🛡️" if is_ativo else "🧊"
    
    is_sorteado = (
        st.session_state.aluno_sorteado and 
        st.session_state.aluno_sorteado["aluno"] == j["aluno"]
    )
    
    item_str = " 🧪" if j.get("tem_porcao_resgate") else ""
    
    with coluna:
        if is_sorteado:
            st.markdown(f"⭐ **{status_icon} {primeiro_nome}**{item_str}")
        else:
            st.markdown(f"**{status_icon} {primeiro_nome}**{item_str}")
        st.caption(f"🎭 {j['personagem']}")

def gerar_narrativa_rpg(g_key, prompt_contexto, is_intro=False, is_final=False, herois_vivos=None, heroi_ativo=None):
    client = inicializar_cliente_gemini(g_key)
    faixa = st.session_state.get("faixa_etaria", "Ensino Fundamental I")
    estilo = st.session_state.get("estilo_arte", "vibrant children storybook style")
    
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
    Parte 1: A narrativa da cena (até 2 parágrafos).
    Parte 2: O prompt em INGLÊS muito detalhado para gerar a imagem. 
    OBRIGATÓRIO na Parte 2:
    - O estilo visual DEVE SER EXACTAMENTE este: "{estilo}".
    - {f"O foco central da imagem deve ser o herói em ação ({heroi_ativo['personagem']})." if heroi_ativo else "A imagem deve mostrar o grupo de heróis."}
    - {lista_observadores}
    - Mantenha os traços e roupas dos personagens o mais consistentes possível com a classe/arquétipo deles.
    """
    
    if is_intro:
        prompt_contexto = (
            f"INTRODUÇÃO DA AVENTURA: Apresente o reino fantástico do livro '{st.session_state.mundo_mestre}'. "
            f"Descreva como a comitiva de heróis chegou a este lugar e apresente o primeiro grande desafio no horizonte!"
        )
    elif is_final:
        prompt_contexto += " ESTA É A RODADA FINAL! Narre a grande vitória vitoriosa e épica da turma contra o desafio principal."

    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt_contexto,
            config=types.GenerateContentConfig(system_instruction=instrucao_mestre)
        )
        texto = response.text
    except Exception as e:
        return f"Erro na narrativa: {e}", f"epic scene, {estilo}"

    if "---" in texto:
        narrativa, prompt_img = texto.split("---", 1)
    else:
        narrativa = texto
        prompt_img = f"epic scene, {estilo}"
    
    return narrativa.strip(), prompt_img.strip()

# ===========================================================================
# NOVA FUNÇÃO GERAR_IMAGEM COM DIAGNÓSTICO DE ERRO (TOGETHER AI)
# ===========================================================================
def gerar_imagem(prompt_text, chave_api):
    if not chave_api:
        st.error("🚨 ERRO: A chave da API não chegou na função. Verifique seus Secrets!")
        return None

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
            data = response.json()
            if "data" in data and len(data["data"]) > 0:
                item = data["data"][0]
                if "url" in item:
                    img_res = requests.get(item["url"])
                    return Image.open(io.BytesIO(img_res.content))
                elif "b64_json" in item:
                    return Image.open(io.BytesIO(base64.b64decode(item["b64_json"])))
                    
        # SE DER ERRO, VAI MOSTRAR NA TELA EXATAMENTE O MOTIVO:
        st.error(f"🚨 **ERRO DA API TOGETHER:** Código {response.status_code}")
        st.error(f"🔍 **Detalhes do Erro:** {response.text}")
        return None

    except Exception as e:
        st.error(f"🚨 **ERRO DO PYTHON/SERVIDOR:** {e}")
        return None

def gerar_pergunta_livro(g_key, livro, faixa):
    client = inicializar_cliente_gemini(g_key)
    prompt = f"""
    Gere uma pergunta de múltipla escolha sobre o livro '{livro}' para a faixa etária {faixa}.
    Formate assim:
    PERGUNTA: [Texto da Pergunta]
    A) [Opção A]
    B) [Opção B]
    C) [Opção C]
    GABARITO: [Letra e Resposta Correta com explicação curta]
    """
    try:
        response = client.models.generate_content(model='gemini-3.5-flash-lite', contents=prompt)
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
            try:
                df = pd.read_csv(csv_file)
                if len(df.columns) <= 1:
                    csv_file.seek(0)
                    df = pd.read_csv(csv_file, sep=';')
            except Exception:
                csv_file.seek(0)
                df = pd.read_csv(csv_file, sep=';')

            df.columns = df.columns.str.strip()
            
            col_map = {col.lower(): col for col in df.columns}
            c_aluno = col_map.get("nome do aluno") or col_map.get("aluno") or col_map.get("nome")
            c_livro = col_map.get("livro lido") or col_map.get("livro")
            c_personagem = col_map.get("nome do personagem") or col_map.get("personagem")
            c_habilidade = col_map.get("habilidade")
            c_item = col_map.get("item mágico") or col_map.get("item magico") or col_map.get("item")

            if not all([c_aluno, c_livro, c_personagem, c_habilidade, c_item]):
                st.error("⚠️ Não encontramos todas as colunas necessárias! Certifique-se de que seu arquivo possui: 'Nome do Aluno', 'Livro Lido', 'Nome do Personagem', 'Habilidade' e 'Item Mágico'.")
            else:
                st.success(f"🟢 {len(df)} alunos carregados com sucesso!")
                st.dataframe(df, use_container_width=True)
                
                if st.button("🚀 Iniciar Aventura e Fixar Mundo!", type="primary"):
                    jogadores = []
                    for _, row in df.iterrows():
                        jogadores.append({
                            "aluno": str(row[c_aluno]),
                            "livro": str(row[c_livro]),
                            "personagem": str(row[c_personagem]),
                            "habilidade": str(row[c_habilidade]),
                            "item": str(row[c_item]),
                            "status": "VIVO",
                            "tem_porcao_resgate": False,
                            "presente": True
                        })
                    
                    st.session_state.jogadores = jogadores
                    
                    livros_disponiveis = list(set([j["livro"] for j in jogadores]))
                    st.session_state.mundo_mestre = random.choice(livros_disponiveis)

                    sortear_proximo_aluno_automatico()
                    vivos_agora = [j for j in st.session_state.jogadores if j["status"] == "VIVO" and j.get("presente", True)]

                    with st.spinner(f"Criando o mundo de '{st.session_state.mundo_mestre}'..."):
                        narrativa_intro, p_img = gerar_narrativa_rpg(
                            gemini_key, 
                            st.session_state.mundo_mestre, 
                            is_intro=True,
                            herois_vivos=vivos_agora
                        )
                        # Chama a geração de imagem com a chave do Together AI
                        img_intro = gerar_imagem(p_img, together_key)

                        st.session_state.historico.append({
                            "texto": narrativa_intro,
                            "img": img_intro,
                            "heroi": f"Abertura da Jornada em {st.session_state.mundo_mestre}"
                        })
                        st.session_state.roteiro_hq.append(f"INTRODUÇÃO AO MUNDO '{st.session_state.mundo_mestre}': {narrativa_intro}")

                    st.session_state.partida_iniciada = True
                    st.rerun()

        except Exception as e:
            st.error(f"Erro ao processar o arquivo CSV: {e}")

# ---------------------------------------------------------------------------
# 6. MODO DE VISUALIZAÇÃO (TUDO NA MESMA ABA)
# ---------------------------------------------------------------------------
else:
    modo_visao = st.sidebar.radio(
        "🖥️ Mudar Visão desta Janela:",
        ["📺 Tela da Turma (Projetor)", "🕹️ Controle do Mestre"],
        index=0
    )

    vivos = [j for j in st.session_state.jogadores if j["status"] == "VIVO" and j.get("presente", True)]
    congelados = [j for j in st.session_state.jogadores if j["status"] == "CONGELADO" and j.get("presente", True)]
    tot_rodadas = st.session_state.get("total_rodadas", 20)
    is_ultima_rodada = st.session_state.rodada_atual >= tot_rodadas

    # =========================================================================
    # VISÃO 1: TELA DA Turma (PROJETOR)
    # =========================================================================
    if modo_visao == "📺 Tela da Turma (Projetor)":
        auto_refresh = st.checkbox("🔄 Atualização Automática da Projeção", value=True)
        
        renderizar_painel_jogadores()

        if st.session_state.aluno_sorteado and st.session_state.aluno_sorteado.get("presente", True):
            h = st.session_state.aluno_sorteado
            p_nome = obter_primeiro_nome(h['aluno'])
            st.markdown(f"### ⭐ Herói em Ação: **{p_nome}** como *{h['personagem']}*")
            st.info(f"✨ **Item Mágico:** {h['item']} | 🪄 **Habilidade:** {h['habilidade']} | 📖 **Livro da Ficha:** {h['livro']}")

        if st.session_state.historico:
            ultimo = st.session_state.historico[-1]
            
            rodada_visual = st.session_state.rodada_atual - 1 
            if rodada_visual < 1: rodada_visual = 1
            
            st.subheader(f"🎬 RODADA {rodada_visual} | {ultimo['heroi']}")
            
            c_img, c_txt = st.columns([1, 1])
            with c_img:
                if ultimo["img"]:
                    st.image(ultimo["img"], use_container_width=True)
                else:
                    st.warning("Imagem indisponível para esta cena.")
            with c_txt:
                st.markdown("### Narrativa Atual:")
                st.write(ultimo["texto"])

        st.divider()
        st.subheader("📜 Cenas Anteriores")
        for item in reversed(st.session_state.historico[:-1]):
            with st.expander(f"Cena: {item['heroi']}"):
                st.write(item["texto"])

        if auto_refresh:
            time.sleep(3)
            st.rerun()

    # =========================================================================
    # VISÃO 2: PAINEL DE CONTROLE DO MESTRE
    # =========================================================================
    else:
        st.header("🕹️ Controle Exclusivo do Mestre")
        
        if st.session_state.historico:
            with st.expander("📖 Leia a Situação Atual da História", expanded=True):
                st.write(st.session_state.historico[-1]["texto"])
        
        with st.expander("📋 Chamada de Alunos (Marque/Desmarque Faltantes)"):
            for idx, j in enumerate(st.session_state.jogadores):
                col_p1, col_p2 = st.columns([3, 1])
                with col_p1:
                    st.write(f"**{j['aluno']}** ({j['personagem']})")
                with col_p2:
                    is_p = st.checkbox("Presente", value=j.get("presente", True), key=f"pres_{idx}_{j['aluno']}")
                    if is_p != j.get("presente", True):
                        j["presente"] = is_p
                        if not is_p and st.session_state.aluno_sorteado == j:
                            sortear_proximo_aluno_automatico()
                        st.rerun()

        renderizar_painel_jogadores()
        
        if not is_ultima_rodada:
            col_m1, col_m2 = st.columns(2)

            with col_m1:
                st.subheader("1. Herói da Rodada")
                
                if not st.session_state.aluno_sorteado and vivos:
                    sortear_proximo_aluno_automatico()

                aluno_selecionado = st.selectbox(
                    "Aluno em ação na rodada atual:",
                    options=vivos,
                    index=vivos.index(st.session_state.aluno_sorteado) if st.session_state.aluno_sorteado in vivos else 0,
                    format_func=lambda j: f"{obter_primeiro_nome(j['aluno'])} ({j['personagem']})"
                ) if vivos else None

                if aluno_selecionado:
                    st.session_state.aluno_sorteado = aluno_selecionado

                    if aluno_selecionado.get("tem_porcao_resgate") and congelados:
                        st.warning(f"🧪 {obter_primeiro_nome(aluno_selecionado['aluno'])} tem uma Poção de Resgate!")
                        aluno_salvar = st.selectbox("Descongelar colega:", options=congelados, format_func=lambda x: obter_primeiro_nome(x["aluno"]))
                        if st.button("Usar Poção de Resgate"):
                            aluno_salvar["status"] = "VIVO"
                            aluno_selecionado["tem_porcao_resgate"] = False
                            st.success(f"{obter_primeiro_nome(aluno_salvar['aluno'])} voltou ao jogo!")
                            st.rerun()

                if st.button("🔄 Resortear Aluno Manualmente"):
                    sortear_proximo_aluno_automatico(st.session_state.aluno_sorteado)
                    st.session_state.pergunta_atual = None
                    st.session_state.pop("ultimo_dado", None)
                    st.rerun()

            with col_m2:
                st.subheader("2. Resolução do Desafio")
                if st.session_state.aluno_sorteado:
                    if st.button("🎲 Rolar D20 (Sorte)"):
                        st.session_state["ultimo_dado"] = rolar_dado()
                    
                    if "ultimo_dado" in st.session_state:
                        st.write(f"Resultado do Dado: **{st.session_state['ultimo_dado']}**")

                    if st.button("📖 Gerar Pergunta sobre o Livro"):
                        with st.spinner("Gerando pergunta..."):
                            q = gerar_pergunta_livro(
                                gemini_key, 
                                st.session_state.aluno_sorteado["livro"], 
                                st.session_state.get("faixa_etaria", "Ensino Fundamental I")
                            )
                            st.session_state.pergunta_atual = q

                    if st.session_state.pergunta_atual:
                        st.warning("🔒 GABARITO DO MESTRE:")
                        st.markdown(st.session_state.pergunta_atual)

            st.divider()

            st.subheader("3. Decisão do Mestre & Avanço do Desafio")
            col_b1, col_b2 = st.columns(2)

            if aluno_selecionado and col_b1.button("✅ APROVAR SUCESSO", type="primary", use_container_width=True):
                if random.random() < 0.30:
                    aluno_selecionado["tem_porcao_resgate"] = True
                    st.toast(f"✨ {obter_primeiro_nome(aluno_selecionado['aluno'])} ganhou uma Poção de Resgate!")

                p_nome = obter_primeiro_nome(aluno_selecionado['aluno'])
                cena_anterior = st.session_state.historico[-1]['texto'] if st.session_state.historico else "Início da jornada."

                contexto = (
                    f"MUNDO BASE: '{st.session_state.mundo_mestre}'. "
                    f"RODADA ATUAL: {st.session_state.rodada_atual} de {tot_rodadas}. "
                    f"CENA ANTERIOR: {cena_anterior} \n"
                    f"AÇÃO: O herói {aluno_selecionado['personagem']} (aluno {p_nome}) usou o item '{aluno_selecionado['item']}' "
                    f"e a habilidade '{aluno_selecionado['habilidade']}' e VENCEU o obstáculo da cena anterior! \n"
                    f"INSTRUÇÃO IMPORTANTE: Primeiro, narre brevemente como ele resolveu o obstáculo anterior. "
                    f"EM SEGUIDA, a história avança: crie um PRÓXIMO DESAFIO totalmente novo no caminho deles."
                )

                with st.spinner("NARRANDO SUCESSO E GERANDO PRÓXIMO DESAFIO..."):
                    narrativa, p_img = gerar_narrativa_rpg(
                        gemini_key, 
                        contexto, 
                        herois_vivos=vivos, 
                        heroi_ativo=aluno_selecionado
                    )
                    # Chama a geração de imagem com a chave do Together AI
                    img = gerar_imagem(p_img, together_key)

                    st.session_state.roteiro_hq.append(f"RODADA {st.session_state.rodada_atual}: [SUCESSO] {aluno_selecionado['personagem']}. Narrativa: {narrativa}")
                    st.session_state.historico.append({"texto": narrativa, "img": img, "heroi": f"Sucesso de {aluno_selecionado['personagem']}"})
                    
                    st.session_state.rodada_atual += 1
                    st.session_state.pergunta_atual = None
                    st.session_state.pop("ultimo_dado", None)
                    
                    sortear_proximo_aluno_automatico(aluno_selecionado)
                    st.rerun()

            if aluno_selecionado and col_b2.button("❌ REGISTRAR FALHA", use_container_width=True):
                for j in st.session_state.jogadores:
                    if j["aluno"] == aluno_selecionado["aluno"]:
                        j["status"] = "CONGELADO"

                p_nome = obter_primeiro_nome(aluno_selecionado['aluno'])
                cena_anterior = st.session_state.historico[-1]['texto'] if st.session_state.historico else "Início da jornada."

                contexto = (
                    f"MUNDO BASE: '{st.session_state.mundo_mestre}'. "
                    f"RODADA ATUAL: {st.session_state.rodada_atual} de {tot_rodadas}. "
                    f"CENA ANTERIOR: {cena_anterior} \n"
                    f"AÇÃO: O herói {aluno_selecionado['personagem']} (aluno {p_nome}) FALHOU ao tentar superar o obstáculo e foi congelado temporariamente (narrativa sem violência). \n"
                    f"INSTRUÇÃO IMPORTANTE: Primeiro, narre a falha e o congelamento. EM SEGUIDA, aplique o 'Fail Forward': a falha causa uma complicação nova ou o obstáculo evolui para um cenário pior, exigindo ação imediata do próximo herói."
                )

                vivos_restantes = [v for v in vivos if v['aluno'] != aluno_selecionado['aluno']]

                with st.spinner("REGISTRANDO FALHA E GERANDO PRÓXIMO DESAFIO..."):
                    narrativa, p_img = gerar_narrativa_rpg(
                        gemini_key, 
                        contexto, 
                        herois_vivos=vivos_restantes, 
                        heroi_ativo=aluno_selecionado
                    )
                    # Chama a geração de imagem com a chave do Together AI
                    img = gerar_imagem(p_img, together_key)

                    st.session_state.roteiro_hq.append(f"RODADA {st.session_state.rodada_atual}: [FALHA] {aluno_selecionado['personagem']}. Narrativa: {narrativa}")
                    st.session_state.historico.append({"texto": narrativa, "img": img, "heroi": f"Falha de {aluno_selecionado['personagem']}"})
                    
                    st.session_state.rodada_atual += 1
                    st.session_state.pergunta_atual = None
                    st.session_state.pop("ultimo_dado", None)
                    
                    sortear_proximo_aluno_automatico(aluno_selecionado)
                    st.rerun()

        else:
            st.header("🏆 Finalizar Jogo")
            if st.button("🎬 Gerar Gran Finale!", type="primary"):
                contexto = f"Mundo da história: {st.session_state.mundo_mestre}. Vitória final de todos os heróis reunidos!"
                with st.spinner("Criando cena final..."):
                    narrativa, p_img = gerar_narrativa_rpg(
                        gemini_key, 
                        contexto, 
                        is_final=True,
                        herois_vivos=vivos
                    )
                    # Chama a geração de imagem final com a chave do Together AI
                    img_final = gerar_imagem(p_img, together_key)

                    st.session_state.historico.append({"texto": narrativa, "img": img_final, "heroi": "TODOS OS HERÓIS REUNIDOS"})
                    st.session_state.roteiro_hq.append(f"CENA FINAL: Vitória Épica. {narrativa}")
                    st.rerun()

        st.divider()
        texto_roteiro = "\n\n".join(st.session_state.roteiro_hq)
        st.download_button(
            label="📥 Baixar Roteiro Completo da Aula (TXT)",
            data=texto_roteiro,
            file_name="roteiro_hq_aula.txt",
            mime="text/plain"
        )
