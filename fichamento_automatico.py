# -*- coding: utf-8 -*-
"""
Analisador Universal de Artigos v3.0

Esta versão combina a otimização de API com um prompt genérico, permitindo
extrair dados estruturados de artigos de QUALQUER área do conhecimento,
gerando um relatório quantitativo e qualitativo em Excel.
"""
import os
import pandas as pd
import getpass
import json
import time
from langchain_google_genai import GoogleGenerativeAI
from langchain_community.document_loaders import PyPDFLoader
from dotenv import load_dotenv

# --- CONFIGURAÇÕES ---
PASTA_ENTRADA = 'artigos_pdf'
ARQUIVO_SAIDA = 'relatorio_analise_universal.xlsx'

# --- CARREGAMENTO DA CHAVE DE API (do arquivo .env) ---
load_dotenv()
if 'GOOGLE_API_KEY' not in os.environ or not os.environ['GOOGLE_API_KEY']:
    print("ERRO: Chave 'GOOGLE_API_KEY' não encontrada no arquivo .env.")
    os.environ['GOOGLE_API_KEY'] = input("Cole sua Google AI API Key e pressione Enter: ")
print("Chave de API carregada.")

# --- O NOVO PROMPT UNIVERSAL ---
# Este prompt instrui o LLM a extrair um conjunto de dados genéricos.
PROMPT_FICHAMENTO_JSON = """
Sua tarefa é atuar como um pesquisador assistente e extrair dados estruturados de um artigo científico de qualquer área.
Analise o TEXTO DO ARTIGO fornecido e retorne um objeto JSON válido contendo as seguintes chaves:
- "titulo_artigo": (String) O título completo e exato do artigo.
- "autores": (Lista de Strings) Uma lista com os nomes de todos os autores, como aparecem no artigo.
- "ano_publicacao": (String) O ano de publicação do artigo. Se não encontrar, retorne "Não encontrado".
- "resumo_ia": (String) Um resumo conciso do artigo em 3 a 4 frases, focando no problema central, metodologia e conclusão principal.
- "palavras_chave_ia": (Lista de Strings) Uma lista com 5 a 10 palavras-chave ou frases-chave que melhor representem os conceitos centrais do artigo.
- "metodologia_principal": (String) Descreva de forma concisa (1 a 2 frases) a principal metodologia empregada na pesquisa.
- "grande_area_conhecimento": (String) Identifique a grande área do conhecimento e o sub-campo específico deste artigo (ex: 'Direito / Direito Penal', 'Engenharia / Engenharia Civil', 'História / História do Brasil', 'Biologia / Ornitologia'). Retorne a resposta no formato 'Área Principal / Sub-área'.

TEXTO DO ARTIGO:
{texto_documento}

OBJETO JSON COM OS DADOS EXTRAÍDOS:
"""

def extrair_dados_com_json(texto_documento):
    """Faz uma única chamada à API pedindo um JSON com todos os dados."""
    # Usamos temperatura 0.0 para respostas mais factuais e consistentes
    llm = GoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.0)
    
    prompt_formatado = PROMPT_FICHAMENTO_JSON.format(texto_documento=texto_documento[:30000]) # Aumentando um pouco o limite de texto
    
    print("   -> Fazendo a 'Super-Pergunta' para extrair todos os dados de uma vez...")
    resposta_llm = llm.invoke(prompt_formatado)
    
    try:
        resposta_limpa = resposta_llm.strip().replace('```json', '').replace('```', '')
        dados_json = json.loads(resposta_limpa)
        return dados_json
    except json.JSONDecodeError:
        print("   -> ALERTA: O modelo não retornou um JSON válido. A resposta foi:", resposta_llm)
        return None

if __name__ == "__main__":
    dados_compilados = []
    arquivos_pdf = [f for f in os.listdir(PASTA_ENTRADA) if f.lower().endswith('.pdf')]
    print(f"Foram encontrados {len(arquivos_pdf)} artigos para análise.")

    for i, nome_arquivo in enumerate(arquivos_pdf):
        print(f"\n--- Processando Artigo {i+1}/{len(arquivos_pdf)}: {nome_arquivo} ---")
        caminho_completo = os.path.join(PASTA_ENTRADA, nome_arquivo)
        
        try:
            loader = PyPDFLoader(caminho_completo)
            documento = loader.load()
            texto_completo = " ".join(page.page_content for page in documento)
            
            if not texto_completo.strip():
                print(f"  -> ALERTA: Nenhum texto útil extraído de '{nome_arquivo}'.")
                continue

            dados_extraidos = extrair_dados_com_json(texto_completo)
            
            if dados_extraidos:
                dados_extraidos['arquivo'] = nome_arquivo
                dados_compilados.append(dados_extraidos)

            time.sleep(1) # Pausa para ser gentil com a API

        except Exception as e:
            print(f"  -> ERRO CRÍTICO ao processar '{nome_arquivo}': {e}")
    
    if dados_compilados:
        print("\nCompilando resultados na planilha Excel...")
        df = pd.DataFrame(dados_compilados)
        
        # Define a ordem ideal das colunas para o relatório final
        ordem_colunas = [
            'arquivo', 'titulo_artigo', 'autores', 'ano_publicacao', 
            'grande_area_conhecimento', 'resumo_ia', 'palavras_chave_ia', 
            'metodologia_principal'
        ]
        
        # Garante que todas as colunas esperadas existam, preenchendo com "Não encontrado" se faltar
        for col in ordem_colunas:
            if col not in df.columns:
                df[col] = "Não encontrado"

        df = df[ordem_colunas] # Reordena o DataFrame
        df.to_excel(ARQUIVO_SAIDA, index=False, engine='openpyxl')
        print(f"Análise concluída! Planilha salva em '{ARQUIVO_SAIDA}'.")
    else:
        print("Nenhuma análise pôde ser gerada.")