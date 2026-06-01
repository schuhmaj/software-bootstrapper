#!python3
"""Install the LLVM/Clang toolchain from source via a CMakePresets.json workflow.

This is the LLVM-specific counterpart to ``installer.py``. It builds LLVM with a
modern ``libstdc++`` (provided by a recent GCC) baked in, so that the resulting
``clang``/``clang++`` no longer pick up the outdated system standard library.
The approach mirrors the manual procedure documented in
``lrz-beast/How-to-llvm.md``:

* the GCC infrastructure paths (``--gcc-install-dir`` and the rpath to
  ``libstdc++``) are derived automatically and exported as environment variables
  that the CMake preset consumes via the ``$env{...}`` macro,
* after the build, a ``clang++.cfg`` (with ``clang.cfg`` symlinked to it) is
  generated next to the binaries so the toolchain is permanently pinned to the
  right ``libstdc++``,
* optional Lmod (``.lua``) or Tcl module files are emitted.
"""

import argparse
import contextlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from loguru import logger

SourceKind = Literal["default", "url", "archive", "directory"]

# Template files ship next to this script, so resolve them relative to the
# script's location rather than the current working directory. This lets the
# script be invoked from anywhere.
TEMPLATES_DIR: Path = Path(__file__).resolve().parent / "templates"

DEFAULT_LLVM_VERSION: str = "20.1.8"
DEFAULT_LLVM_TARGETS: str = "host"

# platform.machine() -> the LLVM backend name used in LLVM_TARGETS_TO_BUILD
LLVM_ARCH_MAP: dict[str, str] = {
    "x86_64": "X86",
    "aarch64": "AArch64",
}


def source_url(version: str) -> str:
    """Build the GitHub download URL for an LLVM release tarball.

    Args:
        version: LLVM release version, e.g. ``"20.1.8"``.

    Returns:
        The URL of the ``llvmorg-<version>`` source tarball on GitHub.
    """
    return f"https://github.com/llvm/llvm-project/archive/refs/tags/llvmorg-{version}.tar.gz"


def is_url(source: str) -> bool:
    """Check whether a ``--source`` string looks like an HTTP(S) URL.

    Args:
        source: The raw ``--source`` value to inspect.

    Returns:
        ``True`` if ``source`` starts with ``http://`` or ``https://``.
    """
    return source.startswith(("http://", "https://"))


def classify_source(source: str | None) -> SourceKind:
    """Determine what kind of ``--source`` was given.

    Args:
        source: The raw ``--source`` value, or ``None`` when the flag is unset.

    Returns:
        ``"default"`` (no source -> download the pinned version), ``"url"`` (a
        custom download URL), ``"archive"`` (a local ``.tar.gz``/``.zip`` file)
        or ``"directory"`` (an already-extracted llvm-project tree).

    Raises:
        FileNotFoundError: If ``source`` is given but is neither a URL nor an
            existing file or directory on disk.
    """
    if source is None:
        return "default"
    if is_url(source):
        return "url"
    path = Path(source).expanduser()
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "archive"
    raise FileNotFoundError(
        f"--source '{source}' is neither a URL, an existing archive file, nor an "
        "existing directory."
    )


def extract_archive(archive_path: Path, dest: Path) -> None:
    """Extract a ``.tar.*`` or ``.zip`` archive, detected by content.

    The archive format is determined from the file contents rather than its
    extension, so extension-less downloads are handled too.

    Args:
        archive_path: Path to the archive file to extract.
        dest: Directory into which the archive is extracted.

    Raises:
        RuntimeError: If ``archive_path`` is neither a tar nor a zip archive.
    """
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(dest)
    elif tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path) as tar:
            tar.extractall(dest)
    else:
        raise RuntimeError(
            f"'{archive_path}' is neither a supported tar nor a zip archive."
        )


@contextlib.contextmanager
def prepare_source(
    source: str | None, source_kind: SourceKind, version: str
) -> Iterator[Path]:
    """Yield the llvm-project root directory (the one containing the ``llvm/`` subdir).

    For a local ``"directory"`` the tree is used in place; otherwise the archive
    (downloaded or local) is extracted into a temporary directory that is cleaned
    up when the context manager exits.

    Args:
        source: The raw ``--source`` value (URL, archive path or directory path),
            or ``None`` for the default download.
        source_kind: The classification of ``source`` as returned by
            :func:`classify_source`.
        version: LLVM version, used to build the download URL for the
            ``"default"`` case.

    Yields:
        Path to the extracted (or in-place) llvm-project root directory.

    Raises:
        RuntimeError: If extracting the archive produces no directory.
    """
    if source_kind == "directory":
        project_root = Path(source).expanduser().resolve()
        logger.info(f"Using existing LLVM source directory {project_root}")
        yield project_root
        return

    with TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        if source_kind == "archive":
            archive_path = Path(source).expanduser().resolve()
            logger.info(f"Using local LLVM archive {archive_path}")
        else:
            url = source if source_kind == "url" else source_url(version)
            logger.info(f"Downloading LLVM from {url}")
            archive_path = tmp / "llvm-src"
            urllib.request.urlretrieve(url, archive_path)

        logger.info("Extracting LLVM source archive")
        extract_archive(archive_path, tmp)
        extracted_dirs = [d for d in tmp.iterdir() if d.is_dir()]
        if not extracted_dirs:
            raise RuntimeError("No directory found after extraction")
        yield extracted_dirs[0].resolve()


