# Hacky Tricks on the LRZ-Beast

A collection of the quirky workarounds needed to get the performance-portability benchmark
built and running on the Beast nodes. Nothing here is elegant — it is written down so it can
be redone when something breaks again.

- [Milan node (AMD Instinct MI210, `gfx90a`)](#milan-node-amd-instinct-mi210-gfx90a)
- [SAP node (Intel GPU Max 1550)](#sap-node-intel-gpu-max-1550)

---

## Milan node (AMD Instinct MI210, `gfx90a`)

### 1. The system ROCm 7.1 is incomplete → use a user-space ROCm 7.10 (TheRock)

**Symptom**

```
Could not find a package configuration file provided by "hip" with any of
the following names:
    hipConfig.cmake
    hip-config.cmake
```

Raised from `KokkosConfig.cmake` (Kokkos with the HIP backend calls `find_dependency(hip)`).
Building AdaptiveCpp against the system ROCm fails similarly with `'hip/hiprtc.h' file not found`.

**Cause**

`/opt/rocm-7.1.0` only has the runtime packages installed. The *devel* packages are missing:
there is no `lib/cmake/hip`, no `lib/cmake/hsa-runtime64` and no hipRTC headers
(`hip-runtime-amd-devel`, `hsa-rocr-devel`). The math libraries (`hipblas`, `rocthrust`, ...)
are present, which makes this easy to miss. No root → cannot install them.

**Fix**

Extract AMD's portable TheRock tarball into user space. The kernel driver (`amdgpu`) is the only
thing that has to come from the system.

- Download page (JS app, filter for `gfx90X`): <https://repo.amd.com/rocm/tarball/>
- The MI210 is `gfx90a` (`rocminfo | grep -m1 gfx`) → family tarball `gfx90X-dcgpu`.

```bash
mkdir -p ~/modules_milan/modules_install/rocm/7.10.0 && cd ~/modules_milan/modules_install/rocm/7.10.0
wget https://repo.amd.com/rocm/tarball/therock-dist-linux-gfx90X-dcgpu-7.10.0.tar.gz
tar -xf therock-dist-linux-gfx90X-dcgpu-7.10.0.tar.gz
ls lib/cmake/hip/hip-config.cmake   # must exist
```

Afterwards, **rebuild everything that links against HIP** (Kokkos, AdaptiveCpp) and clear
AdaptiveCpp's JIT cache (`~/.acpp/apps/*`).

### 2. The ROCm module file

The system ROCm is put on `PATH`/`LD_LIBRARY_PATH` by the shell profile. Mixing both ROCm versions
causes subtle breakage (e.g. `amdclang++` resolving to the 7.1 one), so the module strips them.
Each `setenv` below exists because of one of the issues further down.

```tcl
#%Module1.0
##
## ROCm 7.10.0 (TheRock tarball, gfx90X)
##

proc ModulesHelp { } {
    puts stderr "ROCm 7.10.0 (TheRock user-space install)"
}
module-whatis "ROCm 7.10.0 (TheRock tarball, gfx90X)"

conflict rocm

set root /home/ge25zov2/modules_milan/modules_install/rocm/7.10.0

# drop the system ROCm (set in the shell profile) so its amdclang/hipcc/libs can't shadow this one
foreach dir {/opt/rocm/bin /opt/rocm/llvm/bin /opt/rocm-7.1.0/bin /opt/rocm-7.1.0/lib/llvm/bin} {
    remove-path PATH $dir
}
foreach dir {/opt/rocm/lib /opt/rocm/lib/ /opt/rocm-7.1.0/lib} {
    remove-path LD_LIBRARY_PATH $dir
}

setenv ROCM_PATH           $root
setenv HIP_PATH            $root
# hip-config.cmake otherwise ends up with an empty platform (see 3.)
setenv HIP_PLATFORM        amd
# TheRock tarball: clang can't find its device bitcode when ROCM_PATH is set (TheRock#785, see 4.)
setenv HIP_DEVICE_LIB_PATH $root/lib/llvm/amdgcn/bitcode
# system ocl-icd is too old for OCL_ICD_FILENAMES and /etc/OpenCL/vendors doesn't exist (see 6.)
setenv OCL_ICD_VENDORS     $root/etc/OpenCL/vendors
# AdaptiveCpp's acpp otherwise uses the ROCm path from its build
setenv ACPP_ROCM_PATH      $root

prepend-path PATH              $root/bin
# appended so the upstream LLVM module's clang keeps priority; amdclang is still found
append-path  PATH              $root/lib/llvm/bin
prepend-path LD_LIBRARY_PATH   $root/lib
prepend-path CMAKE_PREFIX_PATH $root
prepend-path PKG_CONFIG_PATH   $root/lib/pkgconfig
```

Notes:

- `lib/llvm/bin` is **appended** on purpose: the `rocm-llvm-cdna` preset uses plain `clang++`
  from the LLVM 20.1.8 module, while `amdclang++` should come from ROCm 7.10. This only works
  because the `/opt/rocm*` entries are removed — otherwise the system `amdclang++` wins.
- `remove-path` needs exact string matches (hence `/opt/rocm/lib` with and without trailing `/`).
- `module unload` does not restore the removed `/opt/rocm*` entries; open a new shell.
- A leftover `rocm/7.1.0` module blocks loading (`conflict rocm`) → `module unload rocm/7.1.0` first.

### 3. `Unexpected HIP_PLATFORM:` (empty)

**Symptom** (configuring Kokkos with `-DKokkos_ENABLE_HIP=ON`)

```
CMake Error at .../rocm/7.10.0/lib/cmake/hip/hip-config.cmake:144 (message):
  Unexpected HIP_PLATFORM:
```

`hipconfig --platform` prints `amd` just fine when run by hand, but the config still ends up empty.

**Fix**: pass it explicitly — `-DHIP_PLATFORM=amd` or `setenv HIP_PLATFORM amd` in the module.

### 4. `cannot find ROCm device library`

**Symptom**

```
clang++: error: cannot find ROCm device library; provide its path via '--rocm-path' or
'--rocm-device-lib-path', or pass '-nogpulib' to build without ROCm device library
```

**Cause** (TheRock issues [#785](https://github.com/ROCm/TheRock/issues/785),
[#2708](https://github.com/ROCm/TheRock/issues/2708))

The GPU device bitcode (`hip.bc`, `ockl.bc`, ...) lives in a non-standard place in the tarball:

| Layout | Bitcode location |
| --- | --- |
| Classic ROCm packages (≤ 7.2) | `<rocm>/amdgcn/bitcode` and `<rocm>/lib/llvm/lib/clang/<ver>/lib/amdgcn/bitcode` |
| TheRock tarball 7.10 | `<rocm>/lib/llvm/amdgcn/bitcode` **only** |

Clang first looks in its resource dir, then in a few ROCm install candidates — but **if
`ROCM_PATH` is set, only `$ROCM_PATH/amdgcn/bitcode` is tried**. An explicit
`--rocm-device-lib-path` overrides everything, including the environment variable.

**Fix** — apply all three, each one covers a different tool:

```bash
# (a) env var: honoured by clang when no --rocm-device-lib-path is passed (Kokkos, plain amdclang++)
export HIP_DEVICE_LIB_PATH=$ROCM_PATH/lib/llvm/amdgcn/bitcode

# (b) classic layout symlink: AdaptiveCpp passes --rocm-device-lib-path=$ACPP_ROCM_PATH/amdgcn/bitcode
#     explicitly, so (a) does NOT help there
ln -s lib/llvm/amdgcn $ROCM_PATH/amdgcn

# (c) resource-dir symlink, like regular ROCm packages
RES=$($ROCM_PATH/lib/llvm/bin/clang++ -print-resource-dir)
mkdir -p $RES/lib && ln -s $ROCM_PATH/lib/llvm/amdgcn $RES/lib/amdgcn
```

Quick check:

```bash
echo 'int main() { return 0; }' > /tmp/t.cpp
$ROCM_PATH/lib/llvm/bin/amdclang++ -std=gnu++20 -fno-gpu-rdc -xhip \
  --rocm-path=$ROCM_PATH --offload-arch=gfx90a /tmp/t.cpp -o /tmp/t && echo OK
```

The Kokkos configure error `The compiler for CXX can not consume flag(s) -fno-gpu-rdc -xhip ...`
is the same problem in disguise: Kokkos' flag check compiles and links a test program and hides the
real error.

### 5. Building Kokkos 5.1.1 with HIP

```bash
cmake .. -G Ninja \
  -DCMAKE_CXX_COMPILER=$ROCM_PATH/lib/llvm/bin/amdclang++ \
  -DHIP_PLATFORM=amd \
  -DKokkos_ENABLE_HIP=ON \
  -DKokkos_ARCH_AMD_GFX90A=ON \
  -DCMAKE_INSTALL_PREFIX=/home/ge25zov2/modules_milan/modules_install/kokkos/5.1.1
```

- `Kokkos_ARCH_AMD_GFX90A` is the arch flag for the MI210.
- Kokkos is built with `amdclang++` 22 while the `rocm-llvm-cdna` preset uses upstream `clang++` 20.
  If the benchmark complains about the compiler, configure it with
  `-DCMAKE_CXX_COMPILER=amdclang++` as well.

### 6. OpenCL: `clGetPlatformIDs(-1001)` / `No OpenCL device found`

**Cause**

- The OpenCL loader on the node is the **system ocl-icd** (`/usr/lib64/libOpenCL.so.1`), and it is
  old: it **ignores `OCL_ICD_FILENAMES`** entirely.
- `/etc/OpenCL/vendors/` does not exist, so no ICD is registered at all.
- TheRock tarballs cannot install into `/etc` ([TheRock#3806](https://github.com/ROCm/TheRock/issues/3806)),
  but they do ship `lib/libamdocl64.so` (some nightlies don't:
  [TheRock#7667](https://github.com/ROCm/TheRock/issues/7667) — check with `tar -tzf ... | grep amdocl`).

**Fix**: a private vendors directory (ocl-icd needs a *directory* here, not a file)

```bash
mkdir -p $ROCM_PATH/etc/OpenCL/vendors
echo $ROCM_PATH/lib/libamdocl64.so > $ROCM_PATH/etc/OpenCL/vendors/amdocl64.icd
export OCL_ICD_VENDORS=$ROCM_PATH/etc/OpenCL/vendors   # in the module
clinfo -l
```

Debugging the loader: `OCL_ICD_DEBUG=15 clinfo -l` (ocl-icd; `OCL_ICD_ENABLE_TRACE` is the Khronos
loader and prints nothing here).

### 7. AdaptiveCpp on the MI210

**`generic` (JIT) target: segfault** — last known state, unresolved

The HIP backend finds all 8 GPUs and the first (small) kernel JIT-compiles and runs. The second, large
reduction kernel crashes with `Speicherzugriffsfehler` right after `LLVMToAmdgpu: Invoking hipRTC...`.
Suspected: AdaptiveCpp's LLVM 20 IR handed to ROCm 7.10's hipRTC (LLVM 22) in the same process.
Things to try: `ulimit -s unlimited`, a `gdb` backtrace, rebuilding AdaptiveCpp against ROCm's LLVM
(`-DLLVM_DIR=$ROCM_PATH/lib/llvm/lib/cmake/llvm`, if AdaptiveCpp accepts that version).

Useful runtime switches: `ACPP_VISIBILITY_MASK=hip` (skip the OpenCL backend),
`ACPP_DEBUG_LEVEL=3` (verbose JIT log).

**Workaround: ahead-of-time target**

```bash
cmake --preset rocm-llvm-cdna --fresh -DACPP_TARGETS="hip:gfx90a" -DHIP_PLATFORM=amd
cmake --build build-rocm-llvm-cdna --target polyhedral_acpp
```

Requires the `amdgcn` symlink from 4.(b). `acpp --acpp-version | grep -i rocm` shows the ROCm
path and flags acpp actually uses. Possible follow-up error: clang 20 reading ROCm 7.10 bitcode
built by LLVM 22 (`Unknown attribute kind`, `Invalid record`) — same LLVM version gap as above.

Note that AOT (`hip:gfx90a`) is a different compilation flow than `generic` — keep that in mind
when comparing AdaptiveCpp results across GPUs.

---

## SAP node (Intel GPU Max 1550)

See also [`sap/README.md`](sap/README.md) for the `icpx.cfg` / `libstdc++` RPATH fix.

### 1. Two Intel toolchains

- The GPU driver runtime on the node is from **2023**.
- **oneAPI 2026** (`compiler/2026.0.0`, `build-intel`, preset `intel`) is used for everything that can
  reach the GPU through the OpenCL interface (SYCL, AdaptiveCpp, stdpar, OpenCL, ...).
- **OpenMP offload needs the matching 2023 toolchain directly** (`compiler/2023.1.0`,
  `build-intel-beast`, preset `intel-beast`). This preset disables Stdpar and RAJA (not supported by
  oneAPI 2023.1), so e.g. `polyhedral_stdpar` does not exist there — run stdpar from the 2026 build.

### 2. `'CL/opencl.hpp' file not found` (only `polyhedral_ocl`)

The Intel compiler ships the OpenCL C headers (`CL/cl.h`) but not the Khronos C++ bindings, and the
benchmark only looks for `opencl.hpp` on macOS. It is a single header:

```bash
mkdir -p ~/modules_sap/modules_install/opencl-clhpp/include/CL
curl -L -o ~/modules_sap/modules_install/opencl-clhpp/include/CL/opencl.hpp \
  https://raw.githubusercontent.com/KhronosGroup/OpenCL-CLHPP/main/include/CL/opencl.hpp
export CPATH=$HOME/modules_sap/modules_install/opencl-clhpp/include:$CPATH
```

If the old driver only reports OpenCL < 3.0, add `-DCL_HPP_TARGET_OPENCL_VERSION=120` (or `200`).

### 3. `'filesystem' file not found` with the 2023 toolchain

**Symptom**

```
icpx ... --gcc-install-dir=/usr/lib64/gcc/x86_64-suse-linux/7 ...
fatal error: 'filesystem' file not found
```

**Cause**

The `intel-beast` preset's toolchain file (`intel-gcc-toolchain.cmake`) pins `icpx` to whatever
`gcc`/`g++` is first on `PATH` at configure time. With no GCC module loaded that is the SLES system
**GCC 7**, which has no `<filesystem>`. The node has no other GCC under `/usr`.

The newer GCC modules *do* exist on the shared file system, but their modulefile directory is **not
on the `MODULEPATH`** of the SAP nodes, so `module avail` does not list them.

**Fix**: add the modulefile directory to the module path, load a modern GCC, reconfigure from scratch

```bash
module use <path-to-the-gcc-modulefiles>      # make the existing modules visible
module load gcc/<version>
cmake --preset intel-beast --fresh             # --fresh: the GCC paths are baked in at configure time
```

Check the configure output for `intel-gcc-toolchain: pinned libstdc++ to ...` — it must not say `/7`.

Without touching `PATH`, the GCC can also be forced directly (the toolchain file only searches if the
variables are unset):

```bash
cmake --preset intel-beast --fresh -D_PPB_GCC=<gcc-prefix>/bin/gcc -D_PPB_GXX=<gcc-prefix>/bin/g++
```
