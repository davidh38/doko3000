from time import time

from flask import flash, \
    Flask, \
    jsonify, \
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
    leave_room, \
    SocketIO

from .config import Config
from .database import DB
from .game import Deck, \
    Game
from .misc import CreateTable, \
    is_xhr, \
    Login

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

game = Game(db)
game.load_from_db()


# game.test_game()


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
    if not current_user.is_anonymous:
        player_id = current_user.id
        table_id = game.players[player_id].table
        round_finished = False
        # if player already sits on a table inform client
        if table_id:
            current_player_id = game.tables[table_id].round.current_player
            round_finished = game.tables[table_id].round.is_finished()
            join_room(table_id)
        else:
            current_player_id = ''
        socketio.emit('you-are-what-you-is',
                      {'player_id': player_id,
                       'table_id': table_id,
                       'current_player_id': current_player_id,
                       'round_finished': round_finished})


@socketio.on('new-table')
def new_table(msg):
    game.add_table('test2')
    game.tables['test2'].add_player(current_user.id)
    socketio.emit('new-table-available',
                  {'tables': game.get_tables_names(),
                   'player_id': current_user.id,
                   'html': render_template('index/list_tables.html',
                                           tables=game.get_tables())},
                  broadcast=True)


@socketio.on('played-card')
def played_card(msg):
    card_id = msg.get('card_id')
    player_id = msg.get('player_id')
    table_id = msg.get('table_id')
    if card_id in Deck.cards and \
            player_id in game.players and \
            table_id in game.tables:
        player = game.players[player_id]
        if player.table == table_id:
            table = game.tables[table_id]
            if current_user.id == player.id == table.round.current_player:
                table.round.current_trick.add_turn(player.id, card_id)
                table.round.increase_turn_count()
                card = Deck.cards[card_id]
                player.remove_card(card.id)
                is_last_turn = table.round.current_trick.is_last_turn()
                current_player_id = table.round.get_current_player()
                idle_players = table.idle_players
                socketio.emit('played-card-by-user',
                              {'player_id': player.id,
                               'card_id': card.id,
                               'card_name': card.name,
                               'is_last_turn': is_last_turn,
                               'current_player_id': current_player_id,
                               'idle_players': idle_players,
                               'html': {'card': render_template('cards/card.html',
                                                                card=Deck.cards[card_id],
                                                                table=table),
                                        'hud_players': render_template('top/hud_players.html',
                                                                       table=table,
                                                                       player=player,
                                                                       current_player_id=current_player_id)
                                        }},
                              room=table.id)


@socketio.on('enter-table')
def enter_table_socket(msg):
    table_id = msg.get('table_id')
    player_id = msg.get('player_id')
    if table_id in game.tables and \
            player_id in game.players:
        table = game.tables[table_id]
        if (table.locked and player_id in table.players) or \
                not table.locked:
            game.tables[table_id].add_player(player_id)
            join_room(table_id)


@socketio.on('setup-table-change')
def enter_table(msg):
    table_id = msg.get('table_id')
    player_id = msg.get('player_id')
    action = msg.get('action')
    if table_id in game.tables:
        table = game.tables[table_id]
        if player_id in table.players:
            if action == 'delete_player':
                table.remove_player(player_id)
                leave_room(table_id)
            elif action == 'lock_table':
                table.locked = True
            elif action == 'unlock_table':
                table.locked = False
            elif action == 'play_with_9':
                table.round.with_9 = True
            elif action == 'play_without_9':
                table.round.with_9 = False
            elif action == 'changed_order':
                order = msg.get('order')
                if set(order) == set(table.order):
                    table.players = order
            elif action == 'start_table':
                table.start()
                # just tell everybody to get personal cards
                socketio.emit('grab-your-cards',
                              {'table_id': table.id},
                              room=table.id)


@socketio.on('deal-cards')
def deal_cards(msg):
    table_id = msg.get('table_id')
    if table_id:
        table = game.tables[table_id]
        table.reset_round()
        # just tell everybody to get personal cards
        socketio.emit('grab-your-cards',
                      {'table_id': table.id},
                      room=table.id)


