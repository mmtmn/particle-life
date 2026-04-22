#include "particle_life.hpp"

#include <cuda_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace particle_life {
namespace {

#define CUDA_CHECK(call)                                                       \
  do {                                                                         \
    cudaError_t status = (call);                                               \
    if (status != cudaSuccess) {                                               \
      std::ostringstream oss;                                                  \
      oss << "CUDA error at " << __FILE__ << ":" << __LINE__ << ": "       \
          << cudaGetErrorString(status);                                       \
      throw std::runtime_error(oss.str());                                     \
    }                                                                          \
  } while (false)

struct KernelConfig {
  int particleCount = 0;
  int speciesCount = 0;
  int threeD = 0;
  float worldSize = 1.0f;
  float interactionRadius = 1.0f;
  float repulsionRadius = 0.1f;
  float forceScale = 1.0f;
  float friction = 0.9f;
  float timeStep = 0.016f;
};

__device__ float wrapDelta(float delta, float halfExtent) {
  const float span = halfExtent * 2.0f;
  if (delta > halfExtent) {
    delta -= span;
  } else if (delta < -halfExtent) {
    delta += span;
  }
  return delta;
}

__device__ float wrapPosition(float value, float halfExtent) {
  const float span = halfExtent * 2.0f;
  if (value > halfExtent) {
    value -= span;
  } else if (value < -halfExtent) {
    value += span;
  }
  return value;
}

__global__ void stepKernel(const float4* inPositions, const float4* inVelocities,
                           const int* species, const float* forceMatrix,
                           float4* outPositions, float4* outVelocities,
                           KernelConfig config) {
  const int i = blockIdx.x * blockDim.x + threadIdx.x;
  if (i >= config.particleCount) {
    return;
  }

  const float4 self = inPositions[i];
  const int selfSpecies = species[i];

  float ax = 0.0f;
  float ay = 0.0f;
  float az = 0.0f;
  const float radius2 = config.interactionRadius * config.interactionRadius;
  const float repelRadius = fmaxf(config.repulsionRadius, 0.001f);
  const float attractionSpan =
      fmaxf(config.interactionRadius - repelRadius, 0.001f);

  for (int j = 0; j < config.particleCount; ++j) {
    if (i == j) {
      continue;
    }

    const float4 other = inPositions[j];
    float dx = wrapDelta(other.x - self.x, config.worldSize);
    float dy = wrapDelta(other.y - self.y, config.worldSize);
    float dz = config.threeD ? wrapDelta(other.z - self.z, config.worldSize)
                             : 0.0f;
    const float dist2 = dx * dx + dy * dy + dz * dz;

    if (dist2 <= 1.0e-7f || dist2 > radius2) {
      continue;
    }

    const float dist = sqrtf(dist2);
    const float invDist = 1.0f / dist;
    const int otherSpecies = species[j];
    const float pull =
        forceMatrix[selfSpecies * kMaxSpecies + otherSpecies];

    float force = 0.0f;
    if (dist < repelRadius) {
      force = -1.0f * (1.0f - dist / repelRadius);
    } else {
      const float t = (dist - repelRadius) / attractionSpan;
      const float bell = 1.0f - fabsf(2.0f * t - 1.0f);
      force = pull * bell;
    }

    const float scaled = force * config.forceScale;
    ax += dx * invDist * scaled;
    ay += dy * invDist * scaled;
    az += dz * invDist * scaled;
  }

  float4 velocity = inVelocities[i];
  velocity.x = (velocity.x + ax * config.timeStep) * config.friction;
  velocity.y = (velocity.y + ay * config.timeStep) * config.friction;
  velocity.z = config.threeD
                   ? (velocity.z + az * config.timeStep) * config.friction
                   : 0.0f;

  const float maxSpeed = fmaxf(config.worldSize * 2.0f, 1.0f);
  const float speed2 = velocity.x * velocity.x + velocity.y * velocity.y +
                       velocity.z * velocity.z;
  if (speed2 > maxSpeed * maxSpeed) {
    const float scale = maxSpeed * rsqrtf(speed2);
    velocity.x *= scale;
    velocity.y *= scale;
    velocity.z *= scale;
  }

  float4 next = self;
  next.x = wrapPosition(next.x + velocity.x * config.timeStep,
                        config.worldSize);
  next.y = wrapPosition(next.y + velocity.y * config.timeStep,
                        config.worldSize);
  next.z = config.threeD ? wrapPosition(next.z + velocity.z * config.timeStep,
                                        config.worldSize)
                         : 0.0f;
  next.w = 1.0f;

  outPositions[i] = next;
  outVelocities[i] = velocity;
}

template <typename T>
T clampValue(T value, T lo, T hi) {
  return std::max(lo, std::min(value, hi));
}

}  // namespace

