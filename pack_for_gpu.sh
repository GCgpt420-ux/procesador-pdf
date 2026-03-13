#!/bin/bash
# Script: Empaqueta datos para llevar a la uni mañana
# Uso: bash pack_for_gpu.sh

set -e

BASEDIR="/home/gabriel/procesamiento_paes"
PACKDIR="$BASEDIR/PACK_GPU_MAÑANA"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "📦 Empaquetando datos para GPU RTX 2050..."
echo ""

# Crea directorio
mkdir -p "$PACKDIR"

# 1. Copia datos procesados
echo "✓ Copiando JSONs intermedios..."
cp -v "$BASEDIR/processed_data/"*.jsonl "$PACKDIR/"
cp -v "$BASEDIR/processed_data/REPORTE.json" "$PACKDIR/"

# 2. Copia Jupyter notebook
echo "✓ Copiando Jupyter Notebook..."
cp -v "$BASEDIR/Notebook_GPU_Ollama.ipynb" "$PACKDIR/"

# 3. Copia plan
echo "✓ Copiando plan de instrucciones..."
cp -v "$BASEDIR/PLAN_MAÑANA.md" "$PACKDIR/README_MAÑANA.md"

# 4. Crea requirements.txt para instalación rápida en la uni
echo "✓ Generando requirements.txt..."
cat > "$PACKDIR/requirements_uni.txt" << 'EOF'
requests>=2.28.0
pandas>=1.5.0
tqdm>=4.65.0
sqlalchemy>=2.0.0
psycopg[binary]>=3.1.0
jupyter>=1.0.0
jupyter-core>=5.0.0
EOF

# 5. Script de setup rápido
echo "✓ Generando script de setup para la uni..."
cat > "$PACKDIR/setup_uni.sh" << 'EOF'
#!/bin/bash
# Setup rápido en la uni

echo "🔧 Setup Universidad"

# 1. Instala dependencias
echo "📦 Instalando Python packages..."
pip install -q -r requirements_uni.txt

# 2. Verifica Ollama
echo "🤖 Verificando Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "❌ Ollama NO está corriendo"
    echo "   Ejecuta en otra terminal: ollama serve"
    exit 1
fi
echo "✅ Ollama está corriendo"

# 3. Verifica modelo
echo "📥 Verificando modelo qwen..."
if ! ollama list | grep -q qwen; then
    echo "❌ Modelo qwen no está descargado"
    echo "   Ejecuta: ollama pull qwen:7b"
    exit 1
fi
echo "✅ Modelo qwen disponible"

# 4. Lanza Jupyter
echo "🚀 Abriendo Jupyter..."
jupyter notebook Notebook_GPU_Ollama.ipynb
EOF

chmod +x "$PACKDIR/setup_uni.sh"

# 6. Crea un resumen visual
echo "✓ Generando resumen..."
cat > "$PACKDIR/CONTENIDO.txt" << 'EOF'
📦 PACK PARA GPU RTX 2050
========================

Archivos incluidos:

1. DATOS (JSONs intermedios):
   - desafios_preguntas.jsonl    (79 preguntas limpias)
   - materia_estudio.jsonl       (7 archivos de materia)
   - contenido_mixto.jsonl       (34 docs para clasificar)
   - REPORTE.json               (estadísticas)

2. NOTEBOOK:
   - Notebook_GPU_Ollama.ipynb   (Jupyter con todo el flujo)

3. INSTRUCCIONES:
   - README_MAÑANA.md            (guía detallada)
   - CONTENIDO.txt               (este archivo)

4. SETUP:
   - setup_uni.sh                (script de instalación rápida)
   - requirements_uni.txt        (dependencias Python)

📋 PASOS EN LA UNI:
===================

1. Extrae este pack en una carpeta
2. bash setup_uni.sh
3. Ejecuta el Jupyter (se abrirá autom)
4. Sigue el notebook paso a paso

⏱️ TIEMPO ESTIMADO: 2 horas

🎯 RESULTADO: BD poblada con ~1,500-1,800 preguntas + materia
EOF

# 7. Crea un índice
echo "✓ Creando índice..."
cat > "$PACKDIR/INDEX.md" << 'EOF'
# 📚 ÍNDICE DE ARCHIVOS

## Para LEER primero:
- `CONTENIDO.txt` - Resumen visual
- `README_MAÑANA.md` - Instrucciones detalladas

## Para EJECUTAR:
- `setup_uni.sh` - Setup automático
- `Notebook_GPU_Ollama.ipynb` - Notebook principal

## Datos (NO editar):
- `desafios_preguntas.jsonl`
- `materia_estudio.jsonl`
- `contenido_mixto.jsonl`
- `REPORTE.json`

## Dependencias:
- `requirements_uni.txt` - Instala con pip

---

**Versión:** $TIMESTAMP
**Máquina origen:** $(hostname)
**Usuario:** $(whoami)
EOF

# 8. Resumen final
echo ""
echo "=========================================="
echo "✅ PACK CREADO EXITOSAMENTE"
echo "=========================================="
echo ""
ls -lah "$PACKDIR"
echo ""
echo "📍 Ubicación: $PACKDIR/"
echo ""
echo "🎯 Próximo paso:"
echo "   1. En la uni, extrae este directorio"
echo "   2. Ejecuta: cd PACK_GPU_MAÑANA && bash setup_uni.sh"
echo ""
echo "Tamaño total: $(du -sh $PACKDIR | cut -f1)"
echo ""