@socketio.on('deal-cards-again')
def deal_cards_again(msg):
    table_id = msg.get('table_id')
    if table_id and table_id in game.tables:
        table = game.tables[table_id]
        # ask dealer if really should be re-dealt
        socketio.emit('really-deal-again',
                      {'table_id': table.id,
                       'html': render_template('round/request_deal_again.html',
                                               table=table)},
                      room=request.sid)


@socketio.on('my-cards-please')
def deal_cards_to_player(msg):
    """
    give player cards after requesting them
    """
    player_id = msg.get('player_id')
    table_id = msg.get('table_id')
    if player_id in game.players and \
            table_id in game.tables:
        player = game.players[player_id]
        if player.table == table_id and \
                table_id in game.tables:
            table = game.tables[table_id]
            if player.id == current_user.id and table.id in game.tables:
                if player.id in table.players:
                    dealer = table.dealer
                    # just in case
                    join_room(table.id)
                    current_player_id = table.round.current_player
                    if player.id in table.round.players:
                        cards_hand = player.get_cards()
                        socketio.emit('your-cards-please',
                                      {'player_id': player.id,
                                       'turn_count': table.round.turn_count,
                                       'current_player_id': current_player_id,
                                       'dealer': dealer,
                                       # 'order_names': table.round.order_names,
                                       'html': {'cards_hand': render_template('cards/hand.html',
                                                                              cards_hand=cards_hand,
                                                                              table=table,
                                                                              player=player),
                                                'hud_players': render_template('top/hud_players.html',
                                                                               table=table,
                                                                               player=player,
                                                                               dealer=dealer,
                                                                               current_player_id=current_player_id)}},
                                      room=request.sid)
                    else:
                        # one day becoming spectator mode
                        socketio.emit('sorry-no-cards-for-you',
                                      {'html': {'hud_players': render_template('top/hud_players.html',
                                                                               table=table,
                                                                               player=player,
                                                                               dealer=dealer,
                                                                               current_player_id=current_player_id)}},
                                      room=request.sid)


@socketio.on('sorted-cards')
def sorted_cards(msg):
    """
    while player sorts cards every card placed somewhere causes transmission of current card sort order
    which gets saved here
    """
    player_id = msg.get('player_id')
    table_id = msg.get('table_id')
    if player_id and table_id:
        if player_id == current_user.id and \
                player_id in game.players and \
                table_id in game.tables:
            player = game.players[player_id]
            if table_id == player.table:
                cards_hand_ids = msg.get('cards_hand_ids')
                if set(cards_hand_ids) == set(player.cards):
                    player.cards = cards_hand_ids
                    player.save()


@socketio.on('claim-trick')
def claimed_trick(msg):
    player = game.players[msg['player_id']]
    if player.id == current_user.id and \
            msg['table_id'] in game.tables:
        table = game.tables[msg['table_id']]
        if player.id in table.round.players:
            if not table.round.is_finished():
                # when ownership changes it does at previous trick because normally there is a new one created
                # so the new one becomes the current one and the reclaimed is the previous
                if not len(table.round.current_trick.cards) == 0:
                    # old trick, freshly claimed
                    # table.round.current_trick.owner = table.round.players[player_id]
                    table.round.current_trick.owner = player.id
                    # new trick for next turns
                    # table.round.add_trick(table.players[player_id])
                    table.round.add_trick(player.id)
                else:
                    # apparently the ownership of the previous trick is not clear - change it
                    table.round.previous_trick.owner = player.id
                    table.round.current_player = player.id
                dealer = table.dealer
                score = table.round.get_score()
                table.round.calculate_trick_order()
                socketio.emit('next-trick',
                              {'current_player_id': player.id,
                               'score': score,
                               'html': {'hud_players': render_template('top/hud_players.html',
                                                                       table=table,
                                                                       player=player,
                                                                       dealer=dealer,
                                                                       current_player_id=player.id)}},
                              room=table.id)
            else:
                table.round.current_trick.owner = player.id
                score = table.round.get_score()
                table.shift_players()
                # tell everybody stats and wait for everybody confirming next round
                socketio.emit('round-finished',
                              {'table_id': table.id,
                               'html': render_template('round/score.html',
                                                       table=table,
                                                       score=score)
                               },
                              room=table.id)


