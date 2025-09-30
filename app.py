import os
import pandas as pd
import json
import re
import streamlit as st
import tempfile
from langchain_google_genai import GoogleGenerativeAI
from langchain_community.document_loaders import PyPDFLoader

st.set_page_config(
    page_title="FichAI",
    page_icon="💡",
    layout="wide"
)

PROMPT_FICHAMENTO_JSON = """
Sua tarefa é atuar como um pesquisador assistente e extrair dados estruturados de um artigo científico de qualquer área.'
Analise o TEXTO DO ARTIGO fornecido e retorne um objeto JSON válido contendo as seguintes chaves:
- "titulo_artigo": (String) O título completo e exato do artigo.
- "autores": (Lista de Strings) Uma lista com os nomes de todos os autores.
- "ano_publicacao": (String) O ano de publicação do artigo.
- "resumo_ia": (String) Um resumo conciso do artigo em 3 a 4 frases, focando no problema, metodologia e conclusão.
- "palavras_chave_ia": (Lista de Strings) Uma lista com 5 a 10 palavras-chave ou frases-chave técnicas.
- "metodologia_principal": (String) Descreva de forma concisa (1 a 2 frases) a principal metodologia.
- "grande_area_conhecimento": (String) Identifique a grande área e o sub-campo do artigo (ex: 'Direito / Direito Penal', 'Biologia / Ornitologia').

IMPORTANTE: Retorne **apenas** o objeto JSON puro, sem usar blocos de código markdown como ```json ou ```.

TEXTO DO ARTIGO:
{texto_documento}

OBJETO JSON COM OS DADOS EXTRAÍDOS:
"""

@st.cache_resource
def get_llm(api_key):
    os.environ['GOOGLE_API_KEY'] = api_key
    return GoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.0)

def construir_prompt(texto_documento, pergunta_extra=None):
    prompt_base = PROMPT_FICHAMENTO_JSON
    if pergunta_extra:
        prompt_base = prompt_base.replace(
            "OBJETO JSON COM OS DADOS EXTRAÍDOS:",
            f"- \"resposta_personalizada\": (String) Responda também à seguinte pergunta: \"{pergunta_extra}\"\n\nOBJETO JSON COM OS DADOS EXTRAÍDOS:"
        )
    return prompt_base.format(texto_documento=texto_documento[:30000])

def extrair_dados_com_json(llm, texto_documento, pergunta_extra=None):
    prompt_formatado = construir_prompt(texto_documento, pergunta_extra)
    try:
        resposta_llm = llm.invoke(prompt_formatado)
        match = re.search(r'\{[\s\S]*?\}', resposta_llm)
        if match:
            return json.loads(match.group(0))
        else:
            st.warning("A resposta do modelo não continha um JSON reconhecível.")
            return None
    except json.JSONDecodeError:
        st.warning("Não foi possível decodificar o JSON extraído. Revise a formatação da resposta.")
        return None
    except Exception as e:
        st.error(f"Erro na API: {e}")
        return None

# Interface principal
st.title(":bulb: FichAI")
st.subheader("Analisador de artigos científicos com Inteligência Artificial!")

tab_analisador, tab_como_funciona, tab_api_key, tab_sobre = st.tabs([
    "**Analisador**", "**Como Funciona**", "**Como obter uma chave de API?**", "**Quem sou eu?**"
])

