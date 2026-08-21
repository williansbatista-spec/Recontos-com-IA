import base64
import io
import json
import math
import os
import random
import re
import time

from openai import OpenAI
import pandas as pd
from PIL import Image
import requests
import streamlit as st


# ==========================================
# 1. FUNÇÕES AUXILIARES, DIFICULDADE E CONVOCAÇÃO
# ==========================================
def obter_primeiro_nome(nome_completo):
    return str(nome_completo).strip().split()[0] if nome_completo else "Herói"


def calcular_dificuldade_rodada(rodada_atual, total_rodadas):
    """Calcula a DC (Classe de Dificuldade) progressiva de 8 a 18 com base na rodada."""
    if total_rodadas <= 1:
        return 10
    progresso = (rodada_atual - 1) / max(1, total_rodadas - 1)
    dc = int(8 + (progresso * 10))
    return min(dc, 18)

# ==========================================
# FUNÇÕES AUXILIARES DE IMAGEM E NARRATIVA
# ==========================================

def construir_prompt_dinamico_imagem(descricao_cena):
    """Constrói o prompt visual limpando quebras de linha e limitando o tamanho do texto."""
    heroi_atual = st.session_state.get("aluno_sorteado") or st.session_state.get("heroi_ativo", {})
    heroi_anterior = st.session_state.get("heroi_anterior", None)
    sucesso_anterior = st.session_state.get("sucesso_rodada_anterior", None)

    nome_atual = heroi_atual.get("personagem", "the brave hero") if isinstance(heroi_atual, dict) else "the brave hero"

    estilo = (
        "Children's storybook illustration style, 3D Pixar render, vibrant colors, "
        "epic fantasy lighting, dramatic perspective."
    )

    primeiro_plano = f"In the dramatic foreground, {nome_atual} steps up heroically with a determined expression."

    segundo_plano = ""
    if heroi_anterior and isinstance(heroi_anterior, dict):
        nome_ant = heroi_anterior.get("personagem", "the previous hero")
        if sucesso_anterior is False:
            segundo_plano = f"In the background, {nome_ant} is trapped inside a glowing blue magical ice crystal."
        elif sucesso_anterior is True:
            segundo_plano = f"In the background, {nome_ant} is cheering and giving a thumbs up."

    # 🟢 LIMPEZA: Remove quebras de linha e limita a descrição a 150 caracteres
    cena_limpa = str(descricao_cena).replace("\n", " ").replace("\r", " ").strip()
    contexto_ambiente = f"Environment: {cena_limpa[:150]}"

    return f"{estilo} {primeiro_plano} {segundo_plano} {contexto_ambiente}"


def gerar_prologo_quadro_duplo(together_key, mundo_mestre, herois_vivos, heroi_ativo):
    """Gera o panorama épico do mundo e os dois quadros visuais para a HQ."""
    nome_heroi = heroi_ativo.get("personagem", "o Jovem Herói") if isinstance(heroi_ativo, dict) else "o Jovem Herói"

    # 1. Prompt para a Narrativa Épica de Abertura
    prompt_narrativa_geral = (
        f"PRÓLOGO ÉPICO DE RPG: Descreva de forma mágica, envolvente e empolgante a chegada da comitiva ao reino de '{mundo_mestre}'. "
        f"Apresente o panorama do mundo, o mistério ou desafio que acaba de surgir e convoque com entusiasmo o herói {nome_heroi} para liderar o grupo!"
    )
    
    res_narrativa = gerar_narrativa_rpg(together_key, prompt_narrativa_geral, is_intro=True, herois_vivos=herois_vivos, heroi_ativo=heroi_ativo)
    
    if isinstance(res_narrativa, tuple) and len(res_narrativa) == 2 and res_narrativa[0]:
        narrativa_geral = res_narrativa[0]
    else:
        narrativa_geral = (
            f"✨ Os portões mágicos se abrem e revelam as maravilhas do reino de **{mundo_mestre}**! "
            f"No entanto, um mistério antigo desperta e paira sobre estas terras. "
            f"O Mestre convoca a coragem do bravo **{nome_heroi}** para dar o primeiro passo nesta grande jornada!"
        )

    # 2. Prompts visuais dos 2 Quadros
    prompts_quadros = [
        f"3D Pixar render style, magical fantasy portal entrance to {mundo_mestre}, vibrant colors, epic atmosphere",
        f"3D Pixar render style, a shadow or mysterious challenge appearing in {mundo_mestre}, hero {nome_heroi} ready for adventure"
    ]
    
    legendas = [
        f"A comitiva atravessa os portões do fantástico reino de {mundo_mestre}.",
        f"O desafio se revela e {nome_heroi} assume a liderança!"
    ]

    quadros = []
    for idx, prompt_img in enumerate(prompts_quadros, start=1):
        img = gerar_imagem(prompt_img, together_key)
        quadros.append({
            "texto": legendas[idx - 1],
            "img": img,
            "heroi": f"Prólogo - Quadro {idx}"
        })

    return {
        "narrativa_geral": narrativa_geral,
        "quadros": quadros
    }

# ---------------------------------------------------------------------------
# 2. CONFIGURAÇÃO DA PÁGINA E ESTADO DA SESSÃO
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="No Multiverso da Leitura", page_icon="🎲", layout="wide"
)

st.title("🎲 No Multiverso da Leitura")

if "partida_iniciada" not in st.session_state:
    st.session_state.partida_iniciada = False
if "jogadores" not in st.session_state:
    st.session_state.jogadores = []
if "mundo_mestre" not in st.session_state:
    st.session_state.mundo_mestre = ""
