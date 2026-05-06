import pytest
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('ALLOWED_USER_ID', '12345')


@pytest.fixture
def auth_update():
    u = MagicMock()
    u.effective_user.id = 12345
    u.effective_chat.id = 12345
    u.message.reply_text = AsyncMock()
    u.message.reply_document = AsyncMock()
    u.message.reply_to_message = None
    return u


@pytest.fixture
def ctx():
    c = MagicMock()
    c.args = []
    c.user_data = {}
    return c


@pytest.mark.asyncio
async def test_files_invalid_path_replies_error(auth_update, ctx):
    ctx.args = ['/nonexistent/path/xyz']
    from bot.handlers.files import files
    await files(auth_update, ctx)
    auth_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_files_lists_valid_dir(auth_update, ctx):
    ctx.args = [str(Path.home())]
    from bot.handlers.files import files
    await files(auth_update, ctx)
    auth_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_download_nonexistent_file_replies_error(auth_update, ctx):
    ctx.args = ['/nonexistent/file.txt']
    from bot.handlers.files import download
    await download(auth_update, ctx)
    auth_update.message.reply_text.assert_called_once()
    assert "not found" in auth_update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_upload_no_reply_explains_usage(auth_update, ctx):
    auth_update.message.reply_to_message = None
    from bot.handlers.files import upload
    await upload(auth_update, ctx)
    auth_update.message.reply_text.assert_called_once()