@socketio.on('need-final-result')
def send_final_result(msg):
    player_id = msg.get('player_id')
    table_id = msg.get('table_id')
    if player_id and table_id:
        if player_id == current_user.id and \
                player_id in game.players and \
                table_id in game.tables:
            player = game.players[player_id]
            if table_id == player.table:
                table = game.tables[msg['table_id']]
                score = table.round.get_score()
                # tell single player stats and wait for everybody confirming next round
                socketio.emit('round-finished',
                              {'table_id': table.id,
                               'html': render_template('round/score.html',
                                                       table=table,
                                                       score=score)
                               },
                              room=request.sid)


@socketio.on('ready-for-next-round')
def ready_for_next_round(msg):
    player_id = msg.get('player_id')
    table_id = msg.get('table_id')
    if player_id == current_user.id and \
            table_id in game.tables:
        table = game.tables[table_id]
        table.add_ready_player(player_id)
        game.players[player_id].remove_all_cards()
        dealer = table.dealer
        next_players = table.order[:4]
        number_of_rows = max(len(next_players), len(table.idle_players))
        if set(table.players_ready) >= set(table.round.players):
            # now shifted when round is finished
            # table.shift_players()
            table.reset_ready_players()
            # just tell everybody to get personal cards
        socketio.emit('start-next-round',
                      {'table_id': table.id,
                       'dealer': dealer,
                       'html': render_template('round/info.html',
                                               table=table,
                                               dealer=dealer,
                                               next_players=next_players,
                                               number_of_rows=number_of_rows)
                       },
                      room=request.sid)


@socketio.on('request-round-reset')
def request_round_reset(msg):
    table = game.tables[msg['table_id']]
    # just tell everybody to get personal cards
    socketio.emit('round-reset-requested',
                  {'table_id': table.id,
                   'html': render_template('round/request_reset.html',
                                           table=table)
                   },
                  room=table.id)


@socketio.on('request-round-finish')
def request_round_finish(msg):
    table = game.tables[msg['table_id']]
    # just tell everybody to get personal cards
    socketio.emit('round-finish-requested',
                  {'table_id': table.id,
                   'html': render_template('round/request_finish.html',
                                           table=table)
                   },
                  room=table.id)


@socketio.on('ready-for-round-reset')
def round_reset(msg):
    player_id = msg['player_id']
    table_id = msg['table_id']
    if player_id == current_user.id and \
            table_id in game.tables:
        table = game.tables[table_id]
        table.add_ready_player(player_id)
        if set(table.players_ready) >= set(table.round.players):
            table.reset_round()
            socketio.emit('grab-your-cards',
                          {'table_id': table.id})


@socketio.on('ready-for-round-finish')
def round_finish(msg):
    player_id = msg['player_id']
    table_id = msg['table_id']
    if player_id == current_user.id and \
            table_id in game.tables:
        table = game.tables[table_id]
        table.add_ready_player(player_id)
        if set(table.players_ready) >= set(table.round.players):
            table.shift_players()
            dealer = table.dealer
            table.reset_ready_players()
            next_players = table.order[:4]
            number_of_rows = max(len(next_players), len(table.idle_players))
            # just tell everybody to get personal cards
            socketio.emit('start-next-round',
                          {'table_id': table.id,
                           'dealer': dealer,
                           'html': render_template('round/info.html',
                                                   table=table,
                                                   next_players=next_players,
                                                   number_of_rows=number_of_rows)}
                          )


