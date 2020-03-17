import json
from typing import Optional

from flask import Flask, render_template, Blueprint
from flask_sockets import Sockets
from gevent import monkey
from geventwebsocket.websocket import WebSocket

monkey.patch_all()


html = Blueprint(r'html', __name__)
soc = Blueprint(r'soc', __name__)

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
sockets = Sockets(app)

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
                self.on_data(data)
            except (json.JSONDecodeError, TypeError):
                pass
        self.on_disconnect()

    def on_connect(self):
        pass

    def on_disconnect(self):
        pass

    def on_data(self, data: dict):
        pass

    def send_dict(self, data: dict):
        self.__soc.send(json.dumps(data))


class GameClient(SocketComm):
    def on_connect(self):
        print('client connected')

    def on_data(self, data: dict):
        print('got variables', data)

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

    server = pywsgi.WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
    print('running')
    server.serve_forever()


app.register_blueprint(html, url_prefix=r'/')
sockets.register_blueprint(soc, url_prefix=r'/')

if __name__ == '__main__':
    main()
