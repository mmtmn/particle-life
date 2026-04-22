# CUDA Kernel Guide

The simulation step runs in `src/sim.cu`. One CUDA thread is launched for each
particle. That thread reads the previous particle positions, computes one new
velocity and position, and writes them to an output buffer.

## Double Buffering

The code keeps two position buffers and two velocity buffers. Each frame reads
from the current buffers and writes to the next buffers, then swaps them. This
avoids a race where one thread would read a particle that another thread has
already updated during the same step.

## Per-Particle Work

For particle `i`, the kernel loops over all particles `j`.

1. Skip itself.
2. Compute the wrapped X/Y/Z delta.
3. Ignore particles outside the interaction radius.
4. Look up the force value for `species[i] <- species[j]`.
5. Apply short-range repulsion if the particles are very close.
6. Otherwise apply the force matrix value with a bell-shaped falloff.
7. Add the result into acceleration.

The implementation is intentionally direct and readable. It is an all-pairs
kernel, so the cost grows with `N * N`.

## Stability Controls

The kernel uses three simple stability limits.

- A short repulsion radius keeps particles from collapsing into one point.
- Friction damps velocity every step.
- A maximum speed clamp prevents extreme forces from throwing particles across
  the whole world in one frame.

## 2D and 3D Branch

The same kernel handles 2D and 3D. In 2D mode it sets `dz` and Z velocity to
zero. In 3D mode it includes wrapped Z distance and updates Z position.

## Rendering Boundary

The CUDA simulation does not render directly. After each step, the app copies
the current particle positions back to the CPU and renders them as OpenGL
points. This keeps the code simple and makes the CUDA part easy to understand.

