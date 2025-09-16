import time
import types
import pytest

from robotlib.multiprocess.account_config import AccountConfig
from robotlib.multiprocess.process_manager import ProcessManager


class FakeRobotProcess:
    """Лёгкая подмена RobotProcess для unit-тестов ProcessManager."""

    def __init__(self, account_config: AccountConfig):
        self._account_config = account_config
        self._running = False
        self._pid = 12345

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self, timeout: float = 30.0) -> bool:
        self._running = False
        return True

    def restart(self) -> bool:
        self._running = True
        return True

    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        return {
            'process_name': self._account_config.get_process_name(),
            'account_id': self._account_config.account_id,
            'figi': self._account_config.figi,
            'is_running': self._running,
            'pid': self._pid,
            'visualization_port': self._account_config.visualization_port,
            'visualization_url': f"http://{self._account_config.visualization_host}:{self._account_config.visualization_port}"
            if self._account_config.enable_visualization else None,
        }

    @property
    def account_config(self) -> AccountConfig:
        return self._account_config


def test_stop_all_safe_with_zero_robots():
    manager = ProcessManager()
    assert manager.stop_all() is True


def test_add_accounts_and_auto_assign_ports(monkeypatch):
    # Подменяем RobotProcess внутри модуля менеджера
    import robotlib.multiprocess.process_manager as pm_mod
    monkeypatch.setattr(pm_mod, 'RobotProcess', FakeRobotProcess)

    manager = ProcessManager()

    cfg1 = AccountConfig(
        account_id='acc1',
        token='t1',
        sandbox_token='',
        figi='FUTIMOEXF000',
        visualization_port=8050,
    )
    cfg2 = AccountConfig(
        account_id='acc2',
        token='t2',
        sandbox_token='',
        figi='FUTIMOEXF000',
        visualization_port=8050,  # тот же порт — должен быть переназначен
    )

    assert manager.add_account(cfg1) is True
    assert manager.add_account(cfg2) is True

    status = manager.get_status()
    assert status['acc1']['visualization_port'] == 8050
    # второй должен получить следующий доступный порт
    assert status['acc2']['visualization_port'] == 8051


def test_start_and_stop_all(monkeypatch):
    import robotlib.multiprocess.process_manager as pm_mod
    monkeypatch.setattr(pm_mod, 'RobotProcess', FakeRobotProcess)

    # Ускоряем запуск — убираем задержки sleep в start_all
    monkeypatch.setattr(pm_mod.time, 'sleep', lambda *_args, **_kwargs: None)

    manager = ProcessManager()

    cfg1 = AccountConfig(account_id='a1', token='t', sandbox_token='')
    cfg2 = AccountConfig(account_id='a2', token='t', sandbox_token='')

    assert manager.add_account(cfg1) is True
    assert manager.add_account(cfg2) is True

    assert manager.start_all() is True
    assert set(manager.get_running_accounts()) == {'a1', 'a2'}

    assert manager.stop_all() is True
    assert manager.get_running_accounts() == []


def test_restart_account(monkeypatch):
    import robotlib.multiprocess.process_manager as pm_mod
    monkeypatch.setattr(pm_mod, 'RobotProcess', FakeRobotProcess)

    manager = ProcessManager()
    cfg = AccountConfig(account_id='acc', token='t', sandbox_token='')
    assert manager.add_account(cfg) is True
    assert manager.start_account('acc') is True
    assert manager.restart_account('acc') is True