if "rodada_atual" not in st.session_state:
    st.session_state.rodada_atual = 1
if "total_rodadas" not in st.session_state:
    st.session_state.total_rodadas = 20
if "historico" not in st.session_state:
    st.session_state.historico = []
if "roteiro_hq" not in st.session_state:
    st.session_state.roteiro_hq = []
if "aluno_sorteado" not in st.session_state:
    st.session_state.aluno_sorteado = None
if "pergunta_atual" not in st.session_state:
    st.session_state.pergunta_atual = None
if "desafio_atual" not in st.session_state:
    st.session_state.desafio_atual = None


# ---------------------------------------------------------------------------
# 3. FUNÇÕES DE IA, DADOS & NARRATIVA
# ---------------------------------------------------------------------------
def rolar_dado():
    return random.randint(1, 20)


def animar_rolagem_dado():
    val_final = rolar_dado()
    som_dado_url = "https://actions.google.com/sounds/v1/games/dice_roll.ogg"

    overlay_html = f'<audio autoplay style="display:none;"><source src="{som_dado_url}" type="audio/ogg"></audio><div id="dice-overlay" style="position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: rgba(0, 0, 0, 0.75); z-index: 99999; display: flex; flex-direction: column; justify-content: center; align-items: center; pointer-events: none; backdrop-filter: blur(5px);"><div style="position: relative; width: 280px; height: 280px; display: flex; justify-content: center; align-items: center; animation: spinAndScale 1.8s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; filter: drop-shadow(0px 0px 35px rgba(255, 215, 0, 0.95));"><svg viewBox="0 0 100 100" style="width: 100%; height: 100%;"><polygon points="50,5 90,25 50,38" fill="#7e22ce" stroke="#ffd700" stroke-width="1.8"/><polygon points="50,5 10,25 50,38" fill="#6b21a8" stroke="#ffd700" stroke-width="1.8"/><polygon points="50,5 90,25 10,25" fill="#9333ea" stroke="#ffd700" stroke-width="1.8" opacity="0.7"/><polygon points="10,25 50,38 10,75" fill="#581c87" stroke="#ffd700" stroke-width="1.8"/><polygon points="90,25 90,75 50,38" fill="#a855f7" stroke="#ffd700" stroke-width="1.8"/><polygon points="10,75 50,38 50,95" fill="#3b0764" stroke="#ffd700" stroke-width="1.8"/><polygon points="90,75 50,95 90,75" fill="#7e22ce" stroke="#ffd700" stroke-width="1.8"/><polygon points="10,75 50,95 90,75" fill="#4c1d95" stroke="#ffd700" stroke-width="1.8"/></svg><div style="position: absolute; font-size: 80px; font-weight: 900; color: #FFFFFF; font-family: \'Arial Black\', sans-serif; text-shadow: 2px 2px 8px #000, -2px -2px 8px #000, 0px 0px 18px #ffd700; margin-top: 8px;">{val_final}</div></div></div><style>@keyframes spinAndScale {{ 0% {{ transform: scale(0.1) rotate(0deg) translateY(-300px); opacity: 0.1; }} 50% {{ transform: scale(1.5) rotate(720deg) translateY(0px); opacity: 0.95; }} 85% {{ transform: scale(1.2) rotate(1080deg); opacity: 0.95; }} 100% {{ transform: scale(1.0) rotate(1080deg); opacity: 0; }} }}</style>'

    placeholder = st.empty()
    placeholder.markdown(overlay_html, unsafe_allow_html=True)
    time.sleep(1.8)
    placeholder.empty()

    return val_final


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

    cols_por_linha = math.ceil(total / 2) if total > 1 else 1

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


