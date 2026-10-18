import pygame
import sys
import math
import time
import random

#board sizing
BOARD_COLS = 11
CELL_SIZE  = 62
MARGIN     = 35
SIDE_PANEL = 285
SCREEN_W   = BOARD_COLS * CELL_SIZE + MARGIN * 2 + SIDE_PANEL
SCREEN_H   = BOARD_COLS * CELL_SIZE + MARGIN * 2

# piece constants
EMPTY    = 0
ATTACKER = 1
DEFENDER = 2
KING     = 3

PLAYER_ATK = "atk"
PLAYER_DEF = "def"

#special squares
THRONE  = (5, 5)
CORNERS = {(0,0), (0,10), (10,0), (10,10)}

#colors
BG           = (11, 7, 3)
TILE_A       = (40, 24, 9)
TILE_B       = (58, 37, 14)
TILE_THRONE  = (85, 52, 13)
TILE_CORNER  = (25, 12, 5)
PANEL_BG     = (14, 9, 3)
C_GRID       = (72, 47, 16)
C_GOLD       = (200, 152, 38)
C_GOLD_FADED = (118, 90, 24)
C_COPPER     = (152, 94, 30)
C_TEXT       = (215, 188, 132)
C_TEXT_FADED = (122, 98, 54)
C_RED        = (148, 28, 18)
C_ORANGE     = (192, 85, 18)

#piece draw colors
ATK_FILL    = (20, 13, 7)
ATK_EDGE    = (84, 46, 15)
ATK_DETAIL  = (148, 74, 22)
DEF_FILL    = (195, 178, 140)
DEF_EDGE    = (132, 110, 66)
DEF_DETAIL  = (74, 56, 18)
KING_FILL   = (215, 178, 40)
KING_EDGE   = (154, 118, 20)
KING_SHINE  = (250, 234, 95)

#highlight overlays (RGBA)
OVL_SELECTED = (248, 208, 36, 125)
OVL_MOVE     = (52, 178, 74, 95)
OVL_CAPTURE  = (192, 30, 18, 172)

RUNES = "ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ"

INF = 10**9
AI_TIME_LIMITS = {1: 0.25, 3: 0.90, 5: 1.85}
DIFFICULTY_NAMES = {1: "Easy", 3: "Medium", 5: "Hard"}



#Board setup
def make_start_board():
    board = [[EMPTY] * BOARD_COLS for _ in range(BOARD_COLS)]

    board[5][5] = KING

    # defenders form a cross around the throne
    for r, c in [(3,5),(4,5),(5,3),(5,4),(5,6),(5,7),(6,5),(7,5),
                 (4,4),(4,6),(6,4),(6,6)]:
        board[r][c] = DEFENDER

    # 24 attackers, 6 per edge
    for r, c in [
        (0,3),(0,4),(0,5),(0,6),(0,7),(1,5),      # top
        (10,3),(10,4),(10,5),(10,6),(10,7),(9,5),  # bottom
        (3,0),(4,0),(5,0),(6,0),(7,0),(5,1),       # left
        (3,10),(4,10),(5,10),(6,10),(7,10),(5,9),  # right
    ]:
        board[r][c] = ATTACKER

    return board


def on_board(r, c):
    return 0 <= r < BOARD_COLS and 0 <= c < BOARD_COLS


def other_player(player):
    return PLAYER_DEF if player == PLAYER_ATK else PLAYER_ATK


def board_key(board):
    return tuple(tuple(row) for row in board)


# movement
def piece_can_stop_at(piece_type, r, c, board):
    if not on_board(r, c):
        return False
    if board[r][c] != EMPTY:
        return False
    # throne and corners: only king allowed
    if (r, c) == THRONE or (r, c) in CORNERS:
        return piece_type == KING
    return True


def raw_moves_for(board, r, c):
    """Rook-like sliding destinations before suicide-stop validation."""
    p = board[r][c]
    if p == EMPTY:
        return []
    result = []
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        nr, nc = r+dr, c+dc
        # keep going until we hit a piece or the edge
        while on_board(nr, nc) and board[nr][nc] == EMPTY:
            if piece_can_stop_at(p, nr, nc, board):
                result.append((nr, nc))
            nr += dr
            nc += dc
    return result


def moves_for(board, r, c):
    """Legal destinations, including the assignment rule: do not stop inside a sandwich."""
    p = board[r][c]
    if p == EMPTY:
        return []
    legal = []
    for tr, tc in raw_moves_for(board, r, c):
        if is_legal_move(board, r, c, tr, tc):
            legal.append((tr, tc))
    return legal


def all_moves_for_player(board, player):
    moves = []
    for r in range(BOARD_COLS):
        for c in range(BOARD_COLS):
            p = board[r][c]
            if player == PLAYER_ATK and p == ATTACKER:
                for dest in moves_for(board, r, c):
                    moves.append((r, c, dest[0], dest[1]))
            elif player == PLAYER_DEF and p in (DEFENDER, KING):
                for dest in moves_for(board, r, c):
                    moves.append((r, c, dest[0], dest[1]))
    return moves


# capture logic
def square_is_hostile_to(victim_type, r, c, board):
    """
    Is square (r,c) hostile for capturing a NORMAL piece?
    Assignment rule: a piece is captured between two opposing pieces, or
    between an opposing piece and an empty throne/corner.
    IMPORTANT: board edges are NOT hostile for normal piece capture.
    The king is unarmed, so he does not help capture attackers.
    """
    if not on_board(r, c):
        return False
    here = board[r][c]
    if (r, c) == THRONE and here == EMPTY:
        return True
    if (r, c) in CORNERS and here == EMPTY:
        return True
    if victim_type == ATTACKER:
        return here == DEFENDER   # the king is unarmed
    return here == ATTACKER


