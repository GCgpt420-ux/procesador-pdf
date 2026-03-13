#!/usr/bin/env python3
"""
Conversor: JSON de preguntas → INSERT SQL para TutorPAES PostgreSQL

Lee archivos *_meta.json de output_json/, extrae preguntas y genera SQL listo.
"""

import json
import re
import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class Choice:
    label: str
    text: str
    is_correct: bool


@dataclass
class ParsedQuestion:
    number: int
    prompt: str
    choices: List[Choice]
    difficulty: int = 1
    reading_text: Optional[str] = None
    explanation: Optional[str] = None


class QuestionParser:
    """Parsea preguntas de texto PDV/PAES"""

    # Patrón: "123. Pregunta completa"
    QUESTION_PATTERN = re.compile(
        r"^(\d+)\.\s+(.+?)(?=\nA\)|\nB\)|^$)",
        re.MULTILINE | re.DOTALL
    )

    # Patrón: "A) texto opción"
    CHOICE_PATTERN = re.compile(r"^([A-E])\)\s+(.+?)(?=\n[A-E]\)|$)", re.MULTILINE | re.DOTALL)

    @staticmethod
    def extract_questions_and_answers(text: str) -> Tuple[List[ParsedQuestion], Dict[int, str]]:
        """
        Extrae preguntas, opciones y respuestas correctas de texto OCR.
        Maneja OCR corrupto y símbolos matemáticos rotos.
        
        Retorna:
        - Lista de ParsedQuestion
        - Dict {numero_pregunta: letra_correcta}
        """
        # Busca la sección "RESPUESTAS" que está al final
        answers_match = re.search(r"RESPUESTAS\s*\n(.*)", text, re.DOTALL)
        answer_dict = {}
        
        if answers_match:
            answers_section = answers_match.group(1)
            # Parse: "1. C    6. D    11. C"
            answer_pairs = re.findall(r"(\d+)\.\s+([A-E])", answers_section)
            answer_dict = {int(num): letter for num, letter in answer_pairs}

        questions = []
        
        # Divide por números de pregunta más robustamente
        # Busca patrones como "1." seguido de contenido y luego "2."
        question_pattern = re.compile(r"\n(?=\d+\.[\s\)])", re.MULTILINE)
        blocks = question_pattern.split(text)
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
                
            # Extrae número de pregunta - PRIMERO intenta con "N)" pattern
            num_match = re.match(r"(\d+)\)\s+(.+?)(?=\n[A-E]\))", block, re.DOTALL)
            
            # Si no fun, intenta con "N."
            if not num_match:
                num_match = re.match(r"(\d+)\.\s+(.+?)(?=\n[A-E]\))", block, re.DOTALL)
            
            if not num_match:
                continue
                
            q_number = int(num_match.group(1))
            prompt = num_match.group(2).strip()
            
            # Normaliza espacios pero preserva saltos de línea que puedan ser importantes
            prompt = re.sub(r"\s+", " ", prompt)
            
            # Descarta preguntas muy cortas (probablemente corrupto OCR)
            if len(prompt) < 5:
                continue
            
            # Extrae opciones A/B/C/D/E (puede ser con () o parens normales)
            choices = []
            # Busca opciones: "A) texto" o "A ) texto"
            choice_matches = list(re.finditer(r"([A-E])\s*\)\s+(.+?)(?=\n[A-E]\s*\)|$)", block, re.DOTALL))
            
            if not choice_matches:
                # Intenta patrón alternativo con números rotos
                choice_matches = list(re.finditer(r"([A-E])\s+(.+?)(?=\n[A-E]\s+|$)", block, re.DOTALL))
            
            for choice_match in choice_matches:
                label = choice_match.group(1)
                choice_text = choice_match.group(2).strip()
                choice_text = re.sub(r"\s+", " ", choice_text)
                
                # Descarta opciones muy cortas
                if len(choice_text) < 2:
                    continue
                
                # Determina si es correcta basándose en el diccionario de respuestas
                is_correct = answer_dict.get(q_number) == label
                
                choices.append(Choice(label=label, text=choice_text, is_correct=is_correct))
            
            # Solo agrega si tiene 4+ opciones válidas (PAES tiene A/B/C/D)
            if len(choices) >= 4:
                pq = ParsedQuestion(
                    number=q_number,
                    prompt=prompt,
                    choices=choices[:5],  # Max 5 opciones
                    difficulty=1,
                    reading_text=None,
                    explanation=None
                )
                questions.append(pq)
        
        return questions, answer_dict


