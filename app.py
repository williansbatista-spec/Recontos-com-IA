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
    page_title="RPG Escolar - Multiverso da Leitura",
    page_icon="🎲",
    layout="wide"
)

st.title("🎲 RPG Escolar: O Multiverso da Leitura")

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
    
    if not st.session_state.get("partida_iniciada", False):
        total_rodadas = st.slider("Duração (Número de Rodadas):", min_value=5, max_value=35, value=20)
        faixa_etaria = st.selectbox(
            "Faixa Etária:",
            ["Ensino Fundamental I (1º ao 3º ano)", "Ensino Fundamental I (4º e 5º ano)", "Ensino Fundamental II"]
        )
        st.session_state["total_rodadas"] = total_rodadas
        st.session_state["faixa_etaria"] = faixa_etaria
    else:
        st.info(f"📌 **Rodadas totais:** {st.session_state.get('total_rodadas', 20)}")
        st.info(f"📌 **Faixa etária:** {st.session_state.get('faixa_etaria', 'Ensino Fundamental I')}")
        st.info(f"📖 **Mundo Atual:** {st.session_state.get('mundo_mestre', 'Indefinido')}")

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

def renderizar_painel_jogadores():
    """Exibe o painel de ícones e primeiro nome com status e itens"""
    st.markdown("### 🛡️ Painel dos Heróis")
    
    # Criar colunas para os jogadores (até 6 por linha)
    jogadores = st.session_state.jogadores
    num_cols = min(len(jogadores), 6) if len(jogadores) > 0 else 1
    cols = st.columns(num_cols)
    
    for idx, j in enumerate(jogadores):
        col = cols[idx % num_cols]
        primeiro_nome = obter_primeiro_nome(j["aluno"])
        is_ativo = j["status"] == "VIVO"
        status_icon = "🛡️" if is_ativo else "🧊"
        status_texto = "Ativo" if is_ativo else "Congelado"
        
        # Verificar se é o aluno sorteado da rodada
        is_sorteado = (
            st.session_state.aluno_sorteado and 
            st.session_state.aluno_sorteado["aluno"] == j["aluno"]
        )
        
        # Montar os itens do inventário
        itens = []
        if j.get("tem_porcao_resgate"):
            itens.append("🧪 Poção")
        
        txt_itens = " | ".join(itens) if itens else "Nenhum"
        
        with col:
            # Destaque visual caso seja o sorteado
            if is_sorteado:
                st.markdown(f"⭐ **{status_icon} {primeiro_nome}**")
            else:
                st.markdown(f"**{status_icon} {primeiro_nome}**")
            
            st.caption(f"🎭 {j['personagem']}")
            st.caption(f"Status: {status_texto}")
            st.caption(f"🎒 {txt_itens}")
            st.divider()

