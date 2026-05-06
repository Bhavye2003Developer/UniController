import pytest
from unittest.mock import MagicMock, patch
import numpy as np


def test_watcher_starts_stopped():
    from utils.guardian_watcher import GuardianWatcher
    w = GuardianWatcher()
    assert not w.is_active()


def test_watcher_active_after_start(mocker):
    from utils.guardian_watcher import GuardianWatcher
    w = GuardianWatcher()
    mock_bot = mocker.MagicMock()
    mock_loop = mocker.MagicMock()
    mocker.patch("utils.guardian_watcher.capture_webcam_frame", return_value=None)
    mocker.patch("threading.Thread")
    w.start(mock_bot, chat_id=123, loop=mock_loop)
    assert w.is_active()


def test_watcher_inactive_after_stop(mocker):
    from utils.guardian_watcher import GuardianWatcher
    w = GuardianWatcher()
    mock_bot = mocker.MagicMock()
    mock_loop = mocker.MagicMock()
    mocker.patch("utils.guardian_watcher.capture_webcam_frame", return_value=None)
    mocker.patch("threading.Thread")
    w.start(mock_bot, chat_id=123, loop=mock_loop)
    w.stop()
    assert not w.is_active()


def test_frame_diff_triggers_alert(mocker):
    from utils.guardian_watcher import GuardianWatcher
    w = GuardianWatcher()
    w._running = True
    w._loop = mocker.MagicMock()
    w._bot = mocker.MagicMock()
    w._chat_id = 123

    baseline = np.zeros((480, 640, 3), dtype=np.uint8)
    changed = np.full((480, 640, 3), 200, dtype=np.uint8)
    w._baseline_frame = baseline

    mocker.patch("utils.guardian_watcher.capture_webcam_frame", return_value=changed)
    mock_send = mocker.patch.object(w, "_send_alert")
    w._check_motion()

    mock_send.assert_called_once()


def test_frame_diff_no_alert_when_static(mocker):
    from utils.guardian_watcher import GuardianWatcher
    w = GuardianWatcher()
    w._running = True
    w._loop = mocker.MagicMock()
    w._bot = mocker.MagicMock()
    w._chat_id = 123

    baseline = np.zeros((480, 640, 3), dtype=np.uint8)
    w._baseline_frame = baseline

    mocker.patch("utils.guardian_watcher.capture_webcam_frame", return_value=baseline.copy())
    mock_send = mocker.patch.object(w, "_send_alert")
    w._check_motion()

    mock_send.assert_not_called()
