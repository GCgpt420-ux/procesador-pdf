import fitz  # PyMuPDF
import re
import json
import os
from tqdm import tqdm

def extraer_preguntas_de_pdf(path_pdf):
    doc = fitz.open(path_pdf)
    texto_completo = ""
    
    for pagina in doc:
        # "blocks" ayuda a mantener el orden de lectura en documentos de 2 columnas
        bloques = pagina.get_text("blocks")
        # Ordenamos los bloques: primero por posición vertical (y), luego horizontal (x)
        bloques.sort(key=lambda b: (b[1], b[0])) 
        for b in bloques:
            texto_completo += b[4] + "\n"
    
    # Expresión regular para detectar el inicio de una pregunta (Ej: "1. ", "45) ")
    # Y buscar las alternativas A) B) C) D) E)
    patron_pregunta = r"(\d+[\.\)])\s*(.*?)(?=\s*[A-E][\.\)])"
    patron_alternativas = r"([A-E][\.\)])\s*(.*?)(?=\s*[A-E][\.\)]|\d+[\.\)]|$)"

    # Esto es una simplificación, la lógica de limpieza irá aquí
    # Por ahora, extraigamos el texto bruto para validar
    return texto_completo

# Prueba rápida
# print(extraer_preguntas_de_pdf("input_pdfs/ensayo_demo.pdf"))