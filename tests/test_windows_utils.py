from unittest.mock import patch, MagicMock
from io import BytesIO
import importlib


def test_capture_webcam_returns_bytesio_on_success():
    import numpy as np
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, fake_frame)

    with patch("cv2.VideoCapture", return_value=mock_cap):
        with patch("cv2.imencode", return_value=(True, np.array([1, 2, 3], dtype=np.uint8))):
            import utils.windows_utils as wu
            importlib.reload(wu)
            result = wu.capture_webcam()
            assert isinstance(result, BytesIO)


def test_capture_webcam_returns_none_when_no_camera():
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False

    with patch("cv2.VideoCapture", return_value=mock_cap):
        import utils.windows_utils as wu
        importlib.reload(wu)
        result = wu.capture_webcam()
        assert result is None


def test_capture_webcam_returns_none_when_read_fails():
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (False, None)

    with patch("cv2.VideoCapture", return_value=mock_cap):
        import utils.windows_utils as wu
        importlib.reload(wu)
        result = wu.capture_webcam()
        assert result is None


def test_frame_diff_pixel_count_detects_changes():
    import numpy as np
    import utils.windows_utils as wu
    importlib.reload(wu)
    a = np.zeros((10, 10, 3), dtype=np.uint8)
    b = np.full((10, 10, 3), 200, dtype=np.uint8)
    count = wu.frame_diff_pixel_count(a, b)
    assert count > 0


def test_frame_diff_pixel_count_zero_on_identical():
    import numpy as np
    import utils.windows_utils as wu
    importlib.reload(wu)
    a = np.zeros((10, 10, 3), dtype=np.uint8)
    count = wu.frame_diff_pixel_count(a, a.copy())
    assert count == 0
