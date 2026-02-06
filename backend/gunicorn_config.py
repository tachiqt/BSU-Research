import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 2048

workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 120
keepalive = 5

accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

proc_name = 'bsu-research-dashboard'
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None