def infer_subject_and_topic(filename: str) -> Tuple[str, str]:
    """
    Infiere asignatura y tópico del nombre del archivo.
    Retorna (subject_code, topic_code, subject_name, topic_name)
    """
    filename_lower = filename.lower()
    
    # Mapeos comunes
    subject_map = {
        # Matemática M1
        "algebra": ("M1", "ALG", "Matemática M1", "Álgebra"),
        "potencias": ("M1", "POT", "Matemática M1", "Potencias"),
        "raices": ("M1", "RAI", "Matemática M1", "Raíces"),
        "logaritmo": ("M1", "LOG", "Matemática M1", "Logaritmos"),
        "ecuacion": ("M1", "ECU", "Matemática M1", "Ecuaciones"),
        "inecuacion": ("M1", "INE", "Matemática M1", "Inecuaciones"),
        
        # Matemática M2
        "geometria": ("M2", "GEO", "Matemática M2", "Geometría"),
        "estadistica": ("M2", "EST", "Matemática M2", "Estadística"),
        "probabilidad": ("M2", "PRO", "Matemática M2", "Probabilidad"),
        
        # Física
        "mecanica": ("FIS", "MEC", "Física", "Mecánica"),
        "ondas": ("FIS", "OND", "Física", "Ondas"),
        "optica": ("FIS", "OPT", "Física", "Óptica"),
        "electricidad": ("FIS", "ELE", "Física", "Electricidad"),
        "termodinamica": ("FIS", "TER", "Física", "Termodinámica"),
        "mru": ("FIS", "MRU", "Física", "Cinemática"),
        "mrua": ("FIS", "MRUA", "Física", "Cinemática"),
        "sonido": ("FIS", "SOU", "Física", "Acústica"),
        "luz": ("FIS", "OPT", "Física", "Óptica"),
        "espejo": ("FIS", "OPT", "Física", "Óptica"),
        "lente": ("FIS", "OPT", "Física", "Óptica"),
        
        # Biología
        "biologia": ("BIO", "BIO", "Biología", "Biología General"),
        
        # Química
        "quimica": ("QUI", "QUI", "Química", "Química"),
        
        # Lenguaje
        "lenguaje": ("LECT", "COMP", "Competencia Lectora", "Comprensión Lectora"),
        "lectura": ("LECT", "COMP", "Competencia Lectora", "Comprensión Lectora"),
        
        # Historia
        "historia": ("HIST", "HIST", "Historia", "Historia de Chile"),
        "geografia": ("HIST", "GEO", "Historia", "Geografía"),
    }
    
    for keyword, mapping in subject_map.items():
        if keyword in filename_lower:
            return mapping
    
    # Default: M1 Álgebra
    return ("M1", "ALG", "Matemática M1", "Álgebra")


