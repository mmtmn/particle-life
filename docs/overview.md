# Particle Life Overview

Particle life is a simple artificial-life model. The simulation contains many
particles, each tagged with a species number. Every species has a configurable
relationship with every other species. One species can attract another, repel
another, ignore another, or do any mixture in between.

## Core Idea

For every particle, the CUDA kernel checks nearby particles. It computes a
wrapped distance, reads the selected force from the force matrix, and adds that
force to the particle acceleration. After the acceleration is accumulated, the
kernel updates velocity and position.

## Force Matrix

The force matrix answers one question: how does a source particle affect a
target particle?

- Rows are target species, the particles being moved.
- Columns are source species, the particles causing the movement.
- Positive values pull the target toward the source.
- Negative values push the target away from the source.
- Zero values make that pair mostly ignore each other outside the short-range
  collision repulsion.

The matrix is directional. Species 1 can attract species 2 while species 2
repels species 1.

## Wrapped World

Positions are kept inside a square or cube centered on the origin. When a
particle crosses one side it re-enters from the opposite side. Distance checks
also wrap, so particles near opposite edges still see each other as close.

## 2D and 3D

In 2D mode, the kernel forces Z velocity and Z position to zero. In 3D mode, the
same rules apply on X, Y, and Z. The viewer changes from an orthographic 2D
camera to an orbiting 3D camera.

## Emergent Patterns

Small changes in the force matrix can create clusters, rings, waves, chasing
streams, turbulent mixing, and layered structures. The application exposes
runtime controls because the interesting behavior usually comes from tuning the
matrix while watching the result.

