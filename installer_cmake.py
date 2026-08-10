#!/usr/bin/env python3
"""Download and install prebuilt CMake and Ninja binaries on Linux.

The script fetches the official upstream binary distributions

* CMake from https://cmake.org/download/ (files served from https://cmake.org/files/)
* Ninja from https://github.com/ninja-build/ninja/releases

for the architecture of the running machine, unpacks them into a versioned
directory layout below the installation directory and -- optionally -- writes
module files in either Lua (Lmod, default) or Tcl (Environment Modules) format.

Resulting layout::

    <install_dir>/cmake/<cmake_version>/bin/cmake
    <install_dir>/ninja/<ninja_version>/bin/ninja
    <module_dir>/cmake/<cmake_version>[.lua]
    <module_dir>/ninja/<ninja_version>[.lua]

Only the Python standard library is used (Python >= 3.10).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Final, Iterable, Sequence

__version__: Final[str] = "1.0.0"

LOGGER: Final[logging.Logger] = logging.getLogger("installer_cmake")

CMAKE_DOWNLOAD_PAGE: Final[str] = "https://cmake.org/download/"
CMAKE_FILES_BASE: Final[str] = "https://cmake.org/files"
NINJA_LATEST_URL: Final[str] = "https://github.com/ninja-build/ninja/releases/latest"
NINJA_DOWNLOAD_BASE: Final[str] = "https://github.com/ninja-build/ninja/releases/download"

#: cmake.org rejects requests carrying the default ``Python-urllib`` agent with
#: HTTP 403, hence the browser compatible prefix.
USER_AGENT: Final[str] = f"Mozilla/5.0 (X11; Linux x86_64) installer_cmake.py/{__version__}"
DOWNLOAD_CHUNK_SIZE: Final[int] = 1 << 16
NETWORK_TIMEOUT: Final[int] = 60

#: Mapping of ``platform.machine()`` values onto the architecture names used by
#: the CMake release artefacts.
CMAKE_ARCH_MAP: Final[dict[str, str]] = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
}

#: Mapping of ``platform.machine()`` values onto the Ninja release asset names.
NINJA_ASSET_MAP: Final[dict[str, str]] = {
    "x86_64": "ninja-linux.zip",
    "amd64": "ninja-linux.zip",
    "aarch64": "ninja-linux-aarch64.zip",
    "arm64": "ninja-linux-aarch64.zip",
}


class InstallerError(RuntimeError):
    """Raised for every unrecoverable, user facing error of this script."""


# --------------------------------------------------------------------------- #
# Generic helpers
# --------------------------------------------------------------------------- #
def configure_logging(verbosity: int) -> None:
    """Configure the root logger according to the requested verbosity.

    Args:
        verbosity: Number of ``-v`` flags given on the command line. ``0`` maps
            to ``WARNING``, ``1`` to ``INFO`` and ``2`` or more to ``DEBUG``.

    Returns:
        None.
    """
    level = {0: logging.WARNING, 1: logging.INFO}.get(verbosity, logging.DEBUG)
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s %(message)s",
        stream=sys.stderr,
    )
    LOGGER.debug("Log level set to %s", logging.getLevelName(level))


def http_get(url: str) -> bytes:
    """Fetch a URL and return the raw response body.

    Args:
        url: Absolute HTTP(S) URL to fetch.

    Returns:
        The response body as :class:`bytes`.

    Raises:
        InstallerError: If the request fails or the server answers with an error.
    """
    LOGGER.debug("GET %s", url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            return response.read()
    except (urllib.error.URLError, OSError) as exc:  # pragma: no cover - network
        raise InstallerError(f"Failed to fetch {url}: {exc}") from exc


def http_get_text(url: str) -> str:
    """Fetch a URL and decode the response body as UTF-8 text.

    Args:
        url: Absolute HTTP(S) URL to fetch.

    Returns:
        The decoded response body.

    Raises:
        InstallerError: If the request fails.
    """
    return http_get(url).decode("utf-8", errors="replace")


def resolve_redirect(url: str) -> str:
    """Resolve an HTTP redirect and return the final URL.

    Args:
        url: URL that is expected to redirect (e.g. a GitHub ``/latest`` link).

    Returns:
        The URL after all redirects have been followed.

    Raises:
        InstallerError: If the request fails.
    """
    LOGGER.debug("HEAD (redirect resolution) %s", url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            return response.geturl()
    except (urllib.error.URLError, OSError) as exc:  # pragma: no cover - network
        raise InstallerError(f"Failed to resolve {url}: {exc}") from exc


def download_file(url: str, destination: Path) -> Path:
    """Download a URL into a local file.

    Args:
        url: Absolute HTTP(S) URL of the file to download.
        destination: Path the downloaded payload is written to. Parent
            directories are created if necessary.

    Returns:
        The path of the downloaded file, i.e. ``destination``.

    Raises:
        InstallerError: If the download fails.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Downloading %s", url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT) as response:
            total = int(response.headers.get("Content-Length", 0))
            written = 0
            with destination.open("wb") as sink:
                while chunk := response.read(DOWNLOAD_CHUNK_SIZE):
                    sink.write(chunk)
                    written += len(chunk)
            LOGGER.debug(
                "Wrote %d bytes to %s (Content-Length: %d)", written, destination, total
            )
            if total and written != total:
                raise InstallerError(
                    f"Truncated download of {url}: got {written} of {total} bytes"
                )
    except (urllib.error.URLError, OSError) as exc:  # pragma: no cover - network
        raise InstallerError(f"Failed to download {url}: {exc}") from exc
    return destination


