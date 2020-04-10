# game logic part of doko3000

from copy import deepcopy
from random import seed,\
                   shuffle

class Card:
    """
    one single card
    """

    def __init__(self, symbol, rank):
        """
        symbol, rank and value come from deck
        """
        self.symbol = symbol
        # value is needed for counting score at the end
        self.rank, self.value = rank


class Deck:
    """
    full deck of cards - enough to be static
    """
    SYMBOLS = ('Schell',
               'Herz',
               'Grün',
               'Eichel')
    RANKS = {'Zehn':10,
             'Bube':2,
             'Dame':3,
             'König':4,
             'Ass':11}
    NUMBER = 2 # Doppelkopf :-)!
    cards = []

    for number in range(NUMBER):
        for symbol in SYMBOLS:
            for rank in RANKS.items():
                cards.append(Card(symbol, rank))


class Player:
    """
    one single player on a table
    """
    def __init__(self, name):
        # Name of player
        self.name = name
        # current set of cards
        self.cards = []
        # gained cards
        self.tricks = []

    def get_card(self, card):
        self.cards.append(card)


class Round:
    """
    one round
    """
    def __init__(self, players):
        # if more than 4 players they change for every round
        # changing too because of the position of dealer changes with every round
        self.players = players
        # cards are an important part but makes in a round context only sense if shuffled
        self.cards = deepcopy(Deck.cards)
        # needed to know how many cards are dealed
        # same as number of turns in a round
        self.cards_per_player = len(self.cards) // len(self.players)
        # first shuffling, then dealing
        self.shuffle()
        self.deal()

    def shuffle(self):
        """
        shuffle cards
        """
        shuffle(self.cards)

    def deal(self):
        """
        deal cards
        """
        for player in self.players:
            for card in range(self.cards_per_player):
                # cards are given to players so the can be .pop()ed
                player.get_card(self.cards.pop())


class Table:
    """
    Definition of a table
    """
    def __init__(self, name):
        # ID
        identity = 0
        # what table?
        self.name = name
        # who plays?
        self.players = {}
        # how are the players seated?
        self.order = []
        # rounds, one after another
        self.rounds = []
        # latest round
        self.current_round = None

    def add_player(self, player):
        """
        adding just one player to the party
        """
        if type(player) is str:
            player = Player(player)
        self.players[player.name] = player

    def add_round(self):
        """
        only 4 players can play at once - find out who and start a new round
        """
        current_players = []
        for name in self.order[:4]:
            current_players.append(self.players[name])
        self.current_round = Round(current_players)


class Game:
    """
    organizes tables
    """
    def __init__(self):
        # very important for game - some randomness
        seed()
        # store tables
        self.tables = {}

    def add_table(self, name):
        """
        adds a new table
        """
        self.tables[name] = Table(name)

    def has_tables(self):
        if len(self.tables) == 0:
            return False
        else:
            return True

    def get_tables(self):
        return self.tables.values()

    def get_tables_names(self):
        return list(self.tables.keys())


game = Game()


def test_game():
    game.add_table('test')
    for name in ('test1', 'test2', 'test3', 'test4', 'test5'):
        player = Player(name)
        game.tables['test'].add_player(player)
    game.tables['test'].order = ['test1', 'test2', 'test3', 'test4', 'test5']

    game.tables['test'].add_round()

    print()