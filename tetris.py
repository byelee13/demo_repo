#!/usr/bin/env python3
"""俄罗斯方块 — 使用 pygame 实现的经典小游戏。"""

import random
import sys

import pygame
from PIL import Image, ImageDraw, ImageFont

# 网格尺寸
COLS = 10
ROWS = 20
CELL = 30
SIDEBAR = 160

WIDTH = COLS * CELL + SIDEBAR
HEIGHT = ROWS * CELL

# 颜色 (R, G, B)
BLACK = (15, 15, 20)
GRID = (35, 35, 45)
WHITE = (240, 240, 245)
GRAY = (100, 100, 110)

SHAPES = {
    "I": {
        "color": (0, 240, 240),
        "cells": [(0, 1), (1, 1), (2, 1), (3, 1)],
    },
    "O": {
        "color": (240, 240, 0),
        "cells": [(1, 0), (2, 0), (1, 1), (2, 1)],
    },
    "T": {
        "color": (160, 0, 240),
        "cells": [(1, 0), (0, 1), (1, 1), (2, 1)],
    },
    "S": {
        "color": (0, 240, 0),
        "cells": [(1, 0), (2, 0), (0, 1), (1, 1)],
    },
    "Z": {
        "color": (240, 0, 0),
        "cells": [(0, 0), (1, 0), (1, 1), (2, 1)],
    },
    "J": {
        "color": (0, 0, 240),
        "cells": [(0, 0), (0, 1), (1, 1), (2, 1)],
    },
    "L": {
        "color": (240, 160, 0),
        "cells": [(2, 0), (0, 1), (1, 1), (2, 1)],
    },
}

LINE_SCORES = {1: 100, 2: 300, 3: 500, 4: 800}

# Python 3.14 下 pygame.font 存在循环导入问题，改用 Pillow 渲染文字。
_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]


class TextRenderer:
    def __init__(self, size=18):
        self._cache = {}
        self._pil_font = None
        for path in _FONT_CANDIDATES:
            try:
                self._pil_font = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
        if self._pil_font is None:
            self._pil_font = ImageFont.load_default()

    def render(self, text, color):
        key = (text, color)
        if key in self._cache:
            return self._cache[key]
        bbox = self._pil_font.getbbox(text)
        width = max(bbox[2] - bbox[0], 1)
        height = max(bbox[3] - bbox[1], 1)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.text((-bbox[0], -bbox[1]), text, fill=(*color, 255), font=self._pil_font)
        surface = pygame.image.frombuffer(image.tobytes(), image.size, "RGBA")
        self._cache[key] = surface
        return surface


def rotate_cells(cells):
    """顺时针旋转方块坐标（以质心近似旋转）。"""
    cx = sum(x for x, _ in cells) / len(cells)
    cy = sum(y for _, y in cells) / len(cells)
    rotated = []
    for x, y in cells:
        rx = round(cx + (y - cy))
        ry = round(cy - (x - cx))
        rotated.append((rx, ry))
    return rotated


class Piece:
    def __init__(self, name=None):
        self.name = name or random.choice(list(SHAPES.keys()))
        self.color = SHAPES[self.name]["color"]
        self.cells = list(SHAPES[self.name]["cells"])
        self.x = COLS // 2 - 2
        self.y = 0

    def rotated_cells(self):
        return rotate_cells(self.cells)


class TetrisGame:
    def __init__(self):
        self.board = [[None for _ in range(COLS)] for _ in range(ROWS)]
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.game_over = False
        self.paused = False
        self.current = Piece()
        self.next_piece = Piece()
        if not self._fits(self.current, self.current.x, self.current.y):
            self.game_over = True

    def _fits(self, piece, offset_x, offset_y, cells=None):
        cells = cells if cells is not None else piece.cells
        for x, y in cells:
            bx, by = piece.x + x + offset_x, piece.y + y + offset_y
            if bx < 0 or bx >= COLS or by >= ROWS:
                return False
            if by >= 0 and self.board[by][bx] is not None:
                return False
        return True

    def move(self, dx, dy):
        if self.game_over or self.paused:
            return False
        if self._fits(self.current, dx, dy):
            self.current.x += dx
            self.current.y += dy
            return True
        return False

    def rotate(self):
        if self.game_over or self.paused:
            return
        new_cells = self.current.rotated_cells()
        kicks = [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1)]
        for kick_x, kick_y in kicks:
            if self._fits(self.current, kick_x, kick_y, new_cells):
                self.current.cells = new_cells
                self.current.x += kick_x
                self.current.y += kick_y
                return

    def hard_drop(self):
        if self.game_over or self.paused:
            return
        while self.move(0, 1):
            self.score += 2
        self.lock_piece()

    def soft_drop(self):
        if self.move(0, 1):
            self.score += 1

    def lock_piece(self):
        for x, y in self.current.cells:
            bx, by = self.current.x + x, self.current.y + y
            if 0 <= by < ROWS and 0 <= bx < COLS:
                self.board[by][bx] = self.current.color
        cleared = self._clear_lines()
        if cleared:
            self.lines_cleared += cleared
            self.score += LINE_SCORES.get(cleared, cleared * 100)
            self.level = 1 + self.lines_cleared // 10
        self.current = self.next_piece
        self.next_piece = Piece()
        if not self._fits(self.current, self.current.x, self.current.y):
            self.game_over = True

    def _clear_lines(self):
        new_board = [row for row in self.board if any(cell is None for cell in row)]
        cleared = ROWS - len(new_board)
        for _ in range(cleared):
            new_board.insert(0, [None for _ in range(COLS)])
        self.board = new_board
        return cleared

    def tick(self):
        if self.game_over or self.paused:
            return
        if not self.move(0, 1):
            self.lock_piece()

    def drop_interval_ms(self):
        return max(80, 500 - (self.level - 1) * 40)


