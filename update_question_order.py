#!/usr/bin/env python3
"""
Script to update the order of Bosnian template questions to match the provided table
"""

import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Flask app for database access
app = Flask(__name__)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///instance/modern360.db')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_group = db.Column(db.String(100), nullable=True)
    question_type = db.Column(db.String(50), nullable=False)
    language = db.Column(db.String(10), default='bs')
    options = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)

# Ordered list of questions as provided
ordered_questions = [
    {"group": "Odgovornost", "text": "Zadatke obavlja tačno i blagovremeno", "order": 1},
    {"group": "Odgovornost", "text": "Prihvata odgovornost za lični uspeh", "order": 2},
    {"group": "Odgovornost", "text": "Preuzima odgovornost za neuspjehe", "order": 3},
    {"group": "Odgovornost", "text": "Pokazuje dosljednost u riječima i na djelu", "order": 4},
    {"group": "Odgovornost", "text": "Postavlja visoka očekivanja za sebe", "order": 5},
    {"group": "Fokus na klijenta", "text": "Traži načine za dodavanje vrijednosti izvan očekvanja klijenata", "order": 6},
    {"group": "Fokus na klijenta", "text": "Istražuje i bavi se neutvrdjenim, temeljnim i dugoročnim potrebama klijenata", "order": 7},
    {"group": "Fokus na klijenta", "text": "Poboljšava sistem i proces pružanja usluga klijentima", "order": 8},
    {"group": "Fokus na klijenta", "text": "Predviđa buduće potrebe i brige klijenata", "order": 9},
    {"group": "Komunikacija", "text": "Prilagođava komunikaciju publici", "order": 10},
    {"group": "Komunikacija", "text": "Pruža efikasne, visokokvalitetne prezentacije", "order": 11},
    {"group": "Komunikacija", "text": "Efikasno koristi metode neverbalne komunikacije", "order": 12},
    {"group": "Komunikacija", "text": "Dijeli odgovarajuću količinu informacija", "order": 13},
    {"group": "Komunikacija", "text": "Profesionalno podnosi kritike", "order": 14},
    {"group": "Usluge klijentima", "text": "Aktivno sluša klijente", "order": 15},
    {"group": "Usluge klijentima", "text": "Odgovara na zahtjeve klijenata", "order": 16},
    {"group": "Usluge klijentima", "text": "Profesionalno i ljubazno rješava pritužbe klijenata", "order": 17},
    {"group": "Usluge klijentima", "text": "Pokazuje empatiju i razumijevanje prema klijentima", "order": 18},
    {"group": "Usluge klijentima", "text": "Komunicira zahtjeve klijenata menadžmentu na odgovarajući način", "order": 19},
    {"group": "Strateško razmišljanje", "text": "Predviđa dugoročne implikacije predloženih rješenja", "order": 20},
    {"group": "Strateško razmišljanje", "text": "Prosudjuje razumno u novim situacijama", "order": 21},
    {"group": "Strateško razmišljanje", "text": "Identificira i razmatra nove mogućnosti i rizike", "order": 22},
    {"group": "Strateško razmišljanje", "text": "Pruža nove informacije ili podatke za ključnu odluku", "order": 23},
    {"group": "Strateško razmišljanje", "text": "Pokazuje pronicljivo razumijevanje organizacijskog konteksta i prioreta", "order": 24},
    {"group": "Timski rad", "text": "Odaje priznanje i priznaje doprinose i napore drugih članova tima", "order": 25},
    {"group": "Timski rad", "text": "Ulaže izuzetne napore da pomogne članovima tima", "order": 26},
    {"group": "Timski rad", "text": "Njeguje timski duh", "order": 27},
    {"group": "Timski rad", "text": "Osigurava da svi članovi grupe imaju priliku da doprinesu grupnim diskusijama", "order": 28},
    {"group": "Timski rad", "text": "Pomaže u izgradnji konsenzusa među članovima tima", "order": 29},
    {"group": "Rješavanje problema", "text": "Pristupa složenim problemima tako što ih dijeli na komponente kojima se može upravljati", "order": 30},
    {"group": "Rješavanje problema", "text": "Identifikuje optimalna rješenja važući prednosti i mane alternativnih pristupa", "order": 31},
    {"group": "Rješavanje problema", "text": "Identificira i traži informacije potrebne za rješavanje problema", "order": 32},
    {"group": "Rješavanje problema", "text": "Predviđa moguće negativne ishode odluka", "order": 33},
    {"group": "Rješavanje problema", "text": "Nakon implementacije, ocjenjuje učinkovitost i efikasnost rešenja", "order": 34},
    {"group": "Upravaljanje vremenom", "text": "Prikladno određuje prioritete zadataka prema važnosti i vremenskom ograničenju", "order": 35},
    {"group": "Upravaljanje vremenom", "text": "Precizno predviđa vrijeme potrebno za završetak zadatka", "order": 36},
    {"group": "Upravaljanje vremenom", "text": "Koristi sisteme za upravljanje projektima i kalendare za organizaciju vremena", "order": 37},
    {"group": "Upravaljanje vremenom", "text": "Uvijek je svjestan statusa svih dodijeljenih zadataka", "order": 38},
    {"group": "Upravaljanje vremenom", "text": "Redovno obavještava druge o statusu zadatka", "order": 39}
]

def update_question_order():
    """Update the order of Bosnian template questions"""
    with app.app_context():
        print("🔄 Starting question order update...")
        
        # Get all Bosnian template questions
        questions = Question.query.filter_by(assessment_id=0, language='bs').all()
        print(f"Found {len(questions)} Bosnian template questions")
        
        if len(questions) != len(ordered_questions):
            print(f"⚠️ Warning: Database has {len(questions)} questions but ordered list has {len(ordered_questions)}")
        
        updated_count = 0
        
        # Update each question based on the ordered list
        for ordered_q in ordered_questions:
            # Find the question in database by matching text (partial match for flexibility)
            db_question = None
            for q in questions:
                if ordered_q["text"].strip() in q.question_text.strip() or q.question_text.strip() in ordered_q["text"].strip():
                    db_question = q
                    break
            
            if db_question:
                # Update the question
                db_question.question_group = ordered_q["group"]
                db_question.order = ordered_q["order"] - 1  # Convert to 0-based indexing
                updated_count += 1
                print(f"✅ Updated question {ordered_q['order']}: {ordered_q['text'][:50]}...")
            else:
                print(f"❌ Could not find question: {ordered_q['text'][:50]}...")
        
        # Commit changes
        try:
            db.session.commit()
            print(f"✅ Successfully updated {updated_count} questions!")
            
            # Verify the update
            print("\n📋 Verification - Questions in order:")
            ordered_questions_db = Question.query.filter_by(assessment_id=0, language='bs').order_by(Question.order).all()
            for i, q in enumerate(ordered_questions_db[:10]):  # Show first 10
                print(f"{q.order + 1:2d}. [{q.question_group}] {q.question_text[:60]}...")
            if len(ordered_questions_db) > 10:
                print(f"... and {len(ordered_questions_db) - 10} more questions")
                
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error updating questions: {e}")
            return False
        
        return True

if __name__ == "__main__":
    if update_question_order():
        print("\n🎉 Question order update completed successfully!")
    else:
        print("\n💥 Question order update failed!")
        sys.exit(1)
