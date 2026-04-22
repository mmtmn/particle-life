#!/usr/bin/env python3
"""Generate dark themed presentation PDFs for Particle Life.

The renderer is intentionally dependency-free so the decks can be regenerated on
any Linux machine with Python. It writes simple vector PDF pages directly.
"""

from __future__ import annotations

import math
import random
import textwrap
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

PAGE_W = 1280
PAGE_H = 720

Color = Tuple[float, float, float]

BG: Color = (0.018, 0.024, 0.040)
BG_2: Color = (0.034, 0.047, 0.075)
PANEL: Color = (0.065, 0.085, 0.120)
PANEL_2: Color = (0.092, 0.112, 0.150)
TEXT: Color = (0.935, 0.955, 0.980)
MUTED: Color = (0.620, 0.680, 0.760)
DIM: Color = (0.360, 0.420, 0.500)
TEAL: Color = (0.080, 0.850, 0.790)
CORAL: Color = (1.000, 0.320, 0.390)
GOLD: Color = (1.000, 0.760, 0.220)
BLUE: Color = (0.260, 0.540, 1.000)
VIOLET: Color = (0.720, 0.420, 1.000)
GREEN: Color = (0.280, 0.860, 0.460)
WHITE: Color = (1.000, 1.000, 1.000)

ACCENTS: Sequence[Color] = (TEAL, CORAL, GOLD, BLUE, VIOLET, GREEN)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def mix(a: Color, b: Color, t: float) -> Color:
    return tuple(a[i] * (1.0 - t) + b[i] * t for i in range(3))  # type: ignore[return-value]


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class Canvas:
    def __init__(self) -> None:
        self.ops: List[str] = []

    def raw(self, command: str) -> None:
        self.ops.append(command)

    def fill(self, color: Color) -> None:
        self.ops.append(f"{color[0]:.4f} {color[1]:.4f} {color[2]:.4f} rg\n")

    def stroke(self, color: Color) -> None:
        self.ops.append(f"{color[0]:.4f} {color[1]:.4f} {color[2]:.4f} RG\n")

    def alpha(self, fill_alpha: float = 1.0, stroke_alpha: float = 1.0) -> None:
        self.ops.append(f"/GS{int(fill_alpha * 100):02d}_{int(stroke_alpha * 100):02d} gs\n")

    def line_width(self, width: float) -> None:
        self.ops.append(f"{width:.2f} w\n")

    def rect(self, x: float, y: float, w: float, h: float,
             fill: Color | None = None, stroke: Color | None = None,
             line_width: float = 1.0) -> None:
        if fill is not None:
            self.fill(fill)
            self.ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f\n")
        if stroke is not None:
            self.stroke(stroke)
            self.line_width(line_width)
            self.ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re S\n")

    def rounded_rect(self, x: float, y: float, w: float, h: float, r: float,
                     fill: Color | None = None, stroke: Color | None = None,
                     line_width: float = 1.0) -> None:
        k = 0.5522847498
        r = min(r, w / 2.0, h / 2.0)
        path = [
            f"{x + r:.2f} {y:.2f} m",
            f"{x + w - r:.2f} {y:.2f} l",
            f"{x + w - r + r * k:.2f} {y:.2f} {x + w:.2f} {y + r - r * k:.2f} {x + w:.2f} {y + r:.2f} c",
            f"{x + w:.2f} {y + h - r:.2f} l",
            f"{x + w:.2f} {y + h - r + r * k:.2f} {x + w - r + r * k:.2f} {y + h:.2f} {x + w - r:.2f} {y + h:.2f} c",
            f"{x + r:.2f} {y + h:.2f} l",
            f"{x + r - r * k:.2f} {y + h:.2f} {x:.2f} {y + h - r + r * k:.2f} {x:.2f} {y + h - r:.2f} c",
            f"{x:.2f} {y + r:.2f} l",
            f"{x:.2f} {y + r - r * k:.2f} {x + r - r * k:.2f} {y:.2f} {x + r:.2f} {y:.2f} c",
            "h",
        ]
        if fill is not None:
            self.fill(fill)
            self.ops.append(" ".join(path) + " f\n")
        if stroke is not None:
            self.stroke(stroke)
            self.line_width(line_width)
            self.ops.append(" ".join(path) + " S\n")

    def circle(self, x: float, y: float, r: float,
               fill: Color | None = None, stroke: Color | None = None,
               line_width: float = 1.0) -> None:
        k = 0.5522847498
        path = (
            f"{x + r:.2f} {y:.2f} m "
            f"{x + r:.2f} {y + k * r:.2f} {x + k * r:.2f} {y + r:.2f} {x:.2f} {y + r:.2f} c "
            f"{x - k * r:.2f} {y + r:.2f} {x - r:.2f} {y + k * r:.2f} {x - r:.2f} {y:.2f} c "
            f"{x - r:.2f} {y - k * r:.2f} {x - k * r:.2f} {y - r:.2f} {x:.2f} {y - r:.2f} c "
            f"{x + k * r:.2f} {y - r:.2f} {x + r:.2f} {y - k * r:.2f} {x + r:.2f} {y:.2f} c h"
        )
        if fill is not None:
            self.fill(fill)
            self.ops.append(path + " f\n")
        if stroke is not None:
            self.stroke(stroke)
            self.line_width(line_width)
            self.ops.append(path + " S\n")

    def line(self, x1: float, y1: float, x2: float, y2: float,
             color: Color, width: float = 1.0) -> None:
        self.stroke(color)
        self.line_width(width)
        self.ops.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S\n")

    def arrow(self, x1: float, y1: float, x2: float, y2: float,
              color: Color, width: float = 2.5) -> None:
        self.line(x1, y1, x2, y2, color, width)
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 13.0
        left = angle + math.pi * 0.82
        right = angle - math.pi * 0.82
        p1 = (x2 + math.cos(left) * size, y2 + math.sin(left) * size)
        p2 = (x2 + math.cos(right) * size, y2 + math.sin(right) * size)
        self.fill(color)
        self.ops.append(
            f"{x2:.2f} {y2:.2f} m {p1[0]:.2f} {p1[1]:.2f} l "
            f"{p2[0]:.2f} {p2[1]:.2f} l h f\n"
        )

    def polyline(self, points: Sequence[Tuple[float, float]], color: Color,
                 width: float = 2.0) -> None:
        if len(points) < 2:
            return
        self.stroke(color)
        self.line_width(width)
        first = points[0]
        parts = [f"{first[0]:.2f} {first[1]:.2f} m"]
        for x, y in points[1:]:
            parts.append(f"{x:.2f} {y:.2f} l")
        self.ops.append(" ".join(parts) + " S\n")

    def text(self, x: float, y: float, text: str, size: float = 24,
             font: str = "F1", color: Color = TEXT) -> None:
        self.fill(color)
        self.ops.append(
            f"BT /{font} {size:.2f} Tf {x:.2f} {y:.2f} Td "
            f"({pdf_escape(text)}) Tj ET\n"
        )

    def paragraph(self, x: float, y: float, text: str, size: float = 24,
                  width: int = 42, leading: float | None = None,
                  font: str = "F1", color: Color = TEXT) -> float:
        if leading is None:
            leading = size * 1.25
        current_y = y
        for line in textwrap.wrap(text, width=width):
            self.text(x, current_y, line, size, font, color)
            current_y -= leading
        return current_y

    def stream(self) -> bytes:
        return "".join(self.ops).encode("latin-1", "replace")


