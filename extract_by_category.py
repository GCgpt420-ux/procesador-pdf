#!/usr/bin/env python3
"""
Extractor por categoría: Separa preguntas vs materia vs mixto.
Genera JSONs intermedios para procesar con Ollama+GPU mañana.

Estructura:
output_json/
├── DESAFIOS/          → preguntas_limpias.jsonl
├── TORPEDO/           → ejercicios_limpios.jsonl
├── RESUMENES/         → materia_estudio.jsonl
├── GUIAS/             → contenido_mixto.jsonl (necesita clasificación)
└── SOLUCIONARIOS/     → ignorado (sin enunciados)
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any


class DataExtractor:
    def __init__(self, output_json_dir: str):
        self.output_dir = Path(output_json_dir)
        self.categories = {
            'preguntas_limpias': [],      # DESAFIOS + TORPEDO de buena calidad
            'ejercicios_limpios': [],     # TORPEDO variados
            'materia_estudio': [],        # RESUMENES sin numeración
            'contenido_mixto': [],        # GUIAS: mezcla que necesita clasificación
            'metadata': {
                'total_archivos': 0,
                'archivos_procesados': 0,
                'archivos_ignorados': 0
            }
        }
    
    def classify_folder(self, folder_path: Path) -> str:
        """Clasifica carpeta padre de archivo JSON."""
        parent = folder_path.parent.name.upper()
        grandparent = folder_path.parent.parent.name.upper()
        
        if 'DESAFIO' in parent or 'DESAFIO' in grandparent:
            return 'DESAFIOS'
        elif 'TORPEDO' in parent:
            return 'TORPEDO'
        elif 'RESUMEN' in parent or 'RESUMEN' in grandparent:
            return 'RESUMENES'
        elif 'GUIA' in parent or 'GUIA' in grandparent:
            return 'GUIAS'
        elif 'SOLUCIONARIO' in parent or 'SOLUCIONARIO' in grandparent:
            return 'SOLUCIONARIOS'
        else:
            return 'OTROS'
    
    def extract_preguntas(self, text: str) -> List[Dict[str, Any]]:
        """
        Extrae preguntas numeradas (1), 2), 3), etc) con opciones A/B/C/D/E
        Retorna lista de preguntas parseadas.
        """
        preguntas = []
        
        # Busca sección RESPUESTAS para mapping
        respuestas_match = re.search(r'RESPUESTA[S]?.*?\n(.*?)(?=$|\Z)', text, re.DOTALL | re.IGNORECASE)
        respuestas = {}
        if respuestas_match:
            resp_text = respuestas_match.group(1)
            pares = re.findall(r'(\d+)\s*[.)]\s*([A-E])', resp_text)
            respuestas = {int(num): letra for num, letra in pares}
        
        # Extrae bloques de preguntas
        # Patrón: número) o número. seguido de texto y opciones
        bloques = re.split(r'\n(?=\d+[.)]\s)', text)
        
        for bloque in bloques:
            if not bloque.strip():
                continue
            
            # Extrae número pregunta
            match_num = re.match(r'(\d+)[.)]\s*(.+?)(?=\n[A-E][.)]\s|$)', bloque, re.DOTALL)
            if not match_num:
                continue
            
            q_num = int(match_num.group(1))
            enunciado = match_num.group(2).strip()
            
            # Normaliza espacios pero preserva estructura
            enunciado = re.sub(r'\s+', ' ', enunciado)
            
            # Descarta enunciados muy cortos (OCR corrupto)
            if len(enunciado) < 10:
                continue
            
            # Extrae opciones A/B/C/D/E
            opciones = []
            opciones_match = re.finditer(r'([A-E])[.)]\s*(.+?)(?=\n[A-E][.)]\s|$)', bloque, re.DOTALL)
            
            for opt_match in opciones_match:
                label = opt_match.group(1)
                texto = opt_match.group(2).strip()
                texto = re.sub(r'\s+', ' ', texto)
                
                if len(texto) >= 2:  # Valida longitud mínima
                    is_correct = respuestas.get(q_num) == label
                    opciones.append({
                        'label': label,
                        'texto': texto,
                        'es_correcta': is_correct
                    })
            
            # Agrega pregunta si tiene 4+ opciones válidas
            if len(opciones) >= 4:
                preguntas.append({
                    'numero': q_num,
                    'enunciado': enunciado,
                    'opciones': opciones[:5],  # Max 5
                    'fuente_archivo': None,  # Se llena después
                    'calidad': 'alta' if len(enunciado) > 50 else 'media'
                })
        
        return preguntas
    
    def is_materia_content(self, text: str) -> bool:
        """Detecta si es contenido de estudio (no preguntas)."""
        # Si tiene muchas líneas de texto seguidas sin números de pregunta
        lineas = text.split('\n')
        parrafos_textuales = sum(1 for l in lineas if len(l.strip()) > 80)
        tiene_preguntas = len(re.findall(r'^\d+[.)]\s', text, re.MULTILINE)) > 0
        
        return parrafos_textuales > 5 and not tiene_preguntas
    
    def process_json(self, json_file: Path) -> None:
        """Procesa un archivo JSON y lo clasifica."""
        self.categories['metadata']['total_archivos'] += 1
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"  ⚠️  Error leyendo {json_file.name}: {e}")
            self.categories['metadata']['archivos_ignorados'] += 1
            return
        
        # Combina texto de todas las páginas
        texto_completo = '\n'.join([p.get('texto', '') for p in data.get('paginas', [])])
        if not texto_completo.strip():
            self.categories['metadata']['archivos_ignorados'] += 1
            return
        
        # Clasifica
        tipo = self.classify_folder(json_file)
        
        if tipo == 'DESAFIOS':
            preguntas = self.extract_preguntas(texto_completo)
            if preguntas:
                for p in preguntas:
                    p['fuente_archivo'] = data.get('filename', 'unknown')
                    p['categoria_origen'] = 'DESAFIOS'
                self.categories['preguntas_limpias'].extend(preguntas)
                self.categories['metadata']['archivos_procesados'] += 1
        
        elif tipo == 'TORPEDO':
            preguntas = self.extract_preguntas(texto_completo)
            if preguntas:
                for p in preguntas:
                    p['fuente_archivo'] = data.get('filename', 'unknown')
                    p['categoria_origen'] = 'TORPEDO'
                self.categories['ejercicios_limpios'].extend(preguntas)
                self.categories['metadata']['archivos_procesados'] += 1
        
        elif tipo == 'RESUMENES':
            # Intenta extraer preguntas primero
            preguntas = self.extract_preguntas(texto_completo)
            if preguntas:
                for p in preguntas:
                    p['fuente_archivo'] = data.get('filename', 'unknown')
                    p['categoria_origen'] = 'RESUMENES'
                self.categories['ejercicios_limpios'].extend(preguntas)
            else:
                # Es contenido de estudio puro
                self.categories['materia_estudio'].append({
                    'archivo': data.get('filename', 'unknown'),
                    'titulo': data.get('titulo', 'Sin título'),
                    'contenido': texto_completo[:2000],  # Primeros 2000 chars
                    'num_paginas': len(data.get('paginas', [])),
                    'categoria_origen': 'RESUMENES'
                })
            self.categories['metadata']['archivos_procesados'] += 1
        
        elif tipo == 'GUIAS':
            # Contenido mixto que necesita clasificación con Ollama
            self.categories['contenido_mixto'].append({
                'archivo': data.get('filename', 'unknown'),
                'paginas': [
                    {
                        'numero': p.get('numero'),
                        'texto': p.get('texto', '')[:1500]  # Primeros 1500 chars
                    }
                    for p in data.get('paginas', [])
                ],
                'categoria_origen': 'GUIAS'
            })
            self.categories['metadata']['archivos_procesados'] += 1
        
        else:
            self.categories['metadata']['archivos_ignorados'] += 1
    
    def run(self) -> None:
        """Ejecuta extracción de todos los JSONs."""
        print("\n🔄 Extrayendo datos por categoría...\n")
        
        json_files = list(self.output_dir.rglob('*_meta.json'))
        print(f"   Total archivos JSON encontrados: {len(json_files)}\n")
        
        for i, json_file in enumerate(sorted(json_files)):
            if (i + 1) % 50 == 0:
                print(f"   [{i+1}/{len(json_files)}] Procesados...")
            self.process_json(json_file)
        
        self._save_results()
    
    def _save_results(self) -> None:
        """Guarda resultados en JSONLs."""
        output_path = self.output_dir.parent / 'processed_data'
        output_path.mkdir(exist_ok=True)
        
        print(f"\n📁 Guardando en {output_path}/\n")
        
        # Preguntas limpias (DESAFIOS)
        clean_file = output_path / 'desafios_preguntas.jsonl'
        with open(clean_file, 'w', encoding='utf-8') as f:
            for p in self.categories['preguntas_limpias']:
                f.write(json.dumps(p, ensure_ascii=False) + '\n')
        print(f"✅ {clean_file.name}: {len(self.categories['preguntas_limpias'])} preguntas")
        
        # Ejercicios limpios (TORPEDO + RESUMENES)
        ejerc_file = output_path / 'ejercicios_preguntas.jsonl'
        with open(ejerc_file, 'w', encoding='utf-8') as f:
            for p in self.categories['ejercicios_limpios']:
                f.write(json.dumps(p, ensure_ascii=False) + '\n')
        print(f"✅ {ejerc_file.name}: {len(self.categories['ejercicios_limpios'])} ejercicios")
        
        # Materia de estudio (RESUMENES puro)
        materia_file = output_path / 'materia_estudio.jsonl'
        with open(materia_file, 'w', encoding='utf-8') as f:
            for m in self.categories['materia_estudio']:
                f.write(json.dumps(m, ensure_ascii=False) + '\n')
        print(f"✅ {materia_file.name}: {len(self.categories['materia_estudio'])} archivos")
        
        # Contenido mixto para Ollama (GUIAS)
        mixto_file = output_path / 'contenido_mixto.jsonl'
        with open(mixto_file, 'w', encoding='utf-8') as f:
            for m in self.categories['contenido_mixto']:
                f.write(json.dumps(m, ensure_ascii=False) + '\n')
        print(f"✅ {mixto_file.name}: {len(self.categories['contenido_mixto'])} archivos (pendiente) ")
        
        # Reporte de metadatos
        meta_file = output_path / 'REPORTE.json'
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(self.categories['metadata'], f, indent=2, ensure_ascii=False)
        
        print(f"\n📊 Reporte:")
        print(f"   Archivos procesados:   {self.categories['metadata']['archivos_procesados']}")
        print(f"   Archivos ignorados:    {self.categories['metadata']['archivos_ignorados']}")
        print(f"\n   Listo para procesar mañana con Ollama + GPU 2050 ✨")


if __name__ == "__main__":
    output_json_dir = "/home/gabriel/procesamiento_paes/output_json"
    extractor = DataExtractor(output_json_dir)
    extractor.run()
