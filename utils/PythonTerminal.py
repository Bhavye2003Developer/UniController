import subprocess
import sys
import threading
import queue
import time
import html
import os
import tempfile

WORKER_CODE = '''
import sys, traceback, codeop

_locals = {}
buffer = []

while True:
    try:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.rstrip()

        if line == "__EXIT__":
            break

        buffer.append(line)
        source = "\\n".join(buffer)

        try:
            code = codeop.compile_command(source + "\\n", "<repl>", "single")
        except SyntaxError as e:
            print(f"SyntaxError: {e}", flush=True)
            buffer.clear()
            print("__DONE__", flush=True)
            continue

        if code is not None:
            try:
                exec(code, _locals)
                sys.stdout.flush()
            except Exception:
                traceback.print_exc(limit=2, file=sys.stdout)
                sys.stdout.flush()
            buffer.clear()
            print("__DONE__", flush=True)
        else:
            print("__MORE__", flush=True)

    except EOFError:
        break
'''


class PythonTerminal:
    def __init__(self):
        self.process = None
        self.output_queue: queue.Queue = queue.Queue()
        self.history: list[str] = []
        self.terminal_message_id: int | None = None
        self.chat_id: int | None = None
        self.waiting_for_more: bool = False
        self._worker_file: str | None = None

    def start(self) -> bool:
        if self.is_active():
            return False

        fd, path = tempfile.mkstemp(suffix='.py')
        with os.fdopen(fd, 'w') as f:
            f.write(WORKER_CODE)
        self._worker_file = path

        self.history = []
        self.output_queue = queue.Queue()
        self.waiting_for_more = False

        self.process = subprocess.Popen(
            [sys.executable, '-u', path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        threading.Thread(
            target=self._reader,
            args=(self.process, self.output_queue),
            daemon=True
        ).start()
        return True

    def execute(self, code: str, wait: float = 0.5) -> tuple[str, bool]:
        if not self.is_active():
            return "[Error] No active session.", False
        try:
            self.process.stdin.write(code + '\n')
            self.process.stdin.flush()
        except BrokenPipeError:
            return "[Error] Session crashed.", False

        time.sleep(wait)
        lines = []
        needs_more = False

        while not self.output_queue.empty():
            line = self.output_queue.get()
            if line == '__MORE__':
                needs_more = True
            elif line == '__DONE__':
                needs_more = False
            else:
                lines.append(line)

        self.waiting_for_more = needs_more
        output = '\n'.join(lines).strip()
        return output, needs_more

    def stop(self):
        if self.process:
            self.process.kill()
            self.process = None
        if self._worker_file and os.path.exists(self._worker_file):
            os.remove(self._worker_file)
            self._worker_file = None

    def is_active(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def add_to_history(self, code: str, output: str, continuation: bool = False):
        prefix = "... " if continuation else ">>> "
        self.history.append(f"{prefix}{code}")
        if output:
            self.history.append(output)

    def render(self) -> str:
        header = "🖥  <b>Python Terminal</b>\n<code>"
        divider = "─" * 28 + "\n"
        if not self.history:
            body = "(session started)\n"
        else:
            escaped = [html.escape(line) for line in self.history[-30:]]
            body = "\n".join(escaped) + "\n"
        prompt = "..." if self.waiting_for_more else "&gt;&gt;&gt;"
        cursor = "─" * 28 + f"\n{prompt} _"
        return f"{header}{divider}{body}{cursor}</code>"

    def _reader(self, process, q: queue.Queue):
        for line in iter(process.stdout.readline, ''):
            q.put(line.rstrip())