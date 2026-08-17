import base64
import io
import math
import os
import random
import time

from openai import OpenAI
import pandas as pd
from PIL import Image
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# 1. CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="No Multiverso da Leitura", page_icon="🎲", layout="wide"
)

st.title("🎲 No Multiverso da Leitura")

# ---------------------------------------------------------------------------
# 2. ESTADO DA SESSÃO (SESSION STATE)
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
# 3. FUNÇÕES AUXILIARES, IA, SOM & ANIMAÇÃO DE DADOS (D20 SVG)
# ---------------------------------------------------------------------------
def rolar_dado():
    return random.randint(1, 20)


def animar_rolagem_dado():
    """Gera o resultado e exibe um D20 geométrico gigante rodando por cima da tela inteira com efeito sonoro."""
    val_final = rolar_dado()
    som_dado_url = "https://actions.google.com/sounds/v1/games/dice_roll.ogg"

    overlay_html = f'<audio autoplay style="display:none;"><source src="{som_dado_url}" type="audio/ogg"></audio><div id="dice-overlay" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: rgba(0, 0, 0, 0.75); z-index: 99999; display: flex; flex-direction: column; justify-content: center; align-items: center; pointer-events: none; backdrop-filter: blur(5px);"><div style="position: relative; width: 280px; height: 280px; display: flex; justify-content: center; align-items: center; animation: spinAndScale 1.8s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; filter: drop-shadow(0px 0px 35px rgba(255, 215, 0, 0.95));"><svg viewBox="0 0 100 100" style="width: 100%; height: 100%;"><polygon points="50,5 90,25 50,38" fill="#7e22ce" stroke="#ffd700" stroke-width="1.8"/><polygon points="50,5 10,25 50,38" fill="#6b21a8" stroke="#ffd700" stroke-width="1.8"/><polygon points="50,5 90,25 10,25" fill="#9333ea" stroke="#ffd700" stroke-width="1.8" opacity="0.7"/><polygon points="10,25 50,38 10,75" fill="#581c87" stroke="#ffd700" stroke-width="1.8"/><polygon points="90,25 90,75 50,38" fill="#a855f7" stroke="#ffd700" stroke-width="1.8"/><polygon points="10,75 50,38 50,95" fill="#3b0764" stroke="#ffd700" stroke-width="1.8"/><polygon points="90,75 50,95 90,75" fill="#7e22ce" stroke="#ffd700" stroke-width="1.8"/><polygon points="10,75 50,95 90,75" fill="#4c1d95" stroke="#ffd700" stroke-width="1.8"/></svg><div style="position: absolute; font-size: 80px; font-weight: 900; color: #FFFFFF; font-family: \'Arial Black\', sans-serif; text-shadow: 2px 2px 8px #000, -2px -2px 8px #000, 0px 0px 18px #ffd700; margin-top: 8px;">{val_final}</div></div></div><style>@keyframes spinAndScale {{ 0% {{ transform: scale(0.1) rotate(0deg) translateY(-300px); opacity: 0.1; }} 50% {{ transform: scale(1.5) rotate(720deg) translateY(0px); opacity: 0.95; }} 85% {{ transform: scale(1.2) rotate(1080deg); opacity: 0.95; }} 100% {{ transform: scale(1.0) rotate(1080deg); opacity: 0; }} }}</style>'

    placeholder = st.empty()
    placeholder.markdown(overlay_html, unsafe_allow_html=True)
    time.sleep(1.8)
    placeholder.empty()

    return val_final


def obter_primeiro_nome(nome_completo):
    return str(nome_completo).strip().split()[0]


def obter_cliente_together(api_key):
    return OpenAI(api_key=api_key, base_url="https://api.together.xyz/v1")


