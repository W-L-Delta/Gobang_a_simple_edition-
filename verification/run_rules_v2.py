"""Run the shared rule test table against engine_v2."""

from __future__ import annotations

import importlib.util
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "五子棋桌面版")
sys.path.insert(0, APP)
sys.path.insert(0, HERE)


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


engine = load("engine_v2")
sys.modules["engine"] = engine
runpy.run_path(os.path.join(HERE, "test_rules.py"), run_name="__main__")
