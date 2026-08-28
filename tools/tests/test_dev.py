import importlib.machinery
import importlib.util
import os
import types
import unittest
from pathlib import Path
from unittest import mock


def load_dev_module() -> types.ModuleType:
    path = Path(__file__).resolve().parents[1] / "dev"
    loader = importlib.machinery.SourceFileLoader("hover_tools_dev", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


dev = load_dev_module()


class DevCliTest(unittest.TestCase):
    def test_port_precedence(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"CONDUCTOR_PORT": "12001", "HOVER_DEV_PORT": "12002"},
            clear=False,
        ):
            self.assertEqual(dev.selected_port(12000), 12000)
            self.assertEqual(dev.selected_port(None), 12001)
            del os.environ["CONDUCTOR_PORT"]
            self.assertEqual(dev.selected_port(None), 12002)
            del os.environ["HOVER_DEV_PORT"]
            self.assertEqual(dev.selected_port(None), 9991)

    def test_instance_id_uses_conductor_identity(self) -> None:
        with mock.patch.dict(os.environ, {"CONDUCTOR_WORKSPACE_ID": "workspace-42"}):
            first = dev.instance_id()
            second = dev.instance_id()
        self.assertEqual(first, second)
        self.assertRegex(first, r"^[a-f0-9]{16}$")

    def test_instance_id_falls_back_to_absolute_worktree(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            current = dev.instance_id()
        self.assertRegex(current, r"^[a-f0-9]{16}$")

    def test_rejects_invalid_port(self) -> None:
        with self.assertRaisesRegex(dev.DevError, "between 1 and 65535"):
            dev.selected_port(70000)


if __name__ == "__main__":
    unittest.main()