def king_side_blocked(board, r, c):
    """For king capture only: walls, empty corners/throne, and attackers block a side."""
    if not on_board(r, c):
        return True
    here = board[r][c]
    return here == ATTACKER or ((r, c) == THRONE and here == EMPTY) or ((r, c) in CORNERS and here == EMPTY)


def piece_is_sandwiched(board, r, c, piece_type):
    """True if a non-king piece is illegally standing between two hostile sides."""
    if piece_type in (EMPTY, KING):
        return False
    for (dr1, dc1), (dr2, dc2) in [((-1,0),(1,0)), ((0,-1),(0,1))]:
        if square_is_hostile_to(piece_type, r+dr1, c+dc1, board) and square_is_hostile_to(piece_type, r+dr2, c+dc2, board):
            return True
    return False


# Apply a move and handle captures. Returns new board
def do_move(board, fr, fc, tr, tc):
    
    nb = [row[:] for row in board]
    moving = nb[fr][fc]
    nb[fr][fc] = EMPTY
    nb[tr][tc] = moving

    # king can't capture anything
    if moving == KING:
        return nb

    #check all 4 directions from landing square
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        mid_r, mid_c = tr+dr, tc+dc       # square of potential victim
        far_r, far_c = tr+2*dr, tc+2*dc   # square on the other side

        if not on_board(mid_r, mid_c):
            continue
        victim = nb[mid_r][mid_c]
        if victim == EMPTY:
            continue

        #check it's actually an enemy
        if moving == ATTACKER and victim not in (DEFENDER, KING):
            continue
        if moving == DEFENDER and victim != ATTACKER:
            continue

        # king capture (needs all 4 sides)
        if victim == KING:
            continue

        if square_is_hostile_to(victim, far_r, far_c, nb):
            nb[mid_r][mid_c] = EMPTY

    return nb


def captures_made_by_move(board, fr, fc, tr, tc):
    """How many ordinary pieces disappear after this move. Used for UI and AI move ordering."""
    before = sum(1 for row in board for sq in row if sq != EMPTY)
    after_board = do_move(board, fr, fc, tr, tc)
    after = sum(1 for row in after_board for sq in row if sq != EMPTY)
    return max(0, before - after)


def is_legal_move(board, fr, fc, tr, tc):
    """Validate destination after captures, preventing illegal self-capture stops."""
    piece = board[fr][fc]
    if piece == EMPTY or (tr, tc) not in raw_moves_for(board, fr, fc):
        return False

    nb = do_move(board, fr, fc, tr, tc)

    # King may win by reaching a corner. Otherwise he must not move into capture.
    if piece == KING:
        if (tr, tc) in CORNERS:
            return True
        return not king_is_captured(nb, tr, tc)

    # Ordinary pieces may pass through sandwich positions, but may not STOP there.
    return not piece_is_sandwiched(nb, tr, tc, piece)


"""
King needs to be surrounded on all blocked sides.
(open field needs 4, near wall needs 3, in corner area needs 2)
"""
def king_is_captured(board, kr, kc):
    """
    King capture:
    - open field: all 4 sides blocked by attackers/hostile squares
    - against a wall: the wall counts as blocked, so 3 attackers can be enough
    - against a corner area: wall/corner can reduce the required attackers to 2
    """
    blocked = 0
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        if king_side_blocked(board, kr+dr, kc+dc):
            blocked += 1
    return blocked >= 4


def find_king(board):
    for r in range(BOARD_COLS):
        for c in range(BOARD_COLS):
            if board[r][c] == KING:
                return (r, c)
    return None


def game_winner(board):
    kpos = find_king(board)
    if kpos is None:
        return PLAYER_ATK
    kr, kc = kpos
    if (kr, kc) in CORNERS:
        return PLAYER_DEF
    if king_is_captured(board, kr, kc):
        return PLAYER_ATK
    return None


def count_pieces(board):
    atk = 0
    dfn = 0
    for row in board:
        for sq in row:
            if sq == ATTACKER: atk += 1
            elif sq in (DEFENDER, KING): dfn += 1
    return atk, dfn