def background(c: Canvas, seed: int) -> None:
    c.rect(0, 0, PAGE_W, PAGE_H, fill=BG)
    for i in range(16):
        y = i * PAGE_H / 16.0
        c.rect(0, y, PAGE_W, PAGE_H / 16.0 + 1, fill=mix(BG, BG_2, i / 20.0))

    rng = random.Random(seed)
    for _ in range(95):
        x = rng.uniform(0, PAGE_W)
        y = rng.uniform(0, PAGE_H)
        r = rng.uniform(0.8, 2.6)
        color = mix(DIM, rng.choice(ACCENTS), rng.uniform(0.12, 0.35))
        c.circle(x, y, r, fill=color)

    c.rounded_rect(-120, 510, 520, 250, 48, fill=(0.035, 0.105, 0.125))
    c.rounded_rect(940, -90, 430, 280, 54, fill=(0.120, 0.060, 0.090))
    c.line(64, 84, 1216, 84, mix(DIM, TEAL, 0.18), 1.2)


def header(c: Canvas, deck_title: str, slide_no: int, total: int) -> None:
    c.text(64, 652, deck_title.upper(), 13, "F2", mix(MUTED, TEAL, 0.28))
    c.text(1164, 652, f"{slide_no:02d}/{total:02d}", 13, "F2", MUTED)


