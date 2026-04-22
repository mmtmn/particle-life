cmake_minimum_required(VERSION 3.24)

# CUDA 12.0 rejects newer distro compilers during compiler detection unless
# this flag is present early. Users with a CUDA-supported host compiler can
# remove it or override CMAKE_CUDA_FLAGS from the command line.
set(CMAKE_CUDA_FLAGS "${CMAKE_CUDA_FLAGS} --allow-unsupported-compiler")

project(particle_life LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_STANDARD_REQUIRED ON)

if(NOT DEFINED CMAKE_CUDA_ARCHITECTURES)
  set(CMAKE_CUDA_ARCHITECTURES native)
endif()

find_package(OpenGL REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(GLFW3 REQUIRED IMPORTED_TARGET glfw3)

add_executable(particle-life
  src/main.cpp
  src/sim.cu
)

target_include_directories(particle-life PRIVATE include)
target_link_libraries(particle-life PRIVATE OpenGL::GL PkgConfig::GLFW3)

target_compile_options(particle-life PRIVATE
  $<$<COMPILE_LANGUAGE:CXX>:-Wall -Wextra -Wpedantic>
  $<$<COMPILE_LANGUAGE:CUDA>:--expt-relaxed-constexpr>
)