# heuristic evaluation
def score_board(board, for_player):
    winner = game_winner(board)
    if winner == for_player:
        return 99999
    if winner is not None:
        return -99999

    kpos = find_king(board)
    if kpos is None:
        return 99999 if for_player == PLAYER_ATK else -99999
    kr, kc = kpos

    # min steps king is from any corner - manhattan
    to_corner = min(abs(kr-cr) + abs(kc-cc) for cr,cc in CORNERS)

    atk_count, def_count = count_pieces(board)

    # attackers adjacent to king
    king_pressure = 0
    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
        if on_board(kr+dr, kc+dc) and board[kr+dr][kc+dc] == ATTACKER:
            king_pressure += 1

    # attacker ring around king (wider net, 3 squares)
    encirclement = 0
    for r in range(max(0, kr-3), min(BOARD_COLS, kr+4)):
        for c in range(max(0, kc-3), min(BOARD_COLS, kc+4)):
            if board[r][c] == ATTACKER:
                encirclement += 1

    # how many corners can king reach without obstruction on same row/col
    open_escapes = 0
    for cr, cc in CORNERS:
        row_match = (kr == cr)
        col_match = (kc == cc)
        if not row_match and not col_match:
            continue
        dr2 = 0 if row_match else (1 if cr > kr else -1)
        dc2 = 0 if col_match else (1 if cc > kc else -1)
        blocked = False
        r2, c2 = kr+dr2, kc+dc2
        while (r2, c2) != (cr, cc):
            if board[r2][c2] != EMPTY:
                blocked = True
                break
            r2 += dr2
            c2 += dc2
        if not blocked:
            open_escapes += 1

    mob_atk = len(all_moves_for_player(board, PLAYER_ATK))
    mob_def = len(all_moves_for_player(board, PLAYER_DEF))

    if for_player == PLAYER_ATK:
        return (
            to_corner       *  14
            + king_pressure *  58
            + encirclement  *  11
            - open_escapes  *  76
            + mob_atk       *   2
            + atk_count     *   9   # reward keeping attackers 
            - def_count     *  17
        )
    else:
        return (
            (10-to_corner)  *  33
            - king_pressure *  66
            - encirclement  *   9
            + open_escapes  *  88
            + mob_def       *   3
            + def_count     *   7
        )


# ALPHA-BETA with iterative deepening, timeout, move ordering, and a small transposition table
class SearchTimeout(Exception):
    pass


def terminal_score(board, ai_side, depth_left=0):
    winner = game_winner(board)
    if winner == ai_side:
        return 100000 + depth_left * 250
    if winner is not None:
        return -100000 - depth_left * 250
    return score_board(board, ai_side)


def move_order_score(board, mv, player, ai_side):
    fr, fc, tr, tc = mv
    moving = board[fr][fc]
    child = do_move(board, fr, fc, tr, tc)
    winner = game_winner(child)
    score = 0

    if winner == ai_side:
        score += 100000
    elif winner is not None:
        score -= 100000

    score += captures_made_by_move(board, fr, fc, tr, tc) * 900

    # Defenders care a lot about king progress and direct escape.
    if moving == KING:
        if (tr, tc) in CORNERS:
            score += 80000
        old_d = min(abs(fr-cr) + abs(fc-cc) for cr, cc in CORNERS)
        new_d = min(abs(tr-cr) + abs(tc-cc) for cr, cc in CORNERS)
        score += (old_d - new_d) * 250

    # Attackers prefer moves that put pressure near the king.
    kpos = find_king(child)
    if kpos:
        kr, kc = kpos
        dist = abs(tr-kr) + abs(tc-kc)
        if player == PLAYER_ATK:
            score += max(0, 8 - dist) * 35
        else:
            score -= max(0, 5 - dist) * 10

    # Slight center control tie-breaker to make play less random.
    score -= abs(tr-5) + abs(tc-5)
    return score


def ordered_moves(board, player, ai_side):
    moves = all_moves_for_player(board, player)
    random.shuffle(moves)  # keeps equal evaluations from always choosing the same line
    moves.sort(key=lambda mv: move_order_score(board, mv, player, ai_side), reverse=True)
    return moves


def alpha_beta(board, depth, alpha, beta, current_player, ai_side, t_start, cutoff, stats, tt):
    if time.time() - t_start > cutoff:
        raise SearchTimeout()

    stats["nodes"] += 1
    winner = game_winner(board)
    if winner is not None or depth == 0:
        return terminal_score(board, ai_side, depth), None

    key = (board_key(board), current_player, depth, ai_side)
    cached = tt.get(key)
    if cached is not None:
        stats["tt_hits"] += 1
        return cached

    candidate_moves = ordered_moves(board, current_player, ai_side)

    # If this side has no moves, skip once. If both have none, evaluate as static.
    if not candidate_moves:
        nxt = other_player(current_player)
        if not all_moves_for_player(board, nxt):
            return score_board(board, ai_side), None
        return alpha_beta(board, max(0, depth-1), alpha, beta, nxt, ai_side, t_start, cutoff, stats, tt)

    best_mv = candidate_moves[0]
    maximizing = (current_player == ai_side)

    if maximizing:
        best_v = -INF
        for mv in candidate_moves:
            child = do_move(board, mv[0], mv[1], mv[2], mv[3])
            v, _ = alpha_beta(child, depth-1, alpha, beta, other_player(current_player), ai_side, t_start, cutoff, stats, tt)
            if v > best_v:
                best_v, best_mv = v, mv
            alpha = max(alpha, best_v)
            if beta <= alpha:
                stats["prunes"] += 1
                break
    else:
        best_v = INF
        for mv in candidate_moves:
            child = do_move(board, mv[0], mv[1], mv[2], mv[3])
            v, _ = alpha_beta(child, depth-1, alpha, beta, other_player(current_player), ai_side, t_start, cutoff, stats, tt)
            if v < best_v:
                best_v, best_mv = v, mv
            beta = min(beta, best_v)
            if beta <= alpha:
                stats["prunes"] += 1
                break

    result = (best_v, best_mv)
    tt[key] = result
    return result


