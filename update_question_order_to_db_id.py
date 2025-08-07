#!/usr/bin/env python3
"""
Update question order to match database ID
"""

from admin_app import admin_app, db, Question

def update_question_order():
    with admin_app.app_context():
        # Get all Bosnian template questions ordered by database ID
        questions = Question.query.filter_by(assessment_id=0, language='bs').order_by(Question.id).all()
        
        print(f'Found {len(questions)} Bosnian template questions')
        print('\nCurrent state:')
        print('DB_ID | Order | Display# | Group                | Question Text')
        print('-' * 90)
        
        for q in questions:
            display_num = q.order + 1
            print(f'{q.id:5} | {q.order:5} | #{display_num:7} | {q.question_group:20} | {q.question_text[:40]}...')
        
        print('\n' + '='*50)
        print('UPDATING ORDER TO MATCH DB_ID')
        print('='*50)
        
        # Update each question's order to match its database ID - 1 (so display shows DB_ID)
        for q in questions:
            old_order = q.order
            new_order = q.id - 1  # Since display adds 1, this will show DB_ID
            q.order = new_order
            print(f'Question ID {q.id}: order {old_order} -> {new_order} (display #{q.id})')
        
        # Commit changes
        db.session.commit()
        print('\nChanges committed successfully!')
        
        print('\nNew state:')
        print('DB_ID | Order | Display# | Group                | Question Text')
        print('-' * 90)
        
        # Re-query to show updated state
        updated_questions = Question.query.filter_by(assessment_id=0, language='bs').order_by(Question.order).all()
        for q in updated_questions:
            display_num = q.order + 1
            print(f'{q.id:5} | {q.order:5} | #{display_num:7} | {q.question_group:20} | {q.question_text[:40]}...')

if __name__ == '__main__':
    update_question_order()
