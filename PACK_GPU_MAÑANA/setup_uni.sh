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
