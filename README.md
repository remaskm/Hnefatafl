# Hnefatafl

A single-player implementation of **Hnefatafl** (Viking chess) in Python and Pygame, with an AI opponent built on alpha-beta search. You pick a side, pick a difficulty and play against the computer.

## Features

- 11×11 board with the standard setup: 24 attackers, 12 defenders and a king on the central throne
- Play as either **Attackers** (dark, move first) or **Defenders** (light)
- Three difficulty levels: Easy, Medium and Hard
- Move highlighting, capture flash effects, a move log and an AI info panel
- Undo, new game and menu shortcuts
- Themed UI with rune decorations

## Requirements

- Python 3.8+
- [Pygame](https://www.pygame.org/)

```bash
pip install pygame
```

## Run

```bash
python hnefatafl.py
```

## How to play

| Rule | Detail |
|------|--------|
| Movement | Pieces slide any distance horizontally or vertically, like a rook, and cannot jump |
| Capture | Sandwich an enemy piece between two of yours |
| Restricted squares | The throne and the four corners can only be occupied by the king; the empty throne and corners are hostile to every piece |
| Sandwich rule | A piece may pass through a sandwiched position but may not stop on one |
| King | The king is unarmed, so he cannot help capture other pieces |
| Defenders win | The king reaches any corner |
| Attackers win | The king is surrounded on all 4 sides (3 next to a wall, 2 next to a corner) |

Attackers always move first. Click a piece to select it, then click a highlighted square to move.

### Controls

| Key | Action |
|-----|--------|
| `Z` | Undo move |
| `N` | New game |
| `M` / `Esc` | Back to menu |
| `H` | Toggle move hints |
| `C` | Toggle board coordinates |

## The AI

The AI uses **minimax with alpha-beta pruning**. The main techniques are:

- **Iterative deepening.** It searches depth 1, 2, … up to the chosen limit and keeps the best move from the last completed depth.
- **Time limits.** Each difficulty has a per-move budget (Easy 0.25s, Medium 0.90s, Hard 1.85s). If the search times out, the best result from a completed depth is used.
- **Move ordering.** Winning moves, captures, king progress toward a corner and attacker pressure near the king are searched first to improve pruning.
- **Transposition table.** Positions that were already evaluated are cached.
- **Heuristic evaluation.** The score weighs the king's Manhattan distance to the nearest corner, attackers adjacent to or near the king, open straight-line escape routes to corners, mobility and piece counts.

| Difficulty | Max search depth |
|------------|------------------|
| Easy | 1 |
| Medium | 3 |
| Hard | 5 |

After each AI move, the side panel shows the depth reached, score, nodes searched, pruning cuts and time taken.

## Project structure

```
hnefatafl/
└── hnefatafl.py    # board logic, rules, AI search and the Pygame UI
```

The file is organised as: board setup → move generation → capture and win logic → heuristic evaluation → alpha-beta search → `Game` class (rendering, input, undo, main loop).

## Notes

Developed as a university AI course project
