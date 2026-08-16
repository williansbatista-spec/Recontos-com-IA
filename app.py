import os
import math
import random
import time
import base64
import io
import requests
import pandas as pd
import streamlit as st
from openai import OpenAI
from PIL import Image

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
# 2. BARRA LATERAL: API TOGETHER AI & CONFIGURAÇÕES
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🔑 Configurações de API")
    together_key = st.secrets.get("TOGETHER_API_KEY", "").strip()

    if not together_key:
        together_key = st.text_input("Together AI API Key", type="password")

    if together_key:
        st.success("🟢 Together AI Conectado (Llama + FLUX)!")
    else:
        st.warning("⚠️ Chave TOGETHER_API_KEY não encontrada nos Secrets ou no campo acima.")

    st.divider()
    st.header("⚙️ Parâmetros da Partida")
    
    modelo_together = st.selectbox(
        "🤖 Modelo da Narrativa (Together AI):",
        [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            "deepseek-ai/DeepSeek-V3",
            "Qwen/Qwen2.5-72B-Instruct-Turbo"
        ]
    )
    st.session_state["modelo_together"] = modelo_together

    modelo_flux = st.selectbox(
        "🎨 Modelo de Imagem FLUX:",
        [
            "black-forest-labs/FLUX.1-schnell",
            "black-forest-labs/FLUX.1-dev"
        ]
    )
    st.session_state["modelo_flux"] = modelo_flux
    
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
# 4. FUNÇÕES AUXILIARES & IA (TOGETHER AI: LLAMA + FLUX)
# ---------------------------------------------------------------------------
def rolar_dado():
    return random.randint(1, 20)

def obter_primeiro_nome(nome_completo):
    return str(nome_completo).strip().split()[0]

def obter_cliente_together(api_key):
    return OpenAI(
        api_key=api_key,
        base_url="https://api.together.xyz/v1"
    )

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

    # Placar de Moedas
    with st.expander("🏆 Placar Geral de Moedas", expanded=False):
        df_placar = pd.DataFrame([
            {
                "Aluno": j["aluno"],
                "Personagem": j["personagem"],
                "Status": "🛡️ Vivo" if j["status"] == "VIVO" else "🧊 Congelado",
                "Poção 🧪": "Sim" if j.get("tem_porcao_resgate") else "Não",
                "Moedas 🪙": j.get("moedas", 0)
            }
            for j in st.session_state.jogadores
        ]).sort_values(by="Moedas 🪙", ascending=False)
        st.dataframe(df_placar, use_container_width=True, hide_index=True)
            
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
    moedas_str = f" 🪙{j.get('moedas', 0)}"
    
    with coluna:
        if is_sorteado:
            st.markdown(f"⭐ **{status_icon} {primeiro_nome}**{item_str}{moedas_str}")
        else:
            st.markdown(f"**{status_icon} {primeiro_nome}**{item_str}{moedas_str}")
        st.caption(f"🎭 {j['personagem']}")

