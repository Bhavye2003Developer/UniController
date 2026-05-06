import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

os.environ.setdefault('ALLOWED_USER_ID', '12345')


@pytest.fixture
def authorized_update():
    update = MagicMock()
    update.effective_user.id = 12345
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    return update


@pytest.fixture
def unauthorized_update():
    update = MagicMock()
    update.effective_user.id = 99999
    update.message.reply_text = AsyncMock()
    update.message.reply_photo = AsyncMock()
    return update


@pytest.fixture
def ctx():
    c = MagicMock()
    c.args = []
    c.bot = MagicMock()
    return c


@pytest.mark.asyncio
async def test_snap_unauthorized_drops_silently(unauthorized_update, ctx):
    from bot.handlers.guardian import snap
    await snap(unauthorized_update, ctx)
    unauthorized_update.message.reply_photo.assert_not_called()
    unauthorized_update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_snap_no_webcam_replies_error(authorized_update, ctx):
    with patch("bot.handlers.guardian.capture_webcam", return_value=None):
        from bot.handlers.guardian import snap
        await snap(authorized_update, ctx)
        authorized_update.message.reply_text.assert_called_once()
        msg = authorized_update.message.reply_text.call_args[0][0].lower()
        assert "webcam" in msg


@pytest.mark.asyncio
async def test_snap_sends_photo(authorized_update, ctx):
    fake_photo = BytesIO(b"img")
    with patch("bot.handlers.guardian.capture_webcam", return_value=fake_photo):
        from bot.handlers.guardian import snap
        await snap(authorized_update, ctx)
        authorized_update.message.reply_photo.assert_called_once_with(photo=fake_photo)


@pytest.mark.asyncio
async def test_guard_on_starts_watcher(authorized_update, ctx):
    ctx.args = ['on']
    mock_watcher = MagicMock()
    mock_watcher.is_active.return_value = False
    with patch("bot.handlers.guardian._watcher", mock_watcher):
        import bot.handlers.guardian as g
        g._watcher = mock_watcher
        with patch("asyncio.get_event_loop"):
            await g.guard(authorized_update, ctx)
        mock_watcher.start.assert_called_once()


@pytest.mark.asyncio
async def test_guard_status_inactive(authorized_update, ctx):
    ctx.args = ['status']
    mock_watcher = MagicMock()
    mock_watcher.is_active.return_value = False
    import bot.handlers.guardian as g
    g._watcher = mock_watcher
    await g.guard(authorized_update, ctx)
    call_text = authorized_update.message.reply_text.call_args[0][0]
    assert "Inactive" in call_text


@pytest.mark.asyncio
async def test_panic_sends_confirmation_first(authorized_update, ctx):
    import bot.handlers.guardian as g
    g._pending_panic.clear()
    await g.panic(authorized_update, ctx)
    authorized_update.message.reply_text.assert_called_once()
    msg = authorized_update.message.reply_text.call_args[0][0]
    assert "confirm" in msg.lower()
