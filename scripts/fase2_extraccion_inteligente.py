#!/usr/bin/env python3
"""
FASE 2: Extracción Inteligente de Preguntas PAES
Usa Ollama (qwen2.5:3b) para análisis semántico y asociación contextual
"""

import fitz  # PyMuPDF
import json
import os
import sys
import re
import time
import requests
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/gabriel/procesamiento_paes/fase2_extraccion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuración
INPUT_PATH = '/home/gabriel/procesamiento_paes/input_pdfs'
OUTPUT_PATH = '/home/gabriel/procesamiento_paes/output_estructurado'
PROGRESS_FILE = '/home/gabriel/procesamiento_paes/fase2_progress.json'
OLLAMA_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'qwen2.5:3b'
PREGUNTA_SPLIT_RE = re.compile(r'(?m)(?=^\s*\d+[\.\)])')

class ExtractorInteligente:
    def __init__(self, usar_ollama=True, timeout_hours=6):
        self.processed_files = self.load_progress()
        self.processed_count = 0
        self.error_count = 0
        self.usar_ollama = usar_ollama
        self.started_at = time.time()
        self.timeout_seconds = max(1, timeout_hours) * 3600
        
    def load_progress(self):
        """Cargar progreso previo"""
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Progreso cargado: {len(data.get('processed', []))} archivos")
                    return set(data.get('processed', []))
            except Exception as e:
                logger.error(f"Error al cargar progreso: {e}")
        return set()
    
    def save_progress(self):
        """Guardar progreso"""
        try:
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'processed': list(self.processed_files),
                    'total_processed': self.processed_count,
                    'total_errors': self.error_count,
                    'last_update': datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar progreso: {e}")

    def timeout_alcanzado(self):
        """Detiene el lote cuando se supera el tiempo límite."""
        return (time.time() - self.started_at) >= self.timeout_seconds
    
    def consultar_ollama(self, prompt, max_tokens=500):
        """Consultar a Ollama para análisis de texto"""
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    'model': OLLAMA_MODEL,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.1,  # Más determinístico
                        'num_predict': max_tokens,
                        'top_p': 0.9,
                        'top_k': 40
                    }
                },
                timeout=60  # Aumentado a 60s
            )
            if response.status_code == 200:
                return response.json().get('response', '').strip()
            else:
                logger.warning(f"Error Ollama: {response.status_code}")
                return None
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout en Ollama (60s)")
            return None
        except Exception as e:
            logger.warning(f"Error consultando Ollama: {e}")
            return None
    
    def clasificar_materia(self, texto_muestra):
        """Usa Ollama para clasificar la materia del documento"""
        if self.usar_ollama:
            prompt = f"""Clasifica en UNA palabra la materia de este documento educacional PAES chileno.

Texto: {texto_muestra[:400]}

Responde SOLO UNA de estas opciones exactamente:
Matemática
Física
Química
Biología
Lectura
Historia

Respuesta:"""

            respuesta = self.consultar_ollama(prompt, max_tokens=20)
            if respuesta:
                # Normalizar respuesta
                respuesta_lower = respuesta.lower().strip()
                if 'matemática' in respuesta_lower or 'matematica' in respuesta_lower or 'math' in respuesta_lower:
                    # Detectar M1 vs M2 por palabras clave
                    if any(x in texto_muestra.lower() for x in ['probabilidad', 'estadística', 'datos', 'muestra']):
                        return 'Matemática M2'
                    return 'Matemática M1'
                elif 'física' in respuesta_lower or 'fisica' in respuesta_lower:
                    return 'Física'
                elif 'química' in respuesta_lower or 'quimica' in respuesta_lower:
                    return 'Química'
                elif 'biología' in respuesta_lower or 'biologia' in respuesta_lower:
                    return 'Biología'
                elif 'lectura' in respuesta_lower or 'lectora' in respuesta_lower:
                    return 'Comprensión Lectora'
                elif 'historia' in respuesta_lower:
                    return 'Historia'
        
        # Fallback: clasificar por palabras clave
        texto_lower = texto_muestra.lower()
        if any(x in texto_lower for x in ['probabilidad', 'ecuación', 'función', 'matemática']):
            return 'Matemática M1'
        elif any(x in texto_lower for x in ['física', 'fuerza', 'energía', 'velocidad']):
            return 'Física'
        elif any(x in texto_lower for x in ['química', 'átomo', 'mol', 'reacción']):
            return 'Química'
        elif any(x in texto_lower for x in ['biología', 'célula', 'adn', 'especie']):
            return 'Biología'
        elif any(x in texto_lower for x in ['texto', 'lectura', 'párrafo', 'autor']):
            return 'Comprensión Lectora'
        elif any(x in texto_lower for x in ['historia', 'siglo', 'época', 'sociedad']):
            return 'Historia'
        
        return 'Sin clasificar'
    
    def extraer_pregunta_estructurada(self, texto_pregunta):
        """Extrae estructura de pregunta, primero con regex, Ollama como fallback"""
        # Intentar primero con regex (más rápido)
        resultado = self.extraer_pregunta_regex(texto_pregunta)
        
        # Si regex funcionó bien, retornar
        if resultado and resultado.get('numero') and len(resultado.get('alternativas', [])) >= 3:
            return resultado

        # En modo rapido no consultar IA: devolver parseo local.
        if not self.usar_ollama:
            return resultado
        
        # Si regex falló, intentar con Ollama
        logger.debug("Regex falló, intentando con Ollama...")
        prompt = f"""Extrae solo: número de pregunta, enunciado y alternativas.

Pregunta:
{texto_pregunta[:600]}

JSON:"""

        respuesta = self.consultar_ollama(prompt, max_tokens=300)
        
        if respuesta:
            try:
                # Intentar extraer JSON de la respuesta
                json_match = re.search(r'\{.*\}', respuesta, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except:
                pass
        
        # Si todo falló, retornar resultado de regex aunque esté incompleto
        return resultado
    
    def extraer_pregunta_regex(self, texto):
        """Extracción de respaldo usando regex"""
        # Buscar número de pregunta
        num_match = re.search(r'^(\d+)[\.\)]', texto.strip(), re.MULTILINE)
        numero = int(num_match.group(1)) if num_match else None
        
        # Extraer alternativas (soporta alternativas en varias lineas)
        alternativas = []
        alt_pattern = r'(?ms)^\s*([A-E])\)\s*(.*?)(?=^\s*[A-E]\)|\Z)'
        for match in re.finditer(alt_pattern, texto):
            letra, contenido = match.groups()
            limpio = re.sub(r'\s+', ' ', contenido).strip()
            alternativas.append({
                'letra': letra,
                'texto': limpio
            })
        
        # El enunciado es todo antes de las alternativas
        primer_alt = re.search(r'(?m)^\s*[A-E]\)', texto)
        if primer_alt:
            enunciado = texto[:primer_alt.start()].strip()
        else:
            enunciado = texto.strip()
        
        return {
            'numero': numero,
            'enunciado': enunciado,
            'alternativas': alternativas
        }

    def extraer_preguntas_desde_texto_pagina(self, texto_pagina):
        """Divide el texto de una página en bloques de preguntas 1), 2), 3), etc."""
        candidatos = []
        for chunk in PREGUNTA_SPLIT_RE.split(texto_pagina):
            item = chunk.strip()
            if not item:
                continue
            if re.match(r'^\d+[\.\)]', item):
                candidatos.append(item)
        return candidatos

    def es_imagen_util(self, bbox, page_rect):
        """Filtra logos/ornamentos: conserva figuras con tamaño y posición útiles."""
        x0, y0, x1, y1 = bbox
        w = max(0.0, x1 - x0)
        h = max(0.0, y1 - y0)
        area = w * h

        page_w = float(page_rect.width)
        page_h = float(page_rect.height)
        page_area = page_w * page_h

        # Ruido típico: íconos/logos muy pequeños.
        if w < 35 or h < 35 or area < 2500:
            return False

        # Cabecera/pie pequeños suelen ser logo o numeración.
        if y0 < page_h * 0.12 and area < page_area * 0.08:
            return False
        if y1 > page_h * 0.95 and area < page_area * 0.05:
            return False

        return True

    def obtener_imagenes_pagina(self, pagina):
        """Obtiene xref + bbox de imágenes de una página."""
        imagenes = []
        for idx, img in enumerate(pagina.get_images(full=True)):
            try:
                xref = img[0]
                rects = pagina.get_image_rects(xref)
                if not rects:
                    continue
                rect = rects[0]
                imagenes.append({
                    'idx': idx,
                    'xref': xref,
                    'bbox': (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)),
                })
            except Exception:
                continue
        return imagenes
    
    def asociar_imagenes_a_pregunta(self, texto_pregunta, imagenes_guardadas):
        """Asocia figuras cuando el enunciado indica soporte visual."""
        if not imagenes_guardadas:
            return []

        texto = texto_pregunta.lower()
        palabras_figura = [
            'figura', 'gráfico', 'grafico', 'plano', 'diagrama', 'esquema',
            'tabla', 'imagen', 'adjunta'
        ]

        if any(p in texto for p in palabras_figura):
            # Evita asociar demasiadas figuras irrelevantes: conserva las 2 mas grandes.
            ordenadas = sorted(imagenes_guardadas, key=lambda x: x.get('area', 0), reverse=True)
            return [img['file'] for img in ordenadas[:2]]
        return []
    
    def extraer_y_guardar_imagenes_pagina(self, doc, pagina_num, imagenes_info, output_dir, nombre_base):
        """Extrae imágenes útiles una sola vez por página (evita duplicados por pregunta)."""
        guardadas = []

        pagina = doc[pagina_num]
        page_rect = pagina.rect

        for idx, img_info in enumerate(imagenes_info):
            try:
                bbox = img_info['bbox']
                if not self.es_imagen_util(bbox, page_rect):
                    continue

                xref = img_info['xref']
                pix = fitz.Pixmap(doc, xref)

                if pix.n >= 5:
                    pix = fitz.Pixmap(fitz.csRGB, pix)

                img_filename = f"{nombre_base}_p{pagina_num+1}_img{idx}.jpg"
                img_path = os.path.join(output_dir, 'imagenes', img_filename)
                os.makedirs(os.path.dirname(img_path), exist_ok=True)

                pix.save(img_path)
                guardadas.append({
                    'file': img_filename,
                    'bbox': bbox,
                    'area': (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]),
                })
            except Exception as e:
                logger.warning(f"Error al extraer imagen {idx}: {e}")

        return guardadas
    
    def procesar_pdf(self, pdf_path):
        """Procesa un PDF completo con análisis inteligente"""
        try:
            doc = fitz.open(pdf_path)
            nombre_base = Path(pdf_path).stem
            
            # Extraer texto de primera página para clasificar
            primera_pagina = doc[0].get_text()
            materia = self.clasificar_materia(primera_pagina)
            
            logger.info(f"Procesando: {nombre_base} | Materia: {materia}")
            
            # Estructura del resultado
            resultado = {
                'archivo_original': os.path.basename(pdf_path),
                'ruta_original': pdf_path,
                'materia': materia,
                'num_paginas': len(doc),
                'fecha_procesamiento': datetime.now().isoformat(),
                'preguntas': []
            }
            
            preguntas_por_numero = {}

            # Procesar cada página buscando preguntas
            for pag_num in range(len(doc)):
                pagina = doc[pag_num]

                # Texto completo de página para detectar múltiples preguntas en un bloque grande.
                bloques = pagina.get_text("blocks")
                bloques.sort(key=lambda b: (b[1], b[0]))
                texto_pagina = "\n".join(b[4] for b in bloques if len(b) >= 5)

                # Extraer figuras útiles una sola vez por página.
                output_dir = os.path.join(OUTPUT_PATH, materia, nombre_base)
                imagenes_info = self.obtener_imagenes_pagina(pagina)
                imagenes_guardadas = self.extraer_y_guardar_imagenes_pagina(
                    doc, pag_num, imagenes_info, output_dir, nombre_base
                )

                # Parsear todas las preguntas detectables de la página.
                preguntas_texto = self.extraer_preguntas_desde_texto_pagina(texto_pagina)
                for texto_pregunta in preguntas_texto:
                    pregunta_data = self.extraer_pregunta_estructurada(texto_pregunta)
                    if not (pregunta_data and pregunta_data.get('numero')):
                        continue

                    numero = int(pregunta_data['numero'])
                    # Corte de ruido: PAES no deberia tener numeros extremos en un solo cuadernillo.
                    if numero <= 0 or numero > 120:
                        continue

                    alternativas = pregunta_data.get('alternativas', []) or []
                    enunciado = (pregunta_data.get('enunciado') or '').strip()

                    # Filtro de calidad: evita capturar fragmentos/noise de columnas.
                    if len(enunciado) < 20:
                        continue
                    if len(alternativas) < 2:
                        continue

                    pregunta_data['pagina'] = pag_num + 1
                    pregunta_data['imagenes'] = self.asociar_imagenes_a_pregunta(
                        texto_pregunta,
                        imagenes_guardadas,
                    )

                    # Dedupe global por numero: conservar la mejor version por calidad.
                    score = len(alternativas) * 10 + len(enunciado) / 100 + len(pregunta_data['imagenes'])
                    previo = preguntas_por_numero.get(numero)
                    if (not previo) or (score > previo['_score']):
                        pregunta_data['_score'] = score
                        preguntas_por_numero[numero] = pregunta_data

            # Orden final por numero de pregunta.
            resultado['preguntas'] = [
                {k: v for k, v in preguntas_por_numero[num].items() if k != '_score'}
                for num in sorted(preguntas_por_numero.keys())
            ]
            
            doc.close()
            
            # Guardar resultado estructurado
            if resultado['preguntas']:
                output_dir = os.path.join(OUTPUT_PATH, materia, nombre_base)
                os.makedirs(output_dir, exist_ok=True)
                
                json_path = os.path.join(output_dir, f"{nombre_base}_estructurado.json")
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(resultado, f, indent=2, ensure_ascii=False)
                
                logger.info(f"✓ {nombre_base}: {len(resultado['preguntas'])} preguntas extraídas")
                return True
            else:
                logger.warning(f"⚠ {nombre_base}: No se encontraron preguntas")
                return False
                
        except Exception as e:
            logger.error(f"Error procesando {pdf_path}: {e}")
            self.error_count += 1
            return False
    
    def procesar_lote(self, limite=None):
        """Procesar múltiples PDFs"""
        # Encontrar PDFs
        pdfs = []
        for root, dirs, files in os.walk(INPUT_PATH):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdfs.append(os.path.join(root, file))
        
        if limite:
            pdfs = pdfs[:limite]
        
        logger.info(f"Total PDFs a procesar: {len(pdfs)}")
        logger.info(f"Ya procesados: {len(self.processed_files)}")
        logger.info(f"Timeout configurado: {self.timeout_seconds / 3600:.2f} horas")
        
        # Procesar
        guardados_desde_ultimo_save = 0
        for pdf_path in tqdm(pdfs, desc="Extracción inteligente"):
            if self.timeout_alcanzado():
                logger.warning("⏱ Timeout alcanzado, deteniendo procesamiento en lote")
                break

            if pdf_path in self.processed_files:
                continue
            
            if self.procesar_pdf(pdf_path):
                self.processed_files.add(pdf_path)
                self.processed_count += 1
                guardados_desde_ultimo_save += 1
            
            # Guardar progreso cada 5 archivos
            if guardados_desde_ultimo_save >= 5:
                self.save_progress()
                guardados_desde_ultimo_save = 0
        
        self.save_progress()
        logger.info(f"\n✅ Procesamiento completado: {self.processed_count} archivos")
        logger.info(f"Errores: {self.error_count}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Extracción inteligente PAES Fase 2')
    parser.add_argument('--test', type=int, help='Procesar solo N archivos de prueba')
    parser.add_argument('--fast', action='store_true', help='Modo rápido: solo regex, sin Ollama')
    parser.add_argument('--timeout', type=int, default=6, help='Timeout en horas (default: 6)')
    args = parser.parse_args()
    
    # Verificar Ollama solo si no está en modo fast
    if not args.fast:
        try:
            resp = requests.get('http://localhost:11434/api/tags', timeout=5)
            if resp.status_code != 200:
                logger.warning("⚠ Ollama no disponible. Usando modo rápido (solo regex)")
                args.fast = True
            else:
                logger.info("✅ Ollama conectado")
        except:
            logger.warning("⚠ No se puede conectar a Ollama. Usando modo rápido")
            args.fast = True
    else:
        logger.info("⚡ Modo RÁPIDO activado (sin Ollama)")
    
    extractor = ExtractorInteligente(
        usar_ollama=not args.fast,
        timeout_hours=args.timeout,
    )
    extractor.procesar_lote(limite=args.test)

if __name__ == '__main__':
    main()
