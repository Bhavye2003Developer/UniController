import subprocess
import sys
import threading
import queue
import time


PYTHON_WORKER = '''
import sys
import traceback

while True:
    try:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        if line == "exit":
            break
        try:
            try:
                result = eval(compile(line, "<input>", "eval"))
                if result is not None:
                    print(repr(result), flush=True)
            except SyntaxError:
                exec(compile(line, "<input>", "exec"))
                sys.stdout.flush()
        except Exception:
            traceback.print_exc(limit=1, file=sys.stdout)
            sys.stdout.flush()
    except EOFError:
        break
'''


class CommandExecutor():
    def __init__(self):
        print('Initialising Command Executor...')
        self.python_process = None
        self.output_queue = queue.Queue()

    def run(self, command: list[str], timeout: int = 30) -> str:
        try:
            cmd_str = " ".join(command)
            result = subprocess.run(
                [r"C:\Program Files\Git\bin\bash.exe", "-c", f"cd / && {cmd_str}"],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                return f"[Error - exit code {result.returncode}]\n{result.stderr.strip()}"
            return result.stdout.strip() or "Done. No output."
        except subprocess.TimeoutExpired:
            return f"[Timeout] Command took longer than {timeout}s and was killed."
        except FileNotFoundError:
            return f"[Error] Command not found: '{command[0]}'"
        except Exception as e:
            return f"[Error] {str(e)}"

    def start_python_session(self) -> str:
        if self.python_process and self.python_process.poll() is None:
            return "Session already running. Type Python code or /exitp to stop."

        self.python_process = subprocess.Popen(
            [sys.executable, '-u', '-c', PYTHON_WORKER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        self.output_queue = queue.Queue()

        t = threading.Thread(
            target=self._read_output,
            args=(self.python_process, self.output_queue),
            daemon=True
        )
        t.start()
        return "🐍 Python session started. Send code directly. /exitp to stop."

    def run_python(self, code: str, wait: float = 0.4) -> str:
        if not self.python_process or self.python_process.poll() is not None:
            return "No active session. Use /runp to start one."
        try:
            self.python_process.stdin.write(code + '\n')
            self.python_process.stdin.flush()
        except BrokenPipeError:
            return "[Error] Python session crashed. Use /runp to restart."

        time.sleep(wait)
        lines = []
        while not self.output_queue.empty():
            lines.append(self.output_queue.get())
        return ''.join(lines).strip() or "(no output)"

    def stop_python_session(self) -> str:
        if self.python_process:
            self.python_process.kill()
            self.python_process = None
        return "🛑 Python session stopped."

    def is_python_session_active(self) -> bool:
        return self.python_process is not None and self.python_process.poll() is None

    def _read_output(self, process, q: queue.Queue):
        for line in iter(process.stdout.readline, ''):
            q.put(line)