def draw_cell(surface, x, y, color, offset_x=0):
    rect = pygame.Rect(offset_x + x * CELL + 1, y * CELL + 1, CELL - 2, CELL - 2)
    pygame.draw.rect(surface, color, rect, border_radius=3)
    highlight = tuple(min(255, c + 40) for c in color)
    pygame.draw.line(surface, highlight, rect.topleft, rect.topright, 2)
    pygame.draw.line(surface, highlight, rect.topleft, rect.bottomleft, 2)


def draw_board(surface, game, font):
    surface.fill(BLACK)
    board_rect = pygame.Rect(0, 0, COLS * CELL, HEIGHT)
    pygame.draw.rect(surface, GRID, board_rect, 1)

    for y in range(ROWS):
        for x in range(COLS):
            pygame.draw.rect(
                surface,
                GRID,
                (x * CELL, y * CELL, CELL, CELL),
                1,
            )
            color = game.board[y][x]
            if color:
                draw_cell(surface, x, y, color)

    if not game.game_over:
        for x, y in game.current.cells:
            draw_cell(surface, game.current.x + x, game.current.y + y, game.current.color)

    sidebar_x = COLS * CELL + 16
    title = font.render("俄罗斯方块", WHITE)
    surface.blit(title, (sidebar_x, 20))

    labels = [
        f"分数: {game.score}",
        f"等级: {game.level}",
        f"消行: {game.lines_cleared}",
    ]
    for i, text in enumerate(labels):
        surface.blit(font.render(text, WHITE), (sidebar_x, 70 + i * 28))

    surface.blit(font.render("下一个", WHITE), (sidebar_x, 180))
    preview_x = sidebar_x + 20
    preview_y = 210
    for x, y in game.next_piece.cells:
        rect = pygame.Rect(preview_x + x * 22, preview_y + y * 22, 20, 20)
        pygame.draw.rect(surface, game.next_piece.color, rect, border_radius=2)

    help_lines = [
        "← → 移动",
        "↑ 旋转",
        "↓ 软降",
        "空格 硬降",
        "P 暂停",
        "R 重开",
        "Esc 退出",
    ]
    for i, line in enumerate(help_lines):
        surface.blit(font.render(line, GRAY), (sidebar_x, 320 + i * 22))

    if game.paused:
        overlay = pygame.Surface((COLS * CELL, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))
        pause_text = font.render("已暂停", WHITE)
        surface.blit(
            pause_text,
            pause_text.get_rect(center=(COLS * CELL // 2, HEIGHT // 2)),
        )

    if game.game_over:
        overlay = pygame.Surface((COLS * CELL, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        over_text = font.render("游戏结束", WHITE)
        hint = font.render("按 R 重新开始", GRAY)
        surface.blit(
            over_text,
            over_text.get_rect(center=(COLS * CELL // 2, HEIGHT // 2 - 16)),
        )
        surface.blit(
            hint,
            hint.get_rect(center=(COLS * CELL // 2, HEIGHT // 2 + 20)),
        )


def main():
    pygame.init()
    pygame.display.set_caption("俄罗斯方块")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = TextRenderer(18)

    game = TetrisGame()
    fall_event = pygame.USEREVENT + 1
    pygame.time.set_timer(fall_event, game.drop_interval_ms())

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == fall_event:
                game.tick()
                pygame.time.set_timer(fall_event, game.drop_interval_ms())
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_p:
                    game.paused = not game.paused
                elif event.key == pygame.K_r:
                    game = TetrisGame()
                    pygame.time.set_timer(fall_event, game.drop_interval_ms())
                elif not game.game_over and not game.paused:
                    if event.key == pygame.K_LEFT:
                        game.move(-1, 0)
                    elif event.key == pygame.K_RIGHT:
                        game.move(1, 0)
                    elif event.key == pygame.K_DOWN:
                        game.soft_drop()
                    elif event.key == pygame.K_UP:
                        game.rotate()
                    elif event.key == pygame.K_SPACE:
                        game.hard_drop()

        draw_board(screen, game, font)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