def gerar_narrativa_rpg(g_key, prompt_contexto, is_intro=False, is_final=False):
    client = inicializar_cliente_gemini(g_key)
    faixa = st.session_state.get("faixa_etaria", "Ensino Fundamental I")
    
    instrucao_mestre = f"""
    Você é o Mestre de um RPG pedagógico infantil para a faixa etária: {faixa}.
    
    REGRAS RÍGIDAS DE NARRATIVA:
    1. Jamais use termos de morte ou violência real. Alunos derrotados são apenas 'congelados', 'capturados' ou 'expulsos da área'.
    2. CONTINUIDADE DA HISTÓRIA: Resolva o desafio atual da rodada E IMEDIATAMENTE apresente o novo obstáculo/desafio que a turma enfrentará no próximo passo!
    3. Mantenha a ambientação estritamente ligada ao livro base do mundo: '{st.session_state.get('mundo_mestre', '')}'.
    
    FORMATO DE RESPOSTA (ESTRITO):
    Responda ESTRITAMENTE em duas partes separadas por '---':
    Parte 1: A narrativa da resolução + apresentação do novo desafio (até 2 parágrafos).
    Parte 2: O prompt em inglês detalhado e visual para a imagem da cena.
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
                            "tem_porcao_resgate": False
                        })
                    
                    st.session_state.jogadores = jogadores
                    
                    # Sortear o Mundo Base ÚNICO
                    livros_disponiveis = list(set([j["livro"] for j in jogadores]))
                    st.session_state.mundo_mestre = random.choice(livros_disponiveis)

                    # Gerar Prólogo / Introdução
                    with st.spinner(f"Criando o mundo de '{st.session_state.mundo_mestre}'..."):
                        narrativa_intro, p_img = gerar_narrativa_rpg(gemini_key, st.session_state.mundo_mestre, is_intro=True)
                        img_intro = gerar_imagem(p_img, False, hf_token)

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
# 6. MODO DE VISUALIZAÇÃO (MESTRE OU PROJETOR VIA BARRA LATERAL)
# ---------------------------------------------------------------------------
else:
    modo_visao = st.sidebar.radio(
        "🖥️ Mudar Visão desta Janela:",
        ["📺 Tela da Turma (Projetor)", "🕹️ Controle do Mestre"],
        index=0
    )

    vivos = [j for j in st.session_state.jogadores if j["status"] == "VIVO"]
    congelados = [j for j in st.session_state.jogadores if j["status"] == "CONGELADO"]
    tot_rodadas = st.session_state.get("total_rodadas", 20)
    is_ultima_rodada = st.session_state.rodada_atual >= tot_rodadas

    # =========================================================================
    # VISÃO 1: TELA DA TURMA (PROJETOR)
    # =========================================================================
    if modo_visao == "📺 Tela da Turma (Projetor)":
        auto_refresh = st.checkbox("🔄 Atualização Automática da Projeção", value=True)
        
        # PAINEL NOVO DE JOGADORES (Substituiu as métricas antigas)
        renderizar_painel_jogadores()

        st.divider()

        # Destaque do Herói da Rodada
        if st.session_state.aluno_sorteado:
            h = st.session_state.aluno_sorteado
            p_nome = obter_primeiro_nome(h['aluno'])
            st.markdown(f"### ⭐ Herói em Ação: **{p_nome}** como *{h['personagem']}*")
            st.info(f"✨ **Item Mágico:** {h['item']} | 🪄 **Habilidade:** {h['habilidade']} | 📖 **Livro da Ficha:** {h['livro']}")

        # Exibição da Última Cena da História
        if st.session_state.historico:
            ultimo = st.session_state.historico[-1]
            st.subheader(f"🎬 {ultimo['heroi']}")
            
            c_img, c_txt = st.columns([1, 1])
            with c_img:
                if ultimo["img"]:
                    st.image(ultimo["img"], use_container_width=True)
            with c_txt:
                st.markdown("### Narrativa Atual:")
                st.write(ultimo["texto"])

        # Linha do Tempo
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
        
        # Exibe o painel de status também no controle do Mestre
        renderizar_painel_jogadores()
        
        if not is_ultima_rodada:
            col_m1, col_m2 = st.columns(2)

            with col_m1:
                st.subheader("1. Sorteio do Herói da Rodada")
                if st.button("🎲 Sortear Próximo Aluno", type="primary"):
                    if vivos:
                        st.session_state.aluno_sorteado = random.choice(vivos)
                        st.session_state.pergunta_atual = None
                        st.session_state.pop("ultimo_dado", None)
                        st.rerun()

                aluno_selecionado = st.selectbox(
                    "Aluno em ação:",
                    options=vivos,
                    index=vivos.index(st.session_state.aluno_sorteado) if st.session_state.aluno_sorteado in vivos else 0,
                    format_func=lambda j: f"{obter_primeiro_nome(j['aluno'])} ({j['personagem']})"
                ) if vivos else None

                if aluno_selecionado:
                    st.session_state.aluno_sorteado = aluno_selecionado

                    # Ação de Resgate/Poção
                    if aluno_selecionado.get("tem_porcao_resgate") and congelados:
                        st.warning(f"🧪 {obter_primeiro_nome(aluno_selecionado['aluno'])} tem uma Poção de Resgate!")
                        aluno_salvar = st.selectbox("Descongelar colega:", options=congelados, format_func=lambda x: obter_primeiro_nome(x["aluno"]))
                        if st.button("Usar Poção de Resgate"):
                            aluno_salvar["status"] = "VIVO"
                            aluno_selecionado["tem_porcao_resgate"] = False
                            st.success(f"{obter_primeiro_nome(aluno_salvar['aluno'])} voltou ao jogo!")
                            st.rerun()

            with col_m2:
                st.subheader("2. Resolução do Desafio")
                if st.session_state.aluno_sorteado:
                    # Dado
                    if st.button("🎲 Rolar D20 (Sorte)"):
                        st.session_state["ultimo_dado"] = rolar_dado()
                    
                    if "ultimo_dado" in st.session_state:
                        st.write(f"Resultado do Dado: **{st.session_state['ultimo_dado']}**")

                    # Pergunta baseada no livro do próprio aluno
                    if st.button("📖 Gerar Pergunta sobre o Livro do Aluno"):
                        with st.spinner("Gerando pergunta..."):
                            q = gerar_pergunta_livro(
                                gemini_key, 
                                st.session_state.aluno_sorteado["livro"], 
                                st.session_state.get("faixa_etaria", "Ensino Fundamental I")
                            )
                            st.session_state.pergunta_atual = q

                    if st.session_state.pergunta_atual:
                        st.warning("🔒 GABARITO DO MESTRE (Não mostrar aos alunos):")
                        st.markdown(st.session_state.pergunta_atual)

            st.divider()

            # Botões de Decisão Final da Rodada
            st.subheader("3. Decisão do Mestre & Avanço do Desafio")
            col_b1, col_b2 = st.columns(2)

            if aluno_selecionado and col_b1.button("✅ APROVAR SUCESSO (Avançar História)", type="primary", use_container_width=True):
                # 30% de chance de ganhar item especial (Poção de Resgate)
                if random.random() < 0.30:
                    aluno_selecionado["tem_porcao_resgate"] = True
                    st.toast(f"✨ {obter_primeiro_nome(aluno_selecionado['aluno'])} ganhou uma Poção de Resgate!")

                p_nome = obter_primeiro_nome(aluno_selecionado['aluno'])
                contexto = (
                    f"MUNDO BASE DA AVENTURA: '{st.session_state.mundo_mestre}'. "
                    f"RODADA ATUAL: {st.session_state.rodada_atual} de {tot_rodadas}. "
                    f"AÇÃO: O herói {aluno_selecionado['personagem']} (aluno {p_nome}) usou o item '{aluno_selecionado['item']}' "
                    f"e a habilidade '{aluno_selecionado['habilidade']}' (do livro {aluno_selecionado['livro']}) e VENCEU o obstáculo! "
                    f"INSTRUÇÃO IMPORTANTE: Narre esse sucesso com empolgação e em seguida APRESENTE O PRÓXIMO DESAFIO/OBSTÁCULO que surge para o grupo no mundo '{st.session_state.mundo_mestre}'."
                )

                with st.spinner("NARRANDO SUCESSO E GERANDO PRÓXIMO DESAFIO..."):
                    narrativa, p_img = gerar_narrativa_rpg(gemini_key, contexto)
                    img = gerar_imagem(p_img, False, hf_token)

                    st.session_state.roteiro_hq.append(f"RODADA {st.session_state.rodada_atual}: [SUCESSO] {aluno_selecionado['personagem']}. Narrativa: {narrativa}")
                    st.session_state.historico.append({"texto": narrativa, "img": img, "heroi": f"Sucesso de {aluno_selecionado['personagem']}"})
                    
                    st.session_state.rodada_atual += 1
                    st.session_state.aluno_sorteado = None
                    st.session_state.pergunta_atual = None
                    st.rerun()

            if aluno_selecionado and col_b2.button("❌ REGISTRAR FALHA (Congelar & Avançar)", use_container_width=True):
                for j in st.session_state.jogadores:
                    if j["aluno"] == aluno_selecionado["aluno"]:
                        j["status"] = "CONGELADO"

                p_nome = obter_primeiro_nome(aluno_selecionado['aluno'])
                contexto = (
                    f"MUNDO BASE DA AVENTURA: '{st.session_state.mundo_mestre}'. "
                    f"RODADA ATUAL: {st.session_state.rodada_atual} de {tot_rodadas}. "
                    f"AÇÃO: O herói {aluno_selecionado['personagem']} (aluno {p_nome}) FALHOU e foi congelado temporariamente. "
                    f"INSTRUÇÃO IMPORTANTE: Narre o congelamento sem violência e APRESENTE O NOVO DESAFIO que continua ameaçando a turma no mundo '{st.session_state.mundo_mestre}'."
                )

                with st.spinner("REGISTRANDO FALHA E GERANDO PRÓXIMO DESAFIO..."):
                    narrativa, p_img = gerar_narrativa_rpg(gemini_key, contexto)
                    img = gerar_imagem(p_img, False, hf_token)

                    st.session_state.roteiro_hq.append(f"RODADA {st.session_state.rodada_atual}: [FALHA] {aluno_selecionado['personagem']}. Narrativa: {narrativa}")
                    st.session_state.historico.append({"texto": narrativa, "img": img, "heroi": f"Falha de {aluno_selecionado['personagem']}"})
                    
                    st.session_state.rodada_atual += 1
                    st.session_state.aluno_sorteado = None
                    st.session_state.pergunta_atual = None
                    st.rerun()

        else:
            st.header("🏆 Finalizar Jogo")
            if st.button("🎬 Gerar Gran Finale!", type="primary"):
                contexto = f"Mundo da história: {st.session_state.mundo_mestre}. Vitória final de todos os heróis reunidos!"
                with st.spinner("Criando cena final..."):
                    narrativa, p_img = gerar_narrativa_rpg(gemini_key, contexto, is_final=True)
                    img_final = gerar_imagem(p_img, is_final=True, token=hf_token)

                    st.session_state.historico.append({"texto": narrativa, "img": img_final, "heroi": "TODOS OS HERÓIS REUNIDOS"})
                    st.session_state.roteiro_hq.append(f"CENA FINAL: Vitória Épica. {narrativa}")
                    st.rerun()

        # Baixar Roteiro
        st.divider()
        texto_roteiro = "\n\n".join(st.session_state.roteiro_hq)
        st.download_button(
            label="📥 Baixar Roteiro Completo da Aula (TXT)",
            data=texto_roteiro,
            file_name="roteiro_hq_aula.txt",
            mime="text/plain"
        )