def title_block(c: Canvas, kicker: str, title: str, subtitle: str = "") -> None:
    if kicker:
        c.text(72, 584, kicker.upper(), 16, "F2", GOLD)
    c.paragraph(72, 526, title, 48, 22, 57, "F2", TEXT)
    if subtitle:
        c.paragraph(76, 414, subtitle, 22, 48, 31, "F1", MUTED)


def bullets(c: Canvas, x: float, y: float, items: Iterable[str],
            accent: Color = TEAL, width: int = 48) -> None:
    current_y = y
    for item in items:
        c.circle(x, current_y + 5, 4.8, fill=accent)
        current_y = c.paragraph(x + 20, current_y, item, 21, width, 29, "F1", TEXT)
        current_y -= 16


def particle_cloud(c: Canvas, x: float, y: float, w: float, h: float,
                   count: int, seed: int, clusters: int = 4,
                   connections: bool = True) -> None:
    rng = random.Random(seed)
    centers = [
        (x + rng.uniform(w * 0.18, w * 0.82), y + rng.uniform(h * 0.20, h * 0.82))
        for _ in range(clusters)
    ]
    points: List[Tuple[float, float, Color, float]] = []
    for i in range(count):
        center = centers[i % clusters]
        spread = rng.uniform(34, 95)
        px = clamp(rng.gauss(center[0], spread), x + 14, x + w - 14)
        py = clamp(rng.gauss(center[1], spread), y + 14, y + h - 14)
        color = ACCENTS[i % len(ACCENTS)]
        radius = rng.uniform(3.0, 7.2)
        points.append((px, py, color, radius))

    if connections:
        for i, (ax, ay, acolor, _) in enumerate(points[:52]):
            for bx, by, _, _ in points[i + 1:i + 7]:
                distance = math.hypot(ax - bx, ay - by)
                if distance < 118:
                    c.line(ax, ay, bx, by, mix(DIM, acolor, 0.35), 0.6)

    for px, py, color, radius in points:
        c.circle(px, py, radius + 2.0, fill=mix(BG, color, 0.22))
        c.circle(px, py, radius, fill=color)


