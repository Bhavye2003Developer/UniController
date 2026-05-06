import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('ALLOWED_USER_ID', '12345')


@pytest.fixture
def auth_update():
    u = MagicMock()
    u.effective_user.id = 12345
    u.effective_chat.id = 12345
    u.message.reply_text = AsyncMock()
    return u


@pytest.fixture
def unauth_update():
    u = MagicMock()
    u.effective_user.id = 99999
    u.message.reply_text = AsyncMock()
    return u


@pytest.fixture
def ctx():
    c = MagicMock()
    c.args = []
    return c


@pytest.mark.asyncio
async def test_sysinfo_unauthorized_drops(unauth_update, ctx):
    from bot.handlers.system import sysinfo
    await sysinfo(unauth_update, ctx)
    unauth_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_sysinfo_sends_message(auth_update, ctx):
    with patch("psutil.cpu_percent", return_value=25.0), \
         patch("psutil.virtual_memory", return_value=MagicMock(percent=60, used=8*1024**3, total=16*1024**3)), \
         patch("psutil.disk_usage", return_value=MagicMock(percent=50, used=250*1024**3, total=500*1024**3)), \
         patch("psutil.net_io_counters", return_value=MagicMock(bytes_sent=1024, bytes_recv=2048)), \
         patch("psutil.boot_time", return_value=0):
        from bot.handlers.system import sysinfo
        await sysinfo(auth_update, ctx)
        auth_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown_adds_to_pending(auth_update, ctx):
    from bot.handlers import system
    system._pending_shutdown.clear()
    await system.shutdown(auth_update, ctx)
    assert auth_update.effective_chat.id in system._pending_shutdown
    auth_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_restart_adds_to_pending(auth_update, ctx):
    from bot.handlers import system
    system._pending_restart.clear()
    await system.restart(auth_update, ctx)
    assert auth_update.effective_chat.id in system._pending_restart
    auth_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_lock_calls_lock_screen(auth_update, ctx):
    with patch("bot.handlers.system.lock_screen") as mock_lock:
        from bot.handlers.system import lock
        await lock(auth_update, ctx)
        mock_lock.assert_called_once()
