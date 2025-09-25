import streamlit as st
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta
import plotly.express as px


# --- FUNÇÃO PARA CALCULAR A MÉDIA DOS 80% MAIORES SALÁRIOS ---
def calcular_media_80_porcento(salarios_list):
    if not salarios_list:
        return 0

    salarios_list.sort()

    num_salarios_a_considerar = int(len(salarios_list) * 0.8)

    if num_salarios_a_considerar == 0:
        return 0

    maiores_salarios = salarios_list[len(salarios_list) - num_salarios_a_considerar:]

    media = sum(maiores_salarios) / len(maiores_salarios)

    return media


# --- FUNÇÃO PARA CONVERTER TEMPO ESPECIAL PARA TEMPO COMUM ---
def converter_tempo_especial(tempo_especial, genero, tipo_atividade):
    fatores_conversao = {
        'Feminino': {
            15: 2.0,
            20: 1.5,
            25: 1.2
        },
        'Masculino': {
            15: 2.33,
            20: 1.75,
            25: 1.4
        }
    }

    fator = fatores_conversao[genero][tipo_atividade]
    tempo_convertido = tempo_especial * fator
    return tempo_convertido


# FATOR PREVIDENCIÁRIO SIMPLIFICADO
def calcular_fator_previdenciario(idade, tempo_contribuicao, dt_nascimento):
    sexo = "Feminino" if st.session_state.genero == "Feminino" else "Masculino"

    TBC = tempo_contribuicao * 0.31
    aliquota = 0.031

    if sexo == "Feminino":
        idade_expectativa = 81.3
    else:
        idade_expectativa = 74.8

    fator = (idade + (tempo_contribuicao * aliquota)) / (idade_expectativa * aliquota)
    return fator


