import json
import sys

from os import path
from typing import Optional, Tuple, List
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

script_dir = path.abspath(path.join(sys.argv[0], path.pardir))

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + path.join(script_dir, 'data', 'db.sqlite')
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
sockets = Sockets(app)

rel_game_users = db.Table('rel-game-users',
                          db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
                          db.Column('game_id', db.Integer, db.ForeignKey('game.id'), primary_key=True)
                          )


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    key = db.Column(db.String, nullable=False)
    games = db.relationship('Game', secondary=rel_game_users, lazy='subquery', backref=db.backref('users', lazy=True))

    def characters_in_game(self, game: "Game") -> List["GamePlayer"]:
        characters = self.characters
        players = game.players
        return [ch for ch in players if ch in characters]


class GamePlayer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    is_infinite = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('characters', lazy=True))
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    money = db.Column(db.String, nullable=False)


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
    owner = db.relationship('User')
    players = db.relationship('GamePlayer', backref='game', lazy=True)

    def format_players(self, user: User) -> List[dict]:
        r = []
        for ch in user.characters_in_game(self):
            r.append({
                'name': ch.name,
                'money': [{'currency': k, 'amount': v} for k, v in json.loads(ch.money).items()],
                'infinite': ch.is_infinite,
                'id': ch.id
            })
        return r


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
                    return 'unknownUser', 'I don\'t know you'
                self.logged_in = True
                self.user = u
                return 'login', u.name
            return

        # Lobby
        if message_type == 'listGames':
            r = []
            for game in Game.query.all():
                r.append({
                    'id': game.id,
                    'name': game.name,
                    'game': game.type.name,
                    'password': game.password is not None
                })
            return 'listGames', r
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

            if not game_name or not game_type_id:
                return 'openNewGameERR', 'Name or type not filled'
            game_type = GameType.query.filter_by(id=game_type_id).first()
            if game_type is None:
                return 'openNewGameERR', 'This game types does not exist'
            existing_game = Game.query.filter_by(name=game_name).first()
            if existing_game is not None:
                return 'openNewGameERR', 'Game with this name already exists'
            game = Game(name=game_name, type=game_type, owner=self.user)
            game.users.append(self.user)
            bank = GamePlayer(name="Bank", game=game, user=self.user, money=game.type.config, is_infinite=True)
            player = GamePlayer(name=self.user.name, game=game, user=self.user, money=game.type.config)
            game.players.append(bank)
            game.players.append(player)
            if game_password:
                game.password = game_password
            db.session.add(game)
            db.session.add(bank)
            db.session.add(player)
            db.session.commit()
            return 'gameEnter', f"{url_for('html.page_game', game_id=game.id)}"
        elif message_type == 'enterGame':
            room_id = message.get('id')
            room_password = message.get('password')
            game = Game.query.filter_by(id=room_id).first()
            if game is None:
                return 'gameEnterERR', 'This game does not exist'
            if game.password is not None and game.password != room_password:
                return 'gameEnterERR', 'Wrong room password'
            if game not in self.user.games:
                game.users.append(self.user)
                player = GamePlayer(name=self.user.name, game=game, user=self.user, money=game.type.config)
                db.session.add(player)
                db.session.commit()
            return 'gameEnter', f"{url_for('html.page_game', game_id=game.id)}"

        # Game
        elif message_type == 'gameInfo':
            game_id = int(message.split('/')[-1])
            game = Game.query.filter_by(id=game_id).first()
            if game is None:
                return 'returnHomepage', 'This game does not exist'
            if self.user not in game.users:
                return 'returnHomepage', 'You are not allowed to be here'
            self.send_event('players', game.format_players(self.user))
            return 'gameInfo', {'name': game.name, 'id': game.id}

        game_id = message.get('game')
        game = Game.query.filter_by(id=game_id).first()
        if game is None:
            return 'returnHomepage', 'This game does not exist'
        if self.user not in game.users:
            return 'returnHomepage', 'You are not allowed to be here'

        if message_type == 'playerNameChange':
            player: Optional[GamePlayer] = GamePlayer.query.filter_by(id=message.get('player')).first()
            if player is None:
                return 'playerNameChangeERR', 'Player does not exist'
            if player.user != self.user:
                return 'playerNameChangeERR', 'Not your player'
            name = message.get('name')
            if not name:
                return 'playerNameChangeERR', 'Invalid name'
            player.name = name
            db.session.commit()
            return 'players', game.format_players(self.user)

    def send_event(self, event_type: str, event_message: any):
        return self.send_dict({'type': event_type, 'message': event_message})

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

    with open(path.join(script_dir, 'data', 'game-types.json')) as f:
        game_types = json.load(f)
        for game_type_name, game_type_config in game_types.items():
            game_type_config = json.dumps(game_type_config)
            game_type = GameType.query.filter_by(name=game_type_name).first()
            if game_type is None:
                game_type = GameType(name=game_type_name, config=game_type_config)
                db.session.add(game_type)
            else:
                game_type.config = game_type_config
    db.session.commit()

    server = pywsgi.WSGIServer(('0.0.0.0', 5000), app, handler_class=WebSocketHandler)
    print('up and running')
    server.serve_forever()


app.register_blueprint(html, url_prefix=r'/')
sockets.register_blueprint(soc, url_prefix=r'/')

if __name__ == '__main__':
    main()
