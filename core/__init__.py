"""
Core processing modules for LinguaLearn.
Adds both the project root and this core directory to sys.path
so that `import config` and cross-module imports work correctly.
"""
import sys
import os

_core_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(_core_dir)

for _p in [_root_dir, _core_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
