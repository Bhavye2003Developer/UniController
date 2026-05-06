import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('ALLOWED_USER_ID', '12345')
os.environ.setdefault('FOCUS_BLOCKLIST', 'notepad,calc')


@pytest.fixture
def auth_update():
    u = MagicMock()
    u.effective_user.id = 12345
    u.effective_chat.id = 12345
    u.message.reply_text = AsyncMock()
    return u


@pytest.fixture
def ctx():
    c = MagicMock()
    c.args = []
    c.job_queue = MagicMock()
    c.job_queue.run_once = MagicMock()
    return c


@pytest.mark.asyncio
async def test_volume_no_args_shows_current(auth_update, ctx):
    ctx.args = []
    with patch("bot.handlers.misc.get_volume", return_value=50.0):
        from bot.handlers.misc import volume
        await volume(auth_update, ctx)
        auth_update.message.reply_text.assert_called_once()
        assert "50" in auth_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_volume_set_number(auth_update, ctx):
    ctx.args = ['75']
    with patch("bot.handlers.misc.set_volume") as mock_set, \
         patch("bot.handlers.misc.get_volume", return_value=75.0):
        from bot.handlers.misc import volume
        await volume(auth_update, ctx)
        mock_set.assert_called_once_with(75)


@pytest.mark.asyncio
async def test_launch_no_args_shows_usage(auth_update, ctx):
    ctx.args = []
    from bot.handlers.misc import launch
    await launch(auth_update, ctx)
    auth_update.message.reply_text.assert_called_once()
    assert "usage" in auth_update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_launch_finds_app(auth_update, ctx):
    ctx.args = ['calc']
    fake_apps = [('Calculator', 'C:\\calc.lnk'), ('Notepad', 'C:\\notepad.lnk')]
    with patch("bot.handlers.misc.list_apps", return_value=fake_apps), \
         patch("bot.handlers.misc.launch_app") as mock_launch:
        from bot.handlers.misc import launch
        await launch(auth_update, ctx)
        mock_launch.assert_called_once()


@pytest.mark.asyncio
async def test_focus_defaults_to_25_minutes(auth_update, ctx):
    ctx.args = []
    with patch("psutil.process_iter", return_value=[]):
        from bot.handlers.misc import focus
        await focus(auth_update, ctx)
        auth_update.message.reply_text.assert_called_once()
        assert "25" in auth_update.message.reply_text.call_args[0][0]
        ctx.job_queue.run_once.assert_called_once()