# Função principal para calcular as regras de aposentadoria
def calcular_aposentadoria(genero, dt_nascimento, tempo_contribuicao_anos, salarios_str, dt_filiacao, is_professor,
                           is_special, tempo_especial_anos, tipo_atividade_especial):
    hoje = date.today()
    idade_anos = hoje.year - dt_nascimento.year - ((hoje.month, hoje.day) < (dt_nascimento.month, dt_nascimento.day))
    st.session_state.genero = genero

    # Adiciona o tempo convertido do tempo especial, se aplicável e válido (antes da reforma)
    tempo_total_contribuicao = tempo_contribuicao_anos
    dt_reforma = date(2019, 11, 13)
    if is_special and dt_filiacao < dt_reforma and tempo_especial_anos > 0:
        tempo_convertido = converter_tempo_especial(tempo_especial_anos, genero, tipo_atividade_especial)
        tempo_total_contribuicao += tempo_convertido

    salarios = []
    if salarios_str:
        try:
            salarios = [float(s.replace(',', '.')) for s in salarios_str.split()]
        except ValueError:
            st.error("Por favor, insira os salários como números válidos, um por linha ou separados por espaços.")
            return None

    media_salarial = calcular_media_80_porcento(salarios)
    resultados = []

    # --- REGRA DE PROFESSOR ---
    if is_professor:
        idade_min_prof = 57 if genero == "Feminino" else 60
        tempo_min_prof = 25 if genero == "Feminino" else 30

        if idade_anos >= idade_min_prof and tempo_total_contribuicao >= tempo_min_prof:
            status_prof = "SIM - Requisitos Atingidos"
        else:
            msg_falta = []
            if idade_anos < idade_min_prof:
                msg_falta.append(f"{idade_min_prof - idade_anos:.1f} anos de idade")
            if tempo_total_contribuicao < tempo_min_prof:
                msg_falta.append(f"{tempo_min_prof - tempo_total_contribuicao:.1f} anos de contribuição")
            status_prof = "Faltam: " + " e ".join(msg_falta)

        valor_prof = f"R$ {media_salarial:.2f}" if media_salarial > 0 else "Não calculado"

        resultados.append({
            "Regra": "Aposentadoria de Professor(a)",
            "Situação": status_prof,
            "Valor Estimado": valor_prof
        })

    # --- APOSENTADORIA ESPECIAL ---
    if is_special:
        tempo_min_special = tipo_atividade_especial

        if tempo_contribuicao_anos >= tempo_min_special:
            status_special = "SIM - Requisitos Atingidos"
        else:
            status_special = f"Faltam {tempo_min_special - tempo_contribuicao_anos:.1f} anos de contribuição especial."

        valor_special = f"R$ {media_salarial:.2f}" if media_salarial > 0 else "Não calculado"

        resultados.append({
            "Regra": "Aposentadoria Especial",
            "Situação": status_special,
            "Valor Estimado": valor_special
        })

    # --- Regras de Transição (Continuação) ---
    # Regra da Idade Mínima Progressiva
    idade_min_prog = 58.5 if genero == "Feminino" else 63.5
    tempo_min_prog = 30 if genero == "Feminino" else 35

    if idade_anos >= idade_min_prog and tempo_total_contribuicao >= tempo_min_prog:
        status_prog = "SIM - Requisitos Atingidos"
    else:
        tempo_falta_prog = 0
        if idade_anos < idade_min_prog:
            tempo_falta_prog += idade_min_prog - idade_anos
        if tempo_total_contribuicao < tempo_min_prog:
            tempo_falta_prog += tempo_min_prog - tempo_total_contribuicao
        status_prog = f"Faltam aproximadamente {tempo_falta_prog:.1f} anos para se aposentar por essa regra."

    acrescimo_prog = max(0, tempo_total_contribuicao - (15 if genero == "Feminino" else 20)) * 0.02
    valor_prog = f"R$ {media_salarial * (0.60 + acrescimo_prog):.2f}" if media_salarial > 0 else "Não calculado"

    resultados.append({
        "Regra": "Idade Progressiva",
        "Situação": status_prog,
        "Valor Estimado": valor_prog
    })

    # Regra dos Pontos
    pontos_min = 92 if genero == "Feminino" else 102
    pontos_atuais = idade_anos + tempo_total_contribuicao

    if pontos_atuais >= pontos_min and tempo_total_contribuicao >= (30 if genero == "Feminino" else 35):
        status_pontos = "SIM - Requisitos Atingidos"
    else:
        pontos_faltantes = pontos_min - pontos_atuais
        status_pontos = f"Faltam {pontos_faltantes} pontos para se aposentar."

    acrescimo_pontos = max(0, tempo_total_contribuicao - (15 if genero == "Feminino" else 20)) * 0.02
    valor_pontos = f"R$ {media_salarial * (0.60 + acrescimo_pontos):.2f}" if media_salarial > 0 else "Não calculado"

    resultados.append({
        "Regra": "Regra dos Pontos",
        "Situação": status_pontos,
        "Valor Estimado": valor_pontos
    })

    # Regra do Pedágio de 50%
    if dt_filiacao >= dt_reforma:
        status_pedagio_50 = "Não se aplica (Filiado após a Reforma)"
        valor_pedagio_50 = "Não se aplica"
    else:
        tempo_total_necessario = 30 if genero == "Feminino" else 35
        anos_faltando_em_2019 = tempo_total_necessario - (tempo_total_contribuicao - (hoje - dt_reforma).days / 365.25)

        if 0 < anos_faltando_em_2019 <= 2:
            tempo_pedagio_50 = anos_faltando_em_2019 * 1.5
            if tempo_total_contribuicao >= tempo_pedagio_50:
                status_pedagio_50 = "SIM - Requisitos Atingidos"
            else:
                status_pedagio_50 = f"Faltam {tempo_pedagio_50 - tempo_total_contribuicao:.1f} anos para cumprir o pedágio."

            fator_prev = calcular_fator_previdenciario(idade_anos, tempo_total_contribuicao, dt_nascimento)
            valor_pedagio_50 = f"R$ {media_salarial * fator_prev:.2f}" if media_salarial > 0 else "Não calculado"
        else:
            status_pedagio_50 = "Não se aplica (Faltavam mais de 2 anos em 2019)"
            valor_pedagio_50 = "Não se aplica"

    resultados.append({
        "Regra": "Pedágio de 50%",
        "Situação": status_pedagio_50,
        "Valor Estimado": valor_pedagio_50
    })

    # Regra do Pedágio de 100%
    idade_min_pedagio_100 = 57 if genero == "Feminino" else 60
    tempo_min_pedagio_100 = 30 if genero == "Feminino" else 35

    if dt_filiacao >= dt_reforma:
        status_pedagio_100 = "Não se aplica (Filiado após a Reforma)"
        valor_pedagio_100 = "Não se aplica"
    else:
        if idade_anos >= idade_min_pedagio_100 and tempo_total_contribuicao >= tempo_min_pedagio_100:
            status_pedagio_100 = "SIM - Requisitos Atingidos"
        else:
            msg_falta = []
            if idade_anos < idade_min_pedagio_100:
                msg_falta.append(f"{idade_min_pedagio_100 - idade_anos:.1f} anos de idade")
            if tempo_total_contribuicao < tempo_min_pedagio_100:
                msg_falta.append(f"{tempo_min_pedagio_100 - tempo_total_contribuicao:.1f} anos de contribuição")
            status_pedagio_100 = "Faltam: " + " e ".join(msg_falta)

        valor_pedagio_100 = f"R$ {media_salarial:.2f}" if media_salarial > 0 else "Não calculado"

    resultados.append({
        "Regra": "Pedágio de 100%",
        "Situação": status_pedagio_100,
        "Valor Estimado": valor_pedagio_100
    })

    # Nova Regra Definitiva
    idade_min_definitiva = 62 if genero == "Feminino" else 65
    tempo_min_definitiva = 15 if genero == "Feminino" else 20

    if idade_anos >= idade_min_definitiva and tempo_total_contribuicao >= tempo_min_definitiva:
        status_definitiva = "SIM - Requisitos Atingidos"
    else:
        msg_falta = []
        if idade_anos < idade_min_definitiva:
            msg_falta.append(f"{idade_min_definitiva - idade_anos:.1f} anos de idade")
        if tempo_total_contribuicao < tempo_min_definitiva:
            msg_falta.append(f"{tempo_min_definitiva - tempo_min_definitiva:.1f} anos de contribuição")
        status_definitiva = "Faltam: " + " e ".join(msg_falta)

    acrescimo_definitivo = max(0, tempo_total_contribuicao - (15 if genero == "Feminino" else 20)) * 0.02
    valor_definitiva = f"R$ {media_salarial * (0.60 + acrescimo_definitivo):.2f}" if media_salarial > 0 else "Não calculado"

    resultados.append({
        "Regra": "Nova Regra Definitiva",
        "Situação": status_definitiva,
        "Valor Estimado": valor_definitiva
    })

    return resultados


