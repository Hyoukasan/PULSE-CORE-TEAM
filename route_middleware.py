from flask import Flask
from flask_cors import CORS
from app.src.extensions.database_info import setConfig

env = dotenv_values(".env")

app = Flask(__name__) 

origin = env.get('CROSS_ORIGIN', '*')
CORS(app, resources={r"*": {"origins": origin}})

setConfig(app, env)

# 5. Подключаем JWT (если у тебя есть файл jwt.py и ты хочешь авторизацию)
# from jwt_config import setConfigJWT
# jwt = setConfigJWT(app, env)

# 6. Регистрируем роуты (Blueprints)
# Это связывает твои файлы с логикой и основной файл приложения
# app.register_blueprint(user_route)

# 7. Запуск (для локальной разработки)
if __name__ == '__main__':
    with app.app_context():
        database.create_all()
        
    app.run(debug=True, port=5000)