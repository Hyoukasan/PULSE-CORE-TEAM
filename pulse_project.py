from app.main import create_app

app = create_app()

if __name__ == '__main__':
    print(f"База подключена: {app.config['SQLALCHEMY_DATABASE_URI']}")
