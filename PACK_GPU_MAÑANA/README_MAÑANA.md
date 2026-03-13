# 🎓 PLAN: Poblar BD PAES con Preguntas + Materia

**Fecha:** 8 de marzo de 2026  
**Lugar:** Universidad (GPU RTX 2050)  
**Tiempo estimado:** ~2 horas (1.5 procesamiento + 0.5 inserción)

---

## 📁 ARCHIVOS PREPARADOS HOY

Están en: `/home/gabriel/procesamiento_paes/processed_data/`

```
desafios_preguntas.jsonl          ← 79 PREGUNTAS LIMPIAS (listas para insertar)
materia_estudio.jsonl             ← 7 ARCHIVOS de contenido de estudio
contenido_mixto.jsonl             ← 34 DOCUMENTOS que necesitan clasificar con Ollama
REPORTE.json                       ← Estadísticas
```

---

## 🚀 PASOS A EJECUTAR MAÑANA

### 1️⃣ Copiar archivos a la uni
```bash
# En la uni, descarga el notebook:
scp gabriel@casa:/home/gabriel/procesamiento_paes/Notebook_GPU_Ollama.ipynb .
scp -r gabriel@casa:/home/gabriel/procesamiento_paes/processed_data/ .
```

### 2️⃣ Levantar Ollama (PRIMERO)
```bash
# En terminal 1 de la uni
ollama serve

# En terminal 2, descarga el modelo (si no lo tienes)
ollama pull qwen:7b
# O para mejor calidad (si tienes VRAM):
ollama pull qwen:14b
```

### 3️⃣ Abrir Jupyter Notebook
```bash
jupyter notebook Notebook_GPU_Ollama.ipynb
```

### 4️⃣ Ejecutar según orden:
- **Sección 1-3:** Cargar datos (20 seg)
- **Sección 4-5:** Verificar Ollama + prueba (30 seg)
- **Sección 6:** Clasificar TODO contenido mixto (15-30 min ⚠️ LENTO)
- **Sección 7-8:** Insertar en PostgreSQL (5 min)
- **Sección 9:** Ver estadísticas finales

---

## 📊 RESULTADOS ESPERADOS

**Hoy (sin GPU) - Ya terminó:**
- ✅ 79 desafíos/preguntas limpias (PAES)
- ✅ 7 archivos de materia (resúmenes)
- ✅ 34 documentos mixtos identificados

**Mañana (con GPU + Ollama) - A hacer:**
- 🚀 Clasificar ~34 documentos con Qwen
  - Estima: 500-1,000 preguntas adicionales
  - Estima: 200-300 archivos de materia
- 💾 Insertar TODO en PostgreSQL

**Resultado final:**
- 📚 ~1,500-1,800 preguntas en BD
- 📖 300-500 archivos de materia por tópico
- 🎓 Frontend listo para usar

---

## 🛠️ CONFIGURACIÓN REQUERIDA EN LA UNI

```python
# En el notebook (sección 1), confirma que:
PROCESSED_DATA_DIR = Path('/ruta/donde/copies/processed_data')
OLLAMA_URL = 'http://localhost:11434'  # Local
MODEL = 'qwen:7b'  # O qwen:14b
```

---

## ⚡ TIPS DE RENDIMIENTO

**Si Ollama es lento:**
```bash
# Usa modelo más rápido (pero menos preciso)
ollama pull mistral:7b  # ~50% más rápido que Qwen
```

**Si PostgreSQL no está disponible en la uni:**
```bash
# Exporta resultados a CSV en la uni:
# Luego los cargas en casa después
df.to_csv('preguntas_clasificadas.csv', index=False)
```

**Para ver progreso en tiempo real:**
```python
# En el notebook, los bucles ya tienen tqdm
# Muestra barra de progreso automáticamente
```

---

## 🆘 TROUBLESHOOTING

| Problema | Solución |
|----------|----------|
| "Ollama no está corriendo" | Ejecuta `ollama serve` en otra terminal |
| "Modelo no encontrado" | `ollama pull qwen:7b` |
| "CUDA out of memory" | Usa `qwen:7b` en lugar de `qwen:14b` |
| "PostgreSQL no responde" | Inicia docker/BD en casa remotamente |
| Clasificación muy lenta | Reduce batch a 5 docs por vez |

---

## 📝 NOTAS IMPORTANTES

1. **El contenido mixto toma MUCHO tiempo** porque Ollama analiza cada página. Es normal que tarde 20-30 min

2. **Asegúrate de copiar los JSONs** - sin ellos no hay nada que clasificar

3. **Guarda los resultados** - después puedes usar para mejorar el modelo

4. **Backup de la BD** antes de insertar masivamente

---

## ✅ CHECKLIST PARA MAÑANA

```
[ ] Copié los archivos de processed_data
[ ] Ollama está corriendo (ollama serve)
[ ] Descargué el modelo (ollama pull qwen:7b)
[ ] Jupyter abierto
[ ] PostgreSQL accesible
[ ] Ejecuto sección 1-5 para verificar
[ ] Ejecuto sección 6 (clasificación)
[ ] Ejecuto secciones 7-8 (inserción)
[ ] Verifico resultados en frontend
```

---

## 🎯 RESUMEN RÁPIDO

**Hoy (preparación):** ✅ HECHO
- Extrajimos 79 preguntas limpias
- Preparamos JSONs ordenados
- Creamos Jupyter notebook

**Mañana (ejecución):**
1. Copiar datos
2. Levantar Ollama
3. Ejecutar notebook (2 horas)
4. Verificar inserciones en BD
5. ¡Listo!

---

## 📞 SOPORTE

Si algo no funciona en la uni, guarda los outputs y me los mandas después para revisar.

**¡Mucho éxito! 🚀**
