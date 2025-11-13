#!python3
import subprocess
import yaml
import sys
import re
from tempfile import TemporaryDirectory
import json
import argparse
from pathlib import Path
import urllib.request
import tarfile
from loguru import logger


def is_compiler(name: str) -> bool:
    return name in ("llvm", "clang", "gcc", "intel", "nvhpc")


def load_cmake_template() -> dict:
    cmake_base_template = Path("templates/CMakePresets.json")
    with open(cmake_base_template, "r") as f:
        return json.load(f)


def load_spec_config(path: Path) -> list[dict[str, str]]:
    configs = list()
    for file in path.iterdir():
        if file.suffix == ".yaml":
            with open(file, "r") as f:
                configs.append(yaml.safe_load(f))
    return configs


def install_spec(config: dict[str, str], install_dir: Path, dry_run: bool = False) -> Path:
    logger.info(f"Installing {config['name']} {config['version']}")
    cmake_config = load_cmake_template()
    install_dir = install_dir / config["name"] / config["version"]
    for k, v in config["cmake"].items():
        cmake_config["configurePresets"][0]["cacheVariables"][k] = v
    cmake_config["configurePresets"][0]["cacheVariables"]["CMAKE_INSTALL_PREFIX"] = str(install_dir.absolute())
    if config['name'] == "llvm":
        cmake_config["configurePresets"][0]["cacheVariables"]["CMAKE_INSTALL_RPATH"] = str((install_dir / "lib").absolute())

    if dry_run:
        return install_dir

    with TemporaryDirectory() as tmp_dir:
        # Download source
        logger.info(f"Downloading {config['name']} {config['version']}")
        archive_path = Path(tmp_dir) / f"{config['name']}.tar.gz"
        urllib.request.urlretrieve(config['source'], archive_path)

        # Extract archive
        logger.info(f"Extracting {config['name']} {config['version']}")
        with tarfile.open(archive_path) as tar:
            tar.extractall(tmp_dir)

        # Find extracted directory
        extracted_dirs = [d for d in Path(tmp_dir).iterdir() if d.is_dir()]
        if not extracted_dirs:
            raise RuntimeError("No directory found after extraction")
        source_dir = extracted_dirs[0]

        # Special case for llvm
        if config['name'] == "llvm":
            source_dir = source_dir / "llvm"

        # Write CMake config
        logger.info(f"Writing CMake config for {config['name']} {config['version']}")
        cmake_preset_path = source_dir / "CMakePresets.json"
        with open(cmake_preset_path, "w") as f:
            json.dump(cmake_config, f)

        # Configure, build and install
        logger.info(f"Configuring, building and installing {config['name']} {config['version']}")
        install_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["cmake", "--workflow", "--preset", "default"], cwd=source_dir, check=True)

        logger.info(f"Installed {config['name']} {config['version']} to {install_dir}")
        return install_dir


def install_module_file(config: dict[str, str], install_dir: Path, module_dir: Path) -> None:
    template_path = Path("templates/module-template.lua") if is_compiler(config['name']) else Path("templates/compiler-module-template.lua")
    with open(template_path, "r") as f:
        template = f.read()

    # Replace variables
    module_content = template.replace("@NAME@", config["name"]) \
        .replace("@VERSION@", config["version"]) \
        .replace("@DESCRIPTION@", config.get("description", "")) \
        .replace("@BRIEF_DESCRIPTION@", config.get("brief_description", "")) \
        .replace("@CATEGORY@", config.get("category", "")) \
        .replace("@INSTALL_DIR@", str(install_dir.absolute()))

    module_file = module_dir / config["name"] / f"{config['version']}.lua"
    module_file.parent.mkdir(parents=True, exist_ok=True)
    with open(module_file, "w") as f:
        f.write(module_content)
    logger.info(f"Created module file at {module_file}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("spec_dir", type=Path)
    parser.add_argument("install_dir", type=Path)
    parser.add_argument("module_dir", nargs="?", type=Path, default=None)
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Verbosity level (Enable Debug & Trace Logs)")
    parser.add_argument("-i", "--include", type=str, default=None, help="Filter specs to install. Must be a regex")
    parser.add_argument("-e", "--exclude", type=str, default=None, help="Filter specs to not install. Must be a regex")
    parser.add_argument("--skip-install", action="store_true", default=False, help="Don't install anything. Only create module files.")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Don't install anything")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stdout, level=["INFO", "DEBUG", "TRACE"][args.verbose])

    include_regex = re.compile(args.include) if args.include else None
    exclude_regex = re.compile(args.exclude) if args.exclude else None

    spec_configs = load_spec_config(args.spec_dir)
    for config in spec_configs:
        if (not include_regex or include_regex.match(config["name"])) and not (exclude_regex and exclude_regex.match(config["name"])):
            if args.dry_run:
                logger.info(f"Would install {config['name']} {config['version']} to {args.install_dir}")
            else:
                install_dir = install_spec(config, args.install_dir, args.skip_install)
                if args.module_dir is not None:
                    install_module_file(config, install_dir, args.module_dir)