def host_target_triple() -> str:
    """Return the host's LLVM runtime-library target triple.

    This is the name of the architecture-specific directory found under
    ``<install>/lib`` (e.g. ``aarch64-unknown-linux-gnu`` or
    ``x86_64-unknown-linux-gnu``), derived from :func:`platform.machine`.

    Returns:
        The ``<arch>-unknown-linux-gnu`` triple for the current machine.
    """
    return f"{platform.machine()}-unknown-linux-gnu"


def validate_targets(targets: str) -> None:
    """Ensure the host backend is part of the requested LLVM targets.

    Without the host backend (either ``host`` or the concrete host
    architecture) the resulting ``clang`` cannot compile for the machine it runs
    on, which is almost never intended.

    Args:
        targets: Semicolon-separated ``LLVM_TARGETS_TO_BUILD`` value, e.g.
            ``"NVPTX;host"``.

    Raises:
        ValueError: If none of the requested targets is ``host``, the host
            architecture (``platform.machine()``), or its mapped LLVM backend.
    """
    requested = {t.strip() for t in targets.split(";") if t.strip()}
    machine = platform.machine()
    acceptable = {"host", machine, LLVM_ARCH_MAP.get(machine, "")}
    if not (requested & acceptable):
        raise ValueError(
            f"LLVM targets {sorted(requested)} do not include the host backend. "
            f"Add 'host' or the host architecture "
            f"('{machine}'/'{LLVM_ARCH_MAP.get(machine, '?')}') to --llvm-targets, "
            "otherwise clang cannot compile for this machine."
        )


def _print_file_name(compiler: str, file_name: str) -> Path:
    """Return ``dirname $(<compiler> -print-file-name=<file_name>)``.

    Args:
        compiler: The compiler binary to query (e.g. ``"gcc"`` or ``"g++"``).
        file_name: The file to locate, e.g. ``"crtbegin.o"`` or
            ``"libstdc++.so"``.

    Returns:
        The directory containing the located file.

    Raises:
        RuntimeError: If the compiler does not resolve the file to an absolute
            path (typically because no suitable GCC is on ``PATH``).
        subprocess.CalledProcessError: If invoking the compiler fails.
    """
    result = subprocess.run(
        [compiler, f"-print-file-name={file_name}"],
        check=True,
        capture_output=True,
        text=True,
    )
    located = Path(result.stdout.strip())
    if not located.is_absolute():
        raise RuntimeError(
            f"'{compiler} -print-file-name={file_name}' did not resolve to an "
            f"absolute path (got '{located}'). Is a suitable GCC loaded/on PATH?"
        )
    return located.parent


def resolve_gcc_paths(gcc: str, gxx: str) -> tuple[Path, Path]:
    """Derive the GCC install dir and libstdc++ dir used to build the runtimes.

    Honors pre-set ``GCC_INSTALL_DIR`` / ``GCC_LIB_DIR`` environment variables so
    a user can override the auto-detection.

    Args:
        gcc: The GCC binary used to locate ``crtbegin.o`` (the gcc install dir).
        gxx: The G++ binary used to locate ``libstdc++.so`` (its lib dir).

    Returns:
        A ``(gcc_install_dir, gcc_lib_dir)`` tuple of directories. The former
        feeds ``--gcc-install-dir``; the latter is used as the runtime rpath.
    """
    gcc_install_dir = (
        Path(os.environ["GCC_INSTALL_DIR"])
        if os.environ.get("GCC_INSTALL_DIR")
        else _print_file_name(gcc, "crtbegin.o")
    )
    gcc_lib_dir = (
        Path(os.environ["GCC_LIB_DIR"])
        if os.environ.get("GCC_LIB_DIR")
        else _print_file_name(gxx, "libstdc++.so")
    )
    logger.info(f"GCC_INSTALL_DIR = {gcc_install_dir}")
    logger.info(f"GCC_LIB_DIR     = {gcc_lib_dir}")
    return gcc_install_dir, gcc_lib_dir


