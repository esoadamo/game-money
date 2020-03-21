import json
import sys

from os import path
from typing import Optional, Tuple
from uuid import uuid4 as uuid

from flask import Flask, render_template, Blueprint
from flask_sockets import Sockets
from gevent import monkey
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

print(app.config["SQLALCHEMY_DATABASE_URI"])


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    key = db.Column(db.String, nullable=False)


class GameType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    config = db.Column(db.String, nullable=False)


class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    password = db.Column(db.String)

    game_type_id = db.Column(db.Integer, db.ForeignKey('game_type.id'), nullable=False)
    game_type = db.relationship('GameType', backref=db.backref('games', lazy=True))
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    owner = db.relationship('User', backref=db.backref('users', lazy=True))


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
                r = self.on_data(data)
                if type(r) == dict:
                    self.send_dict(r)
            except (json.JSONDecodeError, TypeError):
                pass
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
                r.append(t.name)
            print(r)
            return 'openNewGameModal', r

    def on_disconnect(self):
        print('Disconnected')


@soc.route('/soc')
def soc_comm(ws: WebSocket):
    c = GameClient(ws)
    c.run()


@html.route('/')
def hello():
    return render_template('index.html', game=MOCK_GAME, player=MOCK_PLAYER)


def main():
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler

    db.create_all()

    server = pywsgi.WSGIServer(('127.0.0.1', 5000), app, handler_class=WebSocketHandler)
    print('running')
    server.serve_forever()


app.register_blueprint(html, url_prefix=r'/')
sockets.register_blueprint(soc, url_prefix=r'/')

if __name__ == '__main__':
    main()