def pick_ai_move(board, player, depth):
    start = time.time()
    cutoff = AI_TIME_LIMITS.get(depth, 1.0)
    legal = all_moves_for_player(board, player)
    if not legal:
        return None, "no legal moves"

    # Always have a safe fallback, then replace it when a completed depth search succeeds.
    best_mv = ordered_moves(board, player, player)[0]
    best_val = score_board(do_move(board, *best_mv), player)
    reached = 0
    total = {"nodes": 0, "prunes": 0, "tt_hits": 0}
    tt = {}

    for d in range(1, depth + 1):
        stats = {"nodes": 0, "prunes": 0, "tt_hits": 0}
        try:
            val, mv = alpha_beta(board, d, -INF, INF, player, player, start, cutoff, stats, tt)
            if mv is not None:
                best_mv, best_val, reached = mv, val, d
            for k in total:
                total[k] += stats[k]
        except SearchTimeout:
            break

    elapsed = time.time() - start
    info = f"depth {reached}/{depth} | score {int(best_val)} | nodes {total['nodes']} | cuts {total['prunes']} | {elapsed:.2f}s"
    return best_mv, info


#game class
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("HNEFATAFL  |  Viking Chess  |  CS361")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock  = pygame.time.Clock()

        self.fn_big   = self.load_font(52)
        self.fn_med   = self.load_font(28)
        self.fn_norm  = self.load_font(20)
        self.fn_small = self.load_font(15)
        self.fn_xs    = self.load_font(12)

        #rune watermarks scattered in background
        self.rune_sprites = [
            (random.choice(RUNES), random.randint(0, SCREEN_W),
             random.randint(0, SCREEN_H), random.randint(12, 38),
             random.randint(14, 48))
            for _ in range(72)
        ]

        self.state = "menu"
        self.human = PLAYER_ATK
        self.depth = 3

        # game state
        self.board      = make_start_board()
        self.turn       = PLAYER_ATK
        self.winner     = None
        self.selected   = None
        self.legal_mvs  = []
        self.move_log   = []
        self.num_moves  = 0
        self.flash_sq   = []
        self.flash_tick = 0
        self.ai_info    = "AI ready."
        self.show_coords = True
        self.show_hints  = True

        # undo stack: each entry is (board_copy, turn, move_log_copy, num_moves, winner)
        self.history = []

        # buttons (set during draw so clicks work)
        self.btn_undo  = None
        self.btn_new   = None
        self.btn_menu  = None
        self.mb_atk    = None
        self.mb_def    = None
        self.start_btn = None
        self.diff_btns = {}

    def load_font(self, sz):
        for name in ["Cinzel", "Georgia", "Times New Roman",
                     "FreeSerif", "DejaVuSerif", "serif"]:
            try:
                f = pygame.font.SysFont(name, sz, bold=True)
                if f:
                    return f
            except Exception:
                pass
        return pygame.font.Font(None, sz)

    def txt(self, msg, font, col, cx, cy):
        s = font.render(msg, True, col)
        self.screen.blit(s, s.get_rect(center=(cx, cy)))

    def txt_left(self, msg, font, col, x, y):
        s = font.render(msg, True, col)
        self.screen.blit(s, (x, y))
        return s.get_height()

    def btn(self, label, rect, border_col, fill=None):
        hover = rect.collidepoint(pygame.mouse.get_pos())
        base = fill or PANEL_BG
        if hover:
            base = tuple(min(255, int(v * 1.28) + 12) for v in base)
        pygame.draw.rect(self.screen, base, rect, border_radius=7)
        pygame.draw.rect(self.screen, border_col, rect, 3 if hover else 2, border_radius=7)
        self.txt(label, self.fn_small, C_GOLD if hover else border_col, rect.centerx, rect.centery)

    def overlay_rect(self, x, y, w, h, rgba):
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill(rgba)
        self.screen.blit(s, (x, y))


    # board drawing
    def draw_board(self):
        for r in range(BOARD_COLS):
            for c in range(BOARD_COLS):
                x = MARGIN + c * CELL_SIZE
                y = MARGIN + r * CELL_SIZE

                if (r, c) in CORNERS:
                    col = TILE_CORNER
                elif (r, c) == THRONE:
                    col = TILE_THRONE
                elif (r+c) % 2 == 0:
                    col = TILE_A
                else:
                    col = TILE_B

                pygame.draw.rect(self.screen, col, (x, y, CELL_SIZE, CELL_SIZE))
                pygame.draw.rect(self.screen, C_GRID, (x, y, CELL_SIZE, CELL_SIZE), 1)

                # corner rune
                if (r, c) in CORNERS:
                    sym = self.fn_small.render("᛭", True, C_GOLD)
                    self.screen.blit(sym, sym.get_rect(center=(x+CELL_SIZE//2, y+CELL_SIZE//2)))

                # throne carved cross
                if (r, c) == THRONE:
                    cx2 = x + CELL_SIZE//2
                    cy2 = y + CELL_SIZE//2
                    pygame.draw.line(self.screen, C_GOLD, (cx2-12, cy2), (cx2+12, cy2), 2)
                    pygame.draw.line(self.screen, C_GOLD, (cx2, cy2-12), (cx2, cy2+12), 2)
                    pygame.draw.circle(self.screen, C_GOLD, (cx2, cy2), 4, 1)

        # board border
        bx = MARGIN - 3
        by = MARGIN - 3
        bsize = BOARD_COLS * CELL_SIZE + 6
        pygame.draw.rect(self.screen, C_GOLD, (bx, by, bsize, bsize), 2)
        pygame.draw.rect(self.screen, C_COPPER, (bx-2, by-2, bsize+4, bsize+4), 1)

        # row/col number labels
        if self.show_coords:
            for i in range(BOARD_COLS):
                lbl = self.fn_xs.render(str(i), True, C_TEXT_FADED)
                self.screen.blit(lbl, lbl.get_rect(center=(MARGIN + i*CELL_SIZE + CELL_SIZE//2, MARGIN-17)))
                self.screen.blit(lbl, lbl.get_rect(center=(MARGIN-18, MARGIN + i*CELL_SIZE + CELL_SIZE//2)))

    def draw_highlights(self):
        if self.selected:
            r, c = self.selected
            self.overlay_rect(MARGIN+c*CELL_SIZE, MARGIN+r*CELL_SIZE,
                               CELL_SIZE, CELL_SIZE, OVL_SELECTED)

        if self.show_hints:
            for mr, mc in self.legal_mvs:
                rgba = OVL_MOVE
                dot = (52, 178, 74)
                if self.selected:
                    sr, sc = self.selected
                    cap_count = captures_made_by_move(self.board, sr, sc, mr, mc)
                    moving = self.board[sr][sc]
                    if cap_count > 0:
                        rgba = (30, 180, 60, 160)
                        dot = (30, 220, 80)
                    elif moving == KING and (mr, mc) in CORNERS:
                        rgba = (248, 208, 36, 128)
                        dot = C_GOLD
                self.overlay_rect(MARGIN+mc*CELL_SIZE, MARGIN+mr*CELL_SIZE,
                                   CELL_SIZE, CELL_SIZE, rgba)
                cx2 = MARGIN + mc*CELL_SIZE + CELL_SIZE//2
                cy2 = MARGIN + mr*CELL_SIZE + CELL_SIZE//2
                pygame.draw.circle(self.screen, dot, (cx2, cy2), 7)

        if self.flash_tick > 0:
            alpha = int(200 * self.flash_tick / 22)
            for fr, fc in self.flash_sq:
                self.overlay_rect(MARGIN+fc*CELL_SIZE, MARGIN+fr*CELL_SIZE,
                                   CELL_SIZE, CELL_SIZE, (*C_RED, alpha))

    def draw_piece(self, r, c, piece):
        cx2 = MARGIN + c*CELL_SIZE + CELL_SIZE//2
        cy2 = MARGIN + r*CELL_SIZE + CELL_SIZE//2
        rad = CELL_SIZE//2 - 7

        if piece == KING:
            pygame.draw.circle(self.screen, KING_EDGE, (cx2, cy2), rad+2)
            pygame.draw.circle(self.screen, KING_FILL, (cx2, cy2), rad)
            # 5 crown spike lines
            for ang in [-36, -18, 0, 18, 36]:
                a = math.radians(ang - 90)
                bpx = cx2 + int((rad-11)*math.cos(a))
                bpy = cy2 + int((rad-11)*math.sin(a))
                tpx = cx2 + int((rad-3)*math.cos(a))
                tpy = cy2 + int((rad-3)*math.sin(a))
                pygame.draw.line(self.screen, KING_EDGE, (bpx, bpy), (tpx, tpy), 3)
            # gem center
            pygame.draw.circle(self.screen, KING_SHINE, (cx2, cy2), rad//3+1)
            pygame.draw.circle(self.screen, KING_EDGE, (cx2, cy2), rad//3+1, 1)
            lbl = self.fn_xs.render("K", True, (28, 16, 3))
            self.screen.blit(lbl, lbl.get_rect(center=(cx2, cy2)))

        elif piece == DEFENDER:
            pygame.draw.circle(self.screen, DEF_EDGE, (cx2, cy2), rad+2)
            pygame.draw.circle(self.screen, DEF_FILL, (cx2, cy2), rad)
            # shield cross + boss
            pygame.draw.line(self.screen, DEF_DETAIL, (cx2-rad//2+2, cy2), (cx2+rad//2-2, cy2), 2)
            pygame.draw.line(self.screen, DEF_DETAIL, (cx2, cy2-rad//2+2), (cx2, cy2+rad//2-2), 2)
            pygame.draw.circle(self.screen, DEF_DETAIL, (cx2, cy2), 5)
            pygame.draw.circle(self.screen, DEF_FILL, (cx2, cy2), 3)

        elif piece == ATTACKER:
            pygame.draw.circle(self.screen, ATK_EDGE, (cx2, cy2), rad+2)
            pygame.draw.circle(self.screen, ATK_FILL, (cx2, cy2), rad)
            # diagonal axe mark
            off = rad//2 - 3
            pygame.draw.line(self.screen, ATK_DETAIL, (cx2-off, cy2-off), (cx2+off, cy2+off), 3)
            pygame.draw.line(self.screen, ATK_DETAIL, (cx2-off, cy2-off+5), (cx2-off+10, cy2-off), 2)

    def draw_pieces(self):
        for r in range(BOARD_COLS):
            for c in range(BOARD_COLS):
                p = self.board[r][c]
                if p != EMPTY:
                    self.draw_piece(r, c, p)

    def draw_runes(self):
        for ch, x, y, alpha, sz in self.rune_sprites:
            f   = pygame.font.Font(None, sz)
            img = f.render(ch, True, C_GOLD_FADED)
            img.set_alpha(alpha)
            self.screen.blit(img, (x, y))

    # side panel
    def draw_panel(self):
        px = BOARD_COLS * CELL_SIZE + MARGIN * 2
        pygame.draw.rect(self.screen, PANEL_BG, (px, 0, SIDE_PANEL, SCREEN_H))
        pygame.draw.line(self.screen, C_GOLD, (px, 0), (px, SCREEN_H), 2)

        y  = 16
        cx2 = px + SIDE_PANEL//2

        self.txt("HNEFATAFL", self.fn_med, C_GOLD, cx2, y);           y += 34
        self.txt("Viking Chess", self.fn_xs, C_TEXT_FADED, cx2, y);   y += 18
        pygame.draw.line(self.screen, C_GOLD, (px+8, y), (px+SIDE_PANEL-8, y), 1); y += 12

        # turn indicator
        if self.winner is None:
            human_turn = (self.turn == self.human)
            status = "YOUR TURN" if human_turn else "AI THINKING..."
            scol   = C_GOLD if human_turn else C_ORANGE
            self.txt(status, self.fn_norm, scol, cx2, y); y += 26
            side   = "Attackers" if self.turn == PLAYER_ATK else "Defenders"
            scol2  = C_RED if self.turn == PLAYER_ATK else DEF_EDGE
            self.txt(f"[ {side} ]", self.fn_small, scol2, cx2, y); y += 30
        else:
            msg = "ATTACKERS WIN!" if self.winner == PLAYER_ATK else "DEFENDERS WIN!"
            c2  = C_RED if self.winner == PLAYER_ATK else C_GOLD
            self.txt(msg, self.fn_norm, c2, cx2, y); y += 50

        pygame.draw.line(self.screen, C_GOLD, (px+8, y), (px+SIDE_PANEL-8, y), 1); y += 10

        you_s   = "Attackers" if self.human == PLAYER_ATK else "Defenders"
        atk_n, def_n = count_pieces(self.board)

        for lbl, val in [("You play:", you_s), ("Difficulty:", DIFFICULTY_NAMES.get(self.depth,"?")),
                          ("Move #:", str(self.num_moves)),
                          ("Attackers:", str(atk_n)), ("Defenders:", str(def_n))]:
            line = self.fn_xs.render(f"{lbl}  {val}", True, C_TEXT)
            self.screen.blit(line, (px+10, y)); y += 17
        y += 6

        # AI search stats make the alpha-beta work visible in the demo.
        self.txt_left("AI SEARCH", self.fn_xs, C_GOLD, px+10, y); y += 15
        for part in self.ai_info.split(" | ")[:4]:
            line = self.fn_xs.render(part, True, C_TEXT_FADED)
            self.screen.blit(line, (px+10, y)); y += 14
        y += 3

        pygame.draw.line(self.screen, C_GOLD, (px+8, y), (px+SIDE_PANEL-8, y), 1); y += 8

        # legend
        self.txt_left("LEGEND", self.fn_xs, C_GOLD, px+10, y); y += 16
        legend = [
            ("K", "King  (escape to corner)", KING_FILL),
            ("o", "Defender", DEF_FILL),
            ("x", "Attacker", ATK_EDGE),
            ("᛭", "Corner  (hostile+escape)", C_GOLD),
            ("+", "Throne  (hostile if empty)", TILE_THRONE),
        ]
        for sym, desc, col in legend:
            line = self.fn_xs.render(f" {sym}  {desc}", True, col)
            self.screen.blit(line, (px+10, y)); y += 16
        y += 6

        pygame.draw.line(self.screen, C_GOLD, (px+8, y), (px+SIDE_PANEL-8, y), 1); y += 8

        # battle log
        self.txt_left("BATTLE LOG", self.fn_xs, C_GOLD, px+10, y); y += 16
        visible = self.move_log[-6:]
        for entry in visible:
            line = self.fn_xs.render(entry[:34], True, C_TEXT_FADED)
            self.screen.blit(line, (px+10, y)); y += 14

        y += 6
        self.txt_left("HOTKEYS", self.fn_xs, C_GOLD, px+10, y); y += 15
        for entry in ["Z undo", "N new game", "M/Esc menu", "H hints", "C coordinates"]:
            line = self.fn_xs.render(entry, True, C_TEXT_FADED)
            self.screen.blit(line, (px+10, y)); y += 13

        # buttons pinned near bottom
        btn_y = SCREEN_H - 148
        self.btn_undo = pygame.Rect(px+8, btn_y,      SIDE_PANEL-16, 32)
        self.btn_new  = pygame.Rect(px+8, btn_y + 40, SIDE_PANEL-16, 32)
        self.btn_menu = pygame.Rect(px+8, btn_y + 80, SIDE_PANEL-16, 32)

        can_undo = len(self.history) > 0 and self.winner is None
        undo_col = C_COPPER if can_undo else C_TEXT_FADED
        self.btn("UNDO  [Z]",      self.btn_undo, undo_col)
        self.btn("NEW GAME  [N]",  self.btn_new,  C_GOLD)
        self.btn("MENU  [M]",      self.btn_menu, C_TEXT_FADED)


    # menu
    def draw_menu(self):
        self.screen.fill(BG)
        self.draw_runes()

        cx2 = SCREEN_W // 2
        y   = 32

        self.txt("HNEFATAFL", self.fn_big, C_GOLD, cx2, y);                              y += 64
        self.txt("THE GAME OF THE VIKING KINGS", self.fn_small, C_TEXT_FADED, cx2, y);   y += 26
        pygame.draw.line(self.screen, C_GOLD, (cx2-240, y), (cx2+240, y), 2);            y += 14

        lines = [
            "An ancient Norse siege game: attack or defend.",
            "Defenders guide the King to any corner to win.",
            "Attackers must surround and capture the King.",
            "",
            "Pieces slide any distance horizontally or vertically.",
            "Capture: sandwich an enemy between two of yours.",
            "Empty throne and corners are hostile to all pieces.",
            "King is UNARMED  he cannot help capture others.",
            "King needs all 4 sides blocked to be captured.",
            "(3 near a wall, 2 near a corner.)",
        ]
        for line in lines:
            s = self.fn_small.render(line, True, C_TEXT if line else BG)
            self.screen.blit(s, s.get_rect(centerx=cx2, top=y)); y += 21
        y += 10

        pygame.draw.line(self.screen, C_GOLD, (cx2-240, y), (cx2+240, y), 1); y += 16

        self.txt("Choose Your Side", self.fn_med, C_GOLD, cx2, y); y += 36

        self.mb_atk = pygame.Rect(cx2-215, y, 195, 44)
        self.mb_def = pygame.Rect(cx2+20,  y, 195, 44)
        atk_fill = (50, 20, 8) if self.human == PLAYER_ATK else None
        def_fill = (30, 26, 16) if self.human == PLAYER_DEF else None
        self.btn("ATTACKERS (dark)",  self.mb_atk, C_RED,    atk_fill)
        self.btn("DEFENDERS (light)", self.mb_def, DEF_EDGE, def_fill)
        y += 60

        self.txt("Difficulty", self.fn_med, C_GOLD, cx2, y); y += 30
        dw = 124
        total_w = 3*dw + 2*10
        sx = cx2 - total_w//2
        self.diff_btns = {}
        for i, (v, lbl) in enumerate([(1,"EASY"),(3,"MEDIUM"),(5,"HARD")]):
            r2 = pygame.Rect(sx + i*(dw+10), y, dw, 38)
            highlight = (38, 24, 8) if self.depth == v else None
            self.btn(lbl, r2, C_GOLD if self.depth == v else C_TEXT_FADED, highlight)
            self.diff_btns[v] = r2
        y += 56

        self.start_btn = pygame.Rect(cx2-140, y, 280, 46)
        self.btn("START GAME", self.start_btn, C_GOLD, (38, 24, 8))
        y += 60

        self.txt("Attackers always move first", self.fn_xs, C_TEXT_FADED, cx2, y)

   
    # game over
    def draw_gameover(self):
        self.screen.fill(BG)
        self.draw_runes()
        self.draw_board()
        self.draw_pieces()
        self.draw_panel()

        veil = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 145))
        self.screen.blit(veil, (0, 0))

        # center over board area only
        board_cx = (BOARD_COLS * CELL_SIZE + MARGIN * 2) // 2
        cy3      = SCREEN_H // 2

        if self.winner == PLAYER_DEF:
            line1 = "THE KING ESCAPES!"
            line2 = "DEFENDERS VICTORIOUS"
            col   = C_GOLD
        else:
            line1 = "THE KING FALLS!"
            line2 = "ATTACKERS VICTORIOUS"
            col   = C_RED

        self.txt(line1, self.fn_big,  col,    board_cx, cy3 - 50)
        self.txt(line2, self.fn_med,  C_TEXT, board_cx, cy3 + 14)
        self.txt("N = new game    M = menu",
                 self.fn_small, C_TEXT_FADED, board_cx, cy3 + 60)

 
    # master render
    def render(self):
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "game":
            self.screen.fill(BG)
            self.draw_runes()
            self.draw_board()
            self.draw_highlights()
            self.draw_pieces()
            self.draw_panel()
        elif self.state == "gameover":
            self.draw_gameover()
        pygame.display.flip()


    # game logic helpers
    def start_game(self):
        self.board     = make_start_board()
        self.turn      = PLAYER_ATK
        self.winner    = None
        self.selected  = None
        self.legal_mvs = []
        self.move_log  = ["Battle starts - Attackers go first."]
        self.num_moves = 0
        self.flash_sq  = []
        self.flash_tick = 0
        self.ai_info    = "AI ready."
        self.history   = []
        self.state     = "game"

    def push_history(self):
        self.history.append((
            [row[:] for row in self.board],
            self.turn,
            self.move_log[:],
            self.num_moves,
            self.winner
        ))

    def restore_snapshot(self, snap):
        board_snap, turn_snap, log_snap, moves_snap, winner_snap = snap
        self.board     = [row[:] for row in board_snap]
        self.turn      = turn_snap
        self.move_log  = log_snap[:]
        self.num_moves = moves_snap
        self.winner    = winner_snap
        self.state     = "game" if winner_snap is None else "gameover"

    def undo_move(self):
        if not self.history:
            return

        # Undo a full human+AI exchange when we are back to the human turn.
        steps = 2 if (self.state in ("game", "gameover") and self.turn == self.human and len(self.history) >= 2) else 1
        snap = self.history[-steps]
        self.history = self.history[:-steps]
        self.restore_snapshot(snap)

        self.selected   = None
        self.legal_mvs  = []
        self.flash_sq   = []
        self.flash_tick = 0
        self.ai_info    = "AI ready."
        self.move_log.append("-- move undone --")

    def execute_move(self, fr, fc, tr, tc, prefix=""):
        self.push_history()

        before = {(r,c) for r in range(BOARD_COLS) for c in range(BOARD_COLS)
                  if self.board[r][c] != EMPTY}

        self.board = do_move(self.board, fr, fc, tr, tc)

        #let game_winner handle king removal via king_is_captured.
        after = {(r,c) for r in range(BOARD_COLS) for c in range(BOARD_COLS)
                 if self.board[r][c] != EMPTY}

        taken = before - after - {(fr, fc)}

        self.flash_sq   = list(taken)
        self.flash_tick = 22
        self.selected   = None
        self.legal_mvs  = []
        self.num_moves += 1

        log_str = f"{prefix}({fr},{fc})->({tr},{tc})"
        if taken:
            log_str += f"  x{len(taken)}"
        self.move_log.append(log_str)
        if len(self.move_log) > 80:
            self.move_log.pop(0)

        w = game_winner(self.board)
        if w:
            self.winner = w
            if w == PLAYER_ATK:
                self.move_log.append("KING CAPTURED - attackers win")
            else:
                self.move_log.append("KING ESCAPED - defenders win")
            self.state  = "gameover"
            return

        self.turn = PLAYER_DEF if self.turn == PLAYER_ATK else PLAYER_ATK

        if not all_moves_for_player(self.board, self.turn):
            skipped = "Attackers" if self.turn == PLAYER_ATK else "Defenders"
            self.move_log.append(f"{skipped} have no moves, skip!")
            self.turn = PLAYER_DEF if self.turn == PLAYER_ATK else PLAYER_ATK


    # input handlers
    def on_click(self, pos):
        if self.state == "menu":
            self.menu_click(pos)
        elif self.state == "game":
            split = BOARD_COLS * CELL_SIZE + MARGIN * 2
            if pos[0] >= split:
                self.panel_click(pos)
            else:
                self.board_click(pos)
        elif self.state == "gameover":
            split = BOARD_COLS * CELL_SIZE + MARGIN * 2
            if pos[0] >= split:
                self.panel_click(pos)

    def menu_click(self, pos):
        if self.mb_atk and self.mb_atk.collidepoint(pos):
            self.human = PLAYER_ATK
        elif self.mb_def and self.mb_def.collidepoint(pos):
            self.human = PLAYER_DEF
        for v, rect in self.diff_btns.items():
            if rect.collidepoint(pos):
                self.depth = v
        if self.start_btn and self.start_btn.collidepoint(pos):
            self.start_game()

    def panel_click(self, pos):
        if self.btn_undo and self.btn_undo.collidepoint(pos):
            self.undo_move()
        elif self.btn_new and self.btn_new.collidepoint(pos):
            self.start_game()
        elif self.btn_menu and self.btn_menu.collidepoint(pos):
            self.state = "menu"

    def board_click(self, pos):
        if self.winner or self.turn != self.human:
            return
        c = (pos[0] - MARGIN) // CELL_SIZE
        r = (pos[1] - MARGIN) // CELL_SIZE
        if not on_board(r, c):
            self.selected  = None
            self.legal_mvs = []
            return

        piece = self.board[r][c]

        if self.selected is None:
            self.try_select(r, c, piece)
        else:
            if (r, c) == self.selected:
                self.selected  = None
                self.legal_mvs = []
            elif (r, c) in self.legal_mvs:
                sr, sc = self.selected
                self.execute_move(sr, sc, r, c)
            elif piece != EMPTY:
                self.try_select(r, c, piece)
            else:
                self.selected  = None
                self.legal_mvs = []

    def try_select(self, r, c, piece):
        owns_atk = self.human == PLAYER_ATK and piece == ATTACKER
        owns_def = self.human == PLAYER_DEF and piece in (DEFENDER, KING)
        if owns_atk or owns_def:
            self.selected  = (r, c)
            self.legal_mvs = moves_for(self.board, r, c)
        else:
            self.selected  = None
            self.legal_mvs = []

    def on_key(self, key):
        if key == pygame.K_n:
            self.start_game()
        elif key in (pygame.K_m, pygame.K_ESCAPE):
            self.state = "menu"
        elif key == pygame.K_z:
            self.undo_move()
        elif key == pygame.K_h:
            self.show_hints = not self.show_hints
        elif key == pygame.K_c:
            self.show_coords = not self.show_coords

    def do_ai_turn(self):
        if self.state != "game" or self.winner or self.turn == self.human:
            return
        side = self.turn
        mv, info = pick_ai_move(self.board, side, self.depth)
        self.ai_info = info
        if mv:
            pfx = "AI> " if side == PLAYER_ATK else "ai> "
            self.execute_move(mv[0], mv[1], mv[2], mv[3], prefix=pfx)
        else:
            self.move_log.append("AI has no moves - skipping")
            self.turn = other_player(self.turn)


    # main loop
    def run(self):
        AI_PAUSE = 150  # ms before AI moves, so player can see board
        ai_wait  = 0

        while True:
            dt = self.clock.tick(60)

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    self.on_click(ev.pos)
                elif ev.type == pygame.KEYDOWN:
                    self.on_key(ev.key)

            if self.flash_tick > 0:
                self.flash_tick -= 1

            need_ai = (self.state == "game" and self.winner is None
                       and self.turn != self.human)
            if need_ai:
                ai_wait += dt
                if ai_wait >= AI_PAUSE:
                    ai_wait = 0
                    self.do_ai_turn()
            else:
                ai_wait = 0

            self.render()


# ============================================================
if __name__ == "__main__":
    Game().run()
