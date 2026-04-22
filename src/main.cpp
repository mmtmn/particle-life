#include "particle_life.hpp"

#include <GLFW/glfw3.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using particle_life::CudaSimulation;
using particle_life::ParticleSnapshot;
using particle_life::SimConfig;
using particle_life::kMaxSpecies;

constexpr double kPi = 3.14159265358979323846;

struct Options {
  SimConfig config;
  int headlessSteps = -1;
  int width = 1280;
  int height = 800;
};

struct Color {
  float r;
  float g;
  float b;
};

const std::array<Color, kMaxSpecies> kPalette{{
    {0.95f, 0.20f, 0.24f},
    {0.18f, 0.74f, 0.34f},
    {0.20f, 0.48f, 0.95f},
    {0.96f, 0.76f, 0.20f},
    {0.75f, 0.28f, 0.96f},
    {0.08f, 0.78f, 0.82f},
    {1.00f, 0.52f, 0.22f},
    {0.88f, 0.90f, 0.92f},
}};

struct AppState {
  explicit AppState(const SimConfig& config)
      : simulation(config), seedCounter(config.seed + 101) {}

  CudaSimulation simulation;
  std::vector<ParticleSnapshot> particles;
  GLFWwindow* window = nullptr;
  bool paused = false;
  bool dragging = false;
  int selectedTarget = 0;
  int selectedSource = 0;
  int frameSteps = 1;
  float pointSize = 3.0f;
  float yaw = 38.0f;
  float pitch = 28.0f;
  float cameraDistance = 70.0f;
  float zoom = 1.0f;
  float panX = 0.0f;
  float panY = 0.0f;
  double lastMouseX = 0.0;
  double lastMouseY = 0.0;
  std::uint32_t seedCounter = 0;
  double lastTitleTime = 0.0;
  double fpsAccumulator = 0.0;
  int fpsFrames = 0;
  double fps = 0.0;
};

template <typename T>
T clampValue(T value, T lo, T hi) {
  return std::max(lo, std::min(value, hi));
}

[[noreturn]] void failUsage(const std::string& message) {
  throw std::runtime_error(message + "\nRun ./particle-life --help for usage.");
}

int parseInt(const std::string& text, const std::string& name) {
  char* end = nullptr;
  const long value = std::strtol(text.c_str(), &end, 10);
  if (end == text.c_str() || *end != '\0' ||
      value < std::numeric_limits<int>::min() ||
      value > std::numeric_limits<int>::max()) {
    failUsage("Invalid integer for " + name + ": " + text);
  }
  return static_cast<int>(value);
}

float parseFloat(const std::string& text, const std::string& name) {
  char* end = nullptr;
  const float value = std::strtof(text.c_str(), &end);
  if (end == text.c_str() || *end != '\0' || !std::isfinite(value)) {
    failUsage("Invalid number for " + name + ": " + text);
  }
  return value;
}

std::uint32_t parseSeed(const std::string& text) {
  const int value = parseInt(text, "--seed");
  if (value < 0) {
    failUsage("--seed must be non-negative");
  }
  return static_cast<std::uint32_t>(value);
}

void printControls() {
  std::cout
      << "\nParticle Life CUDA controls\n"
      << "  Space       pause/resume\n"
      << "  V           toggle 2D/3D (3D reseeds particle depth)\n"
      << "  R           randomize particles and force matrix\n"
      << "  P           randomize particles only\n"
      << "  F           randomize force matrix only\n"
      << "  Up/Down     increase/decrease particle count (Shift = larger step)\n"
      << "  Left/Right  shrink/grow world size\n"
      << "  I/O         shrink/grow interaction radius\n"
      << "  Q/E         decrease/increase global force scale\n"
      << "  W/S         select affected particle species row\n"
      << "  A/D         select source particle species column\n"
      << "  -/=         repel/attract selected species pair\n"
      << "  0           reset selected pair to neutral\n"
      << "  ,/.         decrease/increase rendered point size\n"
      << "  Mouse drag  pan in 2D, orbit in 3D\n"
      << "  Scroll      zoom in 2D, dolly camera in 3D\n"
      << "  N           reset camera\n"
      << "  H           print this help\n\n";
}

