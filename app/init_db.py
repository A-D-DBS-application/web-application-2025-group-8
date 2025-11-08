from app import db, create_app
app = create_app()
from app import models
with app.app_context():
    try:
        from sqlalchemy import text
        result = db.session.execute(text("SELECT 1"))
        print("✅ Verbonden met de database (Supabase).")
    except Exception as e:
        print("❌ Fout bij verbinden met de database:")
        print(e)