def force_curve(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    c.rounded_rect(x, y, w, h, 24, fill=PANEL)
    c.text(x + 28, y + h - 44, "One pairwise force", 22, "F2", TEXT)
    c.text(x + 28, y + h - 73, "Distance changes how strongly particles react", 15, "F1", MUTED)
    axis_y = y + h * 0.43
    c.line(x + 52, axis_y, x + w - 40, axis_y, DIM, 1.4)
    c.line(x + 70, y + 56, x + 70, y + h - 102, DIM, 1.4)
    c.text(x + 80, y + h - 120, "pull", 14, "F2", GREEN)
    c.text(x + 80, y + 70, "push", 14, "F2", CORAL)
    points: List[Tuple[float, float]] = []
    for i in range(100):
        t = i / 99.0
        if t < 0.18:
            value = -0.85 + t * 3.0
        else:
            value = math.sin((t - 0.18) / 0.82 * math.pi)
        px = x + 70 + t * (w - 128)
        py = axis_y + value * (h * 0.28)
        points.append((px, py))
    c.polyline(points, TEAL, 4.0)
    c.text(x + 58, y + 36, "too close", 13, "F1", CORAL)
    c.text(x + w - 136, y + 36, "too far", 13, "F1", MUTED)


def force_matrix(c: Canvas, x: float, y: float, size: float, species: int = 5) -> None:
    c.rounded_rect(x - 26, y - 42, size + 52, size + 92, 28, fill=PANEL)
    c.text(x - 4, y + size + 18, "Force matrix", 24, "F2", TEXT)
    c.text(x - 4, y - 26, "Rows feel columns", 15, "F1", MUTED)
    cell = size / species
    values = [
        [0.1, 0.8, -0.5, 0.2, -0.9],
        [-0.8, 0.2, 0.7, -0.2, 0.4],
        [0.6, -0.4, -0.1, 0.9, 0.2],
        [0.0, 0.5, -0.8, 0.1, 0.7],
        [0.9, -0.1, 0.3, -0.7, 0.2],
    ]
    for r in range(species):
        for col in range(species):
            value = values[r][col]
            base = GREEN if value >= 0 else CORAL
            color = mix(PANEL_2, base, 0.32 + abs(value) * 0.45)
            c.rounded_rect(x + col * cell + 4, y + (species - 1 - r) * cell + 4,
                           cell - 8, cell - 8, 8, fill=color)
    for i, color in enumerate(ACCENTS[:species]):
        c.circle(x - 13, y + (species - 0.5 - i) * cell, 6, fill=color)
        c.circle(x + (i + 0.5) * cell, y + size + 13, 6, fill=color)


def rule_loop(c: Canvas, x: float, y: float) -> None:
    nodes = [
        (x, y + 160, "rules", "matrix values", TEAL),
        (x + 240, y + 20, "motion", "velocity changes", GOLD),
        (x - 240, y + 20, "patterns", "clusters and waves", VIOLET),
    ]
    for nx, ny, title, subtitle, color in nodes:
        c.circle(nx, ny, 74, fill=mix(PANEL, color, 0.10), stroke=mix(color, WHITE, 0.1), line_width=2.0)
        c.text(nx - 38, ny + 10, title, 24, "F2", TEXT)
        c.text(nx - 58, ny - 22, subtitle, 13, "F1", MUTED)
    c.arrow(x + 50, y + 118, x + 170, y + 60, TEAL, 3)
    c.arrow(x + 162, y + 8, x - 165, y + 8, GOLD, 3)
    c.arrow(x - 170, y + 58, x - 50, y + 118, VIOLET, 3)


def pattern_strips(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    labels = ["clusters", "lanes", "rings", "waves"]
    strip_w = w / len(labels)
    for i, label in enumerate(labels):
        sx = x + i * strip_w
        c.rounded_rect(sx + 8, y, strip_w - 16, h, 22, fill=PANEL)
        particle_cloud(c, sx + 18, y + 38, strip_w - 36, h - 78, 34, 80 + i, 2 + i % 2, False)
        c.text(sx + 28, y + 18, label, 20, "F2", TEXT)


def gpu_grid(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    c.rounded_rect(x, y, w, h, 26, fill=PANEL)
    c.text(x + 32, y + h - 46, "GPU view", 24, "F2", TEXT)
    c.text(x + 32, y + h - 76, "one tiny worker per particle", 15, "F1", MUTED)
    cols, rows = 16, 9
    cell = min((w - 90) / cols, (h - 150) / rows)
    gx = x + 44
    gy = y + 52
    for row in range(rows):
        for col in range(cols):
            t = (row * cols + col) / (rows * cols)
            color = mix(BLUE, TEAL if (row + col) % 3 else GOLD, t * 0.55)
            c.rounded_rect(gx + col * cell, gy + row * cell,
                           cell - 4, cell - 4, 4, fill=mix(PANEL_2, color, 0.58))


def double_buffer(c: Canvas, x: float, y: float) -> None:
    c.rounded_rect(x, y + 86, 240, 116, 22, fill=mix(PANEL, BLUE, 0.08), stroke=BLUE, line_width=2)
    c.rounded_rect(x + 380, y + 86, 240, 116, 22, fill=mix(PANEL, TEAL, 0.08), stroke=TEAL, line_width=2)
    c.text(x + 44, y + 142, "read old state", 24, "F2", TEXT)
    c.text(x + 420, y + 142, "write new state", 24, "F2", TEXT)
    c.arrow(x + 252, y + 144, x + 366, y + 144, GOLD, 4)
    c.text(x + 256, y + 58, "then swap buffers for the next frame", 20, "F1", MUTED)


def wrap_world(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    c.rounded_rect(x, y, w, h, 24, fill=PANEL)
    c.rect(x + 68, y + 60, w - 136, h - 120, stroke=DIM, line_width=2)
    c.circle(x + 94, y + h * 0.5, 9, fill=CORAL)
    c.circle(x + w - 94, y + h * 0.5, 9, fill=CORAL)
    c.arrow(x + 124, y + h * 0.5, x + w - 132, y + h * 0.5, TEAL, 2.6)
    c.arrow(x + w - 124, y + h * 0.5 - 38, x + 132, y + h * 0.5 - 38, GOLD, 2.6)
    c.text(x + 48, y + h - 48, "Wrapped world", 24, "F2", TEXT)
    c.text(x + 48, y + 38, "edges connect, so motion never falls off the map", 17, "F1", MUTED)


def cube_vs_plane(c: Canvas, x: float, y: float, w: float, h: float) -> None:
    c.rounded_rect(x, y, w, h, 24, fill=PANEL)
    c.text(x + 38, y + h - 46, "2D and 3D are the same idea", 24, "F2", TEXT)
    c.rect(x + 68, y + 92, 220, 220, stroke=TEAL, line_width=2.5)
    particle_cloud(c, x + 78, y + 102, 200, 200, 30, 444, 3, False)
    ox, oy = x + 460, y + 92
    c.rect(ox, oy, 210, 210, stroke=BLUE, line_width=2)
    c.line(ox, oy, ox + 70, oy + 70, BLUE, 2)
    c.line(ox + 210, oy, ox + 280, oy + 70, BLUE, 2)
    c.line(ox + 210, oy + 210, ox + 280, oy + 280, BLUE, 2)
    c.line(ox, oy + 210, ox + 70, oy + 280, BLUE, 2)
    c.rect(ox + 70, oy + 70, 210, 210, stroke=VIOLET, line_width=2)
    particle_cloud(c, ox + 22, oy + 18, 250, 246, 36, 512, 4, False)
    c.text(x + 138, y + 48, "2D plane", 18, "F2", TEAL)
    c.text(ox + 112, y + 48, "3D volume", 18, "F2", VIOLET)


def local_rules_diagram(c: Canvas, x: float, y: float) -> None:
    c.circle(x, y, 15, fill=WHITE)
    c.circle(x, y, 122, stroke=DIM, line_width=1.6)
    c.circle(x, y, 48, stroke=CORAL, line_width=1.6)
    rng = random.Random(91)
    for i in range(42):
        angle = rng.uniform(0, math.tau)
        radius = rng.uniform(34, 160)
        color = ACCENTS[i % len(ACCENTS)]
        px = x + math.cos(angle) * radius
        py = y + math.sin(angle) * radius
        c.circle(px, py, rng.uniform(4, 8), fill=color)
        if radius < 122:
            c.line(x, y, px, py, mix(DIM, color, 0.48), 1.0)
    c.text(x - 72, y - 166, "each particle only asks nearby questions", 18, "F1", MUTED)


Deck = Tuple[str, str, Sequence[Dict[str, object]]]

DECKS: Sequence[Deck] = [
    (
        "docs/particle-life-intro-deck.pdf",
        "Particle Life Primer",
        [
            {
                "visual": "hero_cloud",
                "kicker": "a first look",
                "title": "Particle Life: tiny rules, living motion",
                "subtitle": "A particle life system is not scripted animation. It is a crowd of simple dots that repeatedly pull, push, and organize themselves.",
            },
            {
                "visual": "three_ingredients",
                "kicker": "the ingredients",
                "title": "Nothing starts out intelligent",
                "subtitle": "Each particle only carries a few numbers: where it is, how fast it is moving, and what species or color it belongs to.",
                "bullets": [
                    "Position says where the particle is.",
                    "Velocity says where it is heading next.",
                    "Species decides which rules affect it.",
                ],
            },
            {
                "visual": "matrix",
                "kicker": "the rulebook",
                "title": "The whole personality is a table of relationships",
                "subtitle": "For every pair of species, one number says attract, repel, or ignore. That table is enough to create surprisingly rich behavior.",
                "bullets": [
                    "Positive values pull particles together.",
                    "Negative values push them apart.",
                    "The relationship can be directional.",
                ],
            },
            {
                "visual": "curve",
                "kicker": "the motion",
                "title": "Every frame repeats the same small question",
                "subtitle": "For each nearby particle: how far away is it, what species is it, and should I move toward it or away from it?",
            },
            {
                "visual": "loop",
                "kicker": "the result",
                "title": "Patterns appear without being drawn",
                "subtitle": "Clusters, rings, streams, and waves are side effects of the rules feeding back into motion.",
            },
            {
                "visual": "patterns",
                "kicker": "takeaway",
                "title": "Particle life is a microscope for emergence",
                "subtitle": "The interesting part is not any single particle. It is the shared behavior that appears when thousands of simple decisions happen at once.",
            },
        ],
    ),
    (
        "docs/emergence-visual-story.pdf",
        "Emergence Visual Story",
        [
            {
                "visual": "hero_cloud",
                "kicker": "from rules to worlds",
                "title": "How simple pushes become complex motion",
                "subtitle": "Particle life is a useful way to show emergence: local interactions creating global structure.",
            },
            {
                "visual": "attract",
                "kicker": "attraction",
                "title": "Pull creates groups",
                "subtitle": "When two species attract, they gather. Enough attraction creates islands, strands, and orbiting clumps.",
                "bullets": [
                    "Weak pull makes soft clouds.",
                    "Strong pull makes tight centers.",
                    "Mixed pull makes layered groups.",
                ],
            },
            {
                "visual": "repel",
                "kicker": "repulsion",
                "title": "Push creates space",
                "subtitle": "Repulsion is just as important. It prevents collapse and creates boundaries between moving groups.",
                "bullets": [
                    "Short-range push keeps particles separated.",
                    "Longer repulsion can carve lanes.",
                    "Balance matters more than any one force.",
                ],
            },
            {
                "visual": "cycle",
                "kicker": "feedback",
                "title": "Cycles create chase behavior",
                "subtitle": "If red follows green, green follows blue, and blue avoids red, the system can start to chase itself.",
            },
            {
                "visual": "wrap",
                "kicker": "space",
                "title": "The world wraps around",
                "subtitle": "Particles that leave one side re-enter from the other. That keeps the simulation dense and continuous.",
            },
            {
                "visual": "2d3d",
                "kicker": "dimensions",
                "title": "2D is readable. 3D is spatial.",
                "subtitle": "The rule is the same in both modes. The difference is how much room the particles have to arrange themselves.",
            },
            {
                "visual": "patterns",
                "kicker": "watch for",
                "title": "The story is in the changing shapes",
                "subtitle": "A good demo lets the audience see swarms split, merge, chase, stabilize, and then destabilize again.",
            },
        ],
    ),
    (
        "docs/cuda-simulation-story.pdf",
        "CUDA Simulation Story",
        [
            {
                "visual": "gpu",
                "kicker": "why cuda",
                "title": "Particle life asks the same question thousands of times",
                "subtitle": "That repetition is exactly what GPUs are built for: many small workers doing similar math at the same time.",
            },
            {
                "visual": "thread_particle",
                "kicker": "parallel update",
                "title": "One CUDA thread owns one particle",
                "subtitle": "Each thread reads the old world, gathers the forces on its particle, and writes one new position.",
                "bullets": [
                    "The work is independent per particle.",
                    "All particles update together.",
                    "The frame becomes one big parallel step.",
                ],
            },
            {
                "visual": "neighbors",
                "kicker": "the expensive part",
                "title": "Each particle checks its neighborhood",
                "subtitle": "The direct version compares particles against each other. It is easy to understand and maps cleanly to CUDA.",
            },
            {
                "visual": "matrix",
                "kicker": "the rule lookup",
                "title": "The force matrix stays small",
                "subtitle": "Even with many particles, the rule table is tiny. The GPU mostly spends time applying those rules many times.",
            },
            {
                "visual": "buffers",
                "kicker": "correctness",
                "title": "Double buffering keeps the frame consistent",
                "subtitle": "Threads read from one copy of the world and write into another. No particle sees a half-updated neighbor.",
            },
            {
                "visual": "patterns",
                "kicker": "the payoff",
                "title": "The GPU turns simple math into live emergence",
                "subtitle": "Fast parallel updates make the system feel alive because the audience can watch the rules become motion in real time.",
            },
        ],
    ),
]


def draw_visual(c: Canvas, visual: str) -> None:
    if visual == "hero_cloud":
        particle_cloud(c, 680, 134, 500, 430, 150, 21, 5, True)
        c.rounded_rect(684, 118, 490, 40, 20, fill=mix(PANEL, TEAL, 0.08))
        c.text(718, 131, "thousands of local interactions", 20, "F2", TEAL)
    elif visual == "three_ingredients":
        labels = [("position", "where am I?", TEAL), ("velocity", "where next?", GOLD), ("species", "which rules?", CORAL)]
        for i, (label, sub, color) in enumerate(labels):
            x = 696
            y = 438 - i * 132
            c.rounded_rect(x, y, 420, 92, 22, fill=mix(PANEL, color, 0.08), stroke=mix(color, WHITE, 0.08), line_width=1.4)
            c.circle(x + 48, y + 46, 18, fill=color)
            c.text(x + 88, y + 54, label, 28, "F2", TEXT)
            c.text(x + 90, y + 25, sub, 18, "F1", MUTED)
    elif visual == "matrix":
        force_matrix(c, 760, 202, 260)
    elif visual == "curve":
        force_curve(c, 700, 182, 470, 300)
    elif visual == "loop":
        rule_loop(c, 940, 246)
    elif visual == "patterns":
        pattern_strips(c, 92, 152, 1096, 300)
    elif visual == "attract":
        particle_cloud(c, 724, 156, 420, 360, 110, 62, 2, True)
        c.arrow(770, 532, 882, 422, GREEN, 4)
        c.arrow(1098, 182, 974, 300, GREEN, 4)
    elif visual == "repel":
        particle_cloud(c, 720, 156, 420, 360, 80, 68, 5, False)
        c.circle(930, 336, 118, stroke=CORAL, line_width=3)
        c.arrow(930, 336, 780, 454, CORAL, 3)
        c.arrow(930, 336, 1070, 210, CORAL, 3)
        c.arrow(930, 336, 1072, 450, CORAL, 3)
    elif visual == "cycle":
        cx, cy, radius = 930, 336, 155
        positions = []
        for i, color in enumerate((CORAL, GREEN, BLUE)):
            angle = math.radians(90 - i * 120)
            px = cx + math.cos(angle) * radius
            py = cy + math.sin(angle) * radius
            positions.append((px, py, color))
            c.circle(px, py, 50, fill=mix(PANEL, color, 0.18), stroke=color, line_width=2.5)
        names = ["red", "green", "blue"]
        for (px, py, color), name in zip(positions, names):
            c.text(px - 24, py - 6, name, 20, "F2", TEXT)
        for i in range(3):
            ax, ay, color = positions[i]
            bx, by, _ = positions[(i + 1) % 3]
            c.arrow(ax + (bx - ax) * 0.28, ay + (by - ay) * 0.28,
                    ax + (bx - ax) * 0.70, ay + (by - ay) * 0.70, color, 3)
    elif visual == "wrap":
        wrap_world(c, 690, 170, 480, 320)
    elif visual == "2d3d":
        cube_vs_plane(c, 636, 142, 570, 386)
    elif visual == "gpu":
        gpu_grid(c, 672, 152, 500, 360)
    elif visual == "thread_particle":
        local_rules_diagram(c, 920, 342)
    elif visual == "neighbors":
        local_rules_diagram(c, 920, 342)
        c.text(735, 144, "near particles matter most", 22, "F2", TEAL)
    elif visual == "buffers":
        double_buffer(c, 610, 244)


def render_slide(deck_title: str, slide: Dict[str, object],
                 slide_no: int, total: int) -> bytes:
    c = Canvas()
    background(c, 1000 + slide_no * 37)
    header(c, deck_title, slide_no, total)
    title_block(
        c,
        str(slide.get("kicker", "")),
        str(slide.get("title", "")),
        str(slide.get("subtitle", "")),
    )
    if "bullets" in slide:
        bullets(c, 88, 280, slide["bullets"], ACCENTS[(slide_no - 1) % len(ACCENTS)], 42)
    draw_visual(c, str(slide.get("visual", "hero_cloud")))
    return c.stream()


def stream_object(data: bytes) -> bytes:
    return (
        b"<< /Length " + str(len(data)).encode("ascii") +
        b" >>\nstream\n" + data + b"endstream"
    )


def write_pdf(page_streams: Sequence[bytes], output: Path) -> None:
    objects: Dict[int, bytes] = {
        1: b"",
        2: b"",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        5: b"<< /Type /ExtGState /ca 0.95 /CA 0.95 >>",
    }
    page_ids: List[int] = []
    next_id = 6
    for stream in page_streams:
        content_id = next_id
        page_id = next_id + 1
        next_id += 2
        page_ids.append(page_id)
        objects[content_id] = stream_object(stream)
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> "
            f"/ExtGState << /GS95_95 5 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        ).encode("ascii")

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>".encode("ascii")

    max_id = max(objects)
    buffer = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (max_id + 1)
    for object_id in range(1, max_id + 1):
        offsets[object_id] = len(buffer)
        buffer.extend(f"{object_id} 0 obj\n".encode("ascii"))
        buffer.extend(objects[object_id])
        buffer.extend(b"\nendobj\n")

    xref_at = len(buffer)
    buffer.extend(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    buffer.extend(b"0000000000 65535 f \n")
    for object_id in range(1, max_id + 1):
        buffer.extend(f"{offsets[object_id]:010d} 00000 n \n".encode("ascii"))
    buffer.extend(
        f"trailer << /Size {max_id + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n".encode("ascii")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(buffer)


def generate() -> None:
    for output_name, deck_title, slides in DECKS:
        streams = [
            render_slide(deck_title, slide, index + 1, len(slides))
            for index, slide in enumerate(slides)
        ]
        output = ROOT / output_name
        write_pdf(streams, output)
        print(f"wrote {output.relative_to(ROOT)} ({len(slides)} slides)")


if __name__ == "__main__":
    generate()
