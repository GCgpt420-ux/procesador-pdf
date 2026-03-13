#!/usr/bin/env python3
"""
Limpia desafios_preguntas.jsonl eliminando:
- Opciones duplicadas (mismo label)
- Preguntas sin 4+ opciones válidas
"""

import json
from pathlib import Path

def clean_desafios():
    input_file = Path('/home/gabriel/procesamiento_paes/processed_data/desafios_preguntas.jsonl')
    output_file = Path('/home/gabriel/procesamiento_paes/processed_data/desafios_preguntas_clean.jsonl')
    
    preguntas_entrada = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                preguntas_entrada.append(json.loads(line))
    
    print(f"📖 Cargadas {len(preguntas_entrada)} preguntas\n")
    
    preguntas_limpias = []
    problemas = []
    
    for idx, p in enumerate(preguntas_entrada, 1):
        # Elimina opciones duplicadas (mismo label)
        labels_vistos = set()
        opciones_limpias = []
        
        for opt in p['opciones']:
            if opt['label'] not in labels_vistos:
                opciones_limpias.append(opt)
                labels_vistos.add(opt['label'])
            else:
                problemas.append(f"  Q{p['numero']}: Opción duplicada {opt['label']}")
        
        # Valida mínimo 4 opciones
        if len(opciones_limpias) < 4:
            problemas.append(f"  Q{p['numero']}: Solo {len(opciones_limpias)} opciones válidas")
            continue
        
        # Valida que haya respuesta correcta
        tiene_correcta = any(opt['es_correcta'] for opt in opciones_limpias)
        if not tiene_correcta:
            problemas.append(f"  Q{p['numero']}: Sin respuesta correcta")
            continue
        
        # Actualiza pregunta
        p['opciones'] = opciones_limpias
        preguntas_limpias.append(p)
    
    # Guarda limpias
    with open(output_file, 'w', encoding='utf-8') as f:
        for p in preguntas_limpias:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')
    
    print(f"✅ RESULTADOS:")
    print(f"   Input:  {len(preguntas_entrada)} preguntas")
    print(f"   Output: {len(preguntas_limpias)} preguntas válidas")
    print(f"   Descartadas: {len(preguntas_entrada) - len(preguntas_limpias)}")
    
    if problemas:
        print(f"\n⚠️  PROBLEMAS ENCONTRADOS ({len(problemas)}):")
        for p in problemas[:10]:  # Muestra primeros 10
            print(p)
        if len(problemas) > 10:
            print(f"   ... y {len(problemas) - 10} más")
    
    print(f"\n📍 Archivo limpio: {output_file}")
    return preguntas_limpias


if __name__ == "__main__":
    clean_desafios()
