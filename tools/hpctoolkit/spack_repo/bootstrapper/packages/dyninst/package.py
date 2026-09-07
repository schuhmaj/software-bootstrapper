# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""Overlay for the builtin dyninst package.

Dyninst 13.0.0 predates GCC 13, whose libstdc++ stopped transitively including
<cstdint>. Three translation units therefore fail to compile with GCC 13 and
newer. This overlay inherits everything from the builtin recipe and only adds
the missing-include patch.
"""

from spack_repo.builtin.packages.dyninst.package import Dyninst as BuiltinDyninst

from spack.package import *


class Dyninst(BuiltinDyninst):
    __doc__ = BuiltinDyninst.__doc__

    # GCC 13+ libstdc++ no longer transitively includes <cstdint>.
    # Affects common/src/sha1.C, common/src/arch-x86.h and
    # instructionAPI/h/ArchSpecificFormatters.h.
    patch("gcc15-cstdint.patch", when="@13.0.0 %gcc@13:")