def sortear_proximo_aluno_automatico(aluno_atual=None):
    vivos = [
        j
        for j in st.session_state.jogadores
        if j["status"] == "VIVO" and j.get("presente", True)
    ]
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

    jogadores_presentes = [
        j for j in st.session_state.jogadores if j.get("presente", True)
    ]
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
            exibir_card_compacto(
                cols_l2[idx - cols_por_linha], jogadores_presentes[idx]
            )

    with st.expander("🏆 Placar Geral de Moedas", expanded=False):
        df_placar = pd.DataFrame([
            {
                "Aluno": j["aluno"],
                "Personagem": j["personagem"],
                "Status": (
                    "🛡️ Vivo" if j["status"] == "VIVO" else "🧊 Congelado"
                ),
                "Poção 🧪": "Sim" if j.get("tem_porcao_resgate") else "Não",
                "Moedas 🪙": j.get("moedas", 0),
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
        st.session_state.aluno_sorteado
        and st.session_state.aluno_sorteado["aluno"] == j["aluno"]
    )

    item_str = " 🧪" if j.get("tem_porcao_resgate") else ""
    moedas_str = f" 🪙{j.get('moedas', 0)}"

    with coluna:
        if is_sorteado:
            st.markdown(
                f"⭐ **{status_icon} {primeiro_nome}**{item_str}{moedas_str}"
            )
        else:
            st.markdown(
                f"**{status_icon} {primeiro_nome}**{item_str}{moedas_str}"
            )
        st.caption(f"🎭 {j['personagem']}")


def gerar_narrativa_rpg(
    together_key,
    prompt_contexto,
    is_intro=False,
    is_final=False,
    herois_vivos=None,
    heroi_ativo=None,
):
    client = obter_cliente_together(together_key)
    modelo = st.session_state.get(
        "modelo_together", "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    )
    faixa = st.session_state.get("faixa_etaria", "Ensino Fundamental I")
    estilo = st.session_state.get(
        "estilo_arte", "vibrant children storybook style"
    )

    lista_observadores = ""
    if herois_vivos:
        nomes = [h["personagem"] for h in herois_vivos if h != heroi_ativo]
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
                {"role": "user", "content": prompt_contexto},
            ],
            max_tokens=1000,
            temperature=0.7,
        )
        texto = response.choices[0].message.content
    except Exception as e:
        return (
            f"Erro na narrativa (Together AI): {e}",
            f"epic scene, {estilo}",
        )

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
        modelo_flux = st.session_state.get(
            "modelo_flux", "black-forest-labs/FLUX.1-schnell"
        )
        url = "https://api.together.xyz/v1/images/generations"
        payload = {
            "model": modelo_flux,
            "prompt": prompt_text,
            "width": 1024,
            "height": 768,
            "steps": 4,
            "n": 1,
            "response_format": "b64_json",
        }
        headers = {
            "Authorization": f"Bearer {together_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            url, json=payload, headers=headers, timeout=60
        )
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


def gerar_pergunta_livro(together_key, livro, faixa_etaria):
    if not together_key:
        return "⚠️ Chave de API TOGETHER_API_KEY necessária para gerar perguntas."
    try:
        client = obter_cliente_together(together_key)
        modelo = st.session_state.get(
            "modelo_together", "meta-llama/Llama-3.3-70B-Instruct-Turbo"
        )
        prompt = (
            f"Gere uma pergunta desafiadora e pedagógica sobre o livro '{livro}', "
            f"adequada para alunos da faixa etária: {faixa_etaria}. A pergunta deve testar a "
            f"compreensão de leitura do aluno de forma divertida e adequada para um RPG."
        )
        response = client.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Erro ao gerar pergunta: {e}"


# ---------------------------------------------------------------------------
# 4. BARRA LATERAL: CONFIGURAÇÕES & PAINEL DO MESTRE
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🔑 Configurações de API")
    together_key = st.secrets.get("TOGETHER_API_KEY", "").strip()

    if not together_key:
        together_key = st.text_input("Together AI API Key", type="password")

    if together_key:
        st.success("🟢 API Conectada!")
    else:
        st.warning("⚠️ Chave TOGETHER_API_KEY pendente.")

    st.divider()

    modelo_together = st.selectbox(
        "🤖 Modelo da Narrativa:",
        [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "deepseek-ai/DeepSeek-V3",
            "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        ],
    )
    st.session_state["modelo_together"] = modelo_together

    modelo_flux = st.selectbox(
        "🎨 Modelo de Imagem FLUX:",
        ["black-forest-labs/FLUX.1-schnell", "black-forest-labs/FLUX.1-dev"],
    )
    st.session_state["modelo_flux"] = modelo_flux

    if not st.session_state.partida_iniciada:
        st.header("⚙️ Parâmetros do Jogo")
        st.session_state["total_rodadas"] = st.slider(
            "Número de Rodadas:", min_value=5, max_value=35, value=20
        )
        st.session_state["faixa_etaria"] = st.selectbox(
            "Faixa Etária:",
            [
                "Ensino Fundamental I (1º ao 3º ano)",
                "Ensino Fundamental I (4º e 5º ano)",
                "Ensino Fundamental II",
            ],
        )
        st.session_state["estilo_arte"] = st.selectbox(
            "🎨 Estilo Visual:",
            [
                "Children's Storybook Illustration, vibrant colors, flat design",
                "Studio Ghibli Anime Style, magical atmosphere",
                "16-bit Retro Video Game Pixel Art",
                "Soft Watercolor Painting, fantasy children book",
                "3D Pixar CGI Animation style, cute and highly detailed",
            ],
        )
    else:
        st.divider()
        st.header("🕹️ Painel do Mestre")

        vivos = [
            j
            for j in st.session_state.jogadores
            if j["status"] == "VIVO" and j.get("presente", True)
        ]
        congelados = [
            j
            for j in st.session_state.jogadores
            if j["status"] == "CONGELADO" and j.get("presente", True)
        ]
        tot_rodadas = st.session_state.get("total_rodadas", 20)

        is_chefe_rodada = st.session_state.rodada_atual == tot_rodadas - 1
        is_ultima_rodada = st.session_state.rodada_atual >= tot_rodadas

        with st.expander("📋 Chamada / Presença", expanded=False):
            for idx, j in enumerate(st.session_state.jogadores):
                is_p = st.checkbox(
                    f"{j['aluno']} ({j['personagem']})",
                    value=j.get("presente", True),
                    key=f"pres_{idx}_{j['aluno']}",
                )
                if is_p != j.get("presente", True):
                    j["presente"] = is_p
                    if not is_p and st.session_state.aluno_sorteado == j:
                        sortear_proximo_aluno_automatico()
                    st.rerun()

        if not is_chefe_rodada and not is_ultima_rodada:
            st.subheader("1. Seleção do Herói")
            if not st.session_state.aluno_sorteado and vivos:
                sortear_proximo_aluno_automatico()

            aluno_selecionado = (
                st.selectbox(
                    "Herói do Turno:",
                    options=vivos,
                    index=(
                        vivos.index(st.session_state.aluno_sorteado)
                        if st.session_state.aluno_sorteado in vivos
                        else 0
                    ),
                    format_func=lambda j: f"{obter_primeiro_nome(j['aluno'])} ({j['personagem']})",
                )
                if vivos
                else None
            )

            if aluno_selecionado:
                st.session_state.aluno_sorteado = aluno_selecionado

                if aluno_selecionado.get("tem_porcao_resgate") and congelados:
                    st.warning("🧪 Poção Disponível!")
                    aluno_salvar = st.selectbox(
                        "Resgatar colega:",
                        options=congelados,
                        format_func=lambda x: f"{obter_primeiro_nome(x['aluno'])} ({x['personagem']})",
                    )
                    if st.button(
                        "🧪 Usar Poção (Gasta Turno)",
                        type="primary",
                        use_container_width=True,
                    ):
                        aluno_salvar["status"] = "VIVO"
                        aluno_selecionado["tem_porcao_resgate"] = False

                        p_nome_resgatador = obter_primeiro_nome(
                            aluno_selecionado["aluno"]
                        )
                        p_nome_salvo = obter_primeiro_nome(aluno_salvar["aluno"])

                        narrativa_resgate = (
                            f"O herói {aluno_selecionado['personagem']} ({p_nome_resgatador}) usou sua Poção de Resgate! "
                            f"O gelo sobre {aluno_salvar['personagem']} ({p_nome_salvo}) derreteu e ele voltou ao grupo!"
                        )
                        p_img = f"{aluno_selecionado['personagem']} rescue potion on {aluno_salvar['personagem']}, {st.session_state.get('estilo_arte', '')}"

                        with st.spinner("Registrando resgate..."):
                            img = gerar_imagem(p_img, together_key)
                            st.session_state.historico.append({
                                "texto": narrativa_resgate,
                                "img": img,
                                "heroi": f"Resgate de {aluno_salvar['personagem']}",
                            })
                            st.session_state.roteiro_hq.append(
                                f"RODADA {st.session_state.rodada_atual}: [RESGATE] {aluno_selecionado['personagem']} salvou {aluno_salvar['personagem']}."
                            )
                            st.session_state.rodada_atual += 1
                            st.session_state.pergunta_atual = None
                            st.session_state.pop("ultimo_dado", None)
                            sortear_proximo_aluno_automatico(aluno_selecionado)
                            st.rerun()

            if st.button("🔄 Resortear Herói", use_container_width=True):
                sortear_proximo_aluno_automatico(
                    st.session_state.aluno_sorteado
                )
                st.session_state.pergunta_atual = None
                st.session_state.pop("ultimo_dado", None)
                st.rerun()

            st.subheader("2. Decisão do Mestre")
            if aluno_selecionado:
                if st.button(
                    "✅ SUCESSO (+3 Moedas)",
                    type="primary",
                    use_container_width=True,
                ):
                    aluno_selecionado["moedas"] = (
                        aluno_selecionado.get("moedas", 0) + 3
                    )
                    if random.random() < 0.30:
                        aluno_selecionado["tem_porcao_resgate"] = True
                        st.toast(
                            f"✨ {obter_primeiro_nome(aluno_selecionado['aluno'])} ganhou uma Poção!"
                        )

                    p_nome = obter_primeiro_nome(aluno_selecionado["aluno"])
                    cena_anterior = (
                        st.session_state.historico[-1]["texto"]
                        if st.session_state.historico
                        else "Início da jornada."
                    )

                    contexto = (
                        f"MUNDO BASE: '{st.session_state.mundo_mestre}'. RODADA: {st.session_state.rodada_atual}/{tot_rodadas}. "
                        f"CENA ANTERIOR: {cena_anterior}\n"
                        f"AÇÃO: {aluno_selecionado['personagem']} ({p_nome}) usou '{aluno_selecionado['item']}' e VENCEU! "
                        f"INSTRUÇÃO: Narre o sucesso e faça toda a comitiva avançar junta para o próximo desafio."
                    )

                    with st.spinner("Gerando sucesso..."):
                        narrativa, p_img = gerar_narrativa_rpg(
                            together_key,
                            contexto,
                            herois_vivos=vivos,
                            heroi_ativo=aluno_selecionado,
                        )
                        img = gerar_imagem(p_img, together_key)

                        st.session_state.roteiro_hq.append(
                            f"RODADA {st.session_state.rodada_atual}: [SUCESSO] {aluno_selecionado['personagem']}."
                        )
                        st.session_state.historico.append({
                            "texto": narrativa,
                            "img": img,
                            "heroi": f"Sucesso de {aluno_selecionado['personagem']}",
                        })
                        st.session_state.rodada_atual += 1
                        st.session_state.pergunta_atual = None
                        st.session_state.pop("ultimo_dado", None)
                        sortear_proximo_aluno_automatico(aluno_selecionado)
                        st.rerun()

                if st.button("❌ REGISTRAR FALHA", use_container_width=True):
                    for j in st.session_state.jogadores:
                        if j["aluno"] == aluno_selecionado["aluno"]:
                            j["status"] = "CONGELADO"

                    p_nome = obter_primeiro_nome(aluno_selecionado["aluno"])
                    cena_anterior = (
                        st.session_state.historico[-1]["texto"]
                        if st.session_state.historico
                        else "Início da jornada."
                    )

                    contexto = (
                        f"MUNDO BASE: '{st.session_state.mundo_mestre}'. RODADA: {st.session_state.rodada_atual}/{tot_rodadas}. "
                        f"AÇÃO: {aluno_selecionado['personagem']} ({p_nome}) FALHOU e foi congelado temporariamente. "
                        f"INSTRUÇÃO: Narre o congelamento sem descongelar o herói."
                    )

                    vivos_restantes = [
                        v
                        for v in vivos
                        if v["aluno"] != aluno_selecionado["aluno"]
                    ]

                    with st.spinner("Gerando falha..."):
                        narrativa, p_img = gerar_narrativa_rpg(
                            together_key,
                            contexto,
                            herois_vivos=vivos_restantes,
                            heroi_ativo=aluno_selecionado,
                        )
                        img = gerar_imagem(p_img, together_key)

                        st.session_state.roteiro_hq.append(
                            f"RODADA {st.session_state.rodada_atual}: [FALHA] {aluno_selecionado['personagem']}."
                        )
                        st.session_state.historico.append({
                            "texto": narrativa,
                            "img": img,
                            "heroi": f"Falha de {aluno_selecionado['personagem']}",
                        })
                        st.session_state.rodada_atual += 1
                        st.session_state.pergunta_atual = None
                        st.session_state.pop("ultimo_dado", None)
                        sortear_proximo_aluno_automatico(aluno_selecionado)
                        st.rerun()

        elif is_chefe_rodada:
            st.subheader("🐉 Batalha do Chefe Final")
            trio_selecionado = st.multiselect(
                "Trio de Heróis:",
                options=vivos,
                default=vivos[:3] if len(vivos) >= 3 else vivos,
                format_func=lambda j: f"{obter_primeiro_nome(j['aluno'])} ({j['personagem']})",
            )

            if len(trio_selecionado) == 3:
                if st.button(
                    "🔥 DERROTAR CHEFE (+10 Moedas)",
                    type="primary",
                    use_container_width=True,
                ):
                    for hero in trio_selecionado:
                        hero["moedas"] = hero.get("moedas", 0) + 10

                    nomes_trio = ", ".join(
                        [f"{h['personagem']}" for h in trio_selecionado]
                    )
                    contexto_boss = f"MUNDO: '{st.session_state.mundo_mestre}'. O trio {nomes_trio} derrotou o Chefe Final!"

                    with st.spinner("Derrotando chefe..."):
                        narrativa, p_img = gerar_narrativa_rpg(
                            together_key, contexto_boss, herois_vivos=vivos
                        )
                        img = gerar_imagem(p_img, together_key)
                        st.session_state.historico.append({
                            "texto": narrativa,
                            "img": img,
                            "heroi": "Vitória contra o Chefe",
                        })
                        st.session_state.rodada_atual += 1
                        st.rerun()

        else:
            st.subheader("🏆 Encerrar Jogo")
            if st.button(
                "🎬 Gerar Gran Finale!", type="primary", use_container_width=True
            ):
                contexto = f"Mundo: {st.session_state.mundo_mestre}. A grande vitória de todos os heróis!"
                with st.spinner("Finalizando história..."):
                    narrativa, p_img = gerar_narrativa_rpg(
                        together_key, contexto, is_final=True, herois_vivos=vivos
                    )
                    img_final = gerar_imagem(p_img, together_key)
                    st.session_state.historico.append({
                        "texto": narrativa,
                        "img": img_final,
                        "heroi": "VITÓRIA ÉPICA FINAL",
                    })
                    st.rerun()

        st.divider()
        if st.session_state.roteiro_hq:
            st.download_button(
                label="📥 Baixar Roteiro TXT",
                data="\n\n".join(st.session_state.roteiro_hq),
                file_name="roteiro_aula_rpg.txt",
                mime="text/plain",
                use_container_width=True,
            )

        if st.button("🗑️ Reiniciar Jogo", use_container_width=True):
            for key in [
                "partida_iniciada",
                "jogadores",
                "mundo_mestre",
                "rodada_atual",
                "historico",
                "roteiro_hq",
                "aluno_sorteado",
                "pergunta_atual",
                "ultimo_dado",
            ]:
                st.session_state.pop(key, None)
            st.rerun()

# ---------------------------------------------------------------------------
# 5. TELA DE CARREGAMENTO (IMPORTAÇÃO DO CSV)
# ---------------------------------------------------------------------------
if not st.session_state.partida_iniciada:
    st.header("📂 1. Carregar Ficha da Turma (CSV)")
    st.markdown(
        "Envie um arquivo CSV com as colunas: **Nome do Aluno**, **Livro Lido**, **Nome do Personagem**, **Habilidade**, **Item Mágico**."
    )

    csv_file = st.file_uploader("Escolha o arquivo CSV", type=["csv"])

    if csv_file:
        try:
            try:
                df = pd.read_csv(csv_file)
                if len(df.columns) <= 1:
                    csv_file.seek(0)
                    df = pd.read_csv(csv_file, sep=";")
            except Exception:
                csv_file.seek(0)
                df = pd.read_csv(csv_file, sep=";")

            df.columns = df.columns.astype(str).str.strip()

            col_map = {col.lower(): col for col in df.columns}
            c_aluno = (
                col_map.get("nome do aluno")
                or col_map.get("aluno")
                or col_map.get("nome")
            )
            c_livro = col_map.get("livro lido") or col_map.get("livro")
            c_personagem = col_map.get("nome do personagem") or col_map.get(
                "personagem"
            )
            c_habilidade = col_map.get("habilidade")
            c_item = (
                col_map.get("item mágico")
                or col_map.get("item magico")
                or col_map.get("item")
            )

            if not c_aluno and len(df.columns) > 0:
                c_aluno = df.columns[0]
            if not c_livro and len(df.columns) > 1:
                c_livro = df.columns[1]
            if not c_personagem and len(df.columns) > 2:
                c_personagem = df.columns[2]
            if not c_habilidade and len(df.columns) > 3:
                c_habilidade = df.columns[3]
            if not c_item and len(df.columns) > 4:
                c_item = df.columns[4]

            if not all([c_aluno, c_livro, c_personagem, c_habilidade, c_item]):
                st.error("⚠️ Colunas necessárias não encontradas no arquivo CSV!")
            else:
                st.success(f"🟢 {len(df)} alunos carregados com sucesso!")
                st.dataframe(df, use_container_width=True)

                if st.button(
                    "🚀 Iniciar Aventura e Fixar Mundo!", type="primary"
                ):
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
                            "presente": True,
                        })

                    st.session_state.jogadores = jogadores
                    livros_disponiveis = list(
                        set([j["livro"] for j in jogadores])
                    )
                    st.session_state.mundo_mestre = random.choice(
                        livros_disponiveis
                    )

                    sortear_proximo_aluno_automatico()
                    vivos_agora = [
                        j
                        for j in st.session_state.jogadores
                        if j["status"] == "VIVO" and j.get("presente", True)
                    ]

                    with st.spinner(
                        f"Criando o mundo de '{st.session_state.mundo_mestre}'..."
                    ):
                        narrativa_intro, p_img = gerar_narrativa_rpg(
                            together_key,
                            st.session_state.mundo_mestre,
                            is_intro=True,
                            herois_vivos=vivos_agora,
                        )
                        img_intro = gerar_imagem(p_img, together_key)

                        st.session_state.historico.append({
                            "texto": narrativa_intro,
                            "img": img_intro,
                            "heroi": f"Abertura em {st.session_state.mundo_mestre}",
                        })
                        st.session_state.roteiro_hq.append(
                            f"INTRODUÇÃO: {narrativa_intro}"
                        )

                    st.session_state.partida_iniciada = True
                    st.rerun()

        except Exception as e:
            st.error(f"Erro ao processar o arquivo CSV: {e}")

