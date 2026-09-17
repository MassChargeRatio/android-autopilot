# -*- coding: utf-8 -*-
"""扫描 192.168.1.0/24 网段开放的 adb 端口 (5555 等)，并探测可达性。"""
import socket, concurrent.futures, time

NET = "192.168.1."
PORTS = [5555, 5556]
HOSTS = [f"{NET}{i}" for i in range(1, 255)]

def scan(host):
    hits = []
    for port in PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            if s.connect_ex((host, port)) == 0:
                hits.append(port)
        except Exception:
            pass
        finally:
            s.close()
    return (host, hits) if hits else None

t0 = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
    for res in ex.map(scan, HOSTS):
        if res:
            host, hits = res
            print(f"OPEN: {host} ports={hits}")
print(f"scan done in {time.time()-t0:.1f}s")