def gerar_narrativa_rpg(together_key, prompt_contexto, is_intro=False, is_final=False, herois_vivos=None, heroi_ativo=None):
    client = obter_cliente_together(together_key)
    modelo = st.session_state.get("modelo_together", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
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
    2. NUNCA descongele ou salve um jogador congelado por conta própria na narrativa. O resgate ocorre exclusivamente quando outro jogador decide usar sua poção.
    3. Quando o herói vence o desafio da rodada, TODA A COMITIVA de heróis avança junto para o próximo estágio/ambiente do mundo base: '{st.session_state.get('mundo_mestre', '')}'.
    
    FORMATO DE RESPOSTA (ESTRITO):
    Responda ESTRITAMENTE em duas partes separadas por '---':
    Parte 1: A narrativa da cena em português (até 2 parágrafos).
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
        prompt_contexto += " ESTA É A CENA FINAL! Narre a grande celebração vitoriosa e épica da turma após cumprirem a jornada."

    try:
        response = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": instrucao_mestre},
                {"role": "user", "content": prompt_contexto}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        texto = response.choices[0].message.content
    except Exception as e:
        return f"Erro na narrativa (Together AI): {e}", f"epic scene, {estilo}"

    if "---" in texto:
        narrativa, prompt_img = texto.split("---", 1)
    else:
        narrativa = texto
        prompt_img = f"epic scene, {estilo}"
    
    return narrativa.strip(), prompt_img.strip()

def gerar_imagem(prompt_text, together_key):
    if not together_key:
        return None
    try:
        modelo_flux = st.session_state.get("modelo_flux", "black-forest-labs/FLUX.1-schnell")
        url = "https://api.together.xyz/v1/images/generations"
        payload = {
            "model": modelo_flux,
            "prompt": prompt_text,
            "width": 1024,
            "height": 768,
            "steps": 4,
            "n": 1,
            "response_format": "b64_json"
        }
        headers = {
            "Authorization": f"Bearer {together_key}",
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if "data" in data and len(data["data"]) > 0:
            item = data["data"][0]
            if "b64_json" in item and item["b64_json"]:
                img_bytes = base64.b64decode(item["b64_json"])
                return Image.open(io.BytesIO(img_bytes))
            elif "url" in item and item["url"]:
                return item["url"]
        return None
    except Exception as e:
        st.error(f"Erro ao gerar imagem no Together AI (FLUX): {e}")
        return None

def gerar_pergunta_livro(together_key, livro, faixa):
    client = obter_cliente_together(together_key)
    modelo = st.session_state.get("modelo_together", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
    
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
        response = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": "Você é um professor criativo criando perguntas educativas de múltipla escolha sobre livros infantojuvenis."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro ao gerar pergunta com Together AI: {e}"

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

            df.columns = df.columns.astype(str).str.strip()
            
            col_map = {col.lower(): col for col in df.columns}
            c_aluno = col_map.get("nome do aluno") or col_map.get("aluno") or col_map.get("nome")
            c_livro = col_map.get("livro lido") or col_map.get("livro")
            c_personagem = col_map.get("nome do personagem") or col_map.get("personagem")
            c_habilidade = col_map.get("habilidade")
            c_item = col_map.get("item mágico") or col_map.get("item magico") or col_map.get("item")

            if not c_aluno and len(df.columns) > 0: c_aluno = df.columns[0]
            if not c_livro and len(df.columns) > 1: c_livro = df.columns[1]
            if not c_personagem and len(df.columns) > 2: c_personagem = df.columns[2]
            if not c_habilidade and len(df.columns) > 3: c_habilidade = df.columns[3]
            if not c_item and len(df.columns) > 4: c_item = df.columns[4]

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
                            "moedas": 0,
                            "presente": True
                        })
                    
                    st.session_state.jogadores = jogadores
                    
                    livros_disponiveis = list(set([j["livro"] for j in jogadores]))
                    st.session_state.mundo_mestre = random.choice(livros_disponiveis)

                    sortear_proximo_aluno_automatico()
                    vivos_agora = [j for j in st.session_state.jogadores if j["status"] == "VIVO" and j.get("presente", True)]

                    with st.spinner(f"Criando o mundo de '{st.session_state.mundo_mestre}' e gerando imagem no Together AI..."):
                        narrativa_intro, p_img = gerar_narrativa_rpg(
                            together_key, 
                            st.session_state.mundo_mestre, 
                            is_intro=True,
                            herois_vivos=vivos_agora
                        )
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
    
    is_chefe_rodada = (st.session_state.rodada_atual == tot_rodadas - 1)
    is_ultima_rodada = (st.session_state.rodada_atual >= tot_rodadas)

    # =========================================================================
    # VISÃO 1: TELA DA TURMA (PROJETOR)
    # =========================================================================
    if modo_visao == "📺 Tela da Turma (Projetor)":
        auto_refresh = st.checkbox("🔄 Atualização Automática da Projeção", value=True)
        
        renderizar_painel_jogadores()

        if st.session_state.aluno_sorteado and st.session_state.aluno_sorteado.get("presente", True) and not is_chefe_rodada and not is_ultima_rodada:
            h = st.session_state.aluno_sorteado
            p_nome = obter_primeiro_nome(h['aluno'])
            st.markdown(f"### ⭐ Herói em Ação: **{p_nome}** como *{h['personagem']}* (🪙 {h.get('moedas', 0)} Moedas)")
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
                    st.write(f"**{j['aluno']}** ({j['personagem']}) - 🪙 {j.get('moedas', 0)} moedas")
                with col_p2:
                    is_p = st.checkbox("Presente", value=j.get("presente", True), key=f"pres_{idx}_{j['aluno']}")
                    if is_p != j.get("presente", True):
                        j["presente"] = is_p
                        if not is_p and st.session_state.aluno_sorteado == j:
                            sortear_proximo_aluno_automatico()
                        st.rerun()

        renderizar_painel_jogadores()
        
        # ---------------------------------------------------------------------
        # TURNO REGULAR (RODADAS NORMAIS)
        # ---------------------------------------------------------------------
        if not is_chefe_rodada and not is_ultima_rodada:
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

                    # --- USAR POÇÃO DE DESCONGELAMENTO (GASTA O TURNO DO JOGADOR) ---
                    if aluno_selecionado.get("tem_porcao_resgate") and congelados:
                        st.warning(f"🧪 {obter_primeiro_nome(aluno_selecionado['aluno'])} possui uma Poção de Descongelamento!")
                        aluno_salvar = st.selectbox(
                            "Escolha o colega para resgatar (Esta ação gastará seu turno no desafio):", 
                            options=congelados, 
                            format_func=lambda x: f"{obter_primeiro_nome(x['aluno'])} ({x['personagem']})"
                        )
                        if st.button("🧪 Usar Poção & Salvar Colega (Gasta o Turno)", type="primary"):
                            aluno_salvar["status"] = "VIVO"
                            aluno_selecionado["tem_porcao_resgate"] = False
                            
                            p_nome_resgatador = obter_primeiro_nome(aluno_selecionado['aluno'])
                            p_nome_salvo = obter_primeiro_nome(aluno_salvar['aluno'])
                            
                            narrativa_resgate = (
                                f"O herói {aluno_selecionado['personagem']} ({p_nome_resgatador}) utilizou seu turno inteiro e abriu sua valiosa Poção de Resgate! "
                                f"Ao derramar o elixir mágico sobre {aluno_salvar['personagem']} ({p_nome_salvo}), o gelo se dissolveu imediatamente. "
                                f"O colega resgatado está de volta à comitiva para prosseguir na jornada!"
                            )
                            p_img = f"{aluno_selecionado['personagem']} casting glowing rescue potion on frozen {aluno_salvar['personagem']}, {st.session_state.get('estilo_arte', '')}"
                            
                            with st.spinner("Registrando resgate e gerando cena com Together AI..."):
                                img = gerar_imagem(p_img, together_key)
                                st.session_state.historico.append({
                                    "texto": narrativa_resgate,
                                    "img": img,
                                    "heroi": f"Resgate de {aluno_salvar['personagem']}"
                                })
                                st.session_state.roteiro_hq.append(f"RODADA {st.session_state.rodada_atual}: [RESGATE] {aluno_selecionado['personagem']} usou poção para libertar {aluno_salvar['personagem']}.")
                                st.session_state.rodada_atual += 1
                                st.session_state.pergunta_atual = None
                                st.session_state.pop("ultimo_dado", None)
                                sortear_proximo_aluno_automatico(aluno_selecionado)
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
                        with st.spinner("Gerando pergunta com Together AI..."):
                            q = gerar_pergunta_livro(
                                together_key, 
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

            if aluno_selecionado and col_b1.button("✅ APROVAR SUCESSO (+3 Moedas)", type="primary", use_container_width=True):
                # Ganha 3 moedas
                aluno_selecionado["moedas"] = aluno_selecionado.get("moedas", 0) + 3
                
                # Chance de encontrar Poção
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
                    f"INSTRUÇÃO IMPORTANTE: Primeiro, narre brevemente como ele superou o obstáculo. "
                    f"EM SEGUIDA, toda a comitiva de heróis avança junto para o PRÓXIMO ESTÁGIO/DESAFIO do reino."
                )

                with st.spinner("Gerando história e imagem com FLUX (Together AI)..."):
                    narrativa, p_img = gerar_narrativa_rpg(
                        together_key, 
                        contexto, 
                        herois_vivos=vivos, 
                        heroi_ativo=aluno_selecionado
                    )
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
                    f"AÇÃO: O herói {aluno_selecionado['personagem']} (aluno {p_nome}) FALHOU ao tentar superar o obstáculo e foi congelado temporariamente. \n"
                    f"INSTRUÇÃO IMPORTANTE: Narre a falha e o congelamento. Lembre-se: NÃO descongele o jogador na história! Aplique o 'Fail Forward' criando uma complicação para o herói seguinte resolver."
                )

                vivos_restantes = [v for v in vivos if v['aluno'] != aluno_selecionado['aluno']]

                with st.spinner("Gerando falha e imagem com FLUX (Together AI)..."):
                    narrativa, p_img = gerar_narrativa_rpg(
                        together_key, 
                        contexto, 
                        herois_vivos=vivos_restantes, 
                        heroi_ativo=aluno_selecionado
                    )
                    img = gerar_imagem(p_img, together_key)

                    st.session_state.roteiro_hq.append(f"RODADA {st.session_state.rodada_atual}: [FALHA] {aluno_selecionado['personagem']}. Narrativa: {narrativa}")
                    st.session_state.historico.append({"texto": narrativa, "img": img, "heroi": f"Falha de {aluno_selecionado['personagem']}"})
                    
                    st.session_state.rodada_atual += 1
                    st.session_state.pergunta_atual = None
                    st.session_state.pop("ultimo_dado", None)
                    
                    sortear_proximo_aluno_automatico(aluno_selecionado)
                    st.rerun()

        # ---------------------------------------------------------------------
        # PENÚLTIMA RODADA: CONFRONTO COM O CHEFE FINAL (TRIO)
        # ---------------------------------------------------------------------
        elif is_chefe_rodada:
            st.error("🐉 **GRANDE BATALHA: O CHEFE FINAL DO REINO APARECEU!**")
            
            # Pista Anciã dos Itens Combinados
            itens_vivos = list(set([j['item'] for j in vivos]))
            random.seed(st.session_state.rodada_atual)
            pista_combinada = random.sample(itens_vivos, min(3, len(itens_vivos)))
            
            st.info(
                f"📜 **Pista Anciã do Mestre:** *'Para derrotar a força do Chefe Final, a profecia diz que o ataque deve combinar o uso de: **{', '.join(pista_combinada)}**!'*"
            )

            st.subheader("👥 Seleção do Trio de Heróis para a Investida:")
            trio_selecionado = st.multiselect(
                "Escolha os 3 heróis que liderarão o golpe contra o Chefe Final:",
                options=vivos,
                default=vivos[:3] if len(vivos) >= 3 else vivos,
                format_func=lambda j: f"{obter_primeiro_nome(j['aluno'])} ({j['personagem']} - Item: {j['item']})"
            )

            if len(trio_selecionado) != 3:
                st.warning("⚠️ Você precisa selecionar exatamente **3 heróis** para realizar a combinação perfeita de ataque!")
            else:
                col_c1, col_c2 = st.columns(2)
                
                if col_c1.button("🔥 APROVAR GOLPE DE MISERICÓRDIA NO CHEFE (+10 Moedas cada)", type="primary", use_container_width=True):
                    # Bônus de 10 moedas para cada membro do trio
                    for hero in trio_selecionado:
                        hero["moedas"] = hero.get("moedas", 0) + 10

                    nomes_trio = ", ".join([f"{h['personagem']} ({obter_primeiro_nome(h['aluno'])})" for h in trio_selecionado])
                    
                    contexto_boss = (
                        f"MUNDO BASE: '{st.session_state.mundo_mestre}'. "
                        f"O CHEFE FINAL FOI DERROTADO! O trio lendário {nomes_trio} uniu seus itens e habilidades em um ataque perfeito e venceu o Chefe do reino! "
                        f"Narre em tom altamente triunfal o golpe decisivo que libertou todo o mundo e seus habitantes."
                    )

                    with st.spinner("NARRANDO DERRUBADA DO CHEFE FINAL COM TOGETHER AI..."):
                        narrativa, p_img = gerar_narrativa_rpg(together_key, contexto_boss, is_final=False, herois_vivos=vivos)
                        img = gerar_imagem(p_img, together_key)

                        st.session_state.roteiro_hq.append(f"RODADA {st.session_state.rodada_atual}: [CHEFE DERROTADO] Trio: {nomes_trio}. Narrativa: {narrativa}")
                        st.session_state.historico.append({"texto": narrativa, "img": img, "heroi": f"Ataque Final do Trio ({nomes_trio})"})
                        
                        st.session_state.rodada_atual += 1
                        st.rerun()

                if col_c2.button("❌ ATAQUE DO TRIO FALHOU", use_container_width=True):
                    contexto_boss_falha = (
                        f"MUNDO BASE: '{st.session_state.mundo_mestre}'. "
                        f"O trio tentou atacar o Chefe Final, mas a combinação falhou momentaneamente. O Chefe contra-atacou, mas a turma inteira se uniu para recuar e planejar o encerramento!"
                    )
                    with st.spinner("Gerando narrativa da batalha..."):
                        narrativa, p_img = gerar_narrativa_rpg(together_key, contexto_boss_falha, is_final=False, herois_vivos=vivos)
                        img = gerar_imagem(p_img, together_key)

                        st.session_state.historico.append({"texto": narrativa, "img": img, "heroi": "Investida contra o Chefe"})
                        st.session_state.rodada_atual += 1
                        st.rerun()

        # ---------------------------------------------------------------------
        # ÚLTIMA RODADA: FINALIZAÇÃO DA JORNADA
        # ---------------------------------------------------------------------
        else:
            st.header("🏆 Finalizar Jogo")
            if st.button("🎬 Gerar Gran Finale & Encerramento!", type="primary"):
                contexto = f"Mundo da história: {st.session_state.mundo_mestre}. A vitória final de todos os heróis reunidos!"
                with st.spinner("Criando grande cena final e imagem com Together AI..."):
                    narrativa, p_img = gerar_narrativa_rpg(
                        together_key, 
                        contexto, 
                        is_final=True,
                        herois_vivos=vivos
                    )
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
