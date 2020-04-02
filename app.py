import json
import sys
import time

from os import path
from typing import Optional, Tuple, List, Dict
from uuid import uuid4 as uuid

from flask import Flask, render_template, Blueprint, url_for
from flask_sockets import Sockets
from gevent import monkey
# noinspection PyPackageRequirements
from geventwebsocket.websocket import WebSocket
from flask_sqlalchemy import SQLAlchemy

# GLOBAL CONSTANTS

# Directory where this script is located
SCRIPT_DIR = path.abspath(path.join(sys.argv[0], path.pardir))

# Config, overridden by data/config.json if exists
CONFIG = {
    'host': '0.0.0.0',
    'port': 5000
}

# WEB SERVER SETUP section

monkey.patch_all()  # fix sockets

# Different handlers for classic HTTP an WS
html = Blueprint(r'html', __name__)
soc = Blueprint(r'soc', __name__)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + path.join(SCRIPT_DIR, 'data', 'db.sqlite')
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
sockets = Sockets(app)

# DATABASE

# game <-> user, N-N relation table
rel_game_users = db.Table('rel-game-users',
                          db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
                          db.Column('game_id', db.Integer, db.ForeignKey('game.id'), primary_key=True)
                          )


class User(db.Model):
    """
    User is every device connected to this server
    The user is identified by his key
    User can change it's name, join a game, create a game
    User can be member of more games at the same time
    User is owner of his players
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    key = db.Column(db.String, nullable=False, unique=True)
    games = db.relationship('Game', secondary=rel_game_users, lazy='subquery', backref=db.backref('users', lazy=True))

    def characters_in_game(self, game: "Game") -> List["GamePlayer"]:
        """
        Gets all players belonging to this user inside specified game
        :param game: game in which are players looked for
        :return: list of GamePlayer objects inside the game belonging to this user
        """
        characters = self.characters
        players = game.players
        return [ch for ch in players if ch in characters]


class GamePlayer(db.Model):
    """
    A game player is an entity that is assigned to a game
    In this game, a game player can send and receive money
    The player can be only controlled by his user
    Player can be infinite, meaning that he has infinite amount of money
    and is owner of the game
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    is_infinite = db.Column(db.Boolean, default=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('characters', lazy=True))
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    money = db.Column(db.String, nullable=False)

    def notify_transfer(self, sender: "GamePlayer", recipient: "GamePlayer",
                        amount_sender: float, amount_recipient: float, currency: str) -> None:
        """
        Notifies this user about money transfer
        :param sender: sender of the money
        :param recipient: recipient of the money
        :param amount_sender: how much does have sender left
        :param amount_recipient: how much  does have recipient left
        :param currency: the currency used
        :return: None
        """
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
    """
    Specifies the type of the game and it's configuration
    Every game has a GameType
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False, unique=True)
    config = db.Column(db.String, nullable=False)


class Game(db.Model):
    """
    The game itself, has users, players and owner
    Can be password protected or hidden
    Multiple games with the same name can occur
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    password = db.Column(db.String)
    hidden = db.Column(db.Boolean, nullable=False, default=False)

    type_id = db.Column(db.Integer, db.ForeignKey('game_type.id'), nullable=False)
    type = db.relationship('GameType')
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    owner = db.relationship('User')
    players = db.relationship('GamePlayer', backref='game', lazy=True)
    history_records = db.relationship('HistoryRecord', backref='game', lazy=True)

    @staticmethod
    def list_games(user_id: Optional[int] = None, user: Optional[User] = None) -> None:
        """
        Sends a list of all currently shown games to the user
        User can be specified by user_id or User object
        :param user_id: id of User to send to
        :param user: User to send to
        :return: None
        """
        if user is None:
            user = User.query.filter_by(id=user_id).first()
        else:
            user_id = user.id
        if user_id not in online_users:
            return
        r = []
        for game in Game.query.filter_by(hidden=False).all():
            r.append({
                'id': game.id,
                'name': game.name,
                'game': game.type.name,
                'password': game.password is not None and user not in game.users
            })
        online_users[user_id].send_event('listGames', r)

    def notify_online_players(self) -> None:
        """
        Sends a list of all players inside this game to all users
        :return: None
        """
        r = self.get_all_players()

        for u in self.users:
            if u.id not in online_users:
                continue
            online_users[u.id].send_event('playersAll', r)

    def get_all_players(self) -> Dict[int, str]:
        """
        Lists all players inside this game
        :return: {playerID: playerName}
        """
        return {p.id: p.name for p in self.players}

    def format_players(self, user: User) -> List[dict]:
        """
        Takes all user's players inside this game and
        puts them into format readable by the web app
        :param user: User to find players of
        :return: [{id, name, infinite, money: [{currency: str, amount: float}]}]
        """
        r = []
        for ch in user.characters_in_game(self):
            r.append({
                'name': ch.name,
                'money': [{'currency': k, 'amount': v} for k, v in json.loads(ch.money).items()],
                'infinite': ch.is_infinite,
                'id': ch.id
            })
        return r

    def send_history(self, user: User) -> None:
        """
        Sends list of relevant history records of this game to user
        :param user: user receiving the history
        :return: None
        """
        rs = []
        for record in self.history_records:
            p1: GamePlayer = record.player1
            p2: GamePlayer = record.player2
            relevant = self.owner.id == user.id  # always send to the game owner
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

    def update_history(self, record: "HistoryRecord") -> None:
        """
        Updates history of this game with new record and notifies relevant players
        :param record: record to be added to the history of this game
        :return: None
        """
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
        """
        Format history record into a dictionary parseable by web app
        :param record: record to be formatted
        :return: {text, p1: playerId || None, p2: playerId || None}
        """
        message = {'text': record.string, 'all': record.all}
        if record.player1 is not None:
            message['p1'] = record.player1.id
        if record.player2 is not None:
            message['p2'] = record.player2.id
        return message


