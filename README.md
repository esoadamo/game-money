# Game money

An easy way to store your table game's money without having to use paper cards!

## Installation and configuration

Anybody can run their own server and connect with their favorite web browser.

### Installing own server

Clone the repository, install requirements and execute `app.py`, that's all!

```bash
git clone https://github.com/esoadamo/game-money.git
cd game-money
python -m pip install -r requirements.txt
python app.py
```

And you should be running! By default, pointing your browser to the [http://127.0.0.1:5000/](http://127.0.0.1:5000/) should be enough.

### Browser support

Your browser is required to support HTML5 and WebSockets, so all popular modern browsers should be OK. Design of the web pages is mobile-first, but desktop users should not have any difficulties.

### Adding own game type

There are two ways you can add your own game type.

1. By modifying `data/game-types.json`. All updates made to this file will be uploaded to the database during next start of the server. This method is easier as you can see all presently used game types in one place, but keep in mind, that this file can be overridden by git at any time.
2. By directly modifying the database. This method is more persistent, but may become unstable if the database schema is ever changed.

## Public server

There is a public server available at [https://money.adamhlavacek.com/](https://money.adamhlavacek.com/).

## Usage

### Basic concept

When you connect with your web browser to the server, you will be asked to enter your name under which will the server recognize you. You may change your name in the future. The server will then save you in database and create a key for you under which will the server be able to identify you. This key is saved into your browser's local storage and is permanent.

The login process is automatic and consists only of sending saved login key to the server.

Upon entering the main page of the server, you will see a list of active games which are not hidden. Some of them may be password protected. You may enter by clicking on the row in the table.

You can also create a new game by clicking on the Create new game button under the table. If you choose this, you will be assigned a special player, called *'the bank'* or *'infinite player'*, who holds special right to the game, such as possibility to hide the game from the list on the main page and infinite amount of money in every currency.

In both cases, you will be assigned additional player with the name same as your name on the main page. This player has limited resources and cannot go under 0.

You may also create additional players by pressing the `+` button next to the list of your players in the game. All these newly created players will be assigned to your user account and only you will be able to control them.

When you are in game, you can send money to other players in game by pressing the `Send money` button and then providing additional information.

### Additional notes

- the game itself cannot be deleted and can only be hidden from the main page by the so called *'bank'* or *'infinite'* player
- you can change any name you like of any user/player you own by clicking on their name, but note that player names in the game have to be unique

## Used technologies

- Web pages are served using [Flask](https://palletsprojects.com/p/flask/)
- Communication is done by using [Flask-Sockets](https://github.com/heroku-python/flask-sockets) on the backend and WebSockets on the frontend
- Communication with the database is done with the help of [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/en/2.x/)
- Code of web pages is using Flask's templates and [JS Renderer](https://github.com/esoadamo/game-money/blob/master/static/scripts/renderer.js) and Bootstrap 3, of course

## Screenshots

Can be found [here](https://github.com/esoadamo/game-money/issues/1).


## JS Renderer

Source code: [renderer.js](https://github.com/esoadamo/game-money/blob/master/static/scripts/renderer.js) 

Is a minimalistic renderer created for use with this application. It's main goal is to help the developer with creating the web page by allowing him to write `if` and `for` statements right inside the HTML.