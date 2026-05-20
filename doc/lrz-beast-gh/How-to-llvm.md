# Get LLVM 20.1.8 running on the LRZ-Beast (Grace-Hopper Node)

The existing modules LLVM 19.1.2 and LLVM 17.0.4 don't come with the OpenMP module built with NVPTX support.
Further, they aren't working out of the box since the compiler `clang` won't use the `libstdc++` used for
building the LLVM, but rather the outdated system's default one.

## Get the existing compiler working


```bash
# Load the GCC utilized to build the compiler
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
cp <this-folder>/llvm_CMakePresets.json CMakePresets.json

# We assume (load a modern GCC)
module load gcc/14
GCC-ENTRY-PATH = (dirname $(gcc -print-file-name=crtbegin.o))
GCC-LIB-PATH = (dirname $(g++ -print-file-name=libstdc++.so))
GCC-BASE-PATH = (dirname $(g++ -print-file-name=libstdc++.so))/..

# Before executing the following command, make sure to set the correct paths in CMakePresets.json
# CMAKE_INSTALL_PREFIX, CMAKE_INSTALL_RPATH and RUNTIMES_CMAKE_ARGS
cmake --workflow --preset default
```
`CMAKE_INSTALL_PREFIX` and `CMAKE_INSTALL_RPATH` need to be adapted to the path where to install the LLVM toolchain.

`RUNTIMES_CMAKE_ARGS` consists of the following:

- `-DLIBOMP_ARCH=aarch64`
  - might not be necessary
- `-DCMAKE_C_FLAGS=--gcc-install-dir=$GCC-ENTRY-PATH`
- `-DCMAKE_CXX_FLAGS=--gcc-install-dir=$GCC-ENTRY-PATH`
- `-DCMAKE_EXE_LINKER_FLAGS=-Wl,-rpath=$GCC-LIB-PATH`
- `-DCMAKE_SHARED_LINKER_FLAGS=-Wl,-rpath=$GCC-LIB-PATH`

### Post-Install Steps

The LLVM toolchain needs to permanently be pointed to the right `libstdc++`. Hence, do the following:

```bash
cd <install-dir>/bin
touch clang++.cf
ln -s clang++.cfg clang.cfg
```

The `clang.cfg` file should look like this:

```bash
--gcc-install-dir=$GCC-ENTRY-PATH
-Wl,-rpath=$GCC-LIB-PATH
```

### Install Module File

Copy the module file of this folder into the module folder of your system and adapt the paths inside the file.
