#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace particle_life {

constexpr int kMaxSpecies = 8;

struct SimConfig {
  int maxParticles = 65536;
  int particleCount = 8192;
  int speciesCount = 6;
  float worldSize = 22.0f;
  float interactionRadius = 2.6f;
  float repulsionRadius = 0.18f;
  float forceScale = 18.0f;
  float friction = 0.90f;
  float timeStep = 0.016f;
  bool threeD = false;
  std::uint32_t seed = 1337;
};

struct ParticleSnapshot {
  float x = 0.0f;
  float y = 0.0f;
  float z = 0.0f;
  int species = 0;
};

class CudaSimulation {
 public:
  explicit CudaSimulation(SimConfig config);
  ~CudaSimulation();

  CudaSimulation(const CudaSimulation&) = delete;
  CudaSimulation& operator=(const CudaSimulation&) = delete;

  void step();
  void copyParticles(std::vector<ParticleSnapshot>& out) const;

  void setParticleCount(int count);
  void setWorldSize(float size);
  void setThreeD(bool enabled);
  void setInteractionRadius(float radius);
  void setForceScale(float scale);
  void setForce(int targetSpecies, int sourceSpecies, float value);

  float force(int targetSpecies, int sourceSpecies) const;
  void randomizeParticles(std::uint32_t seed);
  void randomizeForces(std::uint32_t seed);

  const SimConfig& config() const;
  const std::vector<float>& forceMatrix() const;

 private:
  struct Impl;
  Impl* impl_ = nullptr;
};

std::string cudaDeviceSummary();

}  // namespace particle_life

