web: gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 4
release: python -c "
from app import app, db; 
from ensure_template_questions import add_predefined_questions;
with app.app_context():
    db.create_all();
    add_predefined_questions();
    print('Database setup complete')
"
