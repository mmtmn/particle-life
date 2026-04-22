# Particle Life CUDA

A GPU-accelerated particle life sandbox for Linux. The simulation runs an
all-pairs particle interaction kernel in CUDA and renders the result with
OpenGL/GLFW. You can switch between 2D and 3D, change the particle count,
resize the world, tune the interaction radius, and edit how each particle type
attracts or repels every other type while it is running.

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
```

Command-line options:

```text
--particles N       starting particle count
--max-particles N   maximum particles available while the app is running
--species N         particle species, 1-8
--size N            half-width of the wrapped simulation world
--radius N          interaction radius
--force-scale N     global attraction/repulsion multiplier
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
V           toggle 2D/3D; entering 3D reseeds particle depth
R           randomize particles and force matrix
P           randomize particles only
F           randomize force matrix only
Up/Down     increase/decrease particle count; hold Shift for larger jumps
Left/Right  shrink/grow world size
I/O         shrink/grow interaction radius
Q/E         decrease/increase global force scale
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

Each CUDA thread updates one particle. For every neighbor inside the interaction
radius, it looks up the force value for `target <- source` in the force matrix.
Close particles repel to avoid collapse. Farther particles use a bell-shaped
falloff, so they pull or repel most strongly near the middle of the interaction
range and taper to zero at the edge.

The world wraps around like a torus. In 2D the kernel ignores the Z axis. In 3D
it applies the same wrapped-distance calculation on X, Y, and Z.

## PDFs

The repository includes generated explanation PDFs:

- `docs/particle-life-overview.pdf`
- `docs/cuda-kernel-guide.pdf`
- `docs/controls-and-tuning.pdf`

Regenerate them from the Markdown sources with:

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

