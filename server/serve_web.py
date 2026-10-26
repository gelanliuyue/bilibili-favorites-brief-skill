"""BiliBrief 本地 Web 托管（静态前端 + 后端同源反向代理）。

为什么需要它
------------
`BillNote_frontend/dist` 是用相对路径 `/api` 构建的（axios baseURL 默认 `/api`）。
如果直接用 `python -m http.server` 托管 dist，前端的 `GET /api/sys_check` 会打到
静态服务器自己身上而不是后端 8483，结果必然是 404：

  * 设置页轮询 `sys_check` 60 秒拿不到 `code:0` → 弹「后端启动失败」
  * 读取供应商 list 失败 → 「暂时无法读取后端模型配置」
  * 保存 API Key 时响应解析失败 → 「操作失败，请稍后再试」

上游 BiliNote 在生产环境用 nginx 做同源反代（见 `server/nginx/`），本脚本用
标准库实现同样的事，零依赖，专门给本地直接跑 dist 的场景用。

用法
----
    python serve_web.py                 # 默认 http://127.0.0.1:3015 -> 后端 8483
    python serve_web.py --port 8080
    python serve_web.py --backend http://127.0.0.1:9000

后端地址也可用环境变量 BACKEND_URL 覆盖。
"""

from __future__ import annotations

import argparse
import gzip
import mimetypes
import os
import posixpath
import sys
import urllib.error
import urllib.parse
import urllib.request
import zlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DIST_DIR = Path(__file__).resolve().parent / 'BillNote_frontend' / 'dist'

# 需要转发给后端的路径前缀。`/static` 是截图等静态资源（IMAGE_BASE_URL）。
PROXY_PREFIXES = ('/api', '/static')

# 逐跳头，不能在代理层转发
HOP_BY_HOP = {
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailers', 'transfer-encoding', 'upgrade', 'host',
}

# 后端会返回自己的 date/server，本进程也会加，重复了浏览器会困惑
DROP_RESPONSE_HEADERS = HOP_BY_HOP | {
    'content-length', 'content-encoding', 'date', 'server', 'vary',
}

# 关键：本机常常配置了全局 HTTP 代理（例如 Clash 的 127.0.0.1:xxxx），
# urllib 默认会继承它，把 127.0.0.1:8483 的请求也代理掉，回一条假的 502。
# 这里显式禁用代理，直连后端。
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

BACKEND = os.environ.get('BACKEND_URL', 'http://127.0.0.1:8483').rstrip('/')


def _decompress(data: bytes, encoding: str) -> bytes:
    encoding = (encoding or '').lower().strip()
    if encoding in ('gzip', 'x-gzip'):
        try:
            return gzip.decompress(data)
        except OSError:
            return data
    if encoding == 'deflate':
        try:
            return zlib.decompress(data)
        except zlib.error:
            try:
                return zlib.decompress(data, -zlib.MAX_WBITS)
            except zlib.error:
                return data
    return data


