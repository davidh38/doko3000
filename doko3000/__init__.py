from time import time

from flask import flash, \
    Flask, \
    redirect, \
    render_template, \
    request, \
    url_for
from flask_login import current_user, \
    LoginManager, \
    login_required, \
    login_user, \
    logout_user
from flask_socketio import join_room, \
    SocketIO

from .config import Config
from .database import DB
from .forms import Login
from .game import Deck, \
    Game

# initialize app
app = Flask(__name__)
app.config.from_object(Config)
# timestamp for files which may change during debugging like .js and .css
app.jinja_env.globals.update(timestamp=int(time()))
# initialize database
db = DB(app)
# login
login = LoginManager(app)
login.login_view = 'login'
# empty message avoids useless errorflash-messae-by-default
login.login_message = ''
# extend by socket.io
socketio = SocketIO(app, manage_session=False)

game = Game(db=db)
game.initialize_components()
#game.test_game()


@login.user_loader
def load_user(id):
    """
    give user back if it exists, otherwise force login
    """
    try:
        player = game.players[id]
        return player
    except KeyError:
        return None


@socketio.on('who-am-i')
def who_am_i():
    print('who-am-i', current_user)
    if not current_user.is_anonymous:
        player_id = current_user.id
        table_id = game.players[player_id].table
        # if player already sits on a table inform client
        if table_id:
            current_player_id = game.tables[table_id].round.current_player
            join_room(table_id)
        else:
            current_player_id = ''
        socketio.emit('you-are-what-you-is',
                      {'player_id': player_id,
                       'current_player_id': current_player_id})



@socketio.on('new-table')
def new_table(msg):
    print('new_table', current_user)
    game.add_table('test2')
    game.tables['test2'].add_player(current_user.id)
    socketio.emit('new-table-available',
                  {'tables': game.get_tables_names(),
                   'player_id': current_user.id,
                   'html': render_template('list_tables.html',
                                           tables=game.get_tables())},
                  broadcast=True)


@socketio.on('played-card')
def played_card(msg):
    print('played-card', current_user, msg['card_id'], msg['card_name'])
    card_id = msg['card_id']
    player_id = msg['player_id']
    table = game.tables[msg['table_id']]
    print(current_user.id, player_id, table.round.current_player)
    if current_user.id == player_id == table.round.current_player:
        print(table.round.current_trick)
        table.round.current_trick.add_turn(player_id, card_id)
        table.round.increase_turn_count()
        game.players[player_id].remove_card(card_id)
        is_last_turn = table.round.current_trick.is_last_turn()
        current_player_id = table.round.shift_players()
        socketio.emit('played-card-by-user',
                      {'player_id': player_id,
                       'card_id': card_id,
                       'card_name': msg['card_name'],
                       'is_last_turn': is_last_turn,
                       'current_player_id': current_player_id,
                       'html': {'card': render_template('card.html',
                                                        card=Deck.cards[card_id],
                                                        table=table),
                                }},
                      room=table.id)


@socketio.on('enter-table')
def enter_table(msg):
    print(msg)
    # table = game.tables[msg['table_id']]
    table_id = msg['table_id']
    player_id = msg['player_id']
    if table_id in game.tables:
        if player_id not in game.tables[table_id].players:
            game.tables[table_id].add_player(player_id)
        join_room(table_id)


@socketio.on('deal-cards')
def deal_cards(msg):
    table = game.tables[msg['table_id']]
    table.reset_round()

    # just tell everybody to get personal cards
    socketio.emit('grab-your-cards',
                  {'table_id': table.id})


@socketio.on('my-cards-please')
def deal_cards_to_player(msg):
    player_id = msg['player_id']
    if player_id == current_user.id and msg['table_id'] in game.tables:
        print(msg)
        table = game.tables[msg['table_id']]
        if player_id in table.round.players:
            player = game.players[player_id]
            cards_hand = player.get_cards()
            # cards_table = table.round.current_trick.get_cards()
            dealer = table.get_dealer()
            current_player_id = table.round.players[1]
            socketio.emit('your-cards-please',
                          {'player_id': player_id,
                           'turn_count': table.round.turn_count,
                           'current_player_id': current_player_id,
                           'dealer': dealer,
                           # 'order_names': table.round.order_names,
                           'html': {'cards_hand': render_template('cards_hand.html',
                                                                  cards_hand=cards_hand,
                                                                  table=table,
                                                                  player=player),
                                    # 'cards_table': render_template('cards_table.html',
                                    #                               cards_table=cards_table,
                                    #                               table=table),
                                    'hud_players': render_template('hud_players.html',
                                                                   player=player,
                                                                   dealer=dealer,
                                                                   current_player_id=current_player_id)}},
                          room=request.sid)