def gerar_desafio_inimigo(together_key, mundo_mestre, jogadores, rodada, total_rodadas):
    """Gera um inimigo e 3 a 4 ações táticas com validação estrita de resposta única."""
    if not together_key:
        return {
            "inimigo": "Golem de Cristal Obscuro",
            "descricao": "Uma criatura pesada imune a lâminas, mas com juntas de cristal frágeis expostas nas costas.",
            "acoes": [
                {"texto": "⚔️ Ataque Frontal Direto", "correta": False},
                {"texto": "🔍 Investigar Ponto Cego nas Costas", "correta": True},
                {"texto": "🎨 Distração Sonora", "correta": False}
            ]
        }

    client = obter_cliente_together(together_key)
    modelo = st.session_state.get("modelo_together", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
    faixa = st.session_state.get("faixa_etaria", "Ensino Fundamental I")
    
    # --- DEFINIÇÃO SEGURA DAS VARIÁVEIS ---
    personagens_escolhidos = [j.get("personagem", "Herói") for j in jogadores]
    livros_lidos = list(set([j.get("livro", "Livro Desconhecido") for j in jogadores]))

    prompt_sistema = f"""
    Você é um Mestre de RPG pedagógico infantil ({faixa}).
    Crie um inimigo ou obstáculo inspirado nos livros da turma ({', '.join(livros_lidos)}).
    
    REGRAS RÍGIDAS DE GERAÇÃO:
    1. Jamais use nenhum destes personagens dos alunos como vilão: {', '.join(personagens_escolhidos)}.
    2. A descrição do inimigo DEVE conter uma PISTA IMPLÍCITA sobre seu ponto fraco/vulnerabilidade.
    3. Gere de 3 a 4 ações táticas para o aluno escolher.
    4. PROIBIDO FUGIR: Nunca crie opções de ignorar, desviar, fugir ou procurar outro caminho. TODAS as opções devem ser tentativas ativas de enfrentar, atacar ou investigar a ameaça diretamente.
    
    FORMATO JSON ESTRITO (Responda APENAS o JSON):
    {{
      "inimigo": "Nome do Inimigo",
      "descricao": "Descrição narrativa com a pista implícita do ponto fraco.",
      "acoes": [
        "Ação 1 (Incorreta - bate na resistência, mas tenta enfrentar)",
        "Ação 2 (A única Correta - explora a fraqueza)",
        "Ação 3 (Incorreta - não funciona, mas tenta enfrentar)"
      ],
      "indice_correto": 1
    }}
    O campo 'indice_correto' DEVE SER um número inteiro (0 para a 1ª ação, 1 para a 2ª, etc) indicando a ÚNICA ação certa.
    """

    prompt_user = f"Gere o desafio para a rodada {rodada}/{total_rodadas} no universo do livro '{mundo_mestre}'."

    try:
        response = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_user},
            ],
            max_tokens=600,
            temperature=0.6,
        )
        conteudo = response.choices[0].message.content.strip()
        
        match = re.search(r"\{.*\}", conteudo, re.DOTALL)
        if match:
            dados_brutos = json.loads(match.group(0))
            
            # --- BLINDAGEM DO PYTHON (FORÇANDO APENAS 1 AÇÃO CORRETA) ---
            acoes_formatadas = []
            lista_textos = dados_brutos.get("acoes", [])
            idx_certo = dados_brutos.get("indice_correto", 0)
            
            for i, texto_acao in enumerate(lista_textos):
                acoes_formatadas.append({
                    "texto": texto_acao,
                    "correta": (i == idx_certo) # Só será Verdadeiro se o índice for exatamente o escolhido
                })
            
            return {
                "inimigo": dados_brutos.get("inimigo", "Ameaça Misteriosa"),
                "descricao": dados_brutos.get("descricao", "Um desafio surge no caminho."),
                "acoes": acoes_formatadas
            }
            
    except Exception as e:
        st.warning(f"Erro ao gerar desafio com validação única: {e}")

    # --- RETORNO PADRÃO DE SEGURANÇA (Garante que nunca retorne None) ---
    return {
        "inimigo": "Monstro Desconhecido",
        "descricao": "Um obstáculo inesperado bloqueia a passagem dos heróis.",
        "acoes": [
            {"texto": "Atacar com coragem", "correta": True},
            {"texto": "Recuar cautelosamente", "correta": False},
            {"texto": "Observar o ambiente", "correta": False}
        ]
    }

    prompt_user = f"Gere o desafio para a rodada {rodada}/{total_rodadas} no universo do livro '{mundo_mestre}'."

    try:
        response = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_user},
            ],
            max_tokens=600,
            temperature=0.6, # Temperatura levemente reduzida para focar na lógica
        )
        conteudo = response.choices[0].message.content.strip()
        
        match = re.search(r"\{.*\}", conteudo, re.DOTALL)
        if match:
            dados_brutos = json.loads(match.group(0))
            
            # --- BLINDAGEM DO PYTHON (FORÇANDO APENAS 1 AÇÃO CORRETA) ---
            acoes_formatadas = []
            lista_textos = dados_brutos.get("acoes", [])
            idx_certo = dados_brutos.get("indice_correto", 0)
            
            for i, texto_acao in enumerate(lista_textos):
                acoes_formatadas.append({
                    "texto": texto_acao,
                    "correta": (i == idx_certo) # Só será Verdadeiro se o índice for exatamente o escolhido
                })
            
            return {
                "inimigo": dados_brutos.get("inimigo", "Ameaça"),
                "descricao": dados_brutos.get("descricao", ""),
                "acoes": acoes_formatadas
            }
            
    except Exception as e:
        st.warning(f"Erro ao gerar desafio com validação única: {e}")

    # Retorno de segurança
    return {
        "inimigo": "Guardião de Pedra Vulcânica",
        "descricao": "Sua carcaça de pedra é imune a força física, mas suas articulações do joelho estão cobertas de limo escorregadio.",
        "acoes": [
            {"texto": "⚔️ Golpear a carcaça no peito", "correta": False},
            {"texto": "🔍 Focar o ataque nas articulações escorregadias do joelho", "correta": True},
            {"texto": "🎨 Tentar assustar a criatura", "correta": False}
        ]
    }

    prompt_user = f"Gere o desafio para a rodada {rodada}/{total_rodadas} no universo do livro '{mundo_mestre}'."

    try:
        response = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_user},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        
        # Proteção contra resposta vazia da API
        conteudo = response.choices[0].message.content if response and response.choices else None
        
        if conteudo:
            match = re.search(r"\{.*\}", conteudo.strip(), re.DOTALL)
            if match:
                dados = json.loads(match.group(0))
                
                # Validação de estrutura: garante que o JSON possui todas as chaves necessárias
                if isinstance(dados, dict) and "inimigo" in dados and "acoes" in dados:
                    return dados

    except Exception as e:
        st.warning(f"Erro ao gerar desafio com validação única: {e}")

    # --- RETORNO PADRÃO (Garante que a função JAMAIS retorne None) ---
    return {
        "inimigo": "Guardião de Pedra Vulcânica",
        "descricao": "Sua carcaça de pedra é imune a força física, mas suas articulações do joelho estão cobertas de limo escorregadio.",
        "acoes": [
            {"texto": "⚔️ Golpear a carcaça no peito", "correta": False},
            {"texto": "🔍 Focar o ataque nas articulações escorregadias do joelho", "correta": True},
            {"texto": "🎨 Tentar assustar a criatura", "correta": False}
        ]
    }


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
    estilo = st.session_state.get(
        "estilo_arte", "3D Pixar CGI Animation style, highly detailed"
    )
    
    # Resgata o nome da turma digitado
    turma = st.session_state.get("turma_atual", "2º B")

    # 🕵️‍♂️ LÓGICA DE EXTRAÇÃO DO ANO ESCOLAR
    # Procura o primeiro número (dígito) digitado no campo da turma
    match_ano = re.search(r'\d+', turma)
    if match_ano:
        numero_ano = match_ano.group()
        nivel_pedagogico = f"crianças do {numero_ano}º Ano do Ensino Fundamental"
    else:
        # Se você digitar apenas letras (ex: "Turma da Borboleta"), ele usa um padrão
        nivel_pedagogico = "crianças do Ensino Fundamental I"

    lista_observadores = ""
    if herois_vivos:
        nomes = [h["personagem"] for h in herois_vivos if h != heroi_ativo]
        if nomes:
            lista_observadores = f"In the background, observing or reacting, are other diverse young heroes: {', '.join(nomes)}."

    # 🧠 INSTRUÇÃO DO MESTRE ATUALIZADA
    instrucao_mestre = f"""
    Você é o Mestre de um RPG pedagógico.
    O SEU PÚBLICO-ALVO SÃO: {nivel_pedagogico}. 
    MUITO IMPORTANTE: Adapte rigorosamente o seu vocabulário, o tamanho das frases e a complexidade narrativa para a capacidade de leitura e compreensão de {nivel_pedagogico}.
    
    REGRAS RÍGIDAS DE NARRATIVA:
    1. Jamais use termos de morte ou violência real. Alunos derrotados são apenas 'congelados', 'capturados' ou 'expulsos da área'.
    2. NUNCA descongele ou salve um jogador congelado por conta própria na narrativa.
    3. Quando o herói vence o desafio, TODA A COMITIVA de heróis avança junto para o próximo estágio.
    4. Se o contexto indicar 'Estratégia Correta', narre como o herói superou com genialidade a fraqueza da ameaça. Se indicar 'Estratégia Incorreta', mostre como o inimigo resistiu e repeliu o ataque.
    
    FORMATO DE RESPOSTA (ESTRITO):
    Responda ESTRITAMENTE em duas partes separadas por '---':
    Parte 1: A narrativa da cena em português (até 2 parágrafos adequados para a idade).
    Parte 2: O prompt em INGLÊS muito detalhado para gerar a imagem. 
    OBRIGATÓRIO na Parte 2:
    - O estilo visual DEVE SER EXACTAMENTE este: "{estilo}".
    - {f"O foco central da imagem deve ser o herói em ação ({heroi_ativo['personagem']})." if heroi_ativo else "A imagem deve mostrar o grupo de heróis."}
    - {lista_observadores}
    - Mantenha os traços e roupas dos personagens consistentes.
    """
    
    # ... (O restante da função do is_intro e is_final continua igual, usando a variável 'turma' que já existe lá)