# Função para projetar aposentadoria futura
def projetar_aposentadoria(genero, dt_nascimento, tempo_contribuicao_anos, dt_filiacao, is_professor, is_special,
                           tempo_especial_anos, tipo_atividade_especial):
    hoje = date.today()
    dt_reforma = date(2019, 11, 13)

    # Adiciona o tempo convertido do tempo especial, se aplicável e válido (antes da reforma)
    tempo_total_contribuicao = tempo_contribuicao_anos
    if is_special and dt_filiacao < dt_reforma and tempo_especial_anos > 0:
        tempo_convertido = converter_tempo_especial(tempo_especial_anos, genero, tipo_atividade_especial)
        tempo_total_contribuicao += tempo_convertido

    projetos = []

    # Projeção de Professor
    if is_professor:
        dt_projecao = hoje
        idade_projecao = (hoje - dt_nascimento).days / 365.25
        tempo_projecao = tempo_total_contribuicao

        idade_min_prof = 57 if genero == "Feminino" else 60
        tempo_min_prof = 25 if genero == "Feminino" else 30

        while idade_projecao < idade_min_prof or tempo_projecao < tempo_min_prof:
            dt_projecao += relativedelta(months=1)
            idade_projecao = (dt_projecao - dt_nascimento).days / 365.25
            tempo_projecao += 1 / 12
        projetos.append({"Regra": "Aposentadoria de Professor(a)", "Data Prevista": dt_projecao})

    # PROJEÇÃO APOSENTADORIA ESPECIAL
    if is_special:
        dt_projecao = hoje
        tempo_projecao = tempo_contribuicao_anos
        tempo_min_special = tipo_atividade_especial

        while tempo_projecao < tempo_min_special:
            dt_projecao += relativedelta(months=1)
            tempo_projecao += 1 / 12
        projetos.append({"Regra": "Aposentadoria Especial", "Data Prevista": dt_projecao})

    # Projeção da Idade Progressiva
    dt_projecao = hoje
    idade_projecao = (hoje - dt_nascimento).days / 365.25
    tempo_projecao = tempo_total_contribuicao

    idade_min_prog = 58.5 if genero == "Feminino" else 63.5
    tempo_min_prog = 30 if genero == "Feminino" else 35

    while idade_projecao < idade_min_prog or tempo_projecao < tempo_min_prog:
        dt_projecao += relativedelta(months=1)
        idade_projecao = (dt_projecao - dt_nascimento).days / 365.25
        tempo_projecao += 1 / 12
    projetos.append({"Regra": "Idade Progressiva", "Data Prevista": dt_projecao})

    # Projeção dos Pontos
    dt_projecao = hoje
    idade_projecao = (hoje - dt_nascimento).days / 365.25
    tempo_projecao = tempo_total_contribuicao

    pontos_min = 92 if genero == "Feminino" else 102

    while (idade_projecao + tempo_projecao) < pontos_min or tempo_projecao < (30 if genero == "Feminino" else 35):
        dt_projecao += relativedelta(months=1)
        idade_projecao = (dt_projecao - dt_nascimento).days / 365.25
        tempo_projecao += 1 / 12
    projetos.append({"Regra": "Regra dos Pontos", "Data Prevista": dt_projecao})

    # PROJEÇÃO DO PEDÁGIO DE 100%
    if dt_filiacao < dt_reforma:
        dt_projecao = hoje
        idade_projecao = (hoje - dt_nascimento).days / 365.25
        tempo_projecao = tempo_total_contribuicao

        idade_min_pedagio_100 = 57 if genero == "Feminino" else 60
        tempo_min_pedagio_100 = 30 if genero == "Feminino" else 35

        while idade_projecao < idade_min_pedagio_100 or tempo_projecao < tempo_min_pedagio_100:
            dt_projecao += relativedelta(months=1)
            idade_projecao = (dt_projecao - dt_nascimento).days / 365.25
            tempo_projecao += 1 / 12
        projetos.append({"Regra": "Pedágio de 100%", "Data Prevista": dt_projecao})

    return projetos


