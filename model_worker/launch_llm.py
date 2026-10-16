"""Run one GPU supervisor; runtime overrides are not accepted."""
import signal
import sys
import threading
from model_worker.supervisor import Supervisor
from model_worker.scheduler import Server


def main():
    if len(sys.argv) != 1:
        raise ValueError('the supervisor does not accept runtime overrides')
    manager = Supervisor()
    manager.initializing = True
    server = Server(None, manager=manager)
    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    threading.Thread(target=manager.initialize, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        manager.close()
        server.server_close()


if __name__ == '__main__':
    main()