struct CudaSimulation::Impl {
  SimConfig config;
  float4* positionsA = nullptr;
  float4* positionsB = nullptr;
  float4* velocitiesA = nullptr;
  float4* velocitiesB = nullptr;
  int* species = nullptr;
  float* deviceForces = nullptr;
  bool useA = true;
  std::vector<float> hostForces;

  explicit Impl(SimConfig input) : config(input) {
    config.speciesCount = clampValue(config.speciesCount, 1, kMaxSpecies);
    config.maxParticles = std::max(config.maxParticles, config.particleCount);
    config.maxParticles = std::max(config.maxParticles, 128);
    config.particleCount =
        clampValue(config.particleCount, 1, config.maxParticles);
    config.worldSize = std::max(config.worldSize, 1.0f);
    config.interactionRadius =
        clampValue(config.interactionRadius, 0.05f, config.worldSize);
    config.repulsionRadius =
        clampValue(config.repulsionRadius, 0.01f, config.interactionRadius);
    config.forceScale = clampValue(config.forceScale, 0.1f, 80.0f);
    config.friction = clampValue(config.friction, 0.1f, 0.999f);
    config.timeStep = clampValue(config.timeStep, 0.001f, 0.05f);

    hostForces.assign(kMaxSpecies * kMaxSpecies, 0.0f);

    CUDA_CHECK(cudaMalloc(&positionsA, sizeof(float4) * config.maxParticles));
    CUDA_CHECK(cudaMalloc(&positionsB, sizeof(float4) * config.maxParticles));
    CUDA_CHECK(cudaMalloc(&velocitiesA, sizeof(float4) * config.maxParticles));
    CUDA_CHECK(cudaMalloc(&velocitiesB, sizeof(float4) * config.maxParticles));
    CUDA_CHECK(cudaMalloc(&species, sizeof(int) * config.maxParticles));
    CUDA_CHECK(cudaMalloc(&deviceForces,
                          sizeof(float) * hostForces.size()));

  }

  ~Impl() {
    cudaFree(positionsA);
    cudaFree(positionsB);
    cudaFree(velocitiesA);
    cudaFree(velocitiesB);
    cudaFree(species);
    cudaFree(deviceForces);
  }

  const float4* currentPositions() const { return useA ? positionsA : positionsB; }
  const float4* currentVelocities() const { return useA ? velocitiesA : velocitiesB; }
  float4* nextPositions() { return useA ? positionsB : positionsA; }
  float4* nextVelocities() { return useA ? velocitiesB : velocitiesA; }

  void uploadForces() {
    CUDA_CHECK(cudaMemcpy(deviceForces, hostForces.data(),
                          sizeof(float) * hostForces.size(),
                          cudaMemcpyHostToDevice));
  }
};

CudaSimulation::CudaSimulation(SimConfig config) : impl_(new Impl(config)) {
  randomizeForces(impl_->config.seed + 17);
  randomizeParticles(impl_->config.seed);
}

CudaSimulation::~CudaSimulation() { delete impl_; }

void CudaSimulation::step() {
  KernelConfig kernelConfig;
  kernelConfig.particleCount = impl_->config.particleCount;
  kernelConfig.speciesCount = impl_->config.speciesCount;
  kernelConfig.threeD = impl_->config.threeD ? 1 : 0;
  kernelConfig.worldSize = impl_->config.worldSize;
  kernelConfig.interactionRadius = impl_->config.interactionRadius;
  kernelConfig.repulsionRadius = impl_->config.repulsionRadius;
  kernelConfig.forceScale = impl_->config.forceScale;
  kernelConfig.friction = impl_->config.friction;
  kernelConfig.timeStep = impl_->config.timeStep;

  const int threads = 128;
  const int blocks = (impl_->config.particleCount + threads - 1) / threads;
  stepKernel<<<blocks, threads>>>(impl_->currentPositions(),
                                  impl_->currentVelocities(), impl_->species,
                                  impl_->deviceForces, impl_->nextPositions(),
                                  impl_->nextVelocities(), kernelConfig);
  CUDA_CHECK(cudaGetLastError());
  impl_->useA = !impl_->useA;
}

void CudaSimulation::copyParticles(std::vector<ParticleSnapshot>& out) const {
  const int count = impl_->config.particleCount;
  std::vector<float4> positions(count);
  std::vector<int> types(count);
  CUDA_CHECK(cudaMemcpy(positions.data(), impl_->currentPositions(),
                        sizeof(float4) * count, cudaMemcpyDeviceToHost));
  CUDA_CHECK(cudaMemcpy(types.data(), impl_->species, sizeof(int) * count,
                        cudaMemcpyDeviceToHost));

  out.resize(count);
  for (int i = 0; i < count; ++i) {
    out[i].x = positions[i].x;
    out[i].y = positions[i].y;
    out[i].z = positions[i].z;
    out[i].species = types[i];
  }
}

void CudaSimulation::setParticleCount(int count) {
  impl_->config.particleCount =
      clampValue(count, 1, impl_->config.maxParticles);
}

