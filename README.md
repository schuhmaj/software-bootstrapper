# Software Bootstrapper

This repository contains scripts to bootstrap software installations and generate Lmod module files. It provides tools to install software from source using CMake configurations or install pre-built binaries like the Vulkan SDK.

## Installer

### Requirements

- Python 3.x
- `pyyaml`
- `loguru`
- `cmake` (available in your path)

### Usage

You need to be in the repository root directory!
Install only googletest and google-benchmark:

```bash
./installer.py -i "googletest|google-benchmark" configs <install-dir> <module-dir>
module use /opt/modules # <-- add this to your .bashrc or .zshrc or similar
module load googletest google-benchmark
```

Install everything else expt llvm:

```bash
./installer.py -e "llvm" configs <install-dir> <module-dir>
```

## Vulkan Installer

### Requirements

- Python 3.x

### Usage

You need to be in the repository root directory!

```bash
./installer_vulkan.py <install-dir> <module-dir>

module use <module-dir> # <-- add this to your .bashrc or .zshrc or similar for future convenience
module load VulkanSDK
```

