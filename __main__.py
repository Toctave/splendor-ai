import csv
import random
from itertools import combinations

DECK_COUNT = 3
EXPOSED_CARD_COUNT = 4
GEM_COLORS = ['white', 'blue', 'green', 'red', 'black']

def load_decks(filename):
    decks = [[] for _ in range(DECK_COUNT)]
    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            price = [int(row[color]) for color in GEM_COLORS]
            card = Card(
                int(row['level']),
                int(row['points']),
                GEM_COLORS.index(row['color']),
                price
            )
            decks[card.level-1].append(card)
    return decks

def load_nobles(filename):
    nobles = []
    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            nobles.append([int(row[color]) for color in GEM_COLORS])
    return nobles

def game_settings(player_count):
    if player_count == 2:
        return 4, 3
    elif player_count == 3:
        return 5, 4
    elif player_count == 4:
        return 7, 5

class Card:
    def __init__(self, level, points, color, price):
        self.points = points
        self.color = color
        self.level = level
        self.price = price

    def __repr__(self):
        return f"Card({self.level}, {self.points}, {self.color}, {self.price})"

class Board:
    def __init__(self, player_count):
        self.decks = load_decks('cards.csv')
        for deck in self.decks:
            random.shuffle(deck)

        self.grid = [[deck.pop() for _ in range(EXPOSED_CARD_COUNT)] for deck in self.decks]

        token_count, noble_count = game_settings(player_count)
        
        all_nobles = load_nobles('nobles.csv')
        random.shuffle(all_nobles)

        self.nobles = all_nobles[:noble_count]
        self.tokens = [token_count for color in GEM_COLORS]
        self.gold = 5

class Player:
    def __init__(self):
        self.tokens = [0 for _ in GEM_COLORS]
        self.card_tokens = [0 for _ in GEM_COLORS]
        self.gold = 0
        self.reserved_cards = []
        self.bought_cards = []
        self.nobles = []
        self.points = 0

    def can_pay(self, price):
        excess = sum(max(0, price[i] - self.tokens[i] - self.card_tokens[i]) for i in range(len(price)))
        return self.gold >= excess

def transfer_tokens(src, dst, color, count):
    src.tokens[color] -= count
    dst.tokens[color] += count

def transfer_gold(src, dst, count):
    src.gold -= count
    dst.gold += count

def pay_card(board, player, card):
    for color in range(len(GEM_COLORS)):
        card_token_count = player.card_tokens[color]
        due = max(0, card.price[color] - card_token_count)
        
        token_count = min(due, player.tokens[color])
        gold_count = due - token_count

        transfer_tokens(player, board, color, token_count)
        transfer_gold(player, board, gold_count)

class ReserveCard:
    def __init__(self, tier, card_index):
        self.tier = tier
        self.card_index = card_index

    def play(self, board, player):
        card = board.grid[self.tier][self.card_index]
        board.grid[self.tier][self.card_index] = board.decks[self.tier].pop()
        player.reserved_cards.append(card)
        transfer_gold(board, player, 1)

    def __repr__(self):
        return f"ReserveCard({self.tier}, {self.card_index})"

class TakeTokens:
    def __init__(self, counts):
        self.counts = counts

    def play(self, board, player):
        for color, count in enumerate(self.counts):
            transfer_tokens(board, player, color, count)

    def __repr__(self):
        return f"TakeTokens({self.counts})"

class BuyBoardCard:
    def __init__(self, tier, card_index):
        self.tier = tier
        self.card_index = card_index

    def play(self, board, player):
        card = board.grid[self.tier][self.card_index]
        pay_card(board, player, card)

        if len(board.decks[self.tier]) > 0:
            board.grid[self.tier][self.card_index] = board.decks[self.tier].pop()
        else:
            board.grid[self.tier][self.card_index] = None
        player.bought_cards.append(card)
        player.points += card.points
        player.card_tokens[card.color] += 1

    def __repr__(self):
        return f"BuyBoardCard({self.tier}, {self.card_index})"

class BuyReservedCard:
    def __init__(self, idx):
        self.idx = idx

    def play(self, board, player):
        card = player.reserved_cards[self.idx]
        pay_card(board, player, card)
        player.reserved_cards = player.reserved_cards[:self.idx] + player.reserved_cards[(self.idx+1):]
        player.bought_cards.append(card)
        player.points += card.points
        player.card_tokens[card.color] += 1

    def __repr__(self):
        return f"BuyReservedCard({self.idx})"

class Game:
    def __init__(self, player_count):
        self.board = Board(player_count)
        self.players = [Player() for _ in range(player_count)]
        self.current_player = 0

    def winners(self):
        return [i for i, player in enumerate(self.players) if player.points >= 15]

    def play_action(self, action):
        action.play(self.board, self.players[self.current_player])
        self.current_player += 1
        if self.current_player == len(self.players):
            self.current_player = 0

def available_actions(player, board):
    actions = []
    for tier in range(DECK_COUNT):
        for idx in range(EXPOSED_CARD_COUNT):
            if player.can_pay(board.grid[tier][idx].price):
                actions.append(BuyBoardCard(tier, idx))
            if len(player.reserved_cards) < 3:
                actions.append(ReserveCard(tier, idx))

    for i, card in enumerate(player.reserved_cards):
        if player.can_pay(card.price):
            actions.append(BuyReservedCard(i))

    token_total = sum(player.tokens)
    tokens_allowed = 10 - token_total

    take_token_counts = set()
    for color in range(len(GEM_COLORS)):
        if board.tokens[color] >= 4:
            counts = [0 for _ in GEM_COLORS]
            counts[color] = min(board.tokens[color], 2, tokens_allowed)

            take_token_counts.add(tuple(counts))

    all_colors = list(range(len(GEM_COLORS)))
    for color_triplet in combinations(all_colors, 3):
        counts = [0 for _ in GEM_COLORS]
        any_left = False
        for color in color_triplet:
            if board.tokens[color] > 0:
                any_left = True
                counts[color] = 1
        take_token_counts.add(tuple(counts))

    actions.extend(TakeTokens(counts) for counts in take_token_counts if sum(counts) > 0)

    return actions

player_count = 2

game = Game(player_count)
while len(game.winners()) == 0:
    for _ in range(player_count):
        player = game.players[game.current_player]
        actions = available_actions(player, game.board)

        action = random.choice(actions)

        print(f"Player {game.current_player + 1} : {action}")
        game.play_action(action)

print("Winners : ", game.winners())