with tab_analisador:
    st.header("Análise de Artigos")
    st.markdown("Faça o upload de um ou mais artigos em PDF e receba uma planilha com um resumo estruturado.")
    campo_extra = st.text_input(":mag: Pergunta adicional (opcional)", placeholder="Ex: Qual a hipótese principal testada no estudo?")

    with st.sidebar:
        st.header("Configurações")
        api_key = st.text_input("Sua Chave de API do Google AI", type="password")
        st.markdown("[Obtenha sua chave de API aqui](https://aistudio.google.com/app/apikey)")

    uploaded_files = st.file_uploader("Escolha os arquivos PDF para analisar", type="pdf", accept_multiple_files=True)

    if st.button("Analisar Artigos", disabled=(not uploaded_files or not api_key)):
        dados_compilados = []
        llm = get_llm(api_key)
        barra_progresso = st.progress(0, text="Iniciando análise...")

        for i, uploaded_file in enumerate(uploaded_files):
            nome_arquivo = uploaded_file.name
            barra_progresso.progress((i) / len(uploaded_files), text=f"Processando {nome_arquivo}")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                caminho_tmp = tmp_file.name

            try:
                loader = PyPDFLoader(caminho_tmp)
                documento = loader.load()
                texto_completo = " ".join(page.page_content for page in documento)

                if texto_completo.strip():
                    dados = extrair_dados_com_json(llm, texto_completo, pergunta_extra=campo_extra)
                    if dados:
                        dados['arquivo'] = nome_arquivo
                        dados_compilados.append(dados)
                else:
                    st.warning(f"Não foi extraído texto de '{nome_arquivo}'.")

            except Exception as e:
                st.error(f"Erro ao processar '{nome_arquivo}': {e}")
            finally:
                os.remove(caminho_tmp)

        barra_progresso.progress(1.0, text="Análise concluída!")
        st.session_state['df_resultado'] = pd.DataFrame(dados_compilados)

    if 'df_resultado' in st.session_state and not st.session_state['df_resultado'].empty:
        st.success("Sua análise está pronta!")
        df = st.session_state['df_resultado']

        ordem_colunas = [
            'arquivo', 'titulo_artigo', 'autores', 'ano_publicacao', 
            'grande_area_conhecimento', 'resumo_ia', 
            'palavras_chave_ia', 'metodologia_principal'
        ]
        if campo_extra and 'resposta_personalizada' in df.columns:
            ordem_colunas.append('resposta_personalizada')
        for col in ordem_colunas:
            if col not in df.columns:
                df[col] = "Não encontrado"
        df_final = df[ordem_colunas]

        st.dataframe(df_final)

        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False, sheet_name='Fichamentos')
        st.download_button(
            label=":floppy_disk: Baixar Planilha Excel",
            data=output.getvalue(),
            file_name="relatorio_fichamentos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

#aba 2: Como Funciona
with tab_como_funciona:
    st.header("Como Funciona?")
    st.markdown("""
    Esta ferramenta utiliza o poder de Grandes Modelos de Linguagem (LLMs), especificamente o **Google Gemini**, para realizar uma leitura inteligente e contextual de artigos científicos.
    
    O processo funciona em três passos simples:

    **1. Envio e Leitura (📤 Upload)**
    * Quando você faz o upload de um PDF, o sistema extrai todo o texto do arquivo, preparando-o para a análise.

    **2. Análise com IA (🧠 Processamento)**
    * O texto completo de cada artigo é enviado para o Gemini com um conjunto de instruções precisas (um "prompt").
    * Pedimos à IA que atue como um pesquisador assistente e extraia dados específicos, como título, autores, resumo, metodologia e palavras-chave. A IA não "inventa" informações, ela as localiza e estrutura a partir do texto fornecido, evitando as famosas "alucinações" comuns em modelos de linguagem.

    **3. Geração do Relatório (📊 Download)**
    * Todos os dados estruturados de cada artigo são compilados em uma tabela organizada.
    * Essa tabela é então convertida em uma planilha Excel, pronta para você baixar e utilizar em sua pesquisa, economizando horas de trabalho manua!.
    """)

#aba 3: Como obter uma chave de API?
# aba 3: Como obter uma chave de API?
with tab_api_key:
    st.header("Como obter uma chave de API?")
    
    st.markdown("""
    ### 🧠 O que é uma chave de API?
    Uma **chave de API** (do inglês *Application Programming Interface*) é como uma "senha" que permite que a sua conta acesse recursos de inteligência artificial oferecidos por serviços como o **Google AI**.

    Neste projeto, usamos essa chave para nos conectar ao modelo **Gemini**, responsável por ler os artigos e extrair automaticamente as informações.

    ---
    
    ### 🔧 Para que ela serve neste app?
    A chave permite que você use os recursos do Google AI com **sua própria conta**, evitando que o app fique restrito a um número pequeno de usuários. Ela é usada apenas para processar os artigos — nenhuma informação pessoal ou arquivo é armazenado.

    ---
    
    ### 🚀 Como obter sua chave de API gratuitamente:
    
    > **⚠️ É necessário ter uma conta Google.**
    
    1. Acesse o site [Google AI Studio](https://aistudio.google.com/app/apikey)  
       *(ou clique no link da barra lateral do app)*.
    2. Faça login com sua conta Google.
    3. Clique em **"Create API Key"** (ou “Criar chave de API”).
    4. Copie a chave gerada e cole no campo da barra lateral do app.
    
    ✅ Pronto! Agora é só fazer upload dos artigos e deixar a IA trabalhar por você.
    
    ---
    **Importante:**  
    Guarde sua chave com cuidado. Ela é pessoal e permite o uso dos recursos da sua conta Google AI.
    """)

#aba 4: Quem sou eu?
with tab_sobre:
    st.header("Quem sou eu?")

    # Coloque sua foto na mesma pasta do script e mude o nome do arquivo aqui
    # OU coloque um link para uma foto online
    caminho_da_foto = "https://raw.githubusercontent.com/jadspereira/fichai/main/eu.jpg" # <--- SUBSTITUA ESTE LINK

    col1, col2 = st.columns([1, 3])

    with col1:
        st.image(caminho_da_foto, caption="Jade Pereira", width=250)

    with col2:
        # Edite este texto com a sua apresentação
        st.markdown("""
        ### Jade Pereira
        
        Olá! Eu sou estudante de Licenciatura em Ciências Biológicas e uma entusiasta da aplicação de novas tecnologias para acelerar e aprofundar a pesquisa científica.
        
        Este projeto, **FichAI**, nasceu da minha própria experiência com tarefa de realizar revisões de literatura. Meu objetivo foi criar uma ferramenta intuitiva que pudesse automatizar o trabalho inicial de fichamento, liberando tempo para a parte mais importante: a análise crítica e a geração de novas ideias.
        
        Mas é claro, nenhuma ferramenta substitui o olhar humano. Recomenda-se fortemente que você revise os dados extraídos, especialmente o resumo e as palavras-chave, para garantir que estejam alinhados com o contexto do seu trabalho, beleza?!
        
        Acredito que a união entre a Biologia e a Ciência da Computação tem um potencial imenso para transformar a forma como fazemos ciência.
        """)

    st.markdown("---")
    st.subheader("Contato")
    st.markdown("Tem alguma dúvida, sugestão ou encontrou algum problema? Ficarei feliz em ajudar!")
    st.markdown("📧 **E-mail:** [jade.pereira@ufv.br](mailto:jade.pereira@ufv.br)")
