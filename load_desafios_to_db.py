#!/usr/bin/env python3
"""
Carga las 79 preguntas limpias (desafios) en PostgreSQL del TutorPAES.
Rápido y directo.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, '/home/gabriel/proyectos/Mvp-paes2/backend')

from sqlalchemy import select
from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import Exam, Subject, Topic, Question, QuestionChoice


def load_desafios():
    """Carga 66 preguntas de desafios a BD."""
    
    # Lee JSON de desafios (limpio)
    desafios_file = Path('/home/gabriel/procesamiento_paes/processed_data/desafios_preguntas_clean.jsonl')
    
    preguntas = []
    with open(desafios_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                preguntas.append(json.loads(line))
    
    print(f"📖 Cargadas {len(preguntas)} preguntas del JSONL\n")
    
    db = SessionLocal()
    
    try:
        # Verifica/crea EXAM PAES
        exam = db.scalar(select(Exam).where(Exam.code == settings.PAES_CODE))
        if not exam:
            print("❌ PAES exam no existe. Ejecuta seed_paes.py primero")
            return
        
        print(f"✅ Exam PAES ID: {exam.id}")
        
        # Crea Subject para DESAFIOS
        subject = db.scalar(
            select(Subject).where(
                Subject.exam_id == exam.id,
                Subject.code == 'DESAFIOS'
            )
        )
        if not subject:
            subject = Subject(exam_id=exam.id, code='DESAFIOS', name='Desafíos PAES')
            db.add(subject)
            db.flush()
            print(f"✅ Creado Subject DESAFIOS ID: {subject.id}")
        else:
            print(f"✅ Subject DESAFIOS ID: {subject.id} (ya existía)")
        
        # Crea Topic para DESAFIOS
        topic = db.scalar(
            select(Topic).where(
                Topic.subject_id == subject.id,
                Topic.code == 'DESAFIOS'
            )
        )
        if not topic:
            topic = Topic(subject_id=subject.id, code='DESAFIOS', name='Desafíos Variados')
            db.add(topic)
            db.flush()
            print(f"✅ Creado Topic DESAFIOS ID: {topic.id}")
        else:
            print(f"✅ Topic DESAFIOS ID: {topic.id} (ya existía)")
        
        print()
        
        # Carga preguntas
        loaded = 0
        duplicated = 0
        
        for idx, p in enumerate(preguntas, 1):
            # Evita duplicados
            existing = db.scalar(
                select(Question).where(
                    Question.topic_id == topic.id,
                    Question.prompt == p['enunciado'][:200]
                )
            )
            if existing:
                duplicated += 1
                continue
            
            # Crea pregunta
            q = Question(
                topic_id=topic.id,
                prompt=p['enunciado'][:1000],
                question_type='mcq',
                difficulty=2,
                is_active=True
            )
            db.add(q)
            db.flush()
            
            # Crea opciones
            for opt in p['opciones']:
                qc = QuestionChoice(
                    question_id=q.id,
                    label=opt['label'],
                    text=opt['texto'][:500],
                    is_correct=opt['es_correcta']
                )
                db.add(qc)
            
            loaded += 1
            
            if loaded % 20 == 0:
                print(f"  [{idx}/{len(preguntas)}] {loaded} preguntas cargadas...")
        
        db.commit()
        
        print(f"\n✅ COMPLETADO:")
        print(f"   ✓ {loaded} preguntas insertadas")
        print(f"   ✓ {loaded * 4} opciones generadas")
        if duplicated > 0:
            print(f"   ⚠️  {duplicated} duplicadas (ignoradas)")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    load_desafios()
