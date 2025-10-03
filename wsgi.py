from app import app, init_database

# Initialize database on startup
init_database()

if __name__ == "__main__":
    app.run()