class Handler(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'BiliBriefWeb/1.0'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    # ---------- 日志 ----------
    def log_message(self, fmt, *args):
        # 静态资源太吵，只记 /api 与错误
        try:
            self.log_to_file(fmt % args)
        except Exception:  # noqa: BLE001
            pass

    def log_to_file(self, line):
        text = line.strip()
        if '/api' in text or ' 4' in text or ' 5' in text:
            sys.stderr.write('[web] %s\n' % text)

    # ---------- 反代 ----------
    def _wants_proxy(self) -> bool:
        return any(self.path == p or self.path.startswith(p + '/') for p in PROXY_PREFIXES)

    def _proxy(self):
        url = BACKEND + self.path
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length > 0 else None

        req = urllib.request.Request(url, data=body, method=self.command)
        for key, value in self.headers.items():
            name = key.lower()
            if name not in HOP_BY_HOP and name != 'accept-encoding':
                req.add_header(key, value)
        # 让后端不要 gzip：本进程直接透传字节，若去掉 content-encoding 却转发
        # 压缩体，浏览器会当成文本解析失败（axios 会静默得到字符串，误报失败）。
        req.add_header('Accept-Encoding', 'identity')

        try:
            with _OPENER.open(req, timeout=600) as resp:
                data = _decompress(resp.read(), resp.headers.get('content-encoding'))
                self.send_response(resp.status)
                for key, value in resp.headers.items():
                    if key.lower() not in DROP_RESPONSE_HEADERS:
                        self.send_header(key, value)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                if self.command != 'HEAD':
                    self.wfile.write(data)
        except urllib.error.HTTPError as exc:
            data = _decompress(exc.read(), exc.headers.get('content-encoding'))
            self.send_response(exc.code)
            if exc.headers.get('content-type'):
                self.send_header('Content-Type', exc.headers.get('content-type'))
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(data)
        except Exception as exc:  # noqa: BLE001  后端没起来 / 连接被拒
            msg = ('后端不可达: %s\n请先启动后端: python main.py (目录 server/backend)\n'
                   % exc).encode('utf-8')
            self.send_response(502)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(msg)))
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(msg)

    # ---------- 静态 / SPA ----------
    def _serve_spa(self):
        """前端用 BrowserRouter，刷新 /brief/setup 这类深链要回落到 index.html。"""
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            index = os.path.join(path, 'index.html')
            if os.path.isfile(index):
                return self._send_file(index, cache=False)
        elif os.path.isfile(path):
            return self._send_file(path, cache=True)
        index = DIST_DIR / 'index.html'
        if index.is_file():
            return self._send_file(str(index), cache=False)
        self.send_error(404, 'dist/index.html not found')

    def _send_file(self, path: str, cache: bool):
        try:
            with open(path, 'rb') as fh:
                data = fh.read()
        except OSError:
            return self.send_error(404)
        ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        if ctype.startswith('text/') or ctype in ('application/json', 'application/javascript'):
            ctype += '; charset=utf-8'
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        # index.html 不缓存，避免改了配置后浏览器一直拿旧入口
        self.send_header('Cache-Control', 'public, max-age=86400' if cache else 'no-store')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    # ---------- 分派 ----------
    def do_GET(self):
        if self._wants_proxy():
            return self._proxy()
        return self._serve_spa()

    def do_HEAD(self):
        if self._wants_proxy():
            return self._proxy()
        return self._serve_spa()

    def do_POST(self):
        return self._proxy() if self._wants_proxy() else self.send_error(405)

    def do_PUT(self):
        return self._proxy() if self._wants_proxy() else self.send_error(405)

    def do_PATCH(self):
        return self._proxy() if self._wants_proxy() else self.send_error(405)

    def do_DELETE(self):
        return self._proxy() if self._wants_proxy() else self.send_error(405)

    def do_OPTIONS(self):
        return self._proxy() if self._wants_proxy() else self.send_error(405)


def main():
    global BACKEND
    default_backend = BACKEND
    parser = argparse.ArgumentParser(description='BiliBrief 本地 Web 托管 + 后端反代')
    parser.add_argument('--port', type=int, default=int(os.environ.get('WEB_PORT', 3015)))
    parser.add_argument('--host', default=os.environ.get('WEB_HOST', '127.0.0.1'))
    parser.add_argument('--backend', default=default_backend)
    args = parser.parse_args()

    BACKEND = args.backend.rstrip('/')

    if not (DIST_DIR / 'index.html').is_file():
        sys.exit('找不到前端产物: %s\n先执行 deploy.ps1 -BuildFrontend，或确认 dist 已随仓库下载。'
                 % DIST_DIR)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print('前端目录 : %s' % DIST_DIR)
    print('页面入口 : http://%s:%d' % (args.host, args.port))
    print('接口反代 : http://%s:%d/api  ->  %s/api' % (args.host, args.port, BACKEND))
    print('按 Ctrl+C 停止')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')


if __name__ == '__main__':
    main()
