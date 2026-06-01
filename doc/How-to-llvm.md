# Get LLVM 20.1.8 running on the LRZ-Beast (Grace-Hopper Node)

The existing modules LLVM 19.1.2 and LLVM 17.0.4 don't come with the OpenMP module built with NVPTX support.
Further, they aren't working out of the box since the compiler `clang` won't use the `libstdc++` used for
building the LLVM, but rather the outdated system's default one.

## Get the existing compiler working


```bash
# Load the GCC utilized to build the compiler (e.g. gcc 13)
ml load gcc/13.2.0-gcc-12.3.0-pzyslmn
# Find where the lib64 folder is located
dirname $(g++ -print-file-name=libstdc++.so)
# Append this path and the path to the lib dir (next to lib64) to the LD_LIBRARY_PATH
export LD_LIBRARY_PATH="/path/to/your/gcc-14/lib64:$LD_LIBRARY_PATH"
# Now your compiled executable should not exit with "Cannot find GLBICXX ..."

```

## Install LLVM 20.1.8 module

The files included in this repository are the ones used to build the LLVM toolchain with the actual paths.
These serve as examples.

### Download & Install LLVM 20.1.8 with modern C++ Standard Library

Overall procedure:

```bash
wget https://github.com/llvm/llvm-project/archive/refs/tags/llvmorg-20.1.8.tar.gz
tar -xf llvmorg-20.1.8.tar.gz
cd llvm-project-llvmorg-20.1.8/llvm
cp <this-folder>/CMakePresets.json CMakePresets.json

# Load a modern GCC (provides the libstdc++ we want LLVM to use)
module load gcc/14

# Derive the GCC paths and export them. CMake presets cannot run shell
# commands, but they read environment variables via the $env{...} macro, so
# the preset picks these up automatically — no manual editing of the JSON.
export GCC_INSTALL_DIR=$(dirname "$(gcc -print-file-name=crtbegin.o)")
export GCC_LIB_DIR=$(dirname "$(g++ -print-file-name=libstdc++.so)")

# Optional: override the install location (defaults to ~/modules_install/llvm/20.1.8)
export LLVM_INSTALL_PREFIX="$HOME/modules_install/llvm/20.1.8"

cmake --workflow --preset default
```

No paths inside `CMakePresets.json` need to be edited anymore — the preset
resolves everything from the environment variables above:

| Environment variable | Used for | Derived from |
| --- | --- | --- |
| `GCC_INSTALL_DIR` | `--gcc-install-dir` in `CMAKE_C_FLAGS` / `CMAKE_CXX_FLAGS` (`RUNTIMES_CMAKE_ARGS`) | `dirname $(gcc -print-file-name=crtbegin.o)` |
| `GCC_LIB_DIR` | `-Wl,-rpath=` in `CMAKE_EXE_LINKER_FLAGS` / `CMAKE_SHARED_LINKER_FLAGS` (`RUNTIMES_CMAKE_ARGS`) | `dirname $(g++ -print-file-name=libstdc++.so)` |
| `LLVM_INSTALL_PREFIX` | `CMAKE_INSTALL_PREFIX` and `CMAKE_INSTALL_RPATH` | path where the toolchain should be installed |

`RUNTIMES_CMAKE_ARGS` therefore expands to:

- `-DLIBOMP_ARCH=aarch64`
  - might not be necessary
- `-DCMAKE_C_FLAGS=--gcc-install-dir=$GCC_INSTALL_DIR`
- `-DCMAKE_CXX_FLAGS=--gcc-install-dir=$GCC_INSTALL_DIR`
- `-DCMAKE_EXE_LINKER_FLAGS=-Wl,-rpath=$GCC_LIB_DIR`
- `-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-rpath=$GCC_LIB_DIR`

### Post-Install Steps

The LLVM toolchain needs to permanently be pointed to the right `libstdc++`.
This is done with a `clang++.cfg` config file next to the binaries, with
`clang.cfg` symlinked to it.

The `clang.cfg` file should look like this (using the same `GCC_INSTALL_DIR`
and `GCC_LIB_DIR` values derived above, written out as literal paths):

```bash
--gcc-install-dir=$GCC_INSTALL_DIR
-Wl,-rpath=$GCC_LIB_DIR
```

You can generate it directly, so the paths are baked in:

```bash
cd <install-dir>/bin
printf -- '--gcc-install-dir=%s\n-Wl,-rpath=%s\n' "$GCC_INSTALL_DIR" "$GCC_LIB_DIR" > clang++.cfg
ln -s clang++.cfg clang.cfg
```

### Install Module File

Copy the module file of this folder into the module folder of your system and adapt the paths inside the file.
