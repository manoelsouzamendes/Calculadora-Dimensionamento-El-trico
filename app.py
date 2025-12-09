import streamlit as st
import math
import pandas as pd

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Projeto Elétrico NBR 5410",
    page_icon="⚡",
    layout="wide"
)

if 'dados_comodos' not in st.session_state:
    st.session_state['dados_comodos'] = []

# ==========================================
# 2. BANCO DE DADOS
# ==========================================
CAPACIDADE_IZ_COBRE = {
    "PVC": {
        "A1": {0.5:7, 0.75:9, 1:11, 1.5:14.5, 2.5:19.5, 4:26, 6:34, 10:46, 16:61},
        "B1": {0.5:9, 0.75:11, 1:14, 1.5:17.5, 2.5:24, 4:32, 6:41, 10:57, 16:76, 25:101},
        "B2": {0.5:8, 0.75:10, 1:12, 1.5:15.5, 2.5:21, 4:28, 6:36, 10:50, 16:68},
        "C":  {0.5:9, 0.75:11, 1:13, 1.5:16.5, 2.5:23, 4:30, 6:38, 10:52, 16:69},
        "D":  {1.5:22, 2.5:29, 4:38, 6:47, 10:63, 16:81}
    },
    "EPR_XLPE": {
        "B1": {1.5:23, 2.5:31, 4:42, 6:54, 10:75, 16:100} 
    }
}

TABELA_40_TEMPERATURA = {
    ("PVC", 30): 1.00, ("PVC", 35): 0.94, ("PVC", 40): 0.87,
    ("EPR_XLPE", 30): 1.00, ("EPR_XLPE", 35): 0.96, ("EPR_XLPE", 40): 0.91
}

TABELA_42_AGRUPAMENTO = {
    1: 1.00, 2: 0.80, 3: 0.70, 4: 0.65, 5: 0.60, 6: 0.57, 7: 0.57, 8: 0.52, 9: 0.50
}

SECOES_PADRONIZADAS = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50]
DISJUNTORES_PADRAO = [6, 10, 13, 16, 20, 25, 32, 40, 50, 63, 70, 80, 100]
SECOES_MINIMAS = {"iluminacao": 1.5, "tug": 2.5, "tue": 2.5}

# ==========================================
# 3. FUNÇÕES LÓGICAS
# ==========================================

def get_fator_agrupamento(n):
    if n <= 1: return 1.0
    return TABELA_42_AGRUPAMENTO.get(n, 0.50)

def get_fator_temperatura(material, temp):
    if temp <= 30: return 1.0
    return TABELA_40_TEMPERATURA.get((material, temp), 0.90)

def calcular_perimetro_area(larg, comp):
    return 2 * (larg + comp), larg * comp

def calcular_tomadas_norma(perimetro, area, nome):
    nome = nome.lower()
    if nome in ['banheiro', 'wc']: return 1
    if nome in ['cozinha', 'copa', 'copa-cozinha', 'area de serviço', 'lavanderia']:
        return max(math.ceil(perimetro/3.5), 2)
    if 'externa' in nome or 'varanda' in nome or 'quintal' in nome: return 1
    if area <= 6: return 1
    return math.ceil(perimetro/5)

def definir_potencias_tugs(nome, qtd):
    nome = nome.lower()
    especiais = ['banheiro', 'wc', 'cozinha', 'copa', 'lavanderia', 'area de serviço', 
                 'área externa', 'area externa', 'varanda', 'quintal']
    potencias = []
    if nome in especiais:
        n_600 = min(qtd, 3)
        for _ in range(n_600): potencias.append(600)
        for _ in range(qtd - n_600): potencias.append(100)
    else:
        for _ in range(qtd): potencias.append(100)
    return potencias

