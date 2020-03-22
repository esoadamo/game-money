import json
import sys

from os import path
from typing import Optional, Tuple, List, Dict
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

    def notify_transfer(self, sender: "GamePlayer", recipient: "GamePlayer",
                        amount_sender: float, amount_recipient: float, currency: str):
        client = online_users.get(self.user.id)
        if client is None:
            return
        client.send_event('moneyTransfer', {'sender': sender.id,
                                            'recipient': recipient.id,
                                            'senderAmount': amount_sender,
                                            'recipientAmount': amount_recipient,
                                            'currency': currency
                                            })


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
    history_records = db.relationship('HistoryRecord', backref='game', lazy=True)

    def notify_online_players(self):
        r = self.get_all_players()

        for u in self.users:
            if u.id not in online_users:
                continue
            online_users[u.id].send_event('playersAll', r)

    def get_all_players(self) -> Dict[int, str]:
        return {p.id: p.name for p in self.players}

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

    def send_history(self, user: User):
        rs = []
        for record in self.history_records:
            p1: GamePlayer = record.player1
            p2: GamePlayer = record.player2
            relevant = self.owner.id == user.id
            if not relevant and p1 is not None and p1.user.id == user.id:
                relevant = True
            elif not relevant and p2 is not None and p2.user.id == user.id:
                relevant = True
            if not relevant:
                continue
            rs.append(self.format_history_record(record))
        client = online_users.get(user.id)
        if client is None:
            return
        client.send_event('history', rs)

    def update_history(self, record: "HistoryRecord"):
        self.history_records.append(record)
        if not record.all:
            notified_players = {record.player1, record.player2} - {None}
            notified_users = {p.user for p in notified_players}
        else:
            notified_users = set(self.users)
        for u in notified_users:
            client = online_users.get(u.id)
            if client is None:
                continue
            client.send_event('historyUpdate', self.format_history_record(record))

    @staticmethod
    def format_history_record(record: "HistoryRecord") -> dict:
        message = {'text': record.string, 'all': record.all}
        if record.player1 is not None:
            message['p1'] = record.player1.id
        if record.player2 is not None:
            message['p2'] = record.player2.id
        return message


class HistoryRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    string = db.Column(db.String, nullable=False)
    all = db.Column(db.Boolean, default=False)
    player1_id = db.Column(db.Integer, db.ForeignKey('game_player.id'), nullable=True)
    player1 = db.relationship('GamePlayer', foreign_keys="HistoryRecord.player1_id")
    player2_id = db.Column(db.Integer, db.ForeignKey('game_player.id'), nullable=True)
    player2 = db.relationship('GamePlayer', foreign_keys="HistoryRecord.player2_id")
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)


online_users: Dict[int, "GameClient"] = {}


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

    def on_disconnect(self):
        user_id = self.user.id
        if self.user is not None and online_users.get(user_id) is not None:
            del online_users[user_id]

    def send_dict(self, data: dict):
        print('->', data)
        super().send_dict(data)

    def on_data(self, data: dict) -> Optional[dict]:
        print('<-', data)
        message_type = data.get('type')
        message = data.get('message')
        if message_type is None or message is None:
            return

        r = self.on_message(message_type, message)
        if r is not None:
            return self.send_event(r[0], r[1])

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
                online_users[self.user.id] = self
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

            record = HistoryRecord(string="The game was stared by %p1%", player1=player, all=True)
            db.session.add(record)
            game.update_history(record)

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
                record = HistoryRecord(string=f"%p1% entered into the game as {player.name}", player1=player, all=True)
                db.session.add(player)
                game.update_history(record)
                db.session.add(record)

                db.session.commit()
            game.notify_online_players()
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
            self.send_event('playersAll', game.get_all_players())
            game.send_history(self.user)
            return 'gameInfo', {'name': game.name, 'id': game.id}

        game_id = message.get('game')
        game: Game = Game.query.filter_by(id=game_id).first()
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

            record = HistoryRecord(string=f"{player.name} has changed it's name to {name}", all=True)
            player.name = name

            game.update_history(record)
            db.session.add(record)
            db.session.commit()

            game.notify_online_players()
            return 'players', game.format_players(self.user)
        elif message_type == 'modalSend':
            player: GamePlayer = GamePlayer.query.filter_by(id=message.get('player')).first()
            r = {
                'otherPlayers': [],
                'currencies': list(json.loads(player.money).keys())
            }
            for p2 in game.players:
                if p2.id == player.id:
                    continue
                r['otherPlayers'].append({'name': p2.name, 'id': p2.id})
            return 'openModalSend', r
        elif message_type == 'sendMoney':
            player: GamePlayer = GamePlayer.query.filter_by(id=message.get('player')).first()
            recipient: GamePlayer = GamePlayer.query.filter_by(id=message.get('recipient')).first()
            amount = float(message.get('amount', 0))
            currency = message.get('currency')

            if None in (player, recipient, currency) or amount <= 0:
                return 'sendMoneyERR', 'Cannot send money'

            p_money = json.loads(player.money)
            r_money = json.loads(recipient.money)
            if None in (p_money.get(currency), r_money.get(currency)):
                return 'sendMoneyERR', 'Invalid currency'

            if p_money.get(currency) < amount and not player.is_infinite:
                return 'sendMoneyERR', 'Not enought money'

            p_money[currency] -= amount
            r_money[currency] += amount

            player.money = json.dumps(p_money)
            recipient.money = json.dumps(r_money)

            for p in (player, recipient):
                p.notify_transfer(player, recipient, p_money[currency], r_money[currency], currency)

            record = HistoryRecord(string=f"%p1% sent %p2% {amount} {currency}", player1=player, player2=recipient)
            game.update_history(record)
            db.session.add(record)
            db.session.commit()
            return

    def send_event(self, event_type: str, event_message: any):
        return self.send_dict({'type': event_type, 'message': event_message})


@soc.route('/soc')
def soc_comm(ws: WebSocket):
    c = GameClient(ws)
    c.run()


@html.route('/')
def page_home():
    return render_template('index.html')


# noinspection PyUnresolvedReferences
@html.route('/game/<int:game_id>')
def page_game(*_, **__):
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