void CudaSimulation::setWorldSize(float size) {
  impl_->config.worldSize = clampValue(size, 1.0f, 500.0f);
  impl_->config.interactionRadius =
      clampValue(impl_->config.interactionRadius, 0.05f,
                 impl_->config.worldSize);
}

void CudaSimulation::setThreeD(bool enabled) { impl_->config.threeD = enabled; }

void CudaSimulation::setInteractionRadius(float radius) {
  impl_->config.interactionRadius =
      clampValue(radius, 0.05f, impl_->config.worldSize);
  impl_->config.repulsionRadius =
      clampValue(impl_->config.repulsionRadius, 0.01f,
                 impl_->config.interactionRadius);
}

void CudaSimulation::setForceScale(float scale) {
  impl_->config.forceScale = clampValue(scale, 0.1f, 80.0f);
}

void CudaSimulation::setForce(int targetSpecies, int sourceSpecies,
                              float value) {
  if (targetSpecies < 0 || targetSpecies >= impl_->config.speciesCount ||
      sourceSpecies < 0 || sourceSpecies >= impl_->config.speciesCount) {
    return;
  }
  impl_->hostForces[targetSpecies * kMaxSpecies + sourceSpecies] =
      clampValue(value, -1.5f, 1.5f);
  impl_->uploadForces();
}

float CudaSimulation::force(int targetSpecies, int sourceSpecies) const {
  if (targetSpecies < 0 || targetSpecies >= impl_->config.speciesCount ||
      sourceSpecies < 0 || sourceSpecies >= impl_->config.speciesCount) {
    return 0.0f;
  }
  return impl_->hostForces[targetSpecies * kMaxSpecies + sourceSpecies];
}

void CudaSimulation::randomizeParticles(std::uint32_t seed) {
  std::mt19937 rng(seed);
  std::uniform_real_distribution<float> position(-impl_->config.worldSize,
                                                  impl_->config.worldSize);
  std::uniform_real_distribution<float> velocity(-0.05f, 0.05f);
  std::uniform_int_distribution<int> type(0, impl_->config.speciesCount - 1);

  std::vector<float4> positions(impl_->config.maxParticles);
  std::vector<float4> velocities(impl_->config.maxParticles);
  std::vector<int> types(impl_->config.maxParticles);

  for (int i = 0; i < impl_->config.maxParticles; ++i) {
    const float z = impl_->config.threeD ? position(rng) : 0.0f;
    positions[i] = make_float4(position(rng), position(rng), z, 1.0f);
    velocities[i] = make_float4(velocity(rng), velocity(rng),
                                impl_->config.threeD ? velocity(rng) : 0.0f,
                                0.0f);
    types[i] = type(rng);
  }

  CUDA_CHECK(cudaMemcpy(impl_->positionsA, positions.data(),
                        sizeof(float4) * positions.size(),
                        cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(impl_->positionsB, positions.data(),
                        sizeof(float4) * positions.size(),
                        cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(impl_->velocitiesA, velocities.data(),
                        sizeof(float4) * velocities.size(),
                        cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(impl_->velocitiesB, velocities.data(),
                        sizeof(float4) * velocities.size(),
                        cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMemcpy(impl_->species, types.data(),
                        sizeof(int) * types.size(), cudaMemcpyHostToDevice));
  impl_->useA = true;
}

void CudaSimulation::randomizeForces(std::uint32_t seed) {
  std::mt19937 rng(seed);
  std::uniform_real_distribution<float> pull(-1.0f, 1.0f);
  impl_->hostForces.assign(kMaxSpecies * kMaxSpecies, 0.0f);

  for (int target = 0; target < impl_->config.speciesCount; ++target) {
    for (int source = 0; source < impl_->config.speciesCount; ++source) {
      float value = pull(rng);
      if (target == source) {
        value *= 0.35f;
      }
      impl_->hostForces[target * kMaxSpecies + source] = value;
    }
  }

  impl_->uploadForces();
}

const SimConfig& CudaSimulation::config() const { return impl_->config; }

const std::vector<float>& CudaSimulation::forceMatrix() const {
  return impl_->hostForces;
}

std::string cudaDeviceSummary() {
  int device = 0;
  cudaError_t status = cudaGetDevice(&device);
  if (status != cudaSuccess) {
    return std::string("CUDA unavailable: ") + cudaGetErrorString(status);
  }

  cudaDeviceProp properties{};
  status = cudaGetDeviceProperties(&properties, device);
  if (status != cudaSuccess) {
    return std::string("CUDA device query failed: ") +
           cudaGetErrorString(status);
  }

  std::ostringstream oss;
  oss << "CUDA device " << device << ": " << properties.name
      << " (compute " << properties.major << "." << properties.minor
      << ", " << (properties.totalGlobalMem / (1024 * 1024)) << " MiB VRAM)";
  return oss.str();
}

}  // namespace particle_life