def dimensionar_circuito(ib, isolacao, metodo, tipo, fct, fca):
    margem_seguranca = 1.15
    if (fct * fca) == 0: return "Erro Fator 0", "", 0, "ERRO"
    
    iz_necessario = (ib * margem_seguranca) / (fct * fca)
    secao_min = SECOES_MINIMAS.get(tipo, 2.5)
    secao_escolhida = None
    iz_tabela_escolhido = 0
    
    tabela_cabos = CAPACIDADE_IZ_COBRE.get(isolacao, {}).get(metodo, {})
    
    for sec in SECOES_PADRONIZADAS:
        iz_tabela = tabela_cabos.get(sec, 0)
        if iz_tabela >= iz_necessario and sec >= secao_min:
            secao_escolhida = sec
            iz_tabela_escolhido = iz_tabela
            break
            
    if not secao_escolhida: return "> 50mm²", "", 0, "ERRO"
    
    iz_corrigido_real = iz_tabela_escolhido * fct * fca
    disjuntor_escolhido = None
    
    for disj in DISJUNTORES_PADRAO:
        if disj >= ib and disj <= iz_corrigido_real:
            disjuntor_escolhido = disj
            break 
    
    status = "✅ OK" if disjuntor_escolhido else "⚠️ Ajustar"
    detalhes = f"{secao_escolhida} mm²"
    detalhes_cap = f"(Cap: {iz_corrigido_real:.1f} A)"
    return detalhes, detalhes_cap, disjuntor_escolhido, status

def dividir_cargas_em_circuitos(lista_potencias, limite_va=1200):
    """
    Divide uma lista de cargas (ex: TUGs da cozinha) em sub-listas
    para não ultrapassar o limite (ex: 1200VA para 127V).
    """
    if not lista_potencias: return []
    
    lista_ordenada = sorted(lista_potencias, reverse=True)
    circuitos = []
    circuito_atual = []
    soma_atual = 0
    
    for pot in lista_ordenada:
        if soma_atual + pot <= limite_va:
            circuito_atual.append(pot)
            soma_atual += pot
        else:
            if circuito_atual: circuitos.append(circuito_atual)
            circuito_atual = [pot]
            soma_atual = pot
            
    if circuito_atual: circuitos.append(circuito_atual)
    return circuitos

# ==========================================
# 4. INTERFACE DO SITE
# ==========================================

st.title("⚡ Calculadora de Projetos Elétricos (NBR 5410)")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configurações")
    temp_amb = st.number_input("Temp. Ambiente (°C)", 20, 50, 30)
    isolacao = st.selectbox("Isolação", ["PVC", "EPR_XLPE"])
    metodo = st.selectbox("Método", ["B1", "B2", "C"], help="B1: Embutido Alvenaria")
    st.divider()
    agrup_ilum = st.slider("Agrupamento Ilum.", 1, 5, 1)
    agrup_tug = st.slider("Agrupamento TUGs", 1, 6, 4)

# --- ENTRADA ---
st.subheader("1. Adicionar Ambiente")
c1, c2, c3 = st.columns(3)
with c1: nome = st.text_input("Nome", placeholder="Ex: Cozinha")
with c2: larg = st.number_input("Largura (m)", 0.0, step=0.1)
with c3: comp = st.number_input("Comp. (m)", 0.0, step=0.1)
c4, c5 = st.columns(2)
with c4: v_ilum = st.selectbox("V Ilum.", [127, 220], key="vi")
with c5: v_tug = st.selectbox("V TUG", [127, 220], key="vt")

tem_tue = st.checkbox("Adicionar Equip. Específico (TUE)?")
tue_dados = None
if tem_tue:
    cc1, cc2, cc3 = st.columns([2,1,1])
    tnome = cc1.text_input("Equipamento")
    tpot = cc2.number_input("Potência (W)", 0, step=100)
    tv = cc3.selectbox("Tensão TUE", [127, 220], index=1)
    if tnome and tpot > 0: tue_dados = {"nome": tnome, "pot": tpot, "v": tv}

if st.button("➕ Adicionar", type="primary"):
    if nome and larg > 0:
        perim, area = calcular_perimetro_area(larg, comp)
        pot_ilum = 100 if area <= 6 else 100 + (math.floor((area-6)/4)*60)
        qtd_tugs = calcular_tomadas_norma(perim, area, nome)
        lista_tugs = definir_potencias_tugs(nome, qtd_tugs)
        
        st.session_state['dados_comodos'].append({
            "nome": nome, "area": area, "ilum_va": pot_ilum, "v_ilum": v_ilum,
            "tugs": lista_tugs, "v_tug": v_tug, "tue": tue_dados
        })
        st.success(f"{nome} Adicionado!")

# --- TABELA DE AMBIENTES ---
if st.session_state['dados_comodos']:
    st.divider()
    view = []
    for c in st.session_state['dados_comodos']:
        tue_s = f"{c['tue']['nome']} ({c['tue']['pot']}W)" if c['tue'] else ""
        view.append({"Local": c['nome'], "Área": f"{c['area']:.1f}", "Ilum": c['ilum_va'], "TUGs (VA)": c['tugs'], "TUE": tue_s})
    st.table(pd.DataFrame(view))
    if st.button("Limpar Lista"):
        st.session_state['dados_comodos'] = []
        st.rerun()