def generate_sql_insert(parsed_questions: List[ParsedQuestion], subject_code: str, topic_code: str, 
                       subject_name: str, topic_name: str, difficulty: int = 1) -> str:
    """Genera SQL INSERT para las preguntas parseadas."""
    
    sql_lines = []
    
    # 1. Asegura que la asignatura existe
    sql_lines.append(f"-- Asignatura: {subject_name}")
    sql_lines.append(
        f"INSERT INTO subjects(exam_id, code, name) "
        f"SELECT (SELECT id FROM exams WHERE code='PAES'), '{subject_code}', '{subject_name}' "
        f"WHERE NOT EXISTS (SELECT 1 FROM subjects WHERE code='{subject_code}');"
    )
    
    # 2. Asegura que el tópico existe
    sql_lines.append(f"\n-- Tópico: {topic_name}")
    sql_lines.append(
        f"INSERT INTO topics(subject_id, code, name) "
        f"SELECT (SELECT id FROM subjects WHERE code='{subject_code}'), '{topic_code}', '{topic_name}' "
        f"WHERE NOT EXISTS (SELECT 1 FROM topics WHERE subject_id=(SELECT id FROM subjects WHERE code='{subject_code}') AND code='{topic_code}');"
    )
    
    # 3. Preguntas
    sql_lines.append(f"\n-- Preguntas ({len(parsed_questions)} total)")
    
    for pq in parsed_questions:
        prompt_escaped = pq.prompt.replace("'", "''")
        explanation_escaped = (pq.explanation or "").replace("'", "''")
        
        sql_lines.append(
            f"INSERT INTO questions(topic_id, prompt, explanation, difficulty, question_type, is_active) "
            f"SELECT (SELECT id FROM topics WHERE code='{topic_code}'), "
            f"'{prompt_escaped}', '{explanation_escaped}', {pq.difficulty}, 'mcq', true "
            f"RETURNING id INTO question_id;"
        )
        
        # Por cada opción
        for choice in pq.choices:
            text_escaped = choice.text.replace("'", "''")
            sql_lines.append(
                f"INSERT INTO question_choices(question_id, label, text, is_correct) "
                f"VALUES (question_id, '{choice.label}', '{text_escaped}', {str(choice.is_correct).lower()});"
            )
    
    return "\n".join(sql_lines)


def process_json_file(json_path: str) -> str:
    """Lee un JSON_meta.json y retorna SQL insert."""
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Combina todo el texto de todas las páginas
    full_text = "\n".join([page.get("texto", "") for page in data.get("paginas", [])])
    
    # Parsea preguntas
    parser = QuestionParser()
    questions, answers = parser.extract_questions_and_answers(full_text)
    
    # Infiere asignatura/tópico
    filename = data.get("filename", "unknown.pdf")
    subject_code, topic_code, subject_name, topic_name = infer_subject_and_topic(filename)
    
    # Genera SQL
    sql = generate_sql_insert(
        questions, 
        subject_code, 
        topic_code, 
        subject_name, 
        topic_name
    )
    
    return sql, len(questions), filename


def main():
    output_dir = Path("/home/gabriel/procesamiento_paes/output_json")
    
    # Busca todos los *_meta.json
    meta_files = list(output_dir.rglob("*_meta.json"))
    
    print(f"✓ Encontrados {len(meta_files)} archivos JSON\n")
    
    all_sql = []
    total_questions = 0
    processed = 0
    
    for meta_file in sorted(meta_files):  # Procesa TODOS
        try:
            sql, q_count, filename = process_json_file(str(meta_file))
            if q_count > 0:
                all_sql.append(f"-- Archivo: {filename}\n{sql}")
                total_questions += q_count
                processed += 1
                if processed % 50 == 0:
                    print(f"  [{processed}] {filename}: {q_count} preguntas (total: {total_questions})")
        except Exception as e:
            pass  # Silencioso para archivos corruptos
    
    # Escribe SQL a archivo
    output_path = Path("/home/gabriel/procesamiento_paes/insert_questions.sql")
    
    preamble = """-- ============================================
-- Datos generados automáticamente desde JSON
-- Conversor: converter_json_to_paes.py
-- ============================================
BEGIN;

-- Asegura que PAES exam existe
INSERT INTO exams(code, name) 
VALUES ('PAES', 'Prueba de Acceso a la Educación Superior')
ON CONFLICT (code) DO NOTHING;

"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(preamble)
        f.write("\n".join(all_sql))
        f.write("\n\nCOMMIT;")
    
    print(f"\n✓ SQL generado: {output_path}")
    print(f"  Total: {total_questions} preguntas")
    print(f"\n  Próximo paso:")
    print(f"  psql -d tutor_paes < /home/gabriel/procesamiento_paes/insert_questions.sql")


if __name__ == "__main__":
    main()
