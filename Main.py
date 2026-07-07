import base64
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(layout="wide")
st.markdown(
    """
    <style>
        .block-container {
            max-width: 100% !important;
            padding-left: 2rem;
            padding-right: 2rem;
            padding-top: 1rem;
        }
        .section-block {
            background: #f8f9fa;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 1rem 1.2rem 1.2rem;
            margin-bottom: 1.2rem;
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

if not excel_files:
    st.error("Nenhum arquivo LEM encontrado na pasta do projeto.")
    st.stop()

workbooks = []
for path in excel_files:
    year_match = re.search(r"(\d{4})", path.name)
    year = year_match.group(1) if year_match else path.stem
    workbooks.append((year, path))

available_years = [year for year, _ in workbooks]
selected_years = st.sidebar.multiselect("Selecione anos", available_years, default=available_years)
selected_years = [year for year in available_years if year in selected_years]

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

        container.write("Totais por linha por ano:")
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

section_dt = []
section_pf = []
section_saude = []
section_educacao = []

for year, file_path in workbooks:
    if year not in selected_years:
        continue

    try:
        df = pd.read_excel(file_path, header=2)
    except PermissionError:
        st.error(f"Erro: O arquivo {file_path.name} está aberto em outro programa. Feche-o e tente novamente.")
        continue

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

for title, section, chart_title in sections:
    show_section(title, section, chart_title, st.container())

