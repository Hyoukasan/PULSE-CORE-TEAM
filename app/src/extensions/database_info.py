from flask_sqlalchemy import SQLAlchemy

database = SQLAlchemy()

def setConfig(app, env):
    """
    Настраивает приложение для работы с SQLite.
    Принимает:
      app: экземпляр Flask приложения
      env: словарь с настройками из .env файла
    """
    
    db_name = env.get('DATABASE', 'default.db')

    basedir = os.path.abspath(os.path.dirname(__file__))
    
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, db_name)}"
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    database.init_app(app)