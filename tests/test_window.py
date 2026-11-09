import unittest
from unittest import mock

from qqbot.ui import window


class FakeWindow:
    def __init__(self) -> None:
        self.hidden = False
        self.shown = 0
        self.restored = 0

    def hide(self) -> None:
        self.hidden = True

    def show(self) -> None:
        self.hidden = False
        self.shown += 1

    def restore(self) -> None:
        self.restored += 1


class FakeIcon:
    def __init__(self) -> None:
        self.visible = True
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class TestWindowApi(unittest.TestCase):
    def _api(self) -> window._WindowApi:
        api = window._WindowApi()
        api.window = FakeWindow()
        api.title = "NoSuchWindow_QQBot_Test"
        return api

    def test_show_restores_hidden_window(self):
        api = self._api()
        api.window.hidden = True
        api.show()
        self.assertFalse(api.window.hidden)
        self.assertEqual(api.window.shown, 1)
        self.assertEqual(api.window.restored, 1)

    def test_restore_hides_tray_icon_without_stopping(self):
        api = self._api()
        api.window.hidden = True
        icon = FakeIcon()
        api.icon = icon
        api._restore(icon, None)
        self.assertIs(api.icon, icon)
        self.assertFalse(icon.visible)
        self.assertFalse(icon.stopped)
        self.assertFalse(api.window.hidden)

    def test_close_action_default_tray(self):
        from qqbot.config import InstanceConfig

        self.assertEqual(InstanceConfig().close_action, "tray")
        fake = type("Cfg", (), {"close_action": "tray"})()
        with mock.patch("qqbot.config.load", return_value=fake):
            self.assertEqual(window._close_action(), "tray")

    def test_close_action_exit(self):
        fake = type("Cfg", (), {"close_action": "exit"})()
        with mock.patch("qqbot.config.load", return_value=fake):
            self.assertEqual(window._close_action(), "exit")

    def test_close_action_invalid_falls_back(self):
        fake = type("Cfg", (), {"close_action": "whatever"})()
        with mock.patch("qqbot.config.load", return_value=fake):
            self.assertEqual(window._close_action(), "tray")

    def test_x_hides_to_tray_by_default(self):
        api = self._api()
        api._hide_to_tray = lambda: True
        with mock.patch.object(window, "_close_action", return_value="tray"):
            self.assertFalse(api._on_closing())

    def test_x_exits_when_configured(self):
        api = self._api()
        api._hide_to_tray = lambda: True
        with mock.patch.object(window, "_close_action", return_value="exit"):
            self.assertTrue(api._on_closing())

    def test_quit_stops_icon_and_exits(self):
        api = self._api()
        icon = FakeIcon()
        with mock.patch.object(window.os, "_exit") as exit_mock, mock.patch.object(
            window.logging, "shutdown"
        ):
            api._quit(icon, None)
        self.assertTrue(icon.stopped)
        self.assertTrue(api._allow_close)
        exit_mock.assert_called_once_with(0)

    def test_find_hwnd_missing_title(self):
        self.assertEqual(window._find_hwnd("NoSuchWindow_QQBot_Test"), 0)


if __name__ == "__main__":
    unittest.main()