@socketio.on('ready-for-round-restart')
def round_restart(msg):
    player_id = msg['player_id']
    table_id = msg['table_id']
    if player_id == current_user.id and \
            table_id in game.tables:
        table = game.tables[table_id]
        table.add_ready_player(player_id)
        if len(table.players_ready) >= 4:
            table.reset_round()
            dealer = table.dealer
            table.reset_ready_players()
            next_players = table.order[:4]
            number_of_rows = max(len(next_players), len(table.idle_players))
            # just tell everybody to get personal cards
            socketio.emit('start-next-round',
                          {'table_id': table.id,
                           'dealer': dealer,
                           'html': render_template('round/info.html',
                                                   table=table,
                                                   next_players=next_players,
                                                   number_of_rows=number_of_rows)})


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = Login()
    if form.validate_on_submit():
        if not form.player_id.data in game.players:
            flash('Spieler nicht bekannt :-(')
            return redirect(url_for('login'))
        else:
            player = game.players[form.player_id.data]
            if not player.check_password(form.password.data):
                flash('Falsches Passwort :-(')
                return redirect(url_for('login'))
            login_user(player)
            return redirect(url_for('index'))
    return render_template('login.html',
                           title=f"{app.config['TITLE']} Login",
                           form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    players = game.get_players()
    tables = game.get_tables()
    return render_template('index.html',
                           tables=tables,
                           players=players,
                           title=f"{app.config['TITLE']}")


@app.route('/table/<table_id>')
@login_required
def table(table_id=''):
    if table_id in game.tables and \
            current_user.id in game.tables[table_id].players:
        player = game.players[current_user.id]
        table = game.tables[table_id]
        dealer = table.dealer
        # if no card is played already the dealer might deal
        dealing_needed = table.round.turn_count == 0
        # if one trick right now was finished the claim-trick-button should be displayed again
        trick_claiming_needed = table.round.turn_count % 4 == 0 and \
                                table.round.turn_count > 0 and \
                                not table.round.is_finished()
        current_player_id = table.round.current_player
        cards_hand = player.get_cards()
        cards_table = table.round.current_trick.get_cards()
        score = table.round.get_score()
        return render_template('table.html',
                               title=f"{app.config['TITLE']} {table_id}",
                               table=table,
                               dealer=dealer,
                               dealing_needed=dealing_needed,
                               trick_claiming_needed=trick_claiming_needed,
                               player=player,
                               current_player_id=current_player_id,
                               cards_hand=cards_hand,
                               cards_table=cards_table,
                               score=score)
    tables = game.get_tables()
    return render_template('index.html',
                           tables=tables,
                           title=f"{app.config['TITLE']}")


@app.route('/table/setup/<table_id>')
@login_required
def setup_table(table_id):
    """
    configure table, its players and start - should be no socket but xhr here for easier formular check
    well, formular check seems to be unnecessary for now, but anyway it is an easy way to deliver it
    """
    if is_xhr(request) and table_id:
        if table_id in game.tables:
            table = game.tables[table_id]
            if current_user.id in game.players and \
                    (current_user.id in table.players or
                     not table.locked):
                return jsonify({'allowed': True,
                                'html': render_template('setup_table.html',
                                                        table=table)})
            else:
                return jsonify({'allowed': False})

        else:
            return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))


@app.route('/table/enter/<table_id>/<player_id>')
@login_required
def enter_table_json(table_id='', player_id=''):
    """
    give #buttom_enter_table permission or not, depending on player membership or table lockedness
    support for socket.io request, just telling #button_enter_table if its link can be followed or not
    """
    if is_xhr(request) and table_id:
        allowed = False
        if table_id in game.tables and \
                player_id in game.players:
            table = game.tables[table_id]
            if (table.locked and player_id in table.players) or \
                    not table.locked:
                allowed = True
        return jsonify({'allowed': allowed})
    else:
        return redirect(url_for('index'))


@app.route('/get/tables')
@login_required
def get_html_tables():
    """
    get HTML list of tables to refresh index.html tables list after changes
    """
    if is_xhr(request):
        tables = game.get_tables()
        return jsonify({'html': render_template('index/list_tables.html',
                                                tables=tables)})
    else:
        return redirect(url_for('index'))


@app.route('/create/table')
@login_required
def create_table():
    """
    create table via button
    """
    if is_xhr(request):
        form = CreateTable()
        if request.method == 'GET':
            return jsonify({'html': render_template('index/create_table.html',
                                                    form=form)})
        elif request.method == 'POST':
            pass
        else:
            return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))
