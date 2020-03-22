import json
import sys

from os import path
from typing import Optional, Tuple
from uuid import uuid4 as uuid

from flask import Flask, render_template, Blueprint, url_for
from flask_sockets import Sockets
from gevent import monkey
# noinspection PyPackageRequirements
from geventwebsocket.websocket import WebSocket
from flask_sqlalchemy import SQLAlchemy

monkey.patch_all()

html = Blueprint(r'html', __name__)
soc = Blueprint(r'soc', __name__)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + path.abspath(path.join(sys.argv[0], path.pardir,
                                                                              'data', 'db.sqlite'))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
sockets = Sockets(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    key = db.Column(db.String, nullable=False)


class GamePlayer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    is_infinite = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('characters', lazy=True))
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)


class GameType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    config = db.Column(db.String, nullable=False)


class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False, unique=True)
    password = db.Column(db.String)

    type_id = db.Column(db.Integer, db.ForeignKey('game_type.id'), nullable=False)
    type = db.relationship('GameType')
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    owner = db.relationship('User', backref=db.backref('users', lazy=True))
    players = db.relationship('GamePlayer', backref='game', lazy=True)


MOCK_GAME = {
    'name': 'My Game',
    'players': []
}

MOCK_PLAYER = {
    'name': 'Adam',
    'goods': [{'name': 'CZK', 'value': 15 * 10 ** 6, 'color': 'green'}],
    'infinite': False
}


class SocketComm:
    def __init__(self, web_soc: "WebSocket"):
        self.__soc = web_soc
        self.on_connect()

    def run(self):
        while not self.__soc.closed:
            try:
                msg: Optional[str] = self.__soc.receive()
                data: dict = json.loads(msg)
            except (json.JSONDecodeError, TypeError):
                continue
            r = self.on_data(data)
            if type(r) == dict:
                self.send_dict(r)
        self.on_disconnect()

    def on_connect(self):
        pass

    def on_disconnect(self):
        pass

    def on_data(self, data: dict) -> Optional[dict]:
        pass

    def send_dict(self, data: dict):
        self.__soc.send(json.dumps(data))


class GameClient(SocketComm):
    def __init__(self, ws: WebSocket):
        super().__init__(ws)
        self.logged_in = False
        self.user: Optional[User] = None

    def on_data(self, data: dict) -> Optional[dict]:
        print('in', data)
        message_type = data.get('type')
        message = data.get('message')
        if message_type is None or message is None:
            return

        r = self.on_message(message_type, message)
        if r is not None:
            return {'type': r[0], 'message': r[1]}

    def on_message(self, message_type: str, message: any) -> Optional[Tuple[str, any]]:
        if not self.logged_in:
            if message_type == 'register':
                u = User(name=message, key=uuid().hex)
                db.session.add(u)
                db.session.commit()
                return 'register', u.key
            if message_type == 'login':
                u = User.query.filter_by(key=message).first()
                if u is None:
                    return
                self.logged_in = True
                self.user = u
                return 'login', u.name
            return
        if message_type == 'listGames':
            return 'listGames', [{'id': 1, 'name': 'Moje Hra', 'game': 'Monopoly'}]
        elif message_type == 'nameChange':
            self.user.name = message
            db.session.commit()
            return 'nameChange', self.user.name
        elif message_type == 'listGameTypes':
            r = []
            for t in GameType.query.all():
                r.append({'type': t.id, 'name': t.name})
            return 'openNewGameModal', r
        elif message_type == 'createGame':
            game_name = message.get('name', '')
            game_type_id = message.get('type', '')
            game_password = message.get('password', '')

            print('opening game')

            if not game_name or not game_type_id:
                return 'openNewGameERR', 'Name or type not filled'
            game_type = GameType.query.filter_by(id=game_type_id).first()
            if game_type is None:
                return 'openNewGameERR', 'This game types does not exist'
            existing_game = Game.query.filter_by(name=game_name).first()
            if existing_game is not None:
                return 'openNewGameERR', 'Game with this name already exists'
            game = Game(name=game_name, type=game_type, owner=self.user)
            if game_password:
                game.password = game_password
            db.session.add(game)
            db.session.commit()
            return 'gameEnter', f"{url_for('html.page_game', game_id=game.id)}"

    def on_disconnect(self):
        print('Disconnected')


@soc.route('/soc')
def soc_comm(ws: WebSocket):
    c = GameClient(ws)
    c.run()


@html.route('/')
def page_home():
    return render_template('index.html')


@html.route('/game/<int:game_id>')
def page_game(game_id: int):
    return render_template('game.html')


def main():
    from gevent import pywsgi
    # noinspection PyPackageRequirements
    from geventwebsocket.handler import WebSocketHandler

    db.create_all()

    server = pywsgi.WSGIServer(('127.0.0.1', 5000), app, handler_class=WebSocketHandler)
    print('running')
    server.serve_forever()


app.register_blueprint(html, url_prefix=r'/')
sockets.register_blueprint(soc, url_prefix=r'/')

if __name__ == '__main__':
    main()
