#!/usr/bin/env python3
"""
Procesador por lotes de PDFs PAES
Procesa todos los PDFs y se detiene automáticamente después de 6 horas
"""

import fitz  # PyMuPDF
import json
import os
import sys
import time
import re
from pathlib import Path
from datetime import datetime, timedelta
from tqdm import tqdm
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/gabriel/procesamiento_paes/batch_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuración
INPUT_PATH = '/home/gabriel/procesamiento_paes/input_pdfs'
OUTPUT_PATH = '/home/gabriel/procesamiento_paes/output_json'
PROGRESS_FILE = '/home/gabriel/procesamiento_paes/batch_progress.json'
TIMEOUT_HOURS = 6
MAX_RUNTIME = TIMEOUT_HOURS * 3600  # segundos

class BatchProcessor:
    def __init__(self):
        self.start_time = time.time()
        self.processed_count = 0
        self.error_count = 0
        self.processed_files = self.load_progress()
        
    def load_progress(self):
        """Cargar progreso previo"""
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Progreso cargado: {len(data.get('processed', []))} PDFs ya procesados")
                    return set(data.get('processed', []))
            except Exception as e:
                logger.error(f"Error al cargar progreso: {e}")
        return set()
    
    def save_progress(self):
        """Guardar progreso actual"""
        try:
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'processed': list(self.processed_files),
                    'total_processed': self.processed_count,
                    'total_errors': self.error_count,
                    'last_update': datetime.now().isoformat(),
                    'elapsed_time_seconds': time.time() - self.start_time
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error al guardar progreso: {e}")
    
    def check_timeout(self):
        """Verificar si se alcanzó el timeout de 6 horas"""
        elapsed = time.time() - self.start_time
        if elapsed > MAX_RUNTIME:
            logger.warning(f"⏱️ TIMEOUT ALCANZADO: {elapsed/3600:.2f} horas. Deteniendo...")
            return True
        return False
    
    def extraer_pdf(self, path_pdf):
        """Extraer información de un PDF"""
        try:
            doc = fitz.open(path_pdf)
            metadata = doc.metadata
            
            contenido = {
                'filename': os.path.basename(path_pdf),
                'ruta_original': path_pdf,
                'num_paginas': len(doc),
                'titulo': metadata.get('title', ''),
                'autor': metadata.get('author', ''),
                'fecha_procesamiento': datetime.now().isoformat(),
                'paginas': []
            }
            
            for idx, pagina in enumerate(doc):
                # Extraer texto respetando estructura
                bloques = pagina.get_text("blocks")
                bloques.sort(key=lambda b: (b[1], b[0]))
                
                texto_pagina = "\n".join([b[4] for b in bloques])
                
                # Extraer imágenes
                imagenes = []
                for img_index, img in enumerate(pagina.get_images()):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        img_data = {
                            'index': img_index,
                            'tipo': pix.n,
                            'tamanio_kb': len(pix.tobytes()) / 1024
                        }
                        imagenes.append(img_data)
                    except:
                        pass
                
                contenido['paginas'].append({
                    'numero': idx + 1,
                    'texto': texto_pagina[:1000],  # Primeros 1000 caracteres
                    'cantidad_caracteres': len(texto_pagina),
                    'imagenes': imagenes
                })
            
            doc.close()
            return contenido
        
        except Exception as e:
            logger.error(f"Error al procesar {path_pdf}: {str(e)}")
            self.error_count += 1
            return None
    
    def guardar_output(self, contenido, nombre_carpeta):
        """Guardar contenido extraído en la estructura de salida"""
        try:
            # Limpiar nombre de carpeta
            nombre_seguro = nombre_carpeta.replace('/', '_').replace('\\', '_')
            output_dir = os.path.join(OUTPUT_PATH, nombre_seguro)
            os.makedirs(output_dir, exist_ok=True)
            
            # Guardar JSON
            nombre_base = contenido['filename'].replace('.pdf', '')
            json_path = os.path.join(output_dir, f"{nombre_base}_meta.json")
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(contenido, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            logger.error(f"Error al guardar output: {e}")
            return False
    
    def procesar_pdfs(self):
        """Procesar todos los PDFs de entrada"""
        logger.info(f"Iniciando procesamiento por lote... Timeout: {TIMEOUT_HOURS} horas")
        
        # Encontrar todos los PDFs
        pdfs = []
        for root, dirs, files in os.walk(INPUT_PATH):
            for file in files:
                if file.lower().endswith('.pdf'):
                    full_path = os.path.join(root, file)
                    pdfs.append(full_path)
        
        total_pdfs = len(pdfs)
        logger.info(f"Total de PDFs encontrados: {total_pdfs}")
        logger.info(f"Ya procesados: {len(self.processed_files)}")
        logger.info(f"Pendientes: {total_pdfs - len(self.processed_files)}")
        
        # Procesar con barra de progreso
        with tqdm(total=total_pdfs, desc="Procesando PDFs", initial=len(self.processed_files)) as pbar:
            for pdf_path in pdfs:
                # Verificar timeout cada iteración
                if self.check_timeout():
                    logger.warning("⏹️ Deteniendo por timeout...")
                    break
                
                # Saltar si ya fue procesado
                if pdf_path in self.processed_files:
                    pbar.update(1)
                    continue
                
                # Procesar PDF
                contenido = self.extraer_pdf(pdf_path)
                if contenido:
                    # Determinar carpeta de salida por nombre
                    nombre_carpeta = os.path.basename(os.path.dirname(pdf_path))
                    if self.guardar_output(contenido, nombre_carpeta):
                        self.processed_files.add(pdf_path)
                        self.processed_count += 1
                
                pbar.update(1)
                
                # Guardar progreso cada 10 archivos
                if self.processed_count % 10 == 0:
                    self.save_progress()
        
        # Guardar progreso final
        self.save_progress()
        
        # Mostrar resumen
        elapsed_hours = (time.time() - self.start_time) / 3600
        logger.info("\n" + "="*60)
        logger.info(f"✅ PROCESAMIENTO COMPLETADO")
        logger.info(f"Tiempo transcurrido: {elapsed_hours:.2f} horas")
        logger.info(f"PDFs procesados: {self.processed_count}")
        logger.info(f"Errores: {self.error_count}")
        logger.info(f"Total en base de datos: {len(self.processed_files)}")
        logger.info("="*60)

def main():
    try:
        processor = BatchProcessor()
        processor.procesar_pdfs()
    except KeyboardInterrupt:
        logger.info("🛑 Interrumpido por usuario")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Error crítico: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
