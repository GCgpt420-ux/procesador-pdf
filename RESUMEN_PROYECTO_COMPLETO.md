# Proyecto procesamiento_paes: contenido y funcionamiento

## 1) Objetivo del proyecto
Este proyecto implementa un flujo ETL para transformar material PAES (principalmente PDFs de preuniversitarios) en datos estructurados listos para cargarse en PostgreSQL para TutorPAES.

Objetivo final:
- Extraer preguntas y alternativas desde PDFs.
- Clasificar contenido por tipo (preguntas, materia, mixto).
- Limpiar calidad de preguntas.
- Convertir a SQL e insertar en BD.
- Dejar base usable para frontend de practica PAES.

## 2) Estado actual del workspace
Se hizo limpieza de la raiz del proyecto para poder depurar codigo con espacio ordenado.

### Carpeta de respaldo creada
`data_extraida_respaldo_2026-04-15/`

Contenido movido a esta carpeta:
- `output_json/`
- `output_estructurado/`
- `processed_data/`
- `marker_temp/`
- `insert_questions.sql`
- `batch_progress.json`
- `fase2_progress.json`
- `fase2_marker_progress.json`
- `batch_processor.log`
- `fase2_extraccion.log`
- `fase2_marker_qwen.log`

### Limpieza aplicada
- Eliminada carpeta `PACK_GPU_MAÑANA/`.

## 3) Inventario principal del proyecto (raiz actual)
- `input_pdfs/`: fuente original de documentos PDF.
- `scripts/`: scripts de extraccion por lotes y fase 2 con LLM.
- `Notebook_GPU_Ollama.ipynb`: notebook para clasificacion con Ollama en GPU.
- `PLAN_MAÑANA.md`: plan operativo para corrida en universidad.
- `extract_by_category.py`: clasifica JSONs a categorias de procesamiento.
- `clean_desafios.py`: limpia preguntas y valida consistencia.
- `converter_json_to_paes.py`: genera SQL masivo desde JSON.
- `load_desafios_to_db.py`: inserta preguntas limpias a PostgreSQL via SQLAlchemy.
- `sql_to_csv.py`: alternativa de exportacion SQL a CSV.
- `pack_for_gpu.sh`: script para empaquetar corrida en GPU.
- `data_extraida_respaldo_2026-04-15/`: respaldo de todo lo ya extraido/procesado.

## 4) Flujo tecnico de trabajo (pipeline)

### Etapa A: Extraccion PDF -> JSON
Script principal:
- `scripts/batch_processor.py`

Funcion:
- Recorre PDFs en `input_pdfs/`.
- Extrae texto por pagina.
- Guarda metadatos en `output_json/` (ahora en respaldo).
- Registra avance en `batch_progress.json`.

### Etapa B: Extraccion semantica alternativa (fase 2)
Scripts:
- `scripts/fase2_extraccion_inteligente.py`
- `scripts/fase2_marker_qwen.py`

Funcion:
- Variante con OCR/estructura + modelo local Ollama.
- Produce material estructurado en `output_estructurado/` (respaldo).
- Usa progreso en `fase2_progress.json` y `fase2_marker_progress.json`.

Estado observado:
- `fase2_marker_progress.json` muestra 0 procesados y 1 error (flujo marker pendiente de correccion).

### Etapa C: Clasificacion por tipo de contenido
Script:
- `extract_by_category.py`

Funcion:
- Lee JSONs y clasifica en:
  - preguntas limpias (desafios)
  - ejercicios
  - materia de estudio
  - contenido mixto para LLM
- Escribe en `processed_data/`.

### Etapa D: Limpieza de calidad
Script:
- `clean_desafios.py`

Validaciones:
- Elimina opciones duplicadas por etiqueta.
- Exige 4 o mas alternativas.
- Exige al menos una respuesta correcta.

Salida:
- `desafios_preguntas_clean.jsonl` dentro de `processed_data/`.

### Etapa E: Conversor a SQL
Script:
- `converter_json_to_paes.py`

Funcion:
- Parsea preguntas/opciones.
- Infiere asignatura y topico por nombre de archivo.
- Genera inserciones SQL para examenes, asignaturas, topicos, preguntas y alternativas.

Salida:
- `insert_questions.sql` (actualmente en respaldo).

### Etapa F: Carga a PostgreSQL
Scripts:
- `load_desafios_to_db.py` (via SQLAlchemy al backend Mvp-paes2)
- `sql_to_csv.py` (ruta alternativa de export/import)

## 5) Metricas del material extraido (en respaldo)
- Archivos `*_meta.json` en `output_json`: 402
- Archivos en `output_estructurado`: 5719
- Archivos en `processed_data`: 6

## 6) Relacion con el notebook
Notebook:
- `Notebook_GPU_Ollama.ipynb`

Uso:
- Cargar `processed_data`.
- Clasificar contenido mixto con modelos Ollama (ej. qwen:7b).
- Insertar resultados en PostgreSQL.

## 7) Dependencias y stack
- Python 3 (entorno virtual `venv`).
- PyMuPDF / procesamiento de PDF.
- Ollama (modelos locales tipo qwen).
- SQLAlchemy + psycopg para PostgreSQL.
- Jupyter Notebook para corrida GPU y clasificacion final.

## 8) Como esta trabajando hoy el proyecto
Operacion actual recomendada tras limpieza:
1. Mantener codigo en raiz limpio para debugging y mejoras.
2. Reusar datos desde `data_extraida_respaldo_2026-04-15/` cuando se necesite reprocesar o validar.
3. Corregir primero falla de fase 2 marker (0 procesados, 1 error).
4. Reejecutar pipeline por etapas con checkpoints para verificar calidad.

## 9) Archivos clave para corregir primero
- `scripts/fase2_marker_qwen.py`
- `scripts/fase2_extraccion_inteligente.py`
- `extract_by_category.py`
- `clean_desafios.py`
- `converter_json_to_paes.py`

## 10) Observacion final
La informacion extraida NO se elimino: fue consolidada en una carpeta de respaldo unica para dejar la raiz limpia y facilitar la reparacion del codigo sin perder trabajo previo.
