#!/usr/bin/env python3
"""
FASE 2: Extracción Inteligente PAES con Marker + Qwen2.5
Arquitectura:
1. Marker: Extrae PDF a Markdown estructurado con imágenes
2. Qwen2.5: Transforma Markdown a JSON de preguntas estructuradas
"""

import json
import os
import sys
import re
import requests
import subprocess
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
import logging
import shutil

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/gabriel/procesamiento_paes/fase2_marker_qwen.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuración
INPUT_PATH = '/home/gabriel/procesamiento_paes/input_pdfs'
OUTPUT_PATH = '/home/gabriel/procesamiento_paes/output_estructurado'
MARKER_TEMP = '/home/gabriel/procesamiento_paes/marker_temp'
PROGRESS_FILE = '/home/gabriel/procesamiento_paes/fase2_marker_progress.json'
OLLAMA_URL = 'http://localhost:11434/api/generate'
OLLAMA_MODEL = 'qwen2.5:3b'
TIMEOUT_HOURS = 6


class ExtractorMarkerQwen:
    def __init__(self):
        self.start_time = datetime.now()
        self.processed_files = self.load_progress()
        self.processed_count = 0
        self.error_count = 0
        os.makedirs(MARKER_TEMP, exist_ok=True)
        os.makedirs(OUTPUT_PATH, exist_ok=True)
        
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
                    'last_update': datetime.now().isoformat(),
                    'elapsed_minutes': (datetime.now() - self.start_time).total_seconds() / 60
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar progreso: {e}")
    
    def check_timeout(self):
        """Verificar timeout"""
        elapsed_hours = (datetime.now() - self.start_time).total_seconds() / 3600
        if elapsed_hours > TIMEOUT_HOURS:
            logger.warning(f"⏱️ TIMEOUT: {elapsed_hours:.2f}h. Deteniendo...")
            return True
        return False
    
    def extraer_con_marker(self, pdf_path):
        """Usa Marker para extraer PDF a Markdown + imágenes"""
        try:
            nombre_base = Path(pdf_path).stem
            
            # Marker necesita carpeta, creamos temporal con symlink
            temp_input = os.path.join(MARKER_TEMP, 'input_temp')
            os.makedirs(temp_input, exist_ok=True)
            
            # Crear symlink al PDF
            pdf_link = os.path.join(temp_input, os.path.basename(pdf_path))
            if os.path.exists(pdf_link):
                os.remove(pdf_link)
            os.symlink(pdf_path, pdf_link)
            
            output_dir = os.path.join(MARKER_TEMP, 'output_temp', nombre_base)
            os.makedirs(output_dir, exist_ok=True)
            
            # Ejecutar marker
            logger.debug(f"Ejecutando Marker en: {pdf_path}")
            cmd = [
                'marker',
                temp_input,
                '--output_dir', output_dir,
                '--output_format', 'markdown',  # markdown es más rápido que json
                '--max_files', '1',
                '--disable_multiprocessing',
                '--disable_image_extraction',  # Más rápido sin extraer imágenes
                '--lowres_image_dpi', '72'  # Menor resolución = más rápido
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180  # Reducido a 3 minutos
            )
            
            if result.returncode != 0:
                logger.error(f"Marker falló: {result.stderr[:300]}")
                return None
            
            # Buscar archivo markdown generado
            md_files = list(Path(output_dir).rglob('*.md'))
            if not md_files:
                logger.warning(f"Marker no generó markdown para {nombre_base}")
                return None
            
            md_file = md_files[0]
            with open(md_file, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            # Buscar imágenes si las hay
            imagenes = []
            img_dir = Path(output_dir) / 'images'
            if img_dir.exists():
                imagenes = [str(f.name) for f in img_dir.glob('*') if f.is_file()]
            
            return {
                'markdown': markdown_content,
                'imagenes': imagenes,
                'output_dir': output_dir
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"Marker timeout en {pdf_path}")
            return None
        except Exception as e:
            logger.error(f"Error en Marker: {e}")
            return None
        finally:
            # Limpiar temp input
            try:
                if os.path.exists(temp_input):
                    shutil.rmtree(temp_input)
            except:
                pass
    
    def consultar_qwen(self, prompt, max_tokens=1000):
        """Consultar Qwen2.5 vía Ollama"""
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    'model': OLLAMA_MODEL,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.1,
                        'num_predict': max_tokens,
                        'top_p': 0.9
                    }
                },
                timeout=120  # 2 minutos
            )
            
            if response.status_code == 200:
                return response.json().get('response', '').strip()
            else:
                logger.warning(f"Qwen error HTTP {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            logger.warning("Qwen timeout")
            return None
        except Exception as e:
            logger.warning(f"Error en Qwen: {e}")
            return None
    
    def clasificar_materia_qwen(self, markdown_muestra):
        """Usa Qwen para clasificar la materia"""
        prompt = f"""Clasifica la materia de este documento PAES chileno.

Contenido:
{markdown_muestra[:600]}

Responde SOLO UNA palabra de estas opciones:
- Matemática
- Física
- Química
- Biología
- Lectura
- Historia

Materia:"""
        
        respuesta = self.consultar_qwen(prompt, max_tokens=20)
        if not respuesta:
            return self.clasificar_fallback(markdown_muestra)
        
        # Normalizar
        resp_lower = respuesta.lower().strip()
        if 'matemá' in resp_lower or 'math' in resp_lower:
            # Detectar M1 vs M2
            if any(x in markdown_muestra.lower() for x in ['probabilidad', 'estadística', 'variable aleatoria', 'distribución']):
                return 'Matemática M2'
            return 'Matemática M1'
        elif 'física' in resp_lower or 'fisic' in resp_lower:
            return 'Física'
        elif 'química' in resp_lower or 'quimic' in resp_lower:
            return 'Química'
        elif 'biolog' in resp_lower:
            return 'Biología'
        elif 'lectura' in resp_lower or 'lector' in resp_lower:
            return 'Comprensión Lectora'
        elif 'historia' in resp_lower:
            return 'Historia'
        
        return self.clasificar_fallback(markdown_muestra)
    
    def clasificar_fallback(self, texto):
        """Clasificación por palabras clave"""
        texto_lower = texto.lower()
        if any(x in texto_lower for x in ['ecuación', 'función', 'logaritmo', 'trigonometría']):
            return 'Matemática M1'
        elif any(x in texto_lower for x in ['fuerza', 'energía', 'movimiento', 'onda']):
            return 'Física'
        elif any(x in texto_lower for x in ['átomo', 'mol', 'reacción', 'enlace']):
            return 'Química'
        elif any(x in texto_lower for x in ['célula', 'gen', 'especie', 'ecosistema']):
            return 'Biología'
        elif any(x in texto_lower for x in ['texto', 'párrafo', 'autor', 'lectura']):
            return 'Comprensión Lectora'
        elif any(x in texto_lower for x in ['siglo', 'época', 'revolución', 'sociedad']):
            return 'Historia'
        return 'Sin clasificar'
    
    def extraer_preguntas_qwen(self, markdown_content):
        """Usa Qwen para extraer preguntas del markdown"""
        prompt = f"""Extrae TODAS las preguntas de este documento PAES en formato JSON.

Markdown:
{markdown_content[:3000]}

Para cada pregunta extrae:
- numero: número de la pregunta
- enunciado: texto completo del enunciado
- alternativas: array de objetos [{{"letra": "A", "texto": "..."}}, ...]
- tiene_imagen: true/false si menciona "figura adjunta" o similar

Responde SOLO con un JSON válido con array "preguntas":
{{"preguntas": [...]}}
"""
        
        respuesta = self.consultar_qwen(prompt, max_tokens=2000)
        if not respuesta:
            logger.warning("Qwen no respondió, usando extracción regex")
            return self.extraer_preguntas_regex(markdown_content)
        
        # Intentar parsear JSON
        try:
            # Buscar JSON en la respuesta
            json_match = re.search(r'\{.*"preguntas".*\}', respuesta, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                if 'preguntas' in data and isinstance(data['preguntas'], list):
                    logger.info(f"Qwen extrajo {len(data['preguntas'])} preguntas")
                    return data['preguntas']
        except json.JSONDecodeError as e:
            logger.warning(f"Error parseando JSON de Qwen: {e}")
        
        # Fallback a regex
        return self.extraer_preguntas_regex(markdown_content)
    
    def extraer_preguntas_regex(self, markdown):
        """Fallback: extracción con regex"""
        preguntas = []
        
        # Buscar bloques que empiecen con número
        patron = r'^(\d+)[\.)\s]+(.+?)(?=^\d+[\.)\s]|$)'
        bloques = re.finditer(patron, markdown, re.MULTILINE | re.DOTALL)
        
        for match in bloques:
            numero = int(match.group(1))
            contenido = match.group(2).strip()
            
            # Extraer alternativas
            alternativas = []
            patron_alt = r'([A-E])\)\s*(.+?)(?=[A-E]\)|$)'
            for alt_match in re.finditer(patron_alt, contenido):
                alternativas.append({
                    'letra': alt_match.group(1),
                    'texto': alt_match.group(2).strip()
                })
            
            # Enunciado es todo antes de las alternativas
            if alternativas:
                enunciado = contenido.split(alternativas[0]['letra'] + ')')[0].strip()
            else:
                enunciado = contenido
            
            # Detectar si menciona figura
            tiene_imagen = bool(re.search(r'figura|imagen|gráfico|diagrama', enunciado, re.IGNORECASE))
            
            preguntas.append({
                'numero': numero,
                'enunciado': enunciado[:500],  # Limitar tamaño
                'alternativas': alternativas,
                'tiene_imagen': tiene_imagen
            })
        
        return preguntas
    
    def procesar_pdf(self, pdf_path):
        """Pipeline completo: Marker → Qwen → JSON estructurado"""
        try:
            nombre_base = Path(pdf_path).stem
            logger.info(f"📄 Procesando: {nombre_base}")
            
            # PASO 1: Marker extrae PDF
            marker_data = self.extraer_con_marker(pdf_path)
            if not marker_data:
                logger.error(f"❌ Marker falló en {nombre_base}")
                self.error_count += 1
                return False
            
            markdown = marker_data['markdown']
            logger.debug(f"✓ Marker extrajo {len(markdown)} caracteres")
            
            # PASO 2: Clasificar materia con Qwen
            materia = self.clasificar_materia_qwen(markdown[:1000])
            logger.info(f"📚 Materia: {materia}")
            
            # PASO 3: Extraer preguntas con Qwen
            preguntas = self.extraer_preguntas_qwen(markdown)
            if not preguntas:
                logger.warning(f"⚠ No se encontraron preguntas en {nombre_base}")
                return False
            
            logger.info(f"✓ Extraídas {len(preguntas)} preguntas")
            
            # PASO 4: Guardar resultado estructurado
            output_dir = os.path.join(OUTPUT_PATH, materia, nombre_base)
            os.makedirs(output_dir, exist_ok=True)
            
            # Copiar imágenes
            if marker_data['imagenes']:
                img_output = os.path.join(output_dir, 'imagenes')
                os.makedirs(img_output, exist_ok=True)
                for img_rel in marker_data['imagenes']:
                    src = os.path.join(marker_data['output_dir'], img_rel)
                    dst = os.path.join(img_output, Path(img_rel).name)
                    if os.path.exists(src):
                        shutil.copy2(src, dst)
            
            # Guardar JSON estructurado
            resultado = {
                'archivo_original': os.path.basename(pdf_path),
                'ruta_original': pdf_path,
                'materia': materia,
                'fecha_procesamiento': datetime.now().isoformat(),
                'total_preguntas': len(preguntas),
                'preguntas': preguntas,
                'markdown_completo': markdown[:5000],  # Muestra
                'imagenes_disponibles': marker_data['imagenes']
            }
            
            json_path = os.path.join(output_dir, f"{nombre_base}_estructurado.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(resultado, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ {nombre_base}: {len(preguntas)} preguntas → {json_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error procesando {pdf_path}: {e}")
            self.error_count += 1
            return False
        finally:
            # Limpiar temp de marker
            try:
                temp_out = os.path.join(MARKER_TEMP, 'output_temp', Path(pdf_path).stem)
                if os.path.exists(temp_out):
                    shutil.rmtree(temp_out)
            except:
                pass
    
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
        
        logger.info(f"📦 Total PDFs: {len(pdfs)}")
        logger.info(f"✓ Ya procesados: {len(self.processed_files)}")
        logger.info(f"⏳ Pendientes: {len([p for p in pdfs if p not in self.processed_files])}")
        
        # Procesar
        for pdf_path in tqdm(pdfs, desc="Extracción Marker+Qwen"):
            if self.check_timeout():
                break
            
            if pdf_path in self.processed_files:
                continue
            
            if self.procesar_pdf(pdf_path):
                self.processed_files.add(pdf_path)
                self.processed_count += 1
            
            # Guardar cada 3 archivos
            if self.processed_count % 3 == 0:
                self.save_progress()
        
        self.save_progress()
        
        logger.info("\n" + "="*60)
        logger.info(f"✅ COMPLETADO")
        logger.info(f"Procesados: {self.processed_count}")
        logger.info(f"Errores: {self.error_count}")
        logger.info(f"Tiempo: {(datetime.now() - self.start_time).total_seconds() / 60:.1f} min")
        logger.info("="*60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Extracción PAES: Marker + Qwen2.5')
    parser.add_argument('--test', type=int, help='Procesar solo N archivos')
    parser.add_argument('--timeout', type=int, default=6, help='Timeout en horas')
    args = parser.parse_args()
    
    global TIMEOUT_HOURS
    TIMEOUT_HOURS = args.timeout
    
    # Verificar Ollama
    try:
        resp = requests.get('http://localhost:11434/api/tags', timeout=5)
        if resp.status_code == 200:
            logger.info("✅ Ollama/Qwen conectado")
        else:
            logger.warning("⚠ Ollama no responde correctamente")
    except:
        logger.error("❌ Ollama no disponible. Inicia con: ollama serve")
        sys.exit(1)
    
    extractor = ExtractorMarkerQwen()
    extractor.procesar_lote(limite=args.test)


if __name__ == '__main__':
    main()
