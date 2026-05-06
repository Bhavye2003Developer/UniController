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
    u.message.reply_to_message = None
    return u


@pytest.fixture
def ctx():
    c = MagicMock()
    c.args = ['get']
    return c


@pytest.mark.asyncio
async def test_clip_get_sends_content(auth_update, ctx):
    ctx.args = ['get']
    with patch("pyperclip.paste", return_value="hello world"):
        from bot.handlers.clipboard import clip
        await clip(auth_update, ctx)
        auth_update.message.reply_text.assert_called_once()
        assert "hello world" in auth_update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_clip_get_empty(auth_update, ctx):
    ctx.args = ['get']
    with patch("pyperclip.paste", return_value=""):
        from bot.handlers.clipboard import clip
        await clip(auth_update, ctx)
        auth_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_clip_set_no_reply_explains(auth_update, ctx):
    ctx.args = ['set']
    auth_update.message.reply_to_message = None
    from bot.handlers.clipboard import clip
    await clip(auth_update, ctx)
    assert "reply" in auth_update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_clip_set_copies_to_pc(auth_update, ctx):
    ctx.args = ['set']
    reply = MagicMock()
    reply.text = "copied text"
    auth_update.message.reply_to_message = reply
    with patch("pyperclip.copy") as mock_copy:
        from bot.handlers.clipboard import clip
        await clip(auth_update, ctx)
        mock_copy.assert_called_once_with("copied text")
