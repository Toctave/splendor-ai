import csv
import random
from itertools import combinations, combinations_with_replacement

DECK_COUNT = 3
EXPOSED_CARD_COUNT = 4
GEM_COLORS = ['white', 'blue', 'green', 'red', 'black']
GEM_COLORS_SHORT = ['w', 'u', 'g', 'r', 'k']

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

def token_counts_str(counts):
    return ", ".join(f"{count} {color}" for count, color in zip(counts, GEM_COLORS) if count != 0)

def token_counts_short_str(counts):
    return "".join(f"{count}{color}" for count, color in zip(counts, GEM_COLORS_SHORT) if count != 0)

class Card:
    def __init__(self, level, points, color, price):
        self.points = points
        self.color = color
        self.level = level
        self.price = price

    def __repr__(self):
        return f"Card({self.level}, {self.points}, {GEM_COLORS[self.color]}, {token_counts_short_str(self.price)})"

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

    def __repr__(self):
        return f"Player(tokens=[{token_counts_short_str(self.tokens)}], gold={self.gold}, reserved={self.reserved_cards}, bought={self.bought_cards}, nobles={list(map(token_counts_short_str, self.nobles))})"

def transfer_tokens(src, dst, color, count):
    src.tokens[color] -= count
    dst.tokens[color] += count

def transfer_token_counts(src, dst, counts):
    for color, count in enumerate(counts):
        transfer_tokens(src, dst, color, count)

def transfer_gold(src, dst, count):
    src.gold -= count
    dst.gold += count

def pay_card(board, player, card):
    paid_tokens = [0] * len(GEM_COLORS)
    paid_gold = 0
    
    for color in range(len(GEM_COLORS)):
        card_token_count = player.card_tokens[color]
        due = max(0, card.price[color] - card_token_count)
        
        token_count = min(due, player.tokens[color])
        gold_count = due - token_count

        transfer_tokens(player, board, color, token_count)
        transfer_gold(player, board, gold_count)

        paid_tokens[color] = token_count
        paid_gold += gold_count
        
    return paid_tokens, paid_gold

class ReserveCard:
    def __init__(self, tier, card_index):
        self.tier = tier
        self.card_index = card_index
        self.transferred_gold = False

    def play(self, board, player):
        card = board.grid[self.tier][self.card_index]
        if len(board.decks[self.tier]) > 0:
            board.grid[self.tier][self.card_index] = board.decks[self.tier].pop()
        else:
            board.grid[self.tier][self.card_index] = None
        player.reserved_cards.append(card)
        if board.gold > 0:
            transfer_gold(board, player, 1)
            self.transferred_gold = True

    def undo(self, board, player):
        new_card = board.grid[self.tier][self.card_index]
        if new_card is not None:
            board.decks[self.tier].append(new_card)
        board.grid[self.tier][self.card_index] = player.reserved_cards.pop()
        if self.transferred_gold:
            transfer_gold(player, board, 1)

    def __repr__(self):
        return f"ReserveCard({self.tier}, {self.card_index})"

class TakeTokens:
    def __init__(self, counts):
        self.counts = counts

    def play(self, board, player):
        for color, count in enumerate(self.counts):
            transfer_tokens(board, player, color, count)

    def undo(self, board, player):
        for color, count in enumerate(self.counts):
            transfer_tokens(player, board, color, count)
            
    def __repr__(self):
        return f"TakeTokens({token_counts_str(self.counts)})"

class BuyBoardCard:
    def __init__(self, tier, card_index):
        self.tier = tier
        self.card_index = card_index

        self.paid_tokens = None
        self.paid_gold = None

    def play(self, board, player):
        card = board.grid[self.tier][self.card_index]
        self.paid_tokens, self.paid_gold = pay_card(board, player, card)

        if len(board.decks[self.tier]) > 0:
            board.grid[self.tier][self.card_index] = board.decks[self.tier].pop()
        else:
            board.grid[self.tier][self.card_index] = None
        player.bought_cards.append(card)
        player.points += card.points
        player.card_tokens[card.color] += 1

    def undo(self, board, player):
        card = player.bought_cards.pop()
        player.points -= card.points
        player.card_tokens[card.color] -= 1
        
        new_card = board.grid[self.tier][self.card_index]
        if new_card is not None:
            board.decks[self.tier].append(new_card)
        board.grid[self.tier][self.card_index] = card

        transfer_token_counts(board, player, self.paid_tokens)
        transfer_gold(board, player, self.paid_gold)

    def __repr__(self):
        return f"BuyBoardCard({self.tier}, {self.card_index})"