def sha256_of_file(path: Path) -> str:
    """Compute the SHA-256 checksum of a file.

    Args:
        path: File to hash.

    Returns:
        The lower case hexadecimal digest.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(DOWNLOAD_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(path: Path, expected: str) -> None:
    """Verify that a file matches an expected SHA-256 checksum.

    Args:
        path: File to verify.
        expected: Expected lower case hexadecimal SHA-256 digest.

    Returns:
        None.

    Raises:
        InstallerError: If the actual checksum differs from ``expected``.
    """
    actual = sha256_of_file(path)
    if actual != expected.lower():
        raise InstallerError(
            f"Checksum mismatch for {path.name}: expected {expected}, got {actual}"
        )
    LOGGER.info("Verified SHA-256 checksum of %s", path.name)


def parse_version(version: str) -> tuple[int, ...]:
    """Convert a dotted version string into a comparable tuple.

    Args:
        version: Version string such as ``"3.31.6"``.

    Returns:
        A tuple of integers, e.g. ``(3, 31, 6)``. Non numeric components are
        ignored.
    """
    return tuple(int(part) for part in re.findall(r"\d+", version))


def normalize_version(version: str) -> str:
    """Strip a leading ``v`` from a user supplied version string.

    Args:
        version: Version as given on the command line, e.g. ``"v1.12.1"``.

    Returns:
        The version without the leading ``v``, e.g. ``"1.12.1"``.
    """
    return version[1:] if version.startswith(("v", "V")) else version


def replace_directory(source: Path, target: Path) -> None:
    """Move a directory to its final location, replacing an existing one.

    Args:
        source: Directory to move (typically inside a temporary staging area).
        target: Final destination directory.

    Returns:
        None.
    """
    if target.exists():
        LOGGER.warning("Replacing existing installation at %s", target)
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    LOGGER.debug("Installed into %s", target)


def extract_tarball(archive: Path, target_dir: Path) -> Path:
    """Extract a gzip compressed tarball with a single top level directory.

    Args:
        archive: Path of the ``.tar.gz`` file.
        target_dir: Directory the archive is extracted into.

    Returns:
        The path of the extracted top level directory.

    Raises:
        InstallerError: If the archive does not contain exactly one top level
            directory.
    """
    LOGGER.debug("Extracting %s into %s", archive, target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, mode="r:gz") as tar:
        # ``filter="data"`` is available from Python 3.11.4 / 3.12 onwards and
        # protects against path traversal; older interpreters fall back to the
        # unfiltered extraction.
        try:
            tar.extractall(path=target_dir, filter="data")
        except TypeError:  # pragma: no cover - Python < 3.11.4
            LOGGER.debug("tarfile extraction filters unavailable, extracting unfiltered")
            tar.extractall(path=target_dir)
    entries = [entry for entry in target_dir.iterdir() if entry.is_dir()]
    if len(entries) != 1:
        raise InstallerError(
            f"Unexpected archive layout in {archive.name}: "
            f"expected one top level directory, found {len(entries)}"
        )
    return entries[0]


def detect_architecture() -> str:
    """Determine the machine architecture of the running system.

    Returns:
        The normalized ``platform.machine()`` value in lower case.
    """
    machine = platform.machine().lower()
    LOGGER.debug("Detected machine architecture %r", machine)
    return machine


def ensure_linux(force: bool) -> None:
    """Abort unless the script runs on Linux.

    Args:
        force: If ``True``, only warn instead of aborting on a non-Linux system.

    Returns:
        None.

    Raises:
        InstallerError: If the current platform is not Linux and ``force`` is
            ``False``.
    """
    system = platform.system()
    if system == "Linux":
        return
    message = f"This installer provides Linux binaries, but the system is {system!r}"
    if force:
        LOGGER.warning("%s -- continuing because --force was given", message)
        return
    raise InstallerError(f"{message}. Use --force to override.")


# --------------------------------------------------------------------------- #
# CMake
# --------------------------------------------------------------------------- #
def latest_cmake_version() -> str:
    """Determine the most recent stable CMake release.

    The official download page is parsed for the per release JSON manifests
    (``cmake-<version>-files-v1.json``); release candidates carry an ``-rcN``
    suffix and are therefore not matched.

    Returns:
        The highest stable version found, e.g. ``"3.31.6"``.

    Raises:
        InstallerError: If no version could be extracted from the page.
    """
    page = http_get_text(CMAKE_DOWNLOAD_PAGE)
    versions = set(re.findall(r"cmake-(\d+\.\d+\.\d+)-files-v1\.json", page))
    if not versions:
        raise InstallerError(
            f"Could not determine the latest CMake version from {CMAKE_DOWNLOAD_PAGE}"
        )
    latest = max(versions, key=parse_version)
    LOGGER.info("Latest stable CMake release: %s", latest)
    LOGGER.debug("CMake versions advertised on the download page: %s", sorted(versions))
    return latest


def cmake_release_directory(version: str) -> str:
    """Build the URL of the release directory of a CMake version.

    Args:
        version: CMake version, e.g. ``"3.31.6"``.

    Returns:
        The URL of the directory holding the release artefacts.
    """
    major_minor = ".".join(version.split(".")[:2])
    return f"{CMAKE_FILES_BASE}/v{major_minor}"


def cmake_archive_name(version: str, machine: str) -> str:
    """Select the CMake binary archive matching a version and architecture.

    The per release JSON manifest is consulted first; if it is unavailable the
    canonical name ``cmake-<version>-linux-<arch>.tar.gz`` is constructed.

    Args:
        version: CMake version, e.g. ``"3.31.6"``.
        machine: Machine architecture as reported by :func:`detect_architecture`.

    Returns:
        The file name of the Linux binary archive.

    Raises:
        InstallerError: If the architecture is unsupported or the release
            provides no matching Linux archive.
    """
    arch = CMAKE_ARCH_MAP.get(machine)
    if arch is None:
        raise InstallerError(
            f"Unsupported architecture {machine!r} for CMake; "
            f"supported: {', '.join(sorted(set(CMAKE_ARCH_MAP)))}"
        )

    manifest_url = f"{cmake_release_directory(version)}/cmake-{version}-files-v1.json"
    try:
        manifest = json.loads(http_get_text(manifest_url))
    except (InstallerError, json.JSONDecodeError) as exc:
        fallback = f"cmake-{version}-linux-{arch}.tar.gz"
        LOGGER.warning(
            "Could not read the release manifest (%s); assuming %s", exc, fallback
        )
        return fallback

    for entry in manifest.get("files", []):
        operating_systems = [item.lower() for item in entry.get("os", [])]
        architectures = [item.lower() for item in entry.get("architecture", [])]
        if (
            entry.get("class") == "archive"
            and "linux" in operating_systems
            and arch in architectures
        ):
            LOGGER.debug("Selected CMake artefact %s", entry["name"])
            return str(entry["name"])

    raise InstallerError(
        f"CMake {version} provides no Linux {arch} archive (checked {manifest_url})"
    )


def cmake_expected_checksum(version: str, archive_name: str) -> str | None:
    """Look up the published SHA-256 checksum of a CMake artefact.

    Args:
        version: CMake version, e.g. ``"3.31.6"``.
        archive_name: File name of the artefact to look up.

    Returns:
        The hexadecimal digest, or ``None`` if the checksum file is unavailable
        or does not list the artefact.
    """
    url = f"{cmake_release_directory(version)}/cmake-{version}-SHA-256.txt"
    try:
        listing = http_get_text(url)
    except InstallerError as exc:
        LOGGER.warning("Checksum file unavailable (%s); skipping verification", exc)
        return None

    for line in listing.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == archive_name:
            return parts[0]
    LOGGER.warning("%s is not listed in %s; skipping verification", archive_name, url)
    return None


def install_cmake(version: str, install_dir: Path, machine: str, workdir: Path) -> Path:
    """Download, verify and install a CMake binary release.

    Args:
        version: CMake version to install, e.g. ``"3.31.6"``.
        install_dir: Root installation directory; CMake ends up in
            ``<install_dir>/cmake/<version>``.
        machine: Machine architecture as reported by :func:`detect_architecture`.
        workdir: Scratch directory used for the download and extraction.

    Returns:
        The prefix of the installed CMake, i.e. ``<install_dir>/cmake/<version>``.

    Raises:
        InstallerError: If the download, verification or extraction fails.
    """
    archive_name = cmake_archive_name(version, machine)
    url = f"{cmake_release_directory(version)}/{archive_name}"

    archive = download_file(url, workdir / archive_name)
    checksum = cmake_expected_checksum(version, archive_name)
    if checksum is not None:
        verify_checksum(archive, checksum)

    extracted = extract_tarball(archive, workdir / "cmake-extract")
    prefix = install_dir / "cmake" / version
    replace_directory(extracted, prefix)

    executable = prefix / "bin" / "cmake"
    if not executable.is_file():
        raise InstallerError(f"Installation looks broken: {executable} is missing")
    LOGGER.info("Installed CMake %s to %s", version, prefix)
    return prefix


# --------------------------------------------------------------------------- #
# Ninja
# --------------------------------------------------------------------------- #
def latest_ninja_version() -> str:
    """Determine the most recent Ninja release.

    The GitHub ``releases/latest`` URL redirects to the tag of the newest
    release, which avoids the rate limited GitHub API.

    Returns:
        The latest version without the leading ``v``, e.g. ``"1.12.1"``.

    Raises:
        InstallerError: If the redirect target contains no recognizable tag.
    """
    final_url = resolve_redirect(NINJA_LATEST_URL)
    match = re.search(r"/tag/v?([0-9][0-9A-Za-z.\-]*)$", final_url)
    if match is None:
        raise InstallerError(
            f"Could not determine the latest Ninja version from {final_url}"
        )
    latest = match.group(1)
    LOGGER.info("Latest Ninja release: %s", latest)
    return latest


def ninja_asset_name(machine: str) -> str:
    """Select the Ninja release asset matching an architecture.

    Args:
        machine: Machine architecture as reported by :func:`detect_architecture`.

    Returns:
        The asset file name, e.g. ``"ninja-linux.zip"``.

    Raises:
        InstallerError: If the architecture is unsupported.
    """
    asset = NINJA_ASSET_MAP.get(machine)
    if asset is None:
        raise InstallerError(
            f"Unsupported architecture {machine!r} for Ninja; "
            f"supported: {', '.join(sorted(set(NINJA_ASSET_MAP)))}"
        )
    LOGGER.debug("Selected Ninja artefact %s", asset)
    return asset


def install_ninja(version: str, install_dir: Path, machine: str, workdir: Path) -> Path:
    """Download and install a Ninja binary release.

    Args:
        version: Ninja version to install, e.g. ``"1.12.1"``.
        install_dir: Root installation directory; Ninja ends up in
            ``<install_dir>/ninja/<version>/bin``.
        machine: Machine architecture as reported by :func:`detect_architecture`.
        workdir: Scratch directory used for the download and extraction.

    Returns:
        The prefix of the installed Ninja, i.e. ``<install_dir>/ninja/<version>``.

    Raises:
        InstallerError: If the download or extraction fails.
    """
    asset = ninja_asset_name(machine)
    url = f"{NINJA_DOWNLOAD_BASE}/v{version}/{asset}"

    archive = download_file(url, workdir / asset)
    staging = workdir / "ninja-extract" / "bin"
    staging.mkdir(parents=True, exist_ok=True)
    LOGGER.debug("Extracting %s into %s", archive, staging)
    try:
        with zipfile.ZipFile(archive) as zip_file:
            zip_file.extractall(path=staging)
    except (zipfile.BadZipFile, OSError) as exc:
        raise InstallerError(f"Failed to extract {archive.name}: {exc}") from exc

    binary = staging / "ninja"
    if not binary.is_file():
        raise InstallerError(f"{asset} did not contain a 'ninja' executable")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    prefix = install_dir / "ninja" / version
    replace_directory(staging.parent, prefix)
    LOGGER.info("Installed Ninja %s to %s", version, prefix)
    return prefix


# --------------------------------------------------------------------------- #
# Module files
# --------------------------------------------------------------------------- #
def module_path_entries(prefix: Path) -> list[tuple[str, str]]:
    """Collect the environment modifications a module file has to perform.

    Only directories that actually exist below ``prefix`` are reported, so the
    generated module files never point at missing paths.

    Args:
        prefix: Installation prefix of the package.

    Returns:
        A list of ``(variable, relative_subdirectory)`` tuples, e.g.
        ``[("PATH", "bin"), ("MANPATH", "man")]``.
    """
    candidates = (
        ("PATH", "bin"),
        ("MANPATH", "man"),
        ("MANPATH", "share/man"),
        ("ACLOCAL_PATH", "share/aclocal"),
    )
    entries = [(var, sub) for var, sub in candidates if (prefix / sub).is_dir()]
    LOGGER.debug("Module environment entries for %s: %s", prefix, entries)
    return entries


def render_tcl_modulefile(name: str, version: str, prefix: Path, summary: str) -> str:
    """Render a Tcl module file for an installed package.

    The generated file uses the classic ``#%Module1.0`` syntax understood by
    both Environment Modules and Lmod.

    Args:
        name: Module name, e.g. ``"cmake"``.
        version: Module version, e.g. ``"3.31.6"``.
        prefix: Installation prefix the module points at.
        summary: One line description used for ``module-whatis``.

    Returns:
        The complete content of the module file.
    """
    lines: list[str] = [
        "#%Module1.0",
        "#",
        f"# {name} {version} -- generated by installer_cmake.py",
        "#",
        "proc ModulesHelp { } {",
        f'    puts stderr "{summary}"',
        f'    puts stderr "Installation prefix: {prefix}"',
        "}",
        "",
        f'module-whatis "{summary}"',
        "",
        f'set root "{prefix}"',
        "",
    ]
    lines += [
        f"prepend-path {variable} $root/{subdir}"
        for variable, subdir in module_path_entries(prefix)
    ]
    lines.append("")
    return "\n".join(lines)


def render_lua_modulefile(name: str, version: str, prefix: Path, summary: str) -> str:
    """Render a Lua (Lmod) module file for an installed package.

    Args:
        name: Module name, e.g. ``"cmake"``.
        version: Module version, e.g. ``"3.31.6"``.
        prefix: Installation prefix the module points at.
        summary: One line description used for ``whatis``.

    Returns:
        The complete content of the module file.
    """
    lines: list[str] = [
        "-- -*- lua -*-",
        f"-- {name} {version} -- generated by installer_cmake.py",
        "",
        "help([[",
        f"{summary}",
        f"Installation prefix: {prefix}",
        "]])",
        "",
        f'whatis("Name: {name}")',
        f'whatis("Version: {version}")',
        f'whatis("Description: {summary}")',
        "",
        f'local root = "{prefix}"',
        "",
    ]
    lines += [
        f'prepend_path("{variable}", pathJoin(root, "{subdir}"))'
        for variable, subdir in module_path_entries(prefix)
    ]
    lines.append("")
    return "\n".join(lines)


def write_modulefile(
    module_dir: Path,
    name: str,
    version: str,
    prefix: Path,
    summary: str,
    language: str = "lua",
) -> Path:
    """Write a module file for an installed package.

    Args:
        module_dir: Root of the module tree; the file is written to
            ``<module_dir>/<name>/<version>`` for Tcl and to
            ``<module_dir>/<name>/<version>.lua`` for Lua.
        name: Module name, e.g. ``"cmake"``.
        version: Module version, e.g. ``"3.31.6"``.
        prefix: Installation prefix the module points at.
        summary: One line description used for ``module-whatis`` / ``whatis``.
        language: Module file format, either ``"lua"`` or ``"tcl"``.

    Returns:
        The path of the written module file.

    Raises:
        InstallerError: If the language is unknown or the file cannot be written.
    """
    if language == "lua":
        content = render_lua_modulefile(name, version, prefix, summary)
        path = module_dir / name / f"{version}.lua"
    elif language == "tcl":
        content = render_tcl_modulefile(name, version, prefix, summary)
        path = module_dir / name / version
    else:  # pragma: no cover - guarded by argparse choices
        raise InstallerError(f"Unknown module file format {language!r}")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise InstallerError(f"Failed to write module file {path}: {exc}") from exc
    LOGGER.info("Wrote %s module file %s", language, path)
    return path


# --------------------------------------------------------------------------- #
# Command line interface
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    """Construct the command line argument parser.

    Returns:
        The configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="installer_cmake.py",
        description=(
            "Download the latest (or a specific) CMake and Ninja release for this "
            "Linux machine and install them into a versioned directory layout."
        ),
        epilog=(
            "Example: installer_cmake.py ~/opt ~/opt/modulefiles -vv -l tcl "
            "--cmake-version 3.31.6"
        ),
    )
    parser.add_argument(
        "install_dir",
        type=Path,
        help="installation directory; packages are placed in <install_dir>/<name>/<version>",
    )
    parser.add_argument(
        "module_dir",
        type=Path,
        nargs="?",
        default=None,
        help=(
            "optional directory for module files; a module file is written to "
            "<module_dir>/<name>/<version>[.lua] (see --language)"
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase verbosity; repeat for more output (-v: info, -vv: debug)",
    )
    parser.add_argument(
        "-l",
        "--language",
        choices=("lua", "tcl"),
        default="lua",
        help=(
            "format of the generated module files: 'lua' for Lmod (default) or "
            "'tcl' for Environment Modules"
        ),
    )
    parser.add_argument(
        "--cmake-version",
        default=None,
        metavar="VERSION",
        help="CMake version to install (default: latest stable release)",
    )
    parser.add_argument(
        "--ninja-version",
        default=None,
        metavar="VERSION",
        help="Ninja version to install (default: latest release)",
    )
    parser.add_argument(
        "--skip-cmake",
        action="store_true",
        help="do not install CMake",
    )
    parser.add_argument(
        "--skip-ninja",
        action="store_true",
        help="do not install Ninja",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="continue even if the system is not Linux",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def install_all(arguments: argparse.Namespace) -> list[tuple[str, str, Path]]:
    """Perform the requested installations.

    Args:
        arguments: Parsed command line arguments.

    Returns:
        A list of ``(name, version, prefix)`` tuples describing what was
        installed.

    Raises:
        InstallerError: If any installation step fails.
    """
    machine = detect_architecture()
    install_dir = arguments.install_dir.expanduser().resolve()
    install_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Installing into %s", install_dir)

    installed: list[tuple[str, str, Path]] = []
    with tempfile.TemporaryDirectory(prefix="installer_cmake-") as tmp:
        workdir = Path(tmp)
        LOGGER.debug("Using scratch directory %s", workdir)

        if not arguments.skip_cmake:
            version = (
                normalize_version(arguments.cmake_version)
                if arguments.cmake_version
                else latest_cmake_version()
            )
            installed.append(
                ("cmake", version, install_cmake(version, install_dir, machine, workdir))
            )

        if not arguments.skip_ninja:
            version = (
                normalize_version(arguments.ninja_version)
                if arguments.ninja_version
                else latest_ninja_version()
            )
            installed.append(
                ("ninja", version, install_ninja(version, install_dir, machine, workdir))
            )

    if arguments.module_dir is not None:
        module_dir = arguments.module_dir.expanduser().resolve()
        summaries = {
            "cmake": "CMake -- cross platform build system generator",
            "ninja": "Ninja -- small and fast build system",
        }
        for name, version, prefix in installed:
            write_modulefile(
                module_dir, name, version, prefix, summaries[name], arguments.language
            )

    return installed


def report(installed: Sequence[tuple[str, str, Path]], module_dir: Path | None) -> None:
    """Print a short human readable summary of the installation.

    Args:
        installed: Result of :func:`install_all`.
        module_dir: Module directory if module files were written, else ``None``.

    Returns:
        None.
    """
    if not installed:
        print("Nothing was installed.")
        return

    print("Installed:")
    for name, version, prefix in installed:
        print(f"  {name:<6} {version:<12} {prefix}")

    if module_dir is not None:
        modules: Iterable[str] = (f"{name}/{version}" for name, version, _ in installed)
        print(f"\nModule files below {module_dir.expanduser().resolve()}")
        print(f"  module use {module_dir.expanduser().resolve()}")
        print(f"  module load {' '.join(modules)}")
    else:
        paths = os.pathsep.join(str(prefix / "bin") for _, _, prefix in installed)
        print("\nAdd the binaries to your PATH, e.g.:")
        print(f'  export PATH="{paths}{os.pathsep}$PATH"')


def main(argv: Sequence[str] | None = None) -> int:
    """Run the installer.

    Args:
        argv: Command line arguments without the program name. Defaults to
            :data:`sys.argv` when ``None``.

    Returns:
        ``0`` on success and ``1`` on a handled error.
    """
    arguments = build_parser().parse_args(argv)
    configure_logging(arguments.verbose)

    try:
        ensure_linux(arguments.force)
        installed = install_all(arguments)
    except InstallerError as exc:
        LOGGER.error("%s", exc)
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive
        LOGGER.error("Aborted by user")
        return 1

    report(installed, arguments.module_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