# Configuração do aplicativo Streamlit
st.title("Simulador de Aposentadoria INSS")
st.markdown("Preencha as informações para ver as suas opções de aposentadoria de acordo com as regras de transição.")

# --- BARRA LATERAL ---
st.sidebar.title("Calculadora Rápida")
st.sidebar.markdown("Veja sua idade e tempo de contribuição.")

sidebar_dt_nascimento = st.sidebar.date_input(
    "Data de Nascimento",
    min_value=date(1900, 1, 1),
    max_value=date.today(),
    format="DD/MM/YYYY"
)

sidebar_dt_filiacao = st.sidebar.date_input(
    "Data de Filiação ao INSS",
    min_value=date(1900, 1, 1),
    max_value=date.today(),
    format="DD/MM/YYYY"
)

hoje = date.today()
idade_calculada = (hoje - sidebar_dt_nascimento).days / 365.25
tempo_contrib_calculado = (hoje - sidebar_dt_filiacao).days / 365.25

st.sidebar.write(f"**Idade:** {idade_calculada:.2f} anos")
st.sidebar.write(f"**Tempo de Contribuição:** {tempo_contrib_calculado:.2f} anos")

# --- FORMULÁRIO PRINCIPAL ---
with st.form("formulario_cliente"):
    st.header("Dados do Cliente")
    genero = st.radio("Gênero", ["Feminino", "Masculino"])

    is_professor = st.checkbox("O cliente é professor(a)?")
    is_special = st.checkbox("O cliente tem direito a Aposentadoria Especial?")

    # Novos campos para tempo especial, visíveis apenas se a opção 'Aposentadoria Especial' for marcada
    tempo_especial_anos = 0
    tipo_atividade_especial = 25
    if is_special:
        st.subheader("Informações de Atividade Especial")
        tempo_especial_anos = st.number_input(
            "Tempo em atividade especial (em anos)",
            min_value=0,
            max_value=50,
            step=1,
            key='tempo_especial_input'
        )
        tipo_atividade_especial = st.radio(
            "Tipo de atividade especial",
            options=[25, 20, 15],
            index=2,  # Valor padrão para 25 anos
            format_func=lambda x: f"{x} anos de contribuição"
        )

    data_nascimento = st.date_input(
        "Data de Nascimento",
        min_value=date(1900, 1, 1),
        max_value=date.today(),
        format="DD/MM/YYYY"
    )

    tempo_contribuicao = st.number_input("Tempo de Contribuição (em anos)", min_value=0, max_value=50, step=1)

    data_filiacao = st.date_input(
        "Data de Filiação ao INSS",
        min_value=date(1900, 1, 1),
        max_value=date.today(),
        format="DD/MM/YYYY"
    )

    salarios_input = st.text_area(
        "Média de Salários a partir de 07/1994 (Opcional)",
        placeholder="Insira um salário por linha, ou separados por espaços. Ex: 2500.00 3000.00"
    )

    submit_button = st.form_submit_button(label="Simular Aposentadoria")

