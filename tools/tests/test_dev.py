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

    @mock.patch.object(dev, "reconcile_registered_rabbitmq_vhosts")
    @mock.patch.object(dev, "initialize_registry")
    @mock.patch.object(dev, "run")
    @mock.patch.object(dev, "infra_compose_args", return_value=["docker", "compose"])
    @mock.patch.object(dev, "ensure_infra_credentials")
    def test_start_infrastructure_reconciles_registered_rabbitmq_vhosts(
        self,
        ensure_credentials: mock.Mock,
        _infra_compose_args: mock.Mock,
        run: mock.Mock,
        initialize_registry: mock.Mock,
        reconcile_vhosts: mock.Mock,
    ) -> None:
        credentials = {"HOVER_INFRA_RABBITMQ_USER": "hover"}
        ensure_credentials.return_value = credentials

        self.assertEqual(dev.start_infrastructure(), credentials)

        run.assert_called_once_with(["docker", "compose", "up", "-d", "--wait"])
        initialize_registry.assert_called_once_with(credentials)
        reconcile_vhosts.assert_called_once_with(credentials)

    @mock.patch.object(dev, "run")
    @mock.patch.object(dev, "infra_compose_args", return_value=["docker", "compose"])
    @mock.patch.object(dev, "command_output", return_value="/\nhover_1")
    @mock.patch.object(dev, "psql", return_value="1\n3")
    def test_reconcile_registered_rabbitmq_vhosts_restores_missing_vhosts(
        self,
        _psql: mock.Mock,
        _command_output: mock.Mock,
        _infra_compose_args: mock.Mock,
        run: mock.Mock,
    ) -> None:
        dev.reconcile_registered_rabbitmq_vhosts({"HOVER_INFRA_RABBITMQ_USER": "hover"})

        self.assertEqual(run.call_count, 3)
        self.assertIn("hover_3", run.call_args_list[1].args[0])
        self.assertIn("set_permissions", run.call_args_list[2].args[0])
        self.assertIn("hover_3", run.call_args_list[2].args[0])

    @mock.patch.object(dev, "run")
    @mock.patch.object(dev, "workspace_compose_args", return_value=["docker", "compose"])
    @mock.patch.object(dev, "configure_rabbitmq")
    @mock.patch.object(dev, "start_infrastructure")
    @mock.patch.object(dev, "assert_port_available")
    @mock.patch.object(dev, "load_workspace_values")
    @mock.patch.object(dev, "selected_port", return_value=55070)
    def test_up_repairs_infrastructure_before_starting_app(
        self,
        _selected_port: mock.Mock,
        load_workspace_values: mock.Mock,
        assert_port_available: mock.Mock,
        start_infrastructure: mock.Mock,
        configure_rabbitmq: mock.Mock,
        _workspace_compose_args: mock.Mock,
        run: mock.Mock,
    ) -> None:
        values = {
            "HOVER_RABBITMQ_VHOST": "hover_1",
            "HOVER_INFRA_RABBITMQ_USER": "hover",
        }
        load_workspace_values.return_value = values

        dev.up(types.SimpleNamespace(port=55070, profile="core"))

        load_workspace_values.assert_called_once_with(port=55070)
        assert_port_available.assert_called_once_with(55070)
        start_infrastructure.assert_called_once_with()
        configure_rabbitmq.assert_called_once_with(values)
        run.assert_called_once_with(["docker", "compose", "up", "--no-deps", "app"])


if __name__ == "__main__":
    unittest.main()
