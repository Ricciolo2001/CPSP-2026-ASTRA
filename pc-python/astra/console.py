import sys
import threading


class Console:
    """
    A simple console interface that allows sending lines of text to the Crazyflie
    and displays received messages above the prompt.
    """

    def __init__(self, callback=None):
        self.callback = callback
        self._lock = threading.Lock()
        self._input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self._running = False

    def start(self):
        self._running = True
        self._input_thread.start()
        self._show_prompt()

    def stop(self):
        self._running = False

    def log(self, message):
        """Print a received message above the prompt."""
        with self._lock:
            # Clear the current prompt line, print the message, redraw prompt
            sys.stdout.write(f"\r\033[K{message}\n")
            self._show_prompt()
            sys.stdout.flush()

    def _show_prompt(self):
        sys.stdout.write("> ")
        sys.stdout.flush()

    def _input_loop(self):
        while self._running:
            try:
                line = sys.stdin.readline()
                if line:
                    user_input = line.rstrip("\n")
                    if self.callback:
                        self.callback(user_input)

                    with self._lock:
                        self._show_prompt()
            except (EOFError, KeyboardInterrupt):
                break