class BuyReservedCard:
    def __init__(self, idx):
        self.idx = idx

        self.paid_tokens = None
        self.paid_gold = None

    def play(self, board, player):
        card = player.reserved_cards[self.idx]
        self.paid_tokens, self.paid_gold = pay_card(board, player, card)
        player.reserved_cards = player.reserved_cards[:self.idx] + player.reserved_cards[(self.idx+1):]
        player.bought_cards.append(card)
        player.points += card.points
        player.card_tokens[card.color] += 1
        
    def undo(self, board, player):
        card = player.bought_cards.pop()
        player.points -= card.points
        player.card_tokens[card.color] -= 1

        player.reserved_cards.insert(self.idx, card)

        transfer_token_counts(board, player, self.paid_tokens)
        transfer_gold(board, player, self.paid_gold)

    def __repr__(self):
        return f"BuyReservedCard({self.idx})"

class Game:
    def __init__(self, player_count):
        self.board = Board(player_count)
        self.players = [Player() for _ in range(player_count)]
        self.current_player = 0

        self.history = []

    def winners(self):
        return [i for i, player in enumerate(self.players) if player.points >= 15]

    def trigger_nobles(self):
        player = self.players[self.current_player]
        for idx, noble in enumerate(self.board.nobles):
            if player.can_pay(noble):
                player.nobles.append(noble)
                player.points += 3
                self.board.nobles = self.board.nobles[:idx] + self.board.nobles[(idx+1):]
                return idx

        return None

    def play_action(self, action):
        action.play(self.board, self.players[self.current_player])

        noble_idx = self.trigger_nobles()
        
        self.current_player += 1
        if self.current_player == len(self.players):
            self.current_player = 0
        self.history.append((action, noble_idx))
        
    def undo_action(self):
        action, noble_idx = self.history.pop()
        self.current_player -= 1
        if self.current_player < 0:
            self.current_player = len(self.players) - 1

        player = self.players[self.current_player]
        if noble_idx is not None:
            player.points -= 3
            self.board.nobles.insert(noble_idx, player.nobles.pop())
            
        action.undo(self.board, player)

def take_and_return(counts, player):
    excess = sum(player.tokens) + player.gold + sum(counts) - 10
    if excess <= 0:
        yield tuple(counts)
    else:
        all_colors = list(range(len(GEM_COLORS)))
        for colors in combinations_with_replacement(all_colors, excess):
            counts_with_returned = [count for count in counts]
            for color in colors:
                counts_with_returned[color] -= 1
            if all(player_count + count >= 0 for player_count, count in zip(player.tokens, counts_with_returned)):
                yield tuple(counts_with_returned)
            
def available_actions(player, board):
    actions = []
    for tier in range(DECK_COUNT):
        for idx in range(EXPOSED_CARD_COUNT):
            if board.grid[tier][idx] is not None:
                if player.can_pay(board.grid[tier][idx].price):
                    actions.append(BuyBoardCard(tier, idx))
                if len(player.reserved_cards) < 3:
                    actions.append(ReserveCard(tier, idx))

    for i, card in enumerate(player.reserved_cards):
        if player.can_pay(card.price):
            actions.append(BuyReservedCard(i))

    token_total = sum(player.tokens)

    take_token_counts = set()
    for color in range(len(GEM_COLORS)):
        if board.tokens[color] >= 4:
            counts = [0 for _ in GEM_COLORS]
            counts[color] = min(board.tokens[color], 2)

            take_token_counts.update(take_and_return(counts, player))

    all_colors = list(range(len(GEM_COLORS)))
    for color_triplet in combinations(all_colors, 3):
        counts = [0 for _ in GEM_COLORS]
        any_left = False
        for color in color_triplet:
            if board.tokens[color] > 0:
                any_left = True
                counts[color] = 1
        
        take_token_counts.update(take_and_return(counts, player))

    actions.extend(TakeTokens(counts) for counts in take_token_counts if not all(count == 0 for count in counts))

    return actions

def simulate_random_game(player_count):
    game = Game(player_count)
    blocked = False
    while len(game.winners()) == 0 and not blocked:
        for _ in range(player_count):
            player = game.players[game.current_player]
            actions = available_actions(player, game.board)

            if len(actions) == 0:
                blocked = True
                break
            
            action = random.choice(actions)
            
            game.play_action(action)

    winners = game.winners()

    for i, (action, noble_idx) in enumerate(game.history):
        print(f"Player {i % player_count} : {action}")

    while len(game.history) > 0:
        game.undo_action()

    return winners

print(simulate_random_game(4))