class HistoryRecord(db.Model):
    """
    A record holding information about a change in a game
    Can have up to two assigned players p1 and p2
    If all is set, then this record is visible to all players in game
    """
    id = db.Column(db.Integer, primary_key=True)
    string = db.Column(db.String, nullable=False)
    all = db.Column(db.Boolean, default=False)
    player1_id = db.Column(db.Integer, db.ForeignKey('game_player.id'), nullable=True)
    player1 = db.relationship('GamePlayer', foreign_keys="HistoryRecord.player1_id")
    player2_id = db.Column(db.Integer, db.ForeignKey('game_player.id'), nullable=True)
    player2 = db.relationship('GamePlayer', foreign_keys="HistoryRecord.player2_id")
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)


# Map of user id -> GameClient for all currenctly online users
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
    database_sync_time: List[float] = [time.time()]

    def __init__(self, ws: WebSocket):
        super().__init__(ws)
        self.logged_in = False
        self.user: Optional[User] = None
        self.local_sync = time.time()

    def on_disconnect(self):
        if self.user is not None and self.user.id in online_users:
            del online_users[self.user.id]

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
        if message_type == 'ping':
            return 'pong', 'pong'

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

        if self.local_sync < self.database_sync_time[0]:
            print('synchronizing with global database')
            db.session.commit()
            self.local_sync = time.time()

        # Lobby
        if message_type == 'listGames':
            Game.list_games(user=self.user)
            return
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

            for u_id in online_users:
                Game.list_games(u_id)

            self.force_sync()
            return 'gameEnter', f"{url_for('html.page_game', game_id=game.id)}"
        elif message_type == 'enterGame':
            room_id = message.get('id')
            room_password = message.get('password')
            game = Game.query.filter_by(id=room_id).first()
            if game is None:
                return 'gameEnterERR', 'This game does not exist'
            if game.password is not None and game.password != room_password and self.user not in game.users:
                return 'gameEnterERR', 'Wrong room password'
            if game not in self.user.games:
                game.users.append(self.user)
                player = GamePlayer(name=self.user.name, game=game, user=self.user, money=game.type.config)
                record = HistoryRecord(string=f"%p1% entered into the game as {player.name}", player1=player, all=True)
                db.session.add(player)
                game.update_history(record)
                db.session.add(record)
                db.session.commit()
                self.force_sync()
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
            self.send_event('hideGame', game.hidden)
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
            for p2 in game.players:
                if p2.id == player.id:
                    continue
                if p2.name == name:
                    return 'playerNameChangeERR', 'Player with this name already exists'

            record = HistoryRecord(string=f"{player.name} has changed it's name to {name}", all=True)
            player.name = name

            game.update_history(record)
            db.session.add(record)
            db.session.commit()
            self.force_sync()

            game.notify_online_players()
            return 'players', game.format_players(self.user)
        elif message_type == 'addPlayer':
            name = message.get('name')
            if not name:
                return 'addPlayer', 'Invalid name'
            for p2 in game.players:
                if p2.name == name:
                    return 'addPlayerERR', 'Player with this name already exists'
            player = GamePlayer(name=name, game=game, user=self.user, money=game.type.config)
            record = HistoryRecord(string=f"%p1% entered into the game as {player.name}", player1=player, all=True)
            db.session.add(player)
            game.update_history(record)
            db.session.add(record)
            db.session.commit()
            self.force_sync()

            game.notify_online_players()
            return 'players', game.format_players(self.user)
        elif message_type == 'hideGame':
            if game.owner != self.user:
                return 'hideGameERR', 'Sorry, only owner of the game can do this'
            game.hidden = not game.hidden

            record = HistoryRecord(string="The game was hidden" if game.hidden else 'The game was shown again',
                                   all=True)
            game.update_history(record)
            db.session.add(record)
            db.session.commit()
            self.force_sync()

            for u_id in online_users:
                Game.list_games(u_id)

            self.force_sync()

            return 'hideGame', game.hidden
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

            if None in (player, recipient, currency):
                return 'sendMoneyERR', 'Invalid information'

            if amount <= 0:
                return 'sendMoneyERR', 'You cannot send less than (or equal to) 0'

            p_money = json.loads(player.money)
            r_money = json.loads(recipient.money)
            if None in (p_money.get(currency), r_money.get(currency)):
                return 'sendMoneyERR', 'Invalid currency'

            if p_money.get(currency) < amount and not player.is_infinite:
                return 'sendMoneyERR', 'You do not have enought money'

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
            self.force_sync()
            return

    def force_sync(self):
        self.database_sync_time[0] = time.time()

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

    config_file = path.join(SCRIPT_DIR, 'data', 'config.json')
    if path.exists(config_file):
        with open(config_file, 'r') as f:
            CONFIG.update(json.load(f))

    with open(path.join(SCRIPT_DIR, 'data', 'game-types.json')) as f:
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

    server = pywsgi.WSGIServer((CONFIG['host'], CONFIG['port']), app, handler_class=WebSocketHandler)
    print('up and running')
    server.serve_forever()


app.register_blueprint(html, url_prefix=r'/')
sockets.register_blueprint(soc, url_prefix=r'/')

if __name__ == '__main__':
    main()