@socketio.on('claim-trick')
def claimed_trick(msg):
    player_id = msg['player_id']
    if player_id == current_user.id and \
            msg['table_id'] in game.tables:
        print(msg)
        table = game.tables[msg['table_id']]
        if player_id in table.round.players:
            if not table.round.is_finished():
                # when ownership changes it does at previous trick because normally there is a new one created
                # so the new one becomes the current one and the reclaimed is the previous
                if not len(table.round.current_trick.cards) == 0:
                    # old trick, freshly claimed
                    # table.round.current_trick.owner = table.round.players[player_id]
                    table.round.current_trick.owner = player_id
                    # new trick for next turns
                    # table.round.add_trick(table.players[player_id])
                    table.round.add_trick(player_id)
                else:
                    # apparently the ownership of the previous trick is not clear - change it
                    table.round.previous_trick.owner = player_id
                    table.round.current_player = player_id
                score = table.round.get_score()
                socketio.emit('next-trick',
                              {'current_player_id': player_id,
                               'score': score},
                              room=table.id)
            else:
                table.round.current_trick.owner = player_id
                print(table.round.tricks)
                print(table.round.get_score())
                # tell everybody stats and wait for everybody confirming next round
                socketio.emit('round-finished',
                              {'table_id': table.id,
                               'html': render_template('score.html',
                                                       table=table,
                                                       score=table.round.get_score())
                               },
                              room=table.id)


@socketio.on('ready-for-next-round')
def ready_for_next_round(msg):
    player_id = msg['player_id']
    if player_id == current_user.id and \
            msg['table_id'] in game.tables:
        print(msg)
        table = game.tables[msg['table_id']]
        table.add_ready_player(player_id)
        # if len(table.players_ready) == len(table.players):
        if set(table.players_ready) == set(table.round.players):
            table.shift_players()
            dealer = table.get_dealer()
            table.reset_ready_players()
            # just tell everybody to get personal cards
            socketio.emit('start-next-round',
                          {'table_id': table.id,
                           'dealer': dealer})


@socketio.on('request-round-reset')
def reset_round_temp_func(msg):
    table = game.tables[msg['table_id']]
    #table.reset_round()
    # just tell everybody to get personal cards
    socketio.emit('round-reset-requested',
                  {'table_id': table.id,
                   'html': render_template('request_round_reset.html',
                                           table=table)
                   },
                 room=table.id)

    # socketio.emit('grab-your-cards',
    #               {'table_id': table.id})



@app.route('/login', methods=['GET', 'POST'])
def login():
    form = Login()
    if form.validate_on_submit():
        if not form.player_id.data in game.players:
            flash('Unknown player :-(')
            return redirect(url_for('login'))
        else:
            player = game.players[form.player_id.data]
            if not player.check_password(form.password.data):
                flash('Wrong password :-(')
                return redirect(url_for('login'))
            login_user(player)
            return redirect(url_for('index'))

    print(current_user, current_user.is_authenticated)

    return render_template('login.html',
                           title='doko3000 Login',
                           form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    return render_template('index.html',
                           tables=game.get_tables(),
                           players=game.get_players(),
                           title='doko3000')


@app.route('/table/<table_id>')
@login_required
def table(table_id=''):
    if table_id in game.tables and \
            current_user.id in game.tables[table_id].players:
        player = game.players[current_user.id]
        table = game.tables[table_id]
        dealer = table.get_dealer()
        # if no card is played already the dealer might deal
        dealing_needed = table.round.turn_count == 0
        # if one trick right now was finished the claim-trick-button should be displayed again
        trick_claiming_needed = table.round.turn_count % 4 == 0 and table.round.turn_count > 0
        current_player_id = table.round.current_player
        cards_hand = player.get_cards()
        cards_table = table.round.current_trick.get_cards()
        score = table.round.get_score()
        return render_template('table.html',
                               title=f'doko3000 {table_id}',
                               table=table,
                               dealer=dealer,
                               dealing_needed=dealing_needed,
                               trick_claiming_needed=trick_claiming_needed,
                               player=player,
                               current_player_id=current_player_id,
                               cards_hand=cards_hand,
                               cards_table=cards_table,
                               score=score)
    return render_template('index.html',
                           tables=game.tables,
                           title='doko3000')