def gerar_imagem(descricao_cena, together_key):
    if not together_key or not descricao_cena:
        return None
    # Gera o prompt dinâmico combinando o herói atual e o anterior.
    prompt_final = construir_prompt_dinamico_imagem(descricao_cena)

    # 2. Pega o modelo escolhido pelo usuário no menu lateral (padrão: Qwen-Image)
    modelo_selecionado = st.session_state.get(
        "modelo_imagem_together", "Qwen/Qwen-Image"
    )

    try:
        url = "https://api.together.xyz/v1/images/generations"
        payload = {
            "model": modelo_selecionado,
            "prompt": prompt_final,
            "width": 1024,
            "height": 768,
            "steps": 30,  # Qualidade alta mantida
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
        st.error(f"Erro ao gerar imagem com {modelo_selecionado}: {e}")
        return None


def gerar_pergunta_livro_com_gabarito(together_key, livro, faixa_etaria):
    """Gera pergunta simples com 3 opções e indica qual é o índice correto (0 a 2)."""
    if not together_key:
        # Retorno de segurança caso a API falhe ou não tenha chave
        return {
            "pergunta": "Onde se passa a maior parte desta história?",
            "opcoes": ["Na floresta", "No espaço sideral", "Na cidade mágica"],
            "resposta_correta": 0 
        }

    client = obter_cliente_together(together_key)
    modelo = st.session_state.get("modelo_together", "meta-llama/Llama-3.3-70B-Instruct-Turbo")

    prompt_sistema = f"""
    Você é um professor criando um quiz rápido sobre o livro '{livro}' para {faixa_etaria}.
    Gere 1 pergunta MUITO SIMPLES e DIRETA sobre a história (ex: Onde se passa a história? O que o personagem principal fez? Quem é o vilão?).
    Crie exatamente 3 alternativas curtas.
    
    FORMATO JSON ESTRITO (Responda APENAS o JSON, sem nenhum texto antes ou depois):
    {{
      "pergunta": "Texto da pergunta",
      "opcoes": ["Opção A", "Opção B", "Opção C"],
      "resposta_correta": 0
    }}
    O campo 'resposta_correta' é o índice inteiro da resposta certa (0 para a primeira, 1 para a segunda, 2 para a terceira).
    """

    try:
        response = client.chat.completions.create(
            model=modelo,
            messages=[{"role": "system", "content": prompt_sistema}],
            max_tokens=400,
            temperature=0.4, # Temperatura mais baixa para evitar invenções complexas
        )
        match = re.search(r"\{.*\}", response.choices[0].message.content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        st.warning(f"Erro ao gerar pergunta com gabarito: {e}")

    # Retorno padrão caso a IA não retorne um JSON válido
    return {
        "pergunta": f"Sobre o livro '{livro}', o que acontece no final?",
        "opcoes": ["Os heróis perdem", "Os heróis vencem", "Ninguém sabe"],
        "resposta_correta": 1
    }

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

# 1. Dicionário que mapeia o NOME AMIGÁVEL para o ID REAL do modelo
modelos_disponiveis = {
    "Llama 3.3 70B (Padrão - Equilibrado e Robusto)": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "Qwen 2.5 72B (Rápido e Preciso em JSON)": "Qwen/Qwen2.5-72B-Instruct",
    "DeepSeek V3 (Lógica e Raciocínio Apurado)": "deepseek-ai/DeepSeek-V3",
    "Llama 3.1 8B (Ultra Rápido - Econômico)": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo"
}

# Usamos o 'key' para o Streamlit gerenciar a memória sozinho
st.sidebar.selectbox(
    "🤖 Modelo da Narrativa:",
    options=list(modelos_disponiveis.keys()),
    key="nome_modelo_amigavel"
)

# Dicionário de Modelos de Imagem (Painel do Mestre)
modelos_imagem_disponiveis = {
    "Qwen Image (Detalhado / Excelente em Cenários e Estilos)": "Qwen/Qwen-Image",
    "Playground v2.5 (Vibrante / Ideal para Pixar e Livros)": "playgroundai/playground-v2.5-1024px-aesthetic",
    "Stable Diffusion XL 1.0 (Mais Confiável e Estável)": "stabilityai/stable-diffusion-xl-base-1.0"
}

# Seletor na barra lateral
nome_modelo_img = st.sidebar.selectbox(
    "🎨 Modelo de Imagem:",
    options=list(modelos_imagem_disponiveis.keys()),
    index=0, # Qwen selecionado como padrão
    help="Escolha qual modelo de IA vai ilustrar as cenas da história."
)

# Salva a escolha na memória do app
st.session_state["modelo_imagem_together"] = modelos_imagem_disponiveis[nome_modelo_img]

if not st.session_state.partida_iniciada:
    st.header("⚙️ Parâmetros do Jogo")
    st.session_state["total_rodadas"] = st.slider(
        "Número de Rodadas:", min_value=5, max_value=35, value=20
    )
    # 1. Seleção da Turma (Gerada Automaticamente)
    opcoes_turmas = []

    # Aqui você define de qual ano até qual ano (ex: 1 ao 5)
    anos = [1, 2, 3, 4, 5]
    # Aqui você define as letras das turmas
    letras = ["A", "B", "C", "D"]

    # O Python mistura os dois automaticamente
    for ano in anos:
        for letra in letras:
            opcoes_turmas.append(f"{ano}º Ano {letra}")

    # Se quiser adicionar turmas sem número (opcional), é só inserir no começo:
    opcoes_turmas.insert(0, "Educação Infantil")

    nome_turma = st.sidebar.selectbox(
        "🎓 Selecione a Turma:",
        options=opcoes_turmas,
        index=0,
        help="O sistema usará o número do ano para ajustar a dificuldade das palavras na história."
    )
    st.session_state["turma_atual"] = nome_turma
    st.session_state["estilo_arte"] = st.sidebar.selectbox(
        "🎨 Estilo Visual:",
        [
        "3D Pixar CGI Animation style, highly detailed, expressive characters, cute, vibrant lighting",
        "Studio Ghibli Anime Style, whimsical, magical atmosphere, detailed background",
        "Classic Children's Storybook Illustration, soft watercolor painting, whimsical, pastel colors",
        "Epic Digital Fantasy Art, vibrant colors, glowing magic, RPG concept art",
        "16-bit Retro Video Game Pixel Art, detailed, colorful, RPG style",
        ],
    )
else:
        st.divider()
        
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

        with st.sidebar.expander("📋 Chamada / Presença", expanded=False):
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
            st.sidebar.subheader("1. Seleção do Herói")
            if not st.session_state.aluno_sorteado and vivos:
                sortear_proximo_aluno_automatico()

            aluno_selecionado = (
                st.sidebar.selectbox(
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
                            st.session_state.desafio_atual = None
                            st.session_state.pop("ultimo_dado", None)
                            sortear_proximo_aluno_automatico(aluno_selecionado)
                            st.rerun()

            if st.sidebar.button("🔄 Sortear Novamente", use_container_width=True):
                sortear_proximo_aluno_automatico(
                    st.session_state.aluno_sorteado
                )
                st.session_state.pergunta_atual = None
                st.session_state.desafio_atual = None
                st.session_state.pop("ultimo_dado", None)
                st.rerun()
                st.sidebar.subheader("2. Decisão do Mestre (Raio-X)")
                aluno_selecionado = st.session_state.get("aluno_sorteado")

        if aluno_selecionado:
            acao_escolhida_texto = st.session_state.get("acao_escolhida", "Ação Tática")
            inimigo_info = st.session_state.desafio_atual.get("inimigo", "Ameaça") if st.session_state.desafio_atual else "Ameaça"

            # 1. Coleta os gabaritos da rodada
            estrategia_ok = st.session_state.get("acao_correta", False)
            livro_ok = st.session_state.get("passou_habilitacao", False)
            dado_rolado = st.session_state.get("ultimo_dado", 0)

            # 2. Verifica a dificuldade atual
            dc_atual = calcular_dificuldade_rodada(st.session_state.rodada_atual, tot_rodadas)
            dado_ok = dado_rolado >= dc_atual

            # 3. Exibe o "Raio-X" da jogada para o Mestre
            st.sidebar.write("**Raio-X da Rodada:**")
            st.sidebar.write(f"- Pergunta do Livro: {'✅' if livro_ok else '❌'}")
            st.sidebar.write(f"- Estratégia Tática: {'✅' if estrategia_ok else '❌'}")
            st.sidebar.write(f"- Rolagem do Dado ({dado_rolado} vs DC {dc_atual}): {'✅' if dado_ok else '❌'}")

            # 4. Cálculo Automático
            sucesso_automatico = estrategia_ok and livro_ok and dado_ok

            if sucesso_automatico:
                st.sidebar.success("🤖 **Sistema:** SUCESSO matemático detectado!")
            else:
                st.sidebar.error("🤖 **Sistema:** FALHA matemática detectada.")

            # 5. O Interruptor Mágico (Override do Mestre)
            st.sidebar.divider()
            forcar_sucesso = st.sidebar.toggle("✨ Substituir regra e Forçar SUCESSO (Decisão do Mestre)")
            resultado_final = sucesso_automatico or forcar_sucesso

            # 6. Botão Único de Avançar
            if st.sidebar.button("➡️ Avançar a História", type="primary", use_container_width=True):
                p_nome = obter_primeiro_nome(aluno_selecionado["aluno"])

                if resultado_final:
                    # ==========================================
                    # LÓGICA DE SUCESSO
                    # ==========================================
                    aluno_selecionado["moedas"] = aluno_selecionado.get("moedas", 0) + 3
                    if random.random() < 0.30:
                        aluno_selecionado["tem_porcao_resgate"] = True
                        st.toast(f"✨ {p_nome} ganhou uma Poção!")

                    cena_anterior = st.session_state.historico[-1]["texto"] if st.session_state.historico else "Início da jornada."
                    contexto = (
                        f"MUNDO BASE: '{st.session_state.mundo_mestre}'. RODADA: {st.session_state.rodada_atual}/{tot_rodadas}. "
                        f"CENA ANTERIOR: {cena_anterior}\n"
                        f"INIMIGO DA RODADA: {inimigo_info}.\n"
                        f"AÇÃO ESCOLHIDA: {acao_escolhida_texto}.\n"
                        f"STATUS: SUCESSO! O herói superou o obstáculo.\n"
                        f"DESEMPENHO: {aluno_selecionado['personagem']} ({p_nome}) usou o item '{aluno_selecionado['item']}' e VENCEU! "
                        f"INSTRUÇÃO: Narre a vitória enfatizando como o herói superou a ameaça '{inimigo_info}'."
                    )

                    with st.spinner("Gerando sucesso..."):
                        narrativa, p_img = gerar_narrativa_rpg(together_key, contexto, herois_vivos=vivos, heroi_ativo=aluno_selecionado)
                        img = gerar_imagem(p_img, together_key)

                        st.session_state.roteiro_hq.append(f"RODADA {st.session_state.rodada_atual}: [SUCESSO - {acao_escolhida_texto}] {aluno_selecionado['personagem']} venceu {inimigo_info}.")
                        st.session_state.historico.append({"texto": narrativa, "img": img, "heroi": f"Sucesso de {aluno_selecionado['personagem']}"})

                else:
                    # ==========================================
                    # LÓGICA DE FALHA
                    # ==========================================
                    for j in st.session_state.jogadores:
                        if j["aluno"] == aluno_selecionado["aluno"]:
                            j["status"] = "CONGELADO"

                    contexto = (
                        f"MUNDO BASE: '{st.session_state.mundo_mestre}'. RODADA: {st.session_state.rodada_atual}/{tot_rodadas}. "
                        f"INIMIGO DA RODADA: {inimigo_info}.\n"
                        f"AÇÃO TENTADA: {acao_escolhida_texto}.\n"
                        f"STATUS: FALHA! O herói não conseguiu superar o desafio.\n"
                        f"DESEMPENHO: {aluno_selecionado['personagem']} ({p_nome}) foi congelado. "
                        f"INSTRUÇÃO: Narre a falha e o congelamento do herói, destacando a reação da ameaça."
                    )

                    vivos_restantes = [v for v in vivos if v["aluno"] != aluno_selecionado["aluno"]]

                    with st.spinner("Gerando falha..."):
                        # 🟢 DESEMPACOTAMENTO SEGURO: evita o erro TypeError se a API retornar None
                        resultado = gerar_narrativa_rpg(together_key, contexto, herois_vivos=vivos_restantes, heroi_ativo=aluno_selecionado)
    
                    if isinstance(resultado, tuple) and len(resultado) == 2 and resultado[0]:
                        narrativa, p_img = resultado
                    else:
                        narrativa = f"O herói {aluno_selecionado['personagem']} tentou bravamente, mas a ação falhou perante {inimigo_info}."
                        p_img = f"3D Pixar render, heroic fantasy, character {aluno_selecionado['personagem']} dramatic failure scene"

                    img = gerar_imagem(p_img, together_key)

                    st.session_state.roteiro_hq.append(f"RODADA {st.session_state.rodada_atual}: [FALHA - {acao_escolhida_texto}] {aluno_selecionado['personagem']} caiu perante {inimigo_info}.")
                    st.session_state.historico.append({"texto": narrativa, "img": img, "heroi": f"Falha de {aluno_selecionado['personagem']}"})
                # ==========================================
                # LIMPEZA COMUM DA RODADA E AVANÇO
                # ==========================================
                st.session_state["heroi_anterior"] = aluno_selecionado
                st.session_state["sucesso_rodada_anterior"] = bool(resultado_final)
                st.session_state.rodada_atual += 1
                st.session_state.pergunta_atual = None
                st.session_state.desafio_atual = None
                st.session_state.pop("ultimo_dado", None)
                st.session_state.pop("acao_escolhida", None)
                st.session_state.pop("acao_correta", None)
                st.session_state.pop("passou_habilitacao", None)
                sortear_proximo_aluno_automatico(aluno_selecionado)
                st.rerun()
        elif is_chefe_rodada:
            st.subheader("🐉 Batalha do Chefe Final")

            col_boss1, col_boss2 = st.columns(2)

            prompt_boss = f"Children's storybook illustration style, 3D Pixar render. Giant intimidating boss monster {inimigo_info}, dramatic dark and glowing red fantasy lighting."
            prompt_comitiva = "Children's storybook illustration style, 3D Pixar render. A united team of brave child heroes standing together in battle stances, ready to attack."

            with st.spinner("⚔️ Gerando os visuais do Clímax..."):
                img_boss = gerar_imagem(
                    prompt_boss, together_key, prompt_customizado=True
                )
                img_grupo = gerar_imagem(
                    prompt_comitiva, together_key, prompt_customizado=True
                )

            with col_boss1:
                if img_boss:
                    st.image(
                        img_boss,
                        caption=f"🔥 O Monstro Final: {inimigo_info}",
                        use_container_width=True,
                    )

            with col_boss2:
                if img_grupo:
                    st.image(
                        img_grupo,
                        caption="🛡️ A Comitiva Reunida",
                        use_container_width=True,
                    )

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
                            st.session_state.desafio_atual = None
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

        if st.sidebar.button("🗑️ Reiniciar Jogo", use_container_width=True):
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
                "acao_escolhida",
                "acao_correta",
                "desafio_atual",
            ]:
                st.session_state.pop(key, None)
            st.rerun()

       
# ---------------------------------------------------------------------------
# ==========================================
# 5. TELA INICIAL: CARREGAMENTO DO CSV
# ==========================================
if not st.session_state.partida_iniciada:
    st.header("📂 1. Carregar Ficha da Turma (CSV)")
    st.markdown(
        "Envie um arquivo CSV com as colunas: **Nome do Aluno**, **Livro Lido**, **Nome do Personagem**, **Habilidade**, **Item Mágico**."
    )

    csv_file = st.file_uploader("Escolha o arquivo CSV", type=["csv"])

    if csv_file:
        try:
            # 1. Leitura e padronização do CSV
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

            c_aluno = col_map.get("nome do aluno") or col_map.get("aluno") or col_map.get("nome")
            c_livro = col_map.get("livro lido") or col_map.get("livro")
            c_personagem = col_map.get("nome do personagem") or col_map.get("personagem")
            c_habilidade = col_map.get("habilidade")
            c_item = col_map.get("item mágico") or col_map.get("item magico") or col_map.get("item")

            if not all([c_aluno, c_livro, c_personagem, c_habilidade, c_item]):
                st.error("⚠️ Colunas necessárias não encontradas no arquivo CSV!")
            else:
                st.success(f"🟢 {len(df)} alunos carregados com sucesso!")
                st.dataframe(df, use_container_width=True)

                # 2. Botão de início de jogo
                if st.button("🚀 Iniciar Aventura e Fixar Mundo!", type="primary", key="btn_iniciar_aventura_secao5"):
                    jogadores = []
                    for _, row in df.iterrows():
                        jogadores.append({
                            "aluno": str(row[c_aluno]),
                            "livro": str(row[c_livro]),
                            "personagem": str(row[c_personagem]),
                            "habilidade": str(row[c_habilidade]),
                            "item": str(row[c_item]),
                            "status": "VIVO",
                            "presente": True,
                            "moedas": 0,
                            "tem_porcao_resgate": False,
                        })

                    st.session_state.jogadores = jogadores
                    st.session_state.mundo_mestre = jogadores[0]["livro"] if jogadores else "Mundo Mágico"
                    sortear_proximo_aluno_automatico()

                    # 3. Geração do Prólogo com try/except dedicado
                    try:
                        with st.spinner("🎨 Criando o panorama do mundo e gerando os quadros..."):
                            dados_prologo = gerar_prologo_quadro_duplo(
                                together_key=together_key,
                                mundo_mestre=st.session_state.mundo_mestre,
                                herois_vivos=jogadores,
                                heroi_ativo=st.session_state.aluno_sorteado,
                            )

                            # Salva os dados gerados
                            st.session_state.narrativa_prologo = dados_prologo["narrativa_geral"]
                            for quadro in dados_prologo["quadros"]:
                                st.session_state.historico.append(quadro)

                        st.session_state.partida_iniciada = True
                        st.rerun()

                    except Exception as err_prologo:
                        st.error(f"🚨 Erro na geração do Prólogo: {err_prologo}")

        # Fecha o try principal do CSV
        except Exception as err_csv:
            st.error(f"Erro ao processar o arquivo CSV: {err_csv}")

# ==========================================
# 6. TELA DO JOGO EM ANDAMENTO
# ==========================================
else:
    renderizar_painel_jogadores()

    # --- EXIBIÇÃO DO PRÓLOGO LADO A LADO (HQ) ---
    quadros_prologo = [q for q in st.session_state.get("historico", []) if "Prólogo" in str(q.get("heroi", ""))]

    if quadros_prologo:
        st.markdown("### 📜 **Prólogo da Aventura**")
        
        narrativa_intro = st.session_state.get("narrativa_prologo")
        if narrativa_intro:
            st.info(f"📖 {narrativa_intro}")

        cols = st.columns(len(quadros_prologo))
        for idx, (col, quadro) in enumerate(zip(cols, quadros_prologo), start=1):
            with col:
                with st.container(border=True):
                    st.caption(f"🎨 **QUADRO {idx}**")
                    if quadro.get("img"):
                        st.image(quadro["img"], use_container_width=True)
                    st.markdown(f"*{quadro['texto']}*")

        st.divider()

    # --- LÓGICA DAS RODADAS NORMALMENTE AQUI ---
    # ... restante da lógica da rodada ...

    # 1. Carrega o aluno e parâmetros da rodada (com indentação correta)
    aluno = st.session_state.get("aluno_sorteado")
    tot_rodadas = st.session_state.get("total_rodadas", 20)
    rodada_atual = st.session_state.get("rodada_atual", 1)
    is_chefe_rodada = (rodada_atual == tot_rodadas - 1)
    is_ultima_rodada = (rodada_atual >= tot_rodadas)
    dc_atual = calcular_dificuldade_rodada(rodada_atual, tot_rodadas)

    # 2. Executa a validação do turno
    # Destaque para a Rodada e Progresso de Dificuldade (DC)
    col_info1, col_info2 = st.columns([2, 1])
    with col_info1:
        st.subheader(f"📍 Rodada {rodada_atual} de {tot_rodadas}")
    with col_info2:
        st.metric(label="🎯 Dificuldade da Rodada (DC)", value=f"DC {dc_atual}")

    # ==========================================
    # VALIDAÇÃO RIGOROSA DE AÇÃO ÚNICA
    # ==========================================
    if aluno and rodada_atual < tot_rodadas - 1:
        pass

    if not st.session_state.desafio_atual:
        with st.spinner("⚠️ Um novo inimigo surge..."):
            st.session_state.desafio_atual = gerar_desafio_inimigo(
                together_key,
                st.session_state.mundo_mestre,
                st.session_state.jogadores,
                rodada_atual,
                tot_rodadas,
            )

    desafio = st.session_state.desafio_atual

    st.error(
        f"👾 **Ameaça:** {desafio.get('inimigo', 'Inimigo')}\n\n"
        f"📖 **Pista do Ponto Fraco:** {desafio.get('descricao', '')}"
    )

    st.markdown("#### 🎯 Escolha a Estratégia (Apenas 1 é a correta!):")
    acoes_lista = desafio.get("acoes", [])
    opcoes_texto = [a["texto"] for a in acoes_lista]

    if opcoes_texto:
        acao_selecionada = st.radio(
            "Leia a pista com atenção e escolha a única ação capaz de superar este desafio:",
            options=opcoes_texto,
            key=f"radio_acao_{rodada_atual}_{aluno['aluno']}",
        )

        acao_obj = next((a for a in acoes_lista if a["texto"] == acao_selecionada), None)
        is_estrategia_correta = acao_obj.get("correta", False) if acao_obj else False

        st.session_state["acao_escolhida"] = acao_selecionada
        st.session_state["acao_correta"] = is_estrategia_correta

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🎲 Rolar D20 com Animação", use_container_width=True):
            val = animar_rolagem_dado()
            st.session_state["ultimo_dado"] = val

        if "ultimo_dado" in st.session_state:
            dado_val = st.session_state["ultimo_dado"]
            if dado_val == 20:
                st.success(f"🎲 Resultado: **{dado_val}** — 🔥 SUCESSO CRÍTICO!")
            elif dado_val == 1:
                st.error(f"🎲 Resultado: **{dado_val}** — 💀 FALHA CRÍTICA!")
            elif dado_val >= dc_atual:
                st.success(f"🎲 Resultado: **{dado_val}** (Superou a DC {dc_atual}! ✅)")
            else:
                st.error(f"🎲 Resultado: **{dado_val}** (Abaixo da DC {dc_atual}... ❌)")

    with c2:
        if st.button("📖 Gerar Pergunta do Livro", use_container_width=True):
            with st.spinner("Buscando pergunta pedagógica..."):
                st.session_state.pergunta_atual = gerar_pergunta_livro_com_gabarito(
                    together_key,
                    aluno.get("livro", ""),
                    st.session_state.get("faixa_etaria", "Ensino Fundamental I"),
                )

        if st.session_state.pergunta_atual:
            p_obj = st.session_state.pergunta_atual
            st.warning(f"**Pergunta sobre '{aluno['livro']}':**\n\n{p_obj['pergunta']}")

            resposta_aluno_idx = st.radio(
                "Escolha a alternativa correta:",
                options=range(len(p_obj["opcoes"])),
                format_func=lambda i: p_obj["opcoes"][i],
                key=f"resp_livro_{rodada_atual}_{aluno['aluno']}",
            )

            st.session_state["passou_habilitacao"] = (
                resposta_aluno_idx == p_obj["resposta_correta"]
            )

# --------------------------------------------------
# HISTÓRICO DA AVENTURA (DIÁRIO DA JORNADA)
# --------------------------------------------------
st.divider()
st.markdown("### 📜 Diário da Jornada")

for item in reversed(st.session_state.get("historico", [])):
    # 🟢 TRAVA DE SEGURANÇA: ignora qualquer registro que contenha "Prólogo" no nome
    if "Prólogo" in str(item.get("heroi", "")):
        continue

    with st.container():
        st.markdown(f"#### 🎭 {item.get('heroi', 'Aventureiro')}")
        st.write(item.get("texto", ""))
        if item.get("img"):
            st.image(item["img"], use_container_width=True)
        st.divider()
