help([[
CUDA 12.9 - NVIDIA CUDA Toolkit

NVIDIA CUDA is a parallel computing platform and programming model
that enables dramatic increases in computing performance by harnessing
the power of the graphics processing unit (GPU).

This module provides access to CUDA 12.9 installed in /usr/local/cuda.

Version: 12.9
]])

whatis("Name: CUDA")
whatis("Version: 12.9")
whatis("Category: gpu, parallel")
whatis("Description: NVIDIA CUDA Toolkit")
whatis("URL: https://developer.nvidia.com/cuda-toolkit")

-- Base installation directory
local cuda_root = "/work_fast/ge25zov/modules/nvidia/hpc_sdk/Linux_x86_64/25.9/cuda/12.9"
local cuda_bin = pathJoin(cuda_root, "bin")
local cuda_lib64 = pathJoin(cuda_root, "lib64")
local cuda_include = pathJoin(cuda_root, "include")

-- Check if CUDA installation exists
if not (isDir(cuda_root)) then
    LmodError("CUDA 12.9 installation not found in " .. cuda_root)
end

-- Add CUDA binaries to PATH
prepend_path("PATH", cuda_bin)

-- Set library paths
prepend_path("LD_LIBRARY_PATH", cuda_lib64)
prepend_path("LIBRARY_PATH", cuda_lib64)

-- Set include path
prepend_path("CPATH", cuda_include)
prepend_path("C_INCLUDE_PATH", cuda_include)
prepend_path("CPLUS_INCLUDE_PATH", cuda_include)

-- Set CUDA environment variables
setenv("CUDA_ROOT", cuda_root)
setenv("CUDA_HOME", cuda_root)
setenv("CUDA_PATH", cuda_root)
setenv("CUDA_VERSION", "13.0")

-- Set compiler paths
setenv("NVCC", pathJoin(cuda_bin, "nvcc"))
setenv("CUDACXX", pathJoin(cuda_bin, "nvcc"))

-- Conflict with other CUDA versions
conflict("cuda")