def load_cmake_template(install_dir: Path, llvm_targets: str, build_dir: str) -> dict:
    """Load the CMake preset template and substitute the build parameters.

    Args:
        install_dir: Final LLVM install prefix (``@INSTALL_DIR@``).
        llvm_targets: ``LLVM_TARGETS_TO_BUILD`` value (``@LLVM_TARGETS@``).
        build_dir: The preset ``binaryDir`` (``@BUILD_DIR@``); either an absolute
            path or the literal ``${sourceDir}/build``.

    Returns:
        The parsed CMake preset configuration as a dictionary.
    """
    template_path = TEMPLATES_DIR / "llvm-CMakePresets.json"
    template = template_path.read_text()
    template = (
        template.replace("@INSTALL_DIR@", str(install_dir.resolve()))
        .replace("@LLVM_TARGETS@", llvm_targets)
        .replace("@BUILD_DIR@", build_dir)
    )
    return json.loads(template)


def write_clang_config(
    install_dir: Path, gcc_install_dir: Path, gcc_lib_dir: Path
) -> None:
    """Pin clang to the right libstdc++ via a ``clang.cfg`` config file.

    Writes ``<install_dir>/bin/clang++.cfg`` and symlinks ``clang.cfg`` to it,
    matching the post-install step from the manual how-to.

    Args:
        install_dir: LLVM install prefix; the config files are written under its
            ``bin/`` directory.
        gcc_install_dir: GCC install dir for the ``--gcc-install-dir`` flag.
        gcc_lib_dir: libstdc++ directory used for the ``-Wl,-rpath`` flag.
    """
    bin_dir = install_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    cfg_content = f"--gcc-install-dir={gcc_install_dir}\n-Wl,-rpath={gcc_lib_dir}\n"
    cxx_cfg = bin_dir / "clang++.cfg"
    cxx_cfg.write_text(cfg_content)

    clang_cfg = bin_dir / "clang.cfg"
    if clang_cfg.exists() or clang_cfg.is_symlink():
        clang_cfg.unlink()
    # Relative symlink so the install tree stays relocatable.
    clang_cfg.symlink_to(cxx_cfg.name)
    logger.info(f"Wrote {cxx_cfg} and symlinked {clang_cfg} -> {cxx_cfg.name}")


def install_llvm(
    install_dir: Path,
    version: str,
    llvm_targets: str,
    gcc: str,
    gxx: str,
    source: str | None = None,
    source_kind: SourceKind = "default",
    build_dir: Path | None = None,
    dry_run: bool = False,
) -> Path:
    """Download/locate, build and install the LLVM toolchain.

    Resolves the source tree (download, local archive or local directory),
    derives the GCC paths, writes the generated ``CMakePresets.json`` into the
    source tree, runs the ``cmake --workflow`` and finally pins clang to the
    right libstdc++ via :func:`write_clang_config`.

    Args:
        install_dir: Base install directory; LLVM lands in
            ``<install_dir>/llvm/<version>``.
        version: LLVM version to install.
        llvm_targets: ``LLVM_TARGETS_TO_BUILD`` value, e.g. ``"NVPTX;host"``.
        gcc: GCC binary used to derive ``GCC_INSTALL_DIR``.
        gxx: G++ binary used to derive ``GCC_LIB_DIR``.
        source: Optional ``--source`` override (URL, archive or directory).
        source_kind: Classification of ``source`` from :func:`classify_source`.
        build_dir: Optional persistent build directory injected into the preset;
            when ``None`` the preset builds under ``${sourceDir}/build``.
        dry_run: If ``True``, only report the target install path without
            downloading, building or installing anything.

    Returns:
        The resolved install directory (``<install_dir>/llvm/<version>``).
    """
    logger.info(f"Installing LLVM {version} (targets: {llvm_targets})")
    install_dir = (install_dir / "llvm" / version).resolve()

    if dry_run:
        logger.info(f"[dry-run] Would install LLVM {version} to {install_dir}")
        return install_dir

    gcc_install_dir, gcc_lib_dir = resolve_gcc_paths(gcc, gxx)

    # The CMake preset reads the GCC paths through the $env{...} macro.
    build_env = os.environ.copy()
    build_env["GCC_INSTALL_DIR"] = str(gcc_install_dir)
    build_env["GCC_LIB_DIR"] = str(gcc_lib_dir)

    # A persistent build dir is injected into the preset; otherwise the preset
    # builds in the (possibly temporary) source tree under ${sourceDir}/build.
    binary_dir = (
        str(build_dir.resolve()) if build_dir is not None else "${sourceDir}/build"
    )
    cmake_config = load_cmake_template(install_dir, llvm_targets, binary_dir)

    with prepare_source(source, source_kind, version) as project_root:
        # The actual CMake project lives in the llvm/ subdirectory.
        source_dir = project_root / "llvm"

        # Write CMake config
        logger.info(f"Writing CMake config for LLVM {version}")
        with open(source_dir / "CMakePresets.json", "w") as f:
            json.dump(cmake_config, f, indent=2)

        # Configure, build and install
        logger.info(f"Configuring, building and installing LLVM {version}")
        if build_dir is not None:
            build_dir.mkdir(parents=True, exist_ok=True)
        install_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["cmake", "--workflow", "--preset", "default"],
            cwd=source_dir,
            check=True,
            env=build_env,
        )

    # Post-install: pin clang to the right libstdc++.
    write_clang_config(install_dir, gcc_install_dir, gcc_lib_dir)

    logger.info(f"Installed LLVM {version} to {install_dir}")
    return install_dir