# ==========================================
# 5. MEMORIAL DE CÁLCULO
# ==========================================
if st.session_state['dados_comodos'] and st.button("🚀 Calcular Dimensionamento"):
    st.markdown("---")
    st.subheader("3. Memorial de Cálculo")
    fct = get_fator_temperatura(isolacao, temp_amb)
    resultados = []
    
    # Variável local para contar circuitos
    contador_circuitos = 1
    
    # 1. ILUMINAÇÃO
    total_ilum = sum(c['ilum_va'] for c in st.session_state['dados_comodos'])
    if total_ilum > 0:
        v_ilum = st.session_state['dados_comodos'][0]['v_ilum']
        ib_i = total_ilum/v_ilum
        fca_i = get_fator_agrupamento(agrup_ilum)
        cabo, det_cap, disj, stt = dimensionar_circuito(ib_i, isolacao, metodo, "iluminacao", fct, fca_i)
        resultados.append({
            "Circuito": f"{contador_circuitos} - Iluminação", "Tensão": f"{v_ilum}V", 
            "Potência Total": f"{total_ilum} VA", "Ib (A)": f"{ib_i:.2f}", 
            "FCA": f"{fca_i:.2f}", "Condutor": f"{cabo} {det_cap}", 
            "Disjuntor": f"{disj}A {stt}"
        })
        contador_circuitos += 1
    
    # 2. TUGs
    tugs_cozinha = {}
    tugs_umidas = {}
    tugs_geral = {}
    umidas_names = ['banheiro', 'wc', 'área externa', 'area externa', 'quintal', 'varanda']
    servico_names = ['cozinha', 'copa', 'area de serviço', 'lavanderia']
    
    for c in st.session_state['dados_comodos']:
        nome_low = c['nome'].lower()
        v = c['v_tug']
        target = tugs_geral
        if nome_low in umidas_names: target = tugs_umidas
        elif nome_low in servico_names: target = tugs_cozinha
        if v not in target: target[v] = []
        target[v].extend(c['tugs'])

    # Processamento dos Grupos
    grupos_para_processar = [
        (tugs_cozinha, "Cozinha e Serviço"),
        (tugs_umidas, "Banheiro e Exterior"),
        (tugs_geral, "Social e Quartos")
    ]

    for dicio_tugs, nome_grupo in grupos_para_processar:
        for tensao, lista_potencias in dicio_tugs.items():
            # Define limite: 1200VA para 127V, 2200VA para 220V
            limite_va = 1200 if tensao == 127 else 2200
            
            # Aqui está a mágica da divisão
            sub_circuitos = dividir_cargas_em_circuitos(lista_potencias, limite_va)
            
            for sub in sub_circuitos:
                pot_total = sum(sub)
                ib = pot_total / tensao
                fca = get_fator_agrupamento(agrup_tug)
                cabo, det_cap, disj, stt = dimensionar_circuito(ib, isolacao, metodo, "tug", fct, fca)
                
                resultados.append({
                    "Circuito": f"{contador_circuitos} - TUG {nome_grupo}", 
                    "Tensão": f"{tensao}V",
                    "Potência Total": f"{pot_total} VA", 
                    "Ib (A)": f"{ib:.2f}",
                    "FCA": f"{fca:.2f}", 
                    "Condutor": f"{cabo} {det_cap}",
                    "Disjuntor": f"{disj}A {stt}"
                })
                contador_circuitos += 1
    
    # 3. TUEs
    for c in st.session_state['dados_comodos']:
        if c['tue']:
            t = c['tue']
            ib = t['pot']/t['v']
            cabo, det_cap, disj, stt = dimensionar_circuito(ib, isolacao, metodo, "tue", fct, 1.0)
            resultados.append({
                "Circuito": f"{contador_circuitos} - Equip. {t['nome']}", 
                "Tensão": f"{t['v']}V", "Potência Total": f"{t['pot']} W", 
                "Ib (A)": f"{ib:.2f}", "FCA": "1.00", 
                "Condutor": f"{cabo} {det_cap}", "Disjuntor": f"{disj}A {stt}"
            })
            contador_circuitos += 1
            
    st.table(pd.DataFrame(resultados))
    st.success("Cálculo realizado com sucesso!")