# ---------------------------------------------------------------------------
# 6. TELA DA PROJEÇÃO (TELA PRINCIPAL DA TURMA)
# ---------------------------------------------------------------------------
else:
    # 1. Painel dos Heróis no topo
    renderizar_painel_jogadores()

    tot_rodadas = st.session_state.get("total_rodadas", 20)
    is_chefe_rodada = (st.session_state.rodada_atual == tot_rodadas - 1)
    is_ultima_rodada = (st.session_state.rodada_atual >= tot_rodadas)

    # 2. Exibição do Texto da Aventura e Imagem Gerada (MUITO IMPORTANTE: FICA NO TOPO DA TELA DA CENA)
    if st.session_state.historico:
        ultima_cena = st.session_state.historico[-1]
        st.markdown(f"### 🗺️ Cena Atual: **Rodada {st.session_state.rodada_atual}/{tot_rodadas}**")
        
        col_img, col_txt = st.columns([1, 1])
        with col_img:
            if ultima_cena.get("img"):
                st.image(ultima_cena["img"], caption=ultima_cena.get("heroi", ""), use_container_width=True)
        with col_txt:
            st.markdown("#### 📜 Narrativa do Mestre")
            st.write(ultima_cena.get("texto", ""))

    st.divider()

    # 3. Informações do Herói em Ação e Interações
    if st.session_state.aluno_sorteado and st.session_state.aluno_sorteado.get("presente", True) and not is_chefe_rodada and not is_ultima_rodada:
        h = st.session_state.aluno_sorteado
        p_nome = obter_primeiro_nome(h['aluno'])
        
        st.markdown(f"### ⭐ Herói em Ação: **{p_nome}** como *{h['personagem']}* (🪙 {h.get('moedas', 0)} Moedas)")
        st.info(f"✨ **Item Mágico:** {h['item']} | 🪄 **Habilidade:** {h['habilidade']} | 📖 **Livro Lido:** {h['livro']}")

        # 4. BOTÕES DE AÇÃO (FICAM ABAIXO DO TEXTO DA AVENTURA E DAS INFORMAÇÕES)
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🎲 Rolar D20", use_container_width=True, type="primary"):
                resultado = animar_rolagem_dado() 
                st.session_state["ultimo_dado"] = resultado
                st.rerun()

        with col2:
            if st.button("❓ Gerar Pergunta do Livro", use_container_width=True):
                with st.spinner("O Mestre está consultando os pergaminhos..."):
                    pergunta = gerar_pergunta_livro(together_key, h['livro'], st.session_state.get("faixa_etaria"))
                    st.session_state.pergunta_atual = pergunta
                st.rerun()

        # 5. RESULTADOS DA ROLAGEM / PERGUNTA (FICAM LOGO ABAIXO DOS BOTÕES)
        if "ultimo_dado" in st.session_state and st.session_state["ultimo_dado"] is not None:
            st.success(f"🎲 O dado parou no número: **{st.session_state['ultimo_dado']}**")

        if st.session_state.pergunta_atual:
            st.markdown("### 📜 Desafio de Sabedoria")
            st.info(st.session_state.pergunta_atual)

    # Apresentação do Chefe Final na Penúltima Rodada
    elif is_chefe_rodada:
        st.error("🐉 **GRANDE BATALHA: O CHEFE FINAL DO REINO APARECEU!**")
        vivos = [j for j in st.session_state.jogadores if j["status"] == "VIVO" and j.get("presente", True)]
        itens_vivos = list(set([j['item'] for j in vivos]))
        random.seed(st.session_state.rodada_atual)
        pista_combinada = random.sample(itens_vivos, min(3, len(itens_vivos)))
        st.info(f"📜 **Pista Anciã do Mestre:** *'Para derrotar o Chefe Final, o trio deve combinar: **{', '.join(pista_combinada)}**!'*")

    elif is_ultima_rodada:
        st.balloons()
        st.success("🎉 **A JORNADA FOI CONCLUÍDA COM SUCESSO! PARABÉNS AOS HERÓIS!**")