if submit_button:
    st.header("Resultados da Simulação")
    resultado = calcular_aposentadoria(genero, data_nascimento, tempo_contribuicao, salarios_input, data_filiacao,
                                       is_professor, is_special, tempo_especial_anos, tipo_atividade_especial)

    if resultado:
        df_resultados = pd.DataFrame(resultado)
        st.dataframe(df_resultados.set_index('Regra'), width='stretch')
        st.write("---")
        st.info(
            "Atenção: Os valores apresentados são estimativas e não substituem uma análise completa com um especialista em direito previdenciário.")

    # --- BLOCO DE PROJEÇÃO FUTURA COM GRÁFICO ---
    st.header("Projeção para a Aposentadoria")
    st.markdown("Veja os dados previstos para cumprir os requisitos de cada regra.")

    projetos = projetar_aposentadoria(genero, data_nascimento, tempo_contribuicao, data_filiacao, is_professor,
                                      is_special, tempo_especial_anos, tipo_atividade_especial)

    df_projetos = pd.DataFrame(projetos)

    if not df_projetos.empty:
        df_projetos['Data Prevista'] = pd.to_datetime(df_projetos['Data Prevista'])
        df_projetos['AnoPrevisto'] = df_projetos['Data Prevista'].dt.year

        min_year = df_projetos['AnoPrevisto'].min() - 1
        max_year = df_projetos['AnoPrevisto'].max() + 1

        fig = px.bar(
            df_projetos,
            x='Regra',
            y='AnoPrevisto',
            title='Comparativo de Projeção de Aposentadoria',
            labels={'AnoPrevisto': 'Ano Previsto'},
            color='Regra',
            text='AnoPrevisto'
        )

        fig.update_yaxes(range=[min_year, max_year])

        st.plotly_chart(fig, use_container_width=True)
        st.write("---")

        df_projetos['Data Prevista'] = df_projetos['Data Prevista'].dt.strftime("%d/%m/%Y")
        st.dataframe(df_projetos.set_index('Regra'), width='stretch')