void printUsage() {
  std::cout
      << "Usage: particle-life [options]\n\n"
      << "Options:\n"
      << "  --particles N       starting particle count (default 8192)\n"
      << "  --max-particles N   maximum particles available at runtime (default 65536)\n"
      << "  --species N         particle species, 1-8 (default 6)\n"
      << "  --size N            half-width of the wrapped world (default 22)\n"
      << "  --radius N          interaction radius (default 2.6)\n"
      << "  --force-scale N     global force multiplier (default 18)\n"
      << "  --dt N              simulation timestep seconds (default 0.016)\n"
      << "  --seed N            deterministic random seed (default 1337)\n"
      << "  --3d                start in 3D mode\n"
      << "  --width N           window width (default 1280)\n"
      << "  --height N          window height (default 800)\n"
      << "  --headless-steps N  run CUDA steps and exit without opening a window\n"
      << "  --help              print this message\n";
  printControls();
}

Options parseOptions(int argc, char** argv) {
  Options options;

  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    auto requireValue = [&](const std::string& name) -> std::string {
      if (i + 1 >= argc) {
        failUsage("Missing value for " + name);
      }
      return argv[++i];
    };

    if (arg == "--help" || arg == "-h") {
      printUsage();
      std::exit(0);
    } else if (arg == "--particles") {
      options.config.particleCount = parseInt(requireValue(arg), arg);
    } else if (arg == "--max-particles") {
      options.config.maxParticles = parseInt(requireValue(arg), arg);
    } else if (arg == "--species") {
      options.config.speciesCount = parseInt(requireValue(arg), arg);
    } else if (arg == "--size") {
      options.config.worldSize = parseFloat(requireValue(arg), arg);
    } else if (arg == "--radius") {
      options.config.interactionRadius = parseFloat(requireValue(arg), arg);
    } else if (arg == "--force-scale") {
      options.config.forceScale = parseFloat(requireValue(arg), arg);
    } else if (arg == "--dt") {
      options.config.timeStep = parseFloat(requireValue(arg), arg);
    } else if (arg == "--seed") {
      options.config.seed = parseSeed(requireValue(arg));
    } else if (arg == "--3d") {
      options.config.threeD = true;
    } else if (arg == "--width") {
      options.width = parseInt(requireValue(arg), arg);
    } else if (arg == "--height") {
      options.height = parseInt(requireValue(arg), arg);
    } else if (arg == "--headless-steps") {
      options.headlessSteps = parseInt(requireValue(arg), arg);
    } else {
      failUsage("Unknown option: " + arg);
    }
  }

  if (options.config.particleCount < 1) {
    failUsage("--particles must be positive");
  }
  if (options.config.maxParticles < options.config.particleCount) {
    options.config.maxParticles = options.config.particleCount;
  }
  if (options.config.speciesCount < 1 ||
      options.config.speciesCount > kMaxSpecies) {
    failUsage("--species must be between 1 and 8");
  }
  if (options.width < 320 || options.height < 240) {
    failUsage("--width/--height must be at least 320x240");
  }
  if (options.headlessSteps < -1) {
    failUsage("--headless-steps must be zero or greater");
  }

  return options;
}

std::string formatFloat(float value, int precision = 2) {
  std::ostringstream oss;
  oss << std::fixed << std::setprecision(precision) << value;
  return oss.str();
}

std::string buildTitle(const AppState& app) {
  const auto& config = app.simulation.config();
  std::ostringstream title;
  title << "Particle Life CUDA | " << (config.threeD ? "3D" : "2D")
        << " | " << config.particleCount << "/" << config.maxParticles
        << " particles | size " << formatFloat(config.worldSize, 1)
        << " | radius " << formatFloat(config.interactionRadius, 2)
        << " | pair " << app.selectedTarget << " <- " << app.selectedSource
        << " " << formatFloat(app.simulation.force(app.selectedTarget,
                                                    app.selectedSource),
                               2)
        << " | scale " << formatFloat(config.forceScale, 1)
        << " | " << formatFloat(static_cast<float>(app.fps), 0) << " fps";
  if (app.paused) {
    title << " | paused";
  }
  title << " | H controls";
  return title.str();
}

void updateTitle(AppState& app, bool force = false) {
  const double now = glfwGetTime();
  if (!force && now - app.lastTitleTime < 0.25) {
    return;
  }
  app.lastTitleTime = now;
  glfwSetWindowTitle(app.window, buildTitle(app).c_str());
}

void resetCamera(AppState& app) {
  const auto& config = app.simulation.config();
  app.yaw = 38.0f;
  app.pitch = 28.0f;
  app.cameraDistance = std::max(8.0f, config.worldSize * 3.2f);
  app.zoom = 1.0f;
  app.panX = 0.0f;
  app.panY = 0.0f;
}

void changeParticleCount(AppState& app, int delta) {
  const auto& config = app.simulation.config();
  app.simulation.setParticleCount(
      clampValue(config.particleCount + delta, 1, config.maxParticles));
  updateTitle(app, true);
}

void changeWorldSize(AppState& app, float delta) {
  const float next = app.simulation.config().worldSize + delta;
  app.simulation.setWorldSize(next);
  app.cameraDistance =
      std::max(app.cameraDistance, app.simulation.config().worldSize * 2.0f);
  updateTitle(app, true);
}

void changeInteractionRadius(AppState& app, float factor) {
  const float next = app.simulation.config().interactionRadius * factor;
  app.simulation.setInteractionRadius(next);
  updateTitle(app, true);
}

void changeForceScale(AppState& app, float delta) {
  app.simulation.setForceScale(app.simulation.config().forceScale + delta);
  updateTitle(app, true);
}

void changeSelectedForce(AppState& app, float delta) {
  const float value =
      app.simulation.force(app.selectedTarget, app.selectedSource) + delta;
  app.simulation.setForce(app.selectedTarget, app.selectedSource, value);
  updateTitle(app, true);
}

void selectWrapped(int& value, int delta, int count) {
  value = (value + delta + count) % count;
}

void keyCallback(GLFWwindow* window, int key, int, int action, int mods) {
  if (action == GLFW_RELEASE) {
    return;
  }

  auto* app = static_cast<AppState*>(glfwGetWindowUserPointer(window));
  const bool fast = (mods & GLFW_MOD_SHIFT) != 0;
  const int speciesCount = app->simulation.config().speciesCount;

  switch (key) {
    case GLFW_KEY_ESCAPE:
      glfwSetWindowShouldClose(window, GLFW_TRUE);
      break;
    case GLFW_KEY_SPACE:
      app->paused = !app->paused;
      updateTitle(*app, true);
      break;
    case GLFW_KEY_H:
      printControls();
      break;
    case GLFW_KEY_V: {
      const bool enable3D = !app->simulation.config().threeD;
      app->simulation.setThreeD(enable3D);
      if (enable3D) {
        app->simulation.randomizeParticles(app->seedCounter++);
      }
      resetCamera(*app);
      updateTitle(*app, true);
      break;
    }
    case GLFW_KEY_R:
      app->simulation.randomizeForces(app->seedCounter++);
      app->simulation.randomizeParticles(app->seedCounter++);
      updateTitle(*app, true);
      break;
    case GLFW_KEY_P:
      app->simulation.randomizeParticles(app->seedCounter++);
      break;
    case GLFW_KEY_F:
      app->simulation.randomizeForces(app->seedCounter++);
      updateTitle(*app, true);
      break;
    case GLFW_KEY_UP:
      changeParticleCount(*app, fast ? 8192 : 1024);
      break;
    case GLFW_KEY_DOWN:
      changeParticleCount(*app, fast ? -8192 : -1024);
      break;
    case GLFW_KEY_RIGHT:
      changeWorldSize(*app, fast ? 5.0f : 1.0f);
      break;
    case GLFW_KEY_LEFT:
      changeWorldSize(*app, fast ? -5.0f : -1.0f);
      break;
    case GLFW_KEY_I:
      changeInteractionRadius(*app, 0.9f);
      break;
    case GLFW_KEY_O:
      changeInteractionRadius(*app, 1.1f);
      break;
    case GLFW_KEY_Q:
      changeForceScale(*app, fast ? -5.0f : -1.0f);
      break;
    case GLFW_KEY_E:
      changeForceScale(*app, fast ? 5.0f : 1.0f);
      break;
    case GLFW_KEY_W:
      selectWrapped(app->selectedTarget, -1, speciesCount);
      updateTitle(*app, true);
      break;
    case GLFW_KEY_S:
      selectWrapped(app->selectedTarget, 1, speciesCount);
      updateTitle(*app, true);
      break;
    case GLFW_KEY_A:
      selectWrapped(app->selectedSource, -1, speciesCount);
      updateTitle(*app, true);
      break;
    case GLFW_KEY_D:
      selectWrapped(app->selectedSource, 1, speciesCount);
      updateTitle(*app, true);
      break;
    case GLFW_KEY_MINUS:
    case GLFW_KEY_KP_SUBTRACT:
      changeSelectedForce(*app, fast ? -0.20f : -0.05f);
      break;
    case GLFW_KEY_EQUAL:
    case GLFW_KEY_KP_ADD:
      changeSelectedForce(*app, fast ? 0.20f : 0.05f);
      break;
    case GLFW_KEY_0:
    case GLFW_KEY_KP_0:
      app->simulation.setForce(app->selectedTarget, app->selectedSource, 0.0f);
      updateTitle(*app, true);
      break;
    case GLFW_KEY_COMMA:
      app->pointSize = clampValue(app->pointSize - 0.5f, 1.0f, 12.0f);
      break;
    case GLFW_KEY_PERIOD:
      app->pointSize = clampValue(app->pointSize + 0.5f, 1.0f, 12.0f);
      break;
    case GLFW_KEY_N:
      resetCamera(*app);
      break;
    default:
      break;
  }
}

void mouseButtonCallback(GLFWwindow* window, int button, int action, int) {
  if (button != GLFW_MOUSE_BUTTON_LEFT) {
    return;
  }
  auto* app = static_cast<AppState*>(glfwGetWindowUserPointer(window));
  app->dragging = action == GLFW_PRESS;
  glfwGetCursorPos(window, &app->lastMouseX, &app->lastMouseY);
}

void cursorCallback(GLFWwindow* window, double x, double y) {
  auto* app = static_cast<AppState*>(glfwGetWindowUserPointer(window));
  if (!app->dragging) {
    app->lastMouseX = x;
    app->lastMouseY = y;
    return;
  }

  const double dx = x - app->lastMouseX;
  const double dy = y - app->lastMouseY;
  app->lastMouseX = x;
  app->lastMouseY = y;

  if (app->simulation.config().threeD) {
    app->yaw += static_cast<float>(dx * 0.25);
    app->pitch =
        clampValue(app->pitch + static_cast<float>(dy * 0.25), -88.0f, 88.0f);
  } else {
    int width = 1;
    int height = 1;
    glfwGetFramebufferSize(window, &width, &height);
    const float aspect = static_cast<float>(width) / std::max(1, height);
    const float halfY = app->simulation.config().worldSize * app->zoom;
    const float halfX = halfY * aspect;
    app->panX -= static_cast<float>(dx) * (2.0f * halfX / width);
    app->panY += static_cast<float>(dy) * (2.0f * halfY / height);
  }
}

void scrollCallback(GLFWwindow* window, double, double yOffset) {
  auto* app = static_cast<AppState*>(glfwGetWindowUserPointer(window));
  const float factor = static_cast<float>(std::pow(0.88, yOffset));
  if (app->simulation.config().threeD) {
    app->cameraDistance =
        clampValue(app->cameraDistance * factor, 2.0f, 1000.0f);
  } else {
    app->zoom = clampValue(app->zoom * factor, 0.08f, 50.0f);
  }
}

void setPerspective(float fovDegrees, float aspect, float nearPlane,
                    float farPlane) {
  const double top = std::tan(fovDegrees * kPi / 360.0) * nearPlane;
  const double right = top * aspect;
  glFrustum(-right, right, -top, top, nearPlane, farPlane);
}

void drawBox2D(float worldSize) {
  glColor4f(0.55f, 0.58f, 0.62f, 0.75f);
  glBegin(GL_LINE_LOOP);
  glVertex2f(-worldSize, -worldSize);
  glVertex2f(worldSize, -worldSize);
  glVertex2f(worldSize, worldSize);
  glVertex2f(-worldSize, worldSize);
  glEnd();

  glColor4f(0.35f, 0.38f, 0.42f, 0.35f);
  glBegin(GL_LINES);
  for (int i = -3; i <= 3; ++i) {
    const float p = worldSize * static_cast<float>(i) / 4.0f;
    glVertex2f(p, -worldSize);
    glVertex2f(p, worldSize);
    glVertex2f(-worldSize, p);
    glVertex2f(worldSize, p);
  }
  glEnd();
}

void drawBox3D(float worldSize) {
  const float w = worldSize;
  const std::array<std::array<float, 3>, 8> corners{{
      {{-w, -w, -w}},
      {{w, -w, -w}},
      {{w, w, -w}},
      {{-w, w, -w}},
      {{-w, -w, w}},
      {{w, -w, w}},
      {{w, w, w}},
      {{-w, w, w}},
  }};
  constexpr int edges[12][2] = {{0, 1}, {1, 2}, {2, 3}, {3, 0},
                                {4, 5}, {5, 6}, {6, 7}, {7, 4},
                                {0, 4}, {1, 5}, {2, 6}, {3, 7}};

  glColor4f(0.55f, 0.58f, 0.62f, 0.55f);
  glBegin(GL_LINES);
  for (const auto& edge : edges) {
    const auto& a = corners[edge[0]];
    const auto& b = corners[edge[1]];
    glVertex3f(a[0], a[1], a[2]);
    glVertex3f(b[0], b[1], b[2]);
  }
  glEnd();

  glBegin(GL_LINES);
  glColor4f(0.95f, 0.20f, 0.24f, 0.8f);
  glVertex3f(-w, 0.0f, 0.0f);
  glVertex3f(w, 0.0f, 0.0f);
  glColor4f(0.18f, 0.74f, 0.34f, 0.8f);
  glVertex3f(0.0f, -w, 0.0f);
  glVertex3f(0.0f, w, 0.0f);
  glColor4f(0.20f, 0.48f, 0.95f, 0.8f);
  glVertex3f(0.0f, 0.0f, -w);
  glVertex3f(0.0f, 0.0f, w);
  glEnd();
}

void drawParticles(const AppState& app) {
  glPointSize(app.pointSize);
  glBegin(GL_POINTS);
  for (const auto& particle : app.particles) {
    const Color color =
        kPalette[static_cast<std::size_t>(particle.species) % kPalette.size()];
    glColor4f(color.r, color.g, color.b, 0.92f);
    glVertex3f(particle.x, particle.y, particle.z);
  }
  glEnd();
}

void rect(float x, float y, float width, float height) {
  glBegin(GL_QUADS);
  glVertex2f(x, y);
  glVertex2f(x + width, y);
  glVertex2f(x + width, y + height);
  glVertex2f(x, y + height);
  glEnd();
}

void rectOutline(float x, float y, float width, float height) {
  glBegin(GL_LINE_LOOP);
  glVertex2f(x, y);
  glVertex2f(x + width, y);
  glVertex2f(x + width, y + height);
  glVertex2f(x, y + height);
  glEnd();
}

void drawForceMatrixOverlay(const AppState& app, int framebufferWidth,
                            int framebufferHeight) {
  const int species = app.simulation.config().speciesCount;
  const float cell = 22.0f;
  const float margin = 18.0f;
  const float x0 = framebufferWidth - margin - cell * species;
  const float y0 = margin;

  glMatrixMode(GL_PROJECTION);
  glPushMatrix();
  glLoadIdentity();
  glOrtho(0.0, framebufferWidth, framebufferHeight, 0.0, -1.0, 1.0);
  glMatrixMode(GL_MODELVIEW);
  glPushMatrix();
  glLoadIdentity();
  glDisable(GL_DEPTH_TEST);

  glColor4f(0.03f, 0.04f, 0.05f, 0.78f);
  rect(x0 - 6.0f, y0 - 6.0f, cell * species + 12.0f,
       cell * species + 12.0f);

  for (int target = 0; target < species; ++target) {
    for (int source = 0; source < species; ++source) {
      const float value = app.simulation.force(target, source);
      const float amount = clampValue(std::fabs(value) / 1.5f, 0.0f, 1.0f);
      if (value >= 0.0f) {
        glColor4f(0.08f + 0.15f * amount, 0.30f + 0.55f * amount,
                  0.22f + 0.35f * amount, 0.90f);
      } else {
        glColor4f(0.38f + 0.50f * amount, 0.10f + 0.10f * amount,
                  0.18f + 0.12f * amount, 0.90f);
      }
      const float x = x0 + source * cell;
      const float y = y0 + target * cell;
      rect(x + 1.0f, y + 1.0f, cell - 2.0f, cell - 2.0f);
    }
  }

  glLineWidth(2.0f);
  glColor4f(1.0f, 1.0f, 1.0f, 0.95f);
  rectOutline(x0 + app.selectedSource * cell + 1.0f,
              y0 + app.selectedTarget * cell + 1.0f, cell - 2.0f,
              cell - 2.0f);
  glLineWidth(1.0f);

  glMatrixMode(GL_MODELVIEW);
  glPopMatrix();
  glMatrixMode(GL_PROJECTION);
  glPopMatrix();
}

