import base64
import re
from io import BytesIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(layout="wide")
st.markdown(
    """
    <style>
        .stApp {
            background-color: #eaf3ff;
        }
        .block-container {
            max-width: 100% !important;
            padding-left: 2rem;
            padding-right: 2rem;
            padding-top: 1rem;
        }
        .section-block {
            background: #ffffff;
            border: 1px solid #d7e7ff;
            border-radius: 10px;
            padding: 1rem 1.2rem 1.2rem;
            margin-bottom: 1.2rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        }
        div[data-testid="stSidebar"] {
            background-color: #0f2b4d;
        }
        div[data-testid="stSidebar"] .stSelectbox > div,
        div[data-testid="stSidebar"] .stMultiSelect > div,
        div[data-testid="stSidebar"] .stTextInput > div,
        div[data-testid="stSidebar"] .stCheckbox > label {
            background-color: #ffffff;
            color: #0f2b4d;
        }
        div[data-testid="stSidebar"] label,
        div[data-testid="stSidebar"] h1,
        div[data-testid="stSidebar"] h2,
        div[data-testid="stSidebar"] h3,
        div[data-testid="stSidebar"] p {
            color: #ffffff;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

meses = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ']

st.sidebar.header("Filtros")
selected_months = st.sidebar.multiselect("Selecione meses", meses, default=meses)
selected_months = [m for m in meses if m in selected_months]

base_dir = Path(__file__).resolve().parent
excel_files = sorted(base_dir.glob("LEM *.xlsx"))

workbooks = []
for path in excel_files:
    year_match = re.search(r"(\d{4})", path.name)
    year = year_match.group(1) if year_match else path.stem
    workbooks.append((year, path, False))

available_years = sorted({year for year, _, _ in workbooks})
selected_years = st.sidebar.multiselect("Selecione anos", available_years, default=available_years)
selected_years = [year for year in available_years if year in selected_years]

uploaded_files = st.sidebar.file_uploader(
    "Adicionar planilhas",
    type=["xlsx"],
    accept_multiple_files=True,
    help="Selecione arquivos Excel para incluir na análise.",
)

if uploaded_files:
    for uploaded_file in uploaded_files:
        year_match = re.search(r"(\d{4})", uploaded_file.name)
        year = year_match.group(1) if year_match else uploaded_file.name.rsplit(".", 1)[0]
        workbooks.append((year, uploaded_file, True))

if not workbooks:
    st.error("Nenhum arquivo LEM encontrado na pasta do projeto ou enviado.")
    st.stop()

logo_path = base_dir / "Logo.jpeg.jpeg"
if logo_path.exists():
    st.sidebar.markdown("---")
    st.sidebar.image(str(logo_path), width=120)

if not selected_years:
    st.sidebar.info("Selecione pelo menos um ano para visualizar os gráficos.")
    st.stop()

"preparando os valores e colunas"
def prepare_section(df, row_slice, label_slice, months):
    table = df.iloc[row_slice, label_slice]
    values = df.iloc[row_slice, 1:14].apply(pd.to_numeric, errors='coerce')
    values = values.reindex(columns=months)
    totals_col = values.sum()
    totals_row = values.sum(axis=1)

    row_label = table.columns[0]
    table_rows = table.set_index(row_label).copy()
    
    # Garantir que o índice seja único adicionando sufixo se necessário
    if not table_rows.index.is_unique:
        table_rows.index = table_rows.index + '_' + table_rows.groupby(level=0).cumcount().astype(str)
    
    table_rows['Total'] = totals_row.values
    table_rows = table_rows[['Total']]

    return table, values, totals_col, table_rows

"apresentando os resultados"
def show_section(title, year_sections, chart_title, container):
    with container:
        container.markdown('<div class="section-block">', unsafe_allow_html=True)
        container.subheader(title)

        totals_by_year = []
        row_totals_by_year = []

        for year, _, totals_col, totals_rows in year_sections:
            totals_by_year.append(totals_col.rename(year))
            row_totals_by_year.append(totals_rows.rename(columns={'Total': year}))

        totals_df = pd.concat(totals_by_year, axis=1)
        row_totals_df = pd.concat(row_totals_by_year, axis=1) if row_totals_by_year else pd.DataFrame()

        plot_df = totals_df.reset_index().rename(columns={'index': 'Mês'})
        plot_df = plot_df.melt(id_vars='Mês', var_name='Ano', value_name='Total')

        fig = px.line(
            plot_df,
            x='Mês',
            y='Total',
            color='Ano',
            markers=True,
            labels={'Mês': 'Mês', 'Total': 'Total', 'Ano': 'Ano'},
            title=chart_title,
        )

        container.write("Tabela:")
        container.dataframe(row_totals_df)

        bottom_cols = container.columns([1.2, 1.5])

        with bottom_cols[0]:
            st.write("Totais por linha por ano:")
            
            if row_totals_df.empty:
                st.write("Nenhum valor disponível para o treemap.")
                st.dataframe(row_totals_df)
            else:
                treemap_data = []
                for row_name in row_totals_df.index:
                    for col_name in row_totals_df.columns:
                        value = row_totals_df.loc[row_name, col_name]
                        if pd.notna(value):
                            treemap_data.append({
                                'Linha': str(row_name),
                                'Ano': str(col_name),
                                'Total': float(value)
                            })

                if treemap_data:
                    treemap_df = pd.DataFrame(treemap_data)
                    fig_treemap = px.treemap(
                        treemap_df,
                        path=['Ano', 'Linha'],
                        values='Total',
                        color='Total',
                        color_continuous_scale='Blues',
                    )
                    st.plotly_chart(fig_treemap, use_container_width=True)
                else:
                    st.write("Nenhum valor disponível para o treemap.")
                    st.dataframe(row_totals_df)

        with bottom_cols[1]:
            st.write(chart_title)
            st.plotly_chart(fig, use_container_width=True)

        container.markdown('</div>', unsafe_allow_html=True)
        return totals_df


def show_correlation_heatmap(section_summaries):
    if not section_summaries:
        return

    corr_frames = []
    for title, totals_df in section_summaries.items():
        monthly_totals = totals_df.sum(axis=1)
        corr_frames.append(monthly_totals.rename(title))

    if len(corr_frames) < 2:
        st.info("Selecione mais de uma tabela para visualizar a correlação.")
        return

    corr_df = pd.concat(corr_frames, axis=1)
    corr_matrix = corr_df.corr().fillna(0)

    st.markdown("---")
    st.subheader("Correlação entre tabelas")
    st.write(
        "Este gráfico mostra a relação entre as tabelas ao comparar os valores de cada eixo. "
        "No eixo X e no eixo Y estão as tabelas analisadas, e cada célula representa a correlação entre elas. "
        "Quando o valor estiver próximo de 1, isso significa que, à medida que o valor de X aumenta, o valor de Y também aumenta. "
        "Quando estiver próximo de -1, isso significa que, quanto maior o valor de X, menor o valor de Y. "
        "E quando estiver próximo de 0, indica que não há uma relação clara entre os dois."
    )
    fig_corr = px.imshow(
        corr_matrix,
        text_auto=True,
        color_continuous_scale='Viridis',
        title='Correlação entre tabelas',
    )
    st.plotly_chart(fig_corr, use_container_width=True)


def show_missing_data_heatmap(loaded_data, months):
    if not loaded_data or not months:
        return

    missing_points = []
    for year, df in loaded_data:
        numeric_values = df.iloc[:, 1:14].apply(pd.to_numeric, errors='coerce')
        numeric_values = numeric_values.reindex(columns=months)
        if numeric_values.empty:
            continue

        missing_mask = numeric_values.isna()
        for idx, row in missing_mask.iterrows():
            row_label = f"{year} | {idx}"
            for month in missing_mask.columns:
                if row.get(month):
                    missing_points.append({
                        'Ano': year,
                        'Linha': row_label,
                        'Mês': month,
                    })

    if not missing_points:
        return

    missing_df = pd.DataFrame(missing_points)

    st.markdown("---")
    st.subheader("Posições de dados faltantes")
    st.write(
        "Este gráfico marca exatamente onde há valores ausentes nas planilhas carregadas. "
        "Cada ponto mostra a linha e o mês em que um dado está faltando."
    )

    fig_missing = px.scatter(
        missing_df,
        x='Mês',
        y='Linha',
        color='Ano',
        symbol='Ano',
        title='Dados faltantes por linha e mês',
        category_orders={'Mês': months},
        hover_data=['Ano', 'Linha', 'Mês'],
        height=700,
    )
    fig_missing.update_traces(marker=dict(size=8, opacity=0.8))
    st.plotly_chart(fig_missing, use_container_width=True)

section_dt = []
section_pf = []
section_saude = []
section_educacao = []

loaded_data = []
for year, file_source, is_uploaded in workbooks:
    if year not in selected_years:
        continue

    try:
        if is_uploaded:
            df = pd.read_excel(BytesIO(file_source.getvalue()), header=2)
        else:
            df = pd.read_excel(file_source, header=2)
    except PermissionError:
        file_name = getattr(file_source, "name", str(file_source))
        st.error(f"Erro: O arquivo {file_name} está aberto em outro programa. Feche-o e tente novamente.")
        continue

    loaded_data.append((year, df))

    tb_dt, _, totais_dt, tb_dt_linhas = prepare_section(df, slice(0, 17), slice(0, 14), selected_months)
    section_dt.append((year, tb_dt, totais_dt, tb_dt_linhas))

    tb_pf, _, totais_pf, tb_pf_linhas = prepare_section(df, slice(18, 22), slice(0, 14), selected_months)
    section_pf.append((year, tb_pf, totais_pf, tb_pf_linhas))

    tb_saude, _, totais_saude, tb_saude_linhas = prepare_section(df, slice(23, 26), slice(0, 14), selected_months)
    section_saude.append((year, tb_saude, totais_saude, tb_saude_linhas))

    tb_educacao, _, totais_educacao, tb_educacao_linhas = prepare_section(df, slice(27, 43), slice(0, 14), selected_months)
    section_educacao.append((year, tb_educacao, totais_educacao, tb_educacao_linhas))

sections = [
    ("Tabela desdobramentos técnicos", section_dt, "Desdobramentos técnicos por mês"),
    ("Tabela Profissionalização", section_pf, "Totais Profissionalização por mês"),
    ("Tabela Saúde", section_saude, "Totais Saúde por mês"),
    ("Tabela Educação", section_educacao, "Educação por mês"),
]

section_summaries = {}
for title, section, chart_title in sections:
    totals_df = show_section(title, section, chart_title, st.container())
    section_summaries[title] = totals_df

show_correlation_heatmap(section_summaries)
show_missing_data_heatmap(loaded_data, selected_months)

