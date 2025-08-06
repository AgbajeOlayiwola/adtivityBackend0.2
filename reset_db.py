from app.database import Base, engine

def reset_db():
    # Add cascade option here
    Base.metadata.drop_all(bind=engine, checkfirst=False)
    print("Dropped all tables (with CASCADE)")
    Base.metadata.create_all(bind=engine)
    print("Created all tables")

if __name__ == "__main__":
    reset_db()