void render(AppState& app) {
  int width = 1;
  int height = 1;
  glfwGetFramebufferSize(app.window, &width, &height);
  glViewport(0, 0, width, height);
  glClearColor(0.015f, 0.017f, 0.020f, 1.0f);
  glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

  glEnable(GL_BLEND);
  glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
  glEnable(GL_POINT_SMOOTH);

  const auto& config = app.simulation.config();
  const float aspect = static_cast<float>(width) / std::max(1, height);

  glMatrixMode(GL_PROJECTION);
  glLoadIdentity();
  glMatrixMode(GL_MODELVIEW);
  glLoadIdentity();

  if (config.threeD) {
    glEnable(GL_DEPTH_TEST);
    glMatrixMode(GL_PROJECTION);
    setPerspective(55.0f, aspect, 0.1f, 2000.0f);
    glMatrixMode(GL_MODELVIEW);
    glTranslatef(0.0f, 0.0f, -app.cameraDistance);
    glRotatef(app.pitch, 1.0f, 0.0f, 0.0f);
    glRotatef(app.yaw, 0.0f, 1.0f, 0.0f);
    drawBox3D(config.worldSize);
  } else {
    glDisable(GL_DEPTH_TEST);
    glMatrixMode(GL_PROJECTION);
    const float halfY = config.worldSize * app.zoom;
    const float halfX = halfY * aspect;
    glOrtho(-halfX + app.panX, halfX + app.panX, -halfY + app.panY,
            halfY + app.panY, -1.0, 1.0);
    glMatrixMode(GL_MODELVIEW);
    drawBox2D(config.worldSize);
  }

  drawParticles(app);
  drawForceMatrixOverlay(app, width, height);
}

void runHeadless(CudaSimulation& simulation, int steps) {
  const auto start = std::chrono::steady_clock::now();
  for (int i = 0; i < steps; ++i) {
    simulation.step();
  }
  std::vector<ParticleSnapshot> particles;
  simulation.copyParticles(particles);
  const auto end = std::chrono::steady_clock::now();
  const double ms =
      std::chrono::duration<double, std::milli>(end - start).count();

  float maxRadius = 0.0f;
  for (const auto& particle : particles) {
    maxRadius = std::max(
        maxRadius,
        std::sqrt(particle.x * particle.x + particle.y * particle.y +
                  particle.z * particle.z));
  }

  std::cout << "Headless run complete: " << steps << " CUDA steps, "
            << particles.size() << " particles, "
            << (simulation.config().threeD ? "3D" : "2D") << ", "
            << formatFloat(static_cast<float>(ms), 2) << " ms wall time\n"
            << "Largest sampled distance from origin: "
            << formatFloat(maxRadius, 3) << "\n";
}

}  // namespace

int main(int argc, char** argv) {
  try {
    Options options = parseOptions(argc, argv);
    AppState app(options.config);
    std::cout << particle_life::cudaDeviceSummary() << "\n";

    if (options.headlessSteps >= 0) {
      runHeadless(app.simulation, options.headlessSteps);
      return 0;
    }

    printControls();

    if (!glfwInit()) {
      throw std::runtime_error("Failed to initialize GLFW");
    }

    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 2);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 1);
    glfwWindowHint(GLFW_SAMPLES, 4);

    app.window =
        glfwCreateWindow(options.width, options.height, "Particle Life CUDA",
                         nullptr, nullptr);
    if (!app.window) {
      glfwTerminate();
      throw std::runtime_error(
          "Failed to open a GLFW window. Check DISPLAY/Wayland access.");
    }

    glfwMakeContextCurrent(app.window);
    glfwSwapInterval(1);
    glfwSetWindowUserPointer(app.window, &app);
    glfwSetKeyCallback(app.window, keyCallback);
    glfwSetMouseButtonCallback(app.window, mouseButtonCallback);
    glfwSetCursorPosCallback(app.window, cursorCallback);
    glfwSetScrollCallback(app.window, scrollCallback);

    resetCamera(app);
    updateTitle(app, true);

    double previousTime = glfwGetTime();
    while (!glfwWindowShouldClose(app.window)) {
      glfwPollEvents();

      if (!app.paused) {
        for (int i = 0; i < app.frameSteps; ++i) {
          app.simulation.step();
        }
      }
      app.simulation.copyParticles(app.particles);

      const double now = glfwGetTime();
      const double dt = now - previousTime;
      previousTime = now;
      app.fpsAccumulator += dt;
      app.fpsFrames += 1;
      if (app.fpsAccumulator >= 0.5) {
        app.fps = app.fpsFrames / app.fpsAccumulator;
        app.fpsFrames = 0;
        app.fpsAccumulator = 0.0;
      }

      render(app);
      updateTitle(app);
      glfwSwapBuffers(app.window);
    }

    glfwDestroyWindow(app.window);
    glfwTerminate();
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "particle-life: " << error.what() << "\n";
    return 1;
  }
}