def install_module_file(
    install_dir: Path,
    module_dir: Path,
    version: str,
    language: Literal["lua", "tcl"] = "lua",
) -> None:
    """Render and write an Lmod or Tcl module file for the install.

    Args:
        install_dir: The LLVM install prefix the module should point at.
        module_dir: Root of the module tree; the file is written to
            ``<module_dir>/llvm/<version>[.lua]``.
        version: LLVM version, used in the module contents and file name.
        language: Module flavour to emit, either ``"lua"`` (Lmod) or ``"tcl"``.
    """
    template_path = TEMPLATES_DIR / f"llvm-module-template.{language}"
    template = template_path.read_text()

    module_content = (
        template.replace("@VERSION@", version)
        .replace("@INSTALL_DIR@", str(install_dir.absolute()))
        .replace("@TARGET_TRIPLE@", host_target_triple())
    )

    module_file = (
        module_dir / "llvm" / f"{version}{'.lua' if language == 'lua' else ''}"
    )
    module_file.parent.mkdir(parents=True, exist_ok=True)
    module_file.write_text(module_content)
    logger.info(f"Created module file at {module_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Install the LLVM toolchain (with a modern libstdc++) via a "
        "CMakePresets.json workflow."
    )
    parser.add_argument("install_dir", type=Path)
    parser.add_argument("module_dir", nargs="?", type=Path, default=None)
    parser.add_argument(
        "--llvm-version",
        type=str,
        default=DEFAULT_LLVM_VERSION,
        help=f"Version of LLVM to install (defaults to {DEFAULT_LLVM_VERSION})",
    )
    parser.add_argument(
        "--llvm-targets",
        type=str,
        default=DEFAULT_LLVM_TARGETS,
        help="Semicolon-separated LLVM_TARGETS_TO_BUILD, e.g. 'NVPTX;host'. Must "
        "include 'host' or the host architecture (defaults to 'host').",
    )
    parser.add_argument(
        "-s",
        "--source",
        type=str,
        default=None,
        help="Override where the LLVM source comes from. May be a download URL, a "
        "local '.tar.gz'/'.zip' archive, or an already-extracted llvm-project "
        "directory. Defaults to downloading the pinned --llvm-version from GitHub.",
    )
    parser.add_argument(
        "-b",
        "--build",
        type=Path,
        default=None,
        help="Persistent build directory to inject into the CMake preset (instead "
        "of a throwaway one). Only valid when --source is an already-extracted "
        "llvm-project directory.",
    )
    parser.add_argument(
        "--gcc",
        type=str,
        default="gcc",
        help="GCC binary used to derive GCC_INSTALL_DIR (defaults to 'gcc')",
    )
    parser.add_argument(
        "--gxx",
        type=str,
        default="g++",
        help="G++ binary used to derive GCC_LIB_DIR (defaults to 'g++')",
    )
    parser.add_argument(
        "-l",
        "--language",
        type=str,
        default="lua",
        choices=["lua", "tcl"],
        help="Language in which to generate the module file - either lua or tcl "
        "(defaults to lua)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Verbosity level (Enable Debug & Trace Logs). Can be stacked.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        default=False,
        help="Don't install anything. Only create module files.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False, help="Don't install anything"
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stdout, level=["INFO", "DEBUG", "TRACE"][min(args.verbose, 2)])

    validate_targets(args.llvm_targets)

    source_kind = classify_source(args.source)
    if args.build is not None and source_kind != "directory":
        raise ValueError(
            "--build/-b can only be used when --source points to an "
            "already-extracted llvm-project directory. A persistent build "
            "directory makes no sense for a throwaway source tree extracted from "
            f"an archive or download (got source kind '{source_kind}')."
        )

    install_dir = install_llvm(
        install_dir=args.install_dir,
        version=args.llvm_version,
        llvm_targets=args.llvm_targets,
        gcc=args.gcc,
        gxx=args.gxx,
        source=args.source,
        source_kind=source_kind,
        build_dir=args.build,
        dry_run=args.dry_run or args.skip_install,
    )

    if args.module_dir is not None:
        install_module_file(
            install_dir=install_dir,
            module_dir=args.module_dir,
            version=args.llvm_version,
            language=args.language,
        )
