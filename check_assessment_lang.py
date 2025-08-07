#!/usr/bin/env python3
"""
Check assessment language and questions
"""

from admin_app import admin_app, db, Assessment, Question

def check_assessment():
    with admin_app.app_context():
        # Check the assessment with ID 1 (ziraat)
        assessment = Assessment.query.get(1)
        if assessment:
            print(f'Assessment: {assessment.title}')
            print(f'Language: {assessment.language}')
            print(f'Number of questions: {len(assessment.questions)}')
            print()
            print('First few questions:')
            for i, q in enumerate(assessment.questions[:5]):
                print(f'{i+1}. Language: {q.language}, Group: {q.question_group}, Text: {q.question_text[:60]}...')
        else:
            print('Assessment not found')

if __name__ == '__main__':
    check_assessment()
