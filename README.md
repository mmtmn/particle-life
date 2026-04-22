# Particle Life CUDA

A GPU-accelerated particle life sandbox for Linux. The simulation runs CUDA
particle kernels and renders the result with OpenGL/GLFW. It includes classic
Particle Life plus a Particle Lenia mode inspired by the energy-based
formulation from Google Research's self-organising systems work. You can switch
between 2D and 3D, change particle count, resize the world, tune interaction
ranges, edit attraction/repulsion rules, or run Lenia-style local energy
descent.

## Install on Linux

Ubuntu/Debian packages:

```bash
sudo apt update
sudo apt install build-essential cmake pkg-config libglfw3-dev libgl1-mesa-dev
```

Install the NVIDIA CUDA Toolkit from NVIDIA or your distribution packages, then
confirm CUDA is visible:

```bash
nvcc --version
nvidia-smi
```

This project uses CUDA, so it needs an NVIDIA GPU and driver that support your
installed CUDA toolkit.

## Build With CMake

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=native
cmake --build build -j
```

Run a quick CUDA-only smoke test:

```bash
./build/particle-life --headless-steps 20 --particles 512
```

## Build the CUDA File Directly

CMake is recommended, but you can compile the CUDA file directly with `nvcc`:

```bash
nvcc -std=c++17 --allow-unsupported-compiler -Iinclude \
  src/main.cpp src/sim.cu -o particle-life \
  $(pkg-config --cflags --libs glfw3) -lGL
```

On some systems you may want to add an explicit GPU architecture, for example
`-arch=sm_86` for an RTX 3060.

## Run

```bash
./build/particle-life
./build/particle-life --particles 12000 --species 6 --size 28
./build/particle-life --3d --particles 4096 --radius 3.5 --force-scale 14
./build/particle-life --mode lenia
./build/particle-life --particle-lenia --particles 1200 --3d
```

Command-line options:

```text
--particles N       starting particle count
--max-particles N   maximum particles available while the app is running
--species N         particle species, 1-8
--mode NAME         simulation mode: life or lenia
--particle-lenia    shortcut for --mode lenia
--size N            half-width of the wrapped simulation world
--radius N          interaction radius
--force-scale N     global attraction/repulsion multiplier
--lenia-mu-k N      Particle Lenia kernel ring radius
--lenia-sigma-k N   Particle Lenia kernel ring width
--lenia-w-k N       Particle Lenia kernel weight
--lenia-mu-g N      Particle Lenia target field density
--lenia-sigma-g N   Particle Lenia growth band width
--lenia-repulsion N Particle Lenia short-range repulsion strength
--dt N              simulation timestep seconds
--seed N            deterministic random seed
--3d                start in 3D mode
--width N           window width
--height N          window height
--headless-steps N  run CUDA steps and exit without a window
```

## Controls

The small color matrix in the top-right corner is the force matrix. Rows are
the particle species being affected. Columns are the source species causing the
effect. Green means attraction, red means repulsion, and the outlined cell is
the selected pair.

```text
Space       pause/resume
L           toggle Particle Life / Particle Lenia mode
V           toggle 2D/3D; entering 3D reseeds particle depth
R           randomize particles and current mode parameters
P           randomize particles only
F           randomize force matrix or Particle Lenia parameters
Up/Down     increase/decrease particle count; hold Shift for larger jumps
Left/Right  shrink/grow world size
I/O         shrink/grow interaction radius
Q/E         decrease/increase global force scale
Z/X         lower/raise Particle Lenia target field density
C/B         narrow/widen Particle Lenia growth band
W/S         select affected particle species row
A/D         select source particle species column
-/=         repel/attract the selected species pair
0           reset selected pair to neutral
,/.         decrease/increase rendered point size
Mouse drag  pan in 2D, orbit in 3D
Scroll      zoom in 2D, dolly camera in 3D
N           reset camera
H           print controls in the terminal
```

## How It Works

### Particle Life

Each CUDA thread updates one particle. For every neighbor inside the interaction
radius, it looks up the force value for `target <- source` in the force matrix.
Close particles repel to avoid collapse. Farther particles use a bell-shaped
falloff, so they pull or repel most strongly near the middle of the interaction
range and taper to zero at the edge.

The world wraps around like a torus. In 2D the kernel ignores the Z axis. In 3D
it applies the same wrapped-distance calculation on X, Y, and Z.

### Particle Lenia

Particle Lenia replaces the hand-edited attraction matrix with a continuous
Lenia-inspired field. Each particle contributes a soft radial kernel to the
field. At every step, a CUDA thread samples the local field around its particle,
computes a growth score, adds short-range repulsion, and moves the particle
down the local energy gradient.

This keeps the mass-conservation property of a particle system because the app
does not create or delete particles during the Lenia update. It also follows
the multi-agent optimization interpretation: each particle greedily reduces its
own local energy, which can produce behavior that differs from directly
minimizing one global energy function.

References:

- Google Research self-organising systems article:
  <https://google-research.github.io/self-organising-systems/particle-lenia/>
- ALIFE 2023 perturbation-response study:
  <https://arxiv.org/abs/2305.16706>

## Presentation PDFs

The repository includes dark themed presentation PDFs for audiences that are
new to particle life. They focus on the concept, emergence, and the high-level
GPU simulation story rather than application controls:

- `docs/particle-life-intro-deck.pdf`
- `docs/emergence-visual-story.pdf`
- `docs/cuda-simulation-story.pdf`
- `docs/particle-lenia-advancement.pdf`

Regenerate them with:

```bash
python3 tools/make_pdfs.py
```

## Troubleshooting

- If CMake cannot find GLFW, install `libglfw3-dev`.
- If CUDA rejects your host compiler, install a CUDA-supported GCC version or
  keep the included `--allow-unsupported-compiler` flag.
- If the window cannot open over SSH, enable X11/Wayland forwarding or run the
  headless test with `--headless-steps`.
- If the frame rate drops, reduce `--particles`, because this simulation uses a
  simple all-pairs CUDA kernel: the work grows with `N * N`.
