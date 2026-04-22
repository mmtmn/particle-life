# Controls and Tuning

Particle life is most useful when tuned interactively. The app exposes the main
simulation parameters from the keyboard and shows the force matrix in the
top-right corner of the window.

## Reading the Matrix

Rows are affected particles. Columns are source particles. The selected cell is
outlined. Green cells attract and red cells repel.

For example, pair `2 <- 5` means species 5 is affecting species 2. Increasing
that value makes species 2 move toward species 5. Decreasing it makes species 2
move away from species 5.

## Important Controls

- `W/S` selects the affected species row.
- `A/D` selects the source species column.
- `-` makes the selected pair more repulsive.
- `=` makes the selected pair more attractive.
- `0` resets the selected pair to neutral.
- `F` randomizes the force matrix.
- `R` randomizes both particles and forces.

## Particle Count and World Size

Use `Up/Down` to change the particle count. Hold Shift for larger jumps. Use
`Left/Right` to change the wrapped world size.

Increasing particle count adds visual richness but costs more GPU work. Reducing
world size packs particles tighter, which usually increases interactions and can
make patterns more energetic.

## Radius and Force Scale

Use `I/O` to shrink or grow the interaction radius. A larger radius lets
particles affect more neighbors. Use `Q/E` to change the global force scale.
High force scale values can create faster motion but may also make the system
noisy.

## 2D and 3D Viewing

Press `V` to switch between 2D and 3D. In 2D, drag to pan and scroll to zoom. In
3D, drag to orbit and scroll to move the camera closer or farther away.

## Practical Starting Points

- Start with 4,096 to 12,000 particles.
- Keep the species count between 4 and 8.
- Randomize the force matrix until a few clusters form.
- Tune one selected matrix cell at a time so the cause of each change is clear.
- If the simulation becomes too chaotic, lower force scale or interaction
  radius.

