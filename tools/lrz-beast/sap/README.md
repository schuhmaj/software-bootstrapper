# Intel oneAPI compiler (icx/icpx) on the SAP node (Sapphire Rapids + 4× Intel PVC)

The SAP node uses the **Intel oneAPI compiler module** (`icx`/`icpx`, here
`intel/compiler/2026.0`), not a self-built LLVM like the Grace-Hopper / Milan
nodes. `icx`/`icpx` are Intel's builds of Clang, so the same `libstdc++`
workaround applies — only the config-file *name* differs (`icpx.cfg` / `icx.cfg`
instead of `clang++.cfg` / `clang.cfg`).

## Symptom

A program compiled with `icpx` aborts at runtime with:

```
/usr/lib64/libstdc++.so.6: version `GLIBCXX_3.4.32' not found
```

The compiler picks up a modern `libstdc++` (from the `gcc/14` module) at
**compile time**, but at **runtime** the loader finds the outdated system
`libstdc++` first, because the gcc-14 `lib64` is not baked into the binary's
RPATH.

## Fix: per-driver config file next to the binary

`icx`/`icpx` auto-load a config file named after the invoked driver
(`icpx.cfg`, `icx.cfg`) from the directory containing the binary — exactly like
upstream `clang.cfg`. No `--config` flag is needed.

The config injects two options:

| Option | Purpose | Derived from |
| --- | --- | --- |
| `--gcc-install-dir=$GCC_INSTALL_DIR` | pin gcc-14's libstdc++ at compile time | `dirname $(gcc -print-file-name=crtbegin.o)` |
| `-Wl,-rpath=$GCC_LIB_DIR` | bake gcc-14's `lib64` into the binary RPATH (the actual runtime fix) | `realpath $(dirname $(g++ -print-file-name=libstdc++.so))` |

### Steps (run on the node, with `gcc/14` loaded)

```bash
# 1. Derive the paths
export GCC_INSTALL_DIR=$(dirname "$(gcc -print-file-name=crtbegin.o)")
export GCC_LIB_DIR=$(realpath "$(dirname "$(g++ -print-file-name=libstdc++.so)")")
echo "$GCC_INSTALL_DIR"   # .../gcc-14.2.0-.../lib/gcc/x86_64-pc-linux-gnu/14.2.0
echo "$GCC_LIB_DIR"       # .../gcc-14.2.0-.../lib64

# 2. Locate the Intel bin dir; check for an Intel-shipped default (do NOT clobber)
ICPX_BIN_DIR=$(dirname "$(command -v icpx)")
ls -l "$ICPX_BIN_DIR"/*.cfg 2>/dev/null

# 3. Append (last option wins, so appending is safe whether or not a default exists)
for drv in icpx icx; do
  printf -- '--gcc-install-dir=%s\n-Wl,-rpath=%s\n' \
    "$GCC_INSTALL_DIR" "$GCC_LIB_DIR" >> "$ICPX_BIN_DIR/$drv.cfg"
done
```

Both `icpx.cfg` and `icx.cfg` are written: the config name follows the invoked
driver — `icpx` for C++ sources, `icx` for C sources and CMake compiler probes.

### Verify

```bash
icpx -v -xc++ -c /dev/null -o /dev/null 2>&1 | grep -i 'configuration file'
echo 'int main(){}' | icpx -xc++ - -o /tmp/a.out && readelf -d /tmp/a.out | grep -i path
```

You should see the `icpx.cfg` path listed and an `RPATH`/`RUNPATH` pointing at
the gcc-14 `lib64`. After this, rebuilt executables run without setting
`LD_LIBRARY_PATH`.

## Alternatives

- **Env var instead of writing into `bin/`** — point `ICPXCFG` / `ICXCFG` at a
  config file elsewhere (Intel's analogue of clang's `--config`); good to set in
  the compiler module file so it travels with the module. Confirm the exact var
  names on the installed version with `icpx --help 2>&1 | grep -i cfg`; the
  bin-dir auto-load above is the more reliable of the two.
- **Quick, non-persistent check** — `export LD_LIBRARY_PATH="$GCC_LIB_DIR:$LD_LIBRARY_PATH"`
  before running. Fixes runtime only, nothing compile-time; use it to confirm the
  diagnosis before committing to the config file.

## Files in this folder

- `icpx.cfg`, `icx.cfg` — templates; regenerate on-system via step 3 so the
  literal Spack paths are correct for the currently loaded `gcc/14` module.

```

cmake .. -G Ninja \
  -DCMAKE_C_COMPILER=icx \
  -DCMAKE_CXX_COMPILER=icpx \
  -DCMAKE_C_FLAGS="--gcc-install-dir=${GCC_INSTALL_DIR} -Wl,-rpath=${GCC_LIB_DIR}" \
  -DCMAKE_CXX_FLAGS="--gcc-install-dir=${GCC_INSTALL_DIR} -Wl,-rpath=${GCC_LIB_DIR}"
```
