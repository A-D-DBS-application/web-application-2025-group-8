import os

class Config:
    SECRET_KEY = 'you-will-never-guesssss'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:Iegfmm740_0@db.fsqylzxocszdduainvqd.supabase.co:5432/postgres'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False



