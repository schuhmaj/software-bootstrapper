-- %Module1.0

help([[
Sets up the HIP environment (version 7.2.3) for the NVIDIA platform.
This module configures HIP to use the local CUDA installation as its backend.
]])

whatis("Name: hip")
whatis("Version: 7.2.3")
whatis("Description: HIP environment configured for the NVIDIA/CUDA backend")

local rocm_dir = "/opt/rocm-7.2.3"
local cuda_dir = "/usr/local/cuda"

-- Core HIP and CUDA paths
setenv("HIP_PATH", rocm_dir)
setenv("ROCM_PATH", rocm_dir)
setenv("CUDA_PATH", cuda_dir)

-- Force HIP to use the NVIDIA backend
setenv("HIP_PLATFORM", "nvidia")
setenv("HIP_RUNTIME", "cuda")
setenv("HIP_COMPILER", "nvcc")

-- Update environment paths
prepend_path("PATH", pathJoin(rocm_dir, "bin"))

-- Include the library and header paths for compilation
prepend_path("LD_LIBRARY_PATH", pathJoin(rocm_dir, "lib"))
prepend_path("CPATH", pathJoin(rocm_dir, "include"))