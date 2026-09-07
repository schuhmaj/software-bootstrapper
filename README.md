# Software Bootstrapper

A lightweight utility to **provision software** on a machine or cluster and to **integrate it into an
existing environment module system** (Lmod `.lua` or Tcl `.tcl` modulefiles).

[Spack](https://spack.io/) solves the same problem far more thoroughly, but it comes with its own
package tree, concretizer and bootstrap step. This repository was written in the context of the
[performance-portability-benchmark](https://github.com/schuhmaj/performance-portability-benchmark)
analysis, where a handful of libraries and toolchains (Kokkos, AdaptiveCpp, LLVM with offloading,
the Vulkan SDK, …) had to be brought up **quickly and reproducibly** on several unrelated HPC nodes
— usually without root, and sometimes with an ancient system `libstdc++` requiring hacky tricks making 
a fully managed solution such as spack unattractive.

## Overview

| Script | Installs                                                                                     | Source | Extra dependencies                            |
| --- |----------------------------------------------------------------------------------------------| --- |-----------------------------------------------|
| [`installer.py`](installer.py) | anything described by a spec in [`configs/`](configs) (Kokkos, Boost, googletest, spdlog, …) | source tarball, built via `cmake --workflow` | `pyyaml`, `loguru`, `cmake`, `ninja`          |
| [`installer_cmake.py`](installer_cmake.py) | CMake + Ninja                                                                                | official prebuilt binaries | none                                          |
| [`installer_llvm.py`](installer_llvm.py) | LLVM/Clang incl. OpenMP offloading                                                           | source tarball, built via `cmake --workflow` | `loguru`, `cmake`, `ninja`, some C/C++ compiler |
| [`installer_vulkan.py`](installer_vulkan.py) | Vulkan SDK (+ Slang)                                                                         | official LunarG SDK, or an [unofficial aarch64 build](https://github.com/jakoch/vulkan-sdk-arm) | none                            |

All four share the same shape:

```
<script> [options] <install-dir> [<module-dir>]
```

Software lands in `<install-dir>/<name>/<version>`, and if the optional `<module-dir>` is given, a
matching modulefile is written to `<module-dir>/<name>/<version>[.lua]`:

```bash
module use <module-dir>   # <-- add this to your .bashrc / .zshrc for future convenience
module load kokkos
```

> [!TIP]
> Every script documents its full set of options via `-h` / `--help`, e.g. `./installer_llvm.py --help`.
> The tables below only list the flags you will reach for most often.

## Setup

Requires **Python ≥ 3.10**. Pick either route:

```bash
# pip
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

```bash
# conda / mamba (also provides cmake and ninja)
conda env create -f environment.yaml
conda activate software-bootstrapper
```

If you only need `installer_cmake.py` or `installer_vulkan.py`, no setup is necessary at all — both
are pure standard library.

> [!IMPORTANT]
> `installer.py` and `installer_vulkan.py` resolve their `templates/` directory **relative to the
> current working directory**, so run them from the repository root. `installer_cmake.py` and
> `installer_llvm.py` can be invoked from anywhere.

---

## `installer.py` — build from a spec in `configs/`

Reads every `*.yaml` configuration in [`configs/`](configs), downloads the source tarball, generates a
`CMakePresets.json` from [`templates/CMakePresets.json`](templates/CMakePresets.json) and runs
`cmake --workflow --preset default`. The spec directory is resolved relative to the working
directory, so run the script from the repository root.

```bash
# Install only googletest and google-benchmark
./installer.py -i "googletest|google-benchmark" /opt/software /opt/modules

module use /opt/modules
module load googletest google-benchmark
```

```bash
# Install everything except AdaptiveCpp
./installer.py -e "AdaptiveCpp" /opt/software /opt/modules
```

### Arguments

| Argument | Required | Description |
| --- | --- | --- |
| `install_dir` | yes | packages are installed into `<install_dir>/<name>/<version>` |
| `module_dir` | no | modulefiles are written to `<module_dir>/<name>/<version>[.lua]`; omit to skip module generation |

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-i`, `--include REGEX` | — | only install specs whose `name` matches the regex |
| `-e`, `--exclude REGEX` | — | skip specs whose `name` matches the regex |
| `-l`, `--language {lua,tcl}` | `lua` | modulefile flavour: Lmod (`lua`) or Environment Modules (`tcl`) |
| `-v`, `--verbose` | `INFO` | stackable: `-v` → debug, `-vv` → trace |
| `--skip-install` | off | don't build anything, only (re)generate the modulefiles |
| `--dry-run` | off | only report what *would* be installed; writes nothing |

### Writing a configuration file

A small YAML file; everything under `cmake:` is injected verbatim as cache variables into
the generated preset. Have a look at [`configs/kokkos.yaml`](configs/kokkos.yaml) — it carries
commented-out CUDA / HIP / SYCL blocks to switch between backends.

```yaml
---
name: googletest
version: 1.17.0
source: https://github.com/google/googletest/archive/refs/tags/v1.17.0.tar.gz
description: |
  C++ Testing and Mocking Framework.
brief_description: C++ Testing and Mocking Framework.
category: testing
cmake:
  CMAKE_BUILD_TYPE: Release
  BUILD_SHARED_LIBS: ON
  CMAKE_POSITION_INDEPENDENT_CODE: ON
  CMAKE_INSTALL_RPATH_USE_LINK_PATH: ON
```

| Field | Purpose |
| --- | --- |
| `name`, `version` | determine the install path, the modulefile path and the module name |
| `source` | URL of the source tarball |
| `description`, `brief_description`, `category` | filled into the modulefile (`help`, `whatis`) |
| `cmake` | mapping of CMake cache variables applied to the preset |

---

## `installer_cmake.py` — prebuilt CMake and Ninja

Fetches the official binary releases (CMake from [cmake.org](https://cmake.org/download/), Ninja from
[GitHub](https://github.com/ninja-build/ninja/releases)) for the architecture of the running Linux
machine — x86_64 and aarch64. CMake downloads are verified against the published SHA-256 checksums.
Useful as the very first step on a node whose system CMake is too old for the other scripts.

```bash
# Latest stable CMake + Ninja, with Lmod modulefiles
./installer_cmake.py ~/opt ~/opt/modulefiles -v

# A pinned CMake version, no Ninja, Tcl modulefiles
./installer_cmake.py ~/opt ~/opt/modulefiles -l tcl --cmake-version 3.31.6 --skip-ninja
```

| Option | Default | Description |
| --- | --- | --- |
| `install_dir` | — | *(positional, required)* packages land in `<install_dir>/{cmake,ninja}/<version>` |
| `module_dir` | — | *(positional, optional)* target directory for the modulefiles |
| `--cmake-version VERSION` | latest stable | CMake version to install (a leading `v` is stripped) |
| `--ninja-version VERSION` | latest | Ninja version to install |
| `--skip-cmake` / `--skip-ninja` | off | install only the other one |
| `-l`, `--language {lua,tcl}` | `lua` | modulefile flavour |
| `-v`, `--verbose` | `WARNING` | stackable: `-v` → info, `-vv` → debug |
| `--force` | off | continue on a non-Linux system (the binaries are Linux-only) |

Without a `module_dir` the script prints the `export PATH=…` line you need instead.

---

## `installer_llvm.py` — LLVM/Clang with OpenMP offloading

Builds the LLVM toolchain from source through
[`templates/llvm-CMakePresets.json`](templates/llvm-CMakePresets.json). Beyond a plain build it
automates the `libstdc++` workaround documented in
[`tools/lrz-beast/How-to-llvm.md`](tools/lrz-beast/How-to-llvm.md):

* `GCC_INSTALL_DIR` and `GCC_LIB_DIR` are derived from the loaded `gcc`/`g++` (via
  `-print-file-name=`) and handed to the preset through `$env{…}`, so the freshly built runtimes use
  a modern standard library rather than the outdated system one;
* after the build a `bin/clang++.cfg` (with `clang.cfg` symlinked to it) is written, permanently
  pinning `clang` to that `libstdc++` — no `LD_LIBRARY_PATH` juggling for downstream users;
* the modulefile is emitted from [`templates/llvm-module-template.lua`](templates/llvm-module-template.lua).

```bash
# LLVM 20.1.8 with NVPTX offloading on a Grace-Hopper node
module load gcc/13
./installer_llvm.py --llvm-version 20.1.8 --llvm-targets "NVPTX;host" /opt/software /opt/modules

# AMD node: restrict the offload plugins (avoids the host plugin's libffi dependency)
./installer_llvm.py --llvm-targets "AMDGPU;host" --offload-plugins amdgpu /opt/software /opt/modules

# Reuse an already-extracted source tree together with a persistent build directory,
# so an interrupted build can be resumed instead of restarted
./installer_llvm.py -s ~/src/llvm-project -b ~/build/llvm /opt/software /opt/modules
```

| Option | Default | Description |
| --- | --- | --- |
| `install_dir` | — | *(positional, required)* LLVM lands in `<install_dir>/llvm/<version>` |
| `module_dir` | — | *(positional, optional)* target directory for the modulefile |
| `--llvm-version VERSION` | `20.1.8` | release to download from GitHub |
| `--llvm-targets TARGETS` | `host` | semicolon-separated `LLVM_TARGETS_TO_BUILD`, e.g. `NVPTX;host`. Must contain the host backend — this is validated up front |
| `--offload-plugins LIST` | auto-detect | restricts `LIBOMPTARGET_PLUGINS_TO_BUILD`, e.g. `amdgpu` |
| `-s`, `--source SOURCE` | GitHub release | a download URL, a local `.tar.gz`/`.zip`, or an already-extracted `llvm-project` directory |
| `-b`, `--build DIR` | throwaway | persistent build directory; **only valid together with `--source <directory>`** |
| `--gcc BIN` / `--gxx BIN` | `gcc` / `g++` | compilers used to derive the GCC paths (override by pre-setting `GCC_INSTALL_DIR` / `GCC_LIB_DIR`) |
| `-l`, `--language {lua,tcl}` | `lua` | modulefile flavour |
| `-v`, `--verbose` | `INFO` | stackable: `-v` → debug, `-vv` → trace |
| `--dry-run`, `--skip-install` | off | report the target install path without building; the modulefile is still written |

> [!WARNING]
> A full LLVM build can take a long time. A persistent build directory is recommended.

---

## `installer_vulkan.py` — Vulkan SDK

Installs a prebuilt Vulkan SDK:

* **Linux x86_64** → the official [LunarG SDK](https://sdk.lunarg.com/);
* **Linux aarch64 (Ubuntu)** → an unofficial but public CI build from
  [jakoch/vulkan-sdk-arm](https://github.com/jakoch/vulkan-sdk-arm). Since that build does not ship
  the [Slang](https://github.com/shader-slang/slang) compiler, the matching Slang release is
  downloaded and merged into the SDK prefix automatically.

Any other platform is rejected — build the SDK from source (e.g. in a container) instead.

```bash
./installer_vulkan.py /opt/software /opt/modules

module use /opt/modules
module load VulkanSDK
```

```bash
# Air-gapped node: install from a manually transferred archive
./installer_vulkan.py -s ~/vulkansdk-linux-x86_64-1.4.350.1.tar.xz \
    --vulkan-sdk-version 1.4.350.1 /opt/software /opt/modules
```

| Option | Default | Description |
| --- | --- | --- |
| `install_dir` | — | *(positional, required)* the SDK lands in `<install_dir>/VulkanSDK/<version>/<arch>` |
| `module_dir` | — | *(positional, optional)* target directory for the modulefile |
| `--vulkan-sdk-version VERSION` | `1.4.350.1` | SDK version to install |
| `-s`, `--source ARCHIVE` | download | install from a local `.tar.xz` instead; must match `--vulkan-sdk-version` |
| `-l`, `--language {lua,tcl}` | `lua` | modulefile flavour |
| `--skip-install` | off | don't unpack anything, only (re)generate the modulefile |

---

## Repository layout

| Path | Contents |
| --- | --- |
| [`configs/`](configs) | YAML specs consumed by `installer.py` |
| [`templates/`](templates) | `CMakePresets.json` and modulefile templates with `@PLACEHOLDER@` markers |
| [`tools/lrz-beast/`](tools/lrz-beast) | node-specific notes and configs for the LRZ BEAST cluster (Grace-Hopper, Milan, Sapphire Rapids + PVC), including the [`libstdc++`/`icpx` how-tos](tools/lrz-beast/sap/README.md) |
| [`tools/examples/`](tools/examples) | example modulefiles and `CMakePresets.json` for reference |
| [`tools/hpctoolkit/`](tools/hpctoolkit) | [how-to for installing HPCToolkit (+cuda +opencl) via Spack](tools/hpctoolkit/How-to-hpctoolkit.md), plus a Spack package repo overlay carrying the GCC 15 `<cstdint>` patch for `dyninst@13.0.0` |

## Related

[performance-portability-benchmark](https://github.com/schuhmaj/performance-portability-benchmark) — the analysis this bootstrapper was built for
