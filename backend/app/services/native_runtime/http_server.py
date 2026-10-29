"""Bounded internal control/gateway HTTP concurrency; no request logging."""
from http.server import ThreadingHTTPServer
import threading

class BoundedHTTPServer(ThreadingHTTPServer):
    request_queue_size=16
    daemon_threads=True
    def __init__(self,*args,**kwargs):
        self.slots=threading.BoundedSemaphore(16)
        super().__init__(*args,**kwargs)
    def get_request(self):
        connection,address=super().get_request();connection.settimeout(10)
        return connection,address
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request);return
        try:super().process_request(request,address)
        except BaseException:
            self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()
    def handle_error(self,*args):pass
