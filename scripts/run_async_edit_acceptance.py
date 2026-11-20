"""Real browser UI regression with explicitly injected offline AI and held HTTP replies.

No store functions are called from page.evaluate. Each run starts its own services
and SQLite database below ignored output/playwright, leaving existing services alone.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback

import httpx
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
MATERIAL = ('资料一\n山东省潍坊市杨家埠的一种民间版画\n来源：回归资料一\n\n'
            '资料二\n杨家埠木版年画分钩描、刻版、印刷3道工序\n来源：回归资料二')


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Runner:
    def __init__(self, output):
        self.output = output
        self.backend_port, self.front_port = free_port(), free_port()
        self.base = f'http://127.0.0.1:{self.backend_port}'
        self.front = f'http://127.0.0.1:{self.front_port}'
        self.env = {**os.environ, 'DRAFT_DB_PATH': str(output / 'test.sqlite3'), 'PYTHONUTF8': '1',
                    'PYTHONDONTWRITEBYTECODE': '1', 'VITE_USE_MOCK': 'false', 'VITE_PROXY_TARGET': self.base}
        for key in ('AI_API_KEY', 'AI_MODEL', 'AI_BASE_URL', 'AI_VERIFY_MODEL'):
            self.env.pop(key, None)
        self.client = httpx.Client(base_url=self.base, timeout=10)
        self.processes, self.logs = [], []
        self.results = []

    def start(self, command, cwd, name, url):
        log = (self.output / (name + '.log')).open('w', encoding='utf8'); self.logs.append(log)
        p = subprocess.Popen(command, cwd=cwd, env=self.env, stdout=log, stderr=log,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.processes.append(p)
        for _ in range(150):
            if p.poll() is not None:
                raise RuntimeError(f'{name} exited; inspect {log.name}')
            try:
                if httpx.get(url, timeout=.5).status_code == 200:
                    return p
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        raise RuntimeError(f'{name} did not start')

    def backend(self, name='backend'):
        return self.start([sys.executable, '-m', 'uvicorn', 'scripts.async_edit_fixture:app',
                           '--host', '127.0.0.1', '--port', str(self.backend_port)], ROOT, name, self.base+'/api/drafts')

    def get(self, id):
        r = self.client.get('/api/drafts/'+id); r.raise_for_status(); return r.json()

    def seed(self, marker):
        r = self.client.post('/api/generate', json={'material': MATERIAL, 'requirement': '介绍工序，不新增事实。', 'platform': 'xiaohongshu'})
        r.raise_for_status(); d = r.json()
        assert d['mode'] == 'mock' and d['ai_meta']['mode'] == 'fixture'
        edits = [{'id': s['id'], 'text': s['text']} for s in d['segments']]
        edits[0]['text'] = marker
        r = self.client.put('/api/drafts/'+d['draft_id'], json={'base_version': d['version'], 'segments': edits})
        r.raise_for_status(); return d['draft_id']

    def open(self, page, marker, expected_text=None):
        page.locator('.conv-item:not(.is-new)').filter(has_text=marker).click()
        if page.get_by_role('dialog').is_visible():
            page.get_by_role('button', name='确认', exact=True).click()
        expect(page.locator('.composer-input')).to_be_visible()
        expect(page.locator('article')).to_contain_text(expected_text or marker)

    def hold(self, page, suffix, method, before_fetch=False):
        held = []
        pattern = '**/api/drafts/'+suffix
        def handler(route):
            if route.request.method != method:
                route.continue_(); return
            response = None if before_fetch else route.fetch()
            held.append((route, response))
        page.route(pattern, handler)
        def ready():
            deadline = time.monotonic()+10
            while not held and time.monotonic() < deadline:
                page.wait_for_timeout(20)
            assert held, 'HTTP reply gate not reached'
        def release(status=None):
            ready(); route, response = held.pop(0)
            with page.expect_response(lambda r: r.request.method == method and r.url.endswith('/api/drafts/'+suffix)):
                if status:
                    route.fulfill(status=status, content_type='application/json', body=json.dumps({'detail': {'code': 'TEST_FAILURE', 'message': '故障模拟，未确认成功'}}))
                else:
                    route.fulfill(response=response)
            page.unroute(pattern, handler)
            # Let the completed fetch/JSON promise and Vue microtasks consume the
            # released reply. Ordering itself is controlled by the explicit gate.
            page.wait_for_timeout(50)
        return ready, release

    def edit(self, page, text, index=0):
        if not page.locator('.fe-input').count():
            page.get_by_role('button', name='在右栏编辑', exact=True).click()
        page.locator('.fe-input').nth(index).fill(text)

    def r1(self, page, structure=False, roundtrip=False):
        marker = '结构回归稿' if structure else '追问回归稿'+('文字往返' if roundtrip else '')
        id = self.seed(marker); page.goto(self.front); self.open(page, marker)
        self.edit(page, marker)
        ready, release = self.hold(page, id+'/refine', 'POST')
        page.locator('.composer-input').fill('删除第二段' if structure else '压缩第二段')
        page.get_by_role('button', name='发送', exact=True).click(); ready()
        text = marker if roundtrip else '追问提交以后才输入的人工文字，必须完整保留。'
        if roundtrip:self.edit(page,'临时输入后改回提交时文本')
        self.edit(page, text, 1 if structure else 0)
        release()
        expect(page.locator('.composer-input')).to_be_enabled()
        expect(page.locator('.fe-input').first).to_be_visible()
        texts = '\n'.join(el.input_value() for el in page.locator('.fe-input').all())
        assert text in texts, 'late refine receipt deleted the new human text'
        expect(page.get_by_text('有未保存的修改，导出的将是上一次保存的版本', exact=True)).to_be_visible()
        if structure:
            assert '结构冲突' in texts
            assert '段落结构' in page.locator('.toast').inner_text()
        assert all(text not in s['text'] for s in self.get(id)['segments']), 'later edit must not be falsely acknowledged'
        with page.expect_response(lambda r: r.request.method == 'PUT' and r.url.endswith('/'+id)) as response:
            page.get_by_role('button', name='保存草稿', exact=True).last.click()
        assert response.value.status == 200
        assert any(text in s['text'] for s in self.get(id)['segments'])
        return {'draft_id': id, 'manual_text_preserved_and_then_saved': True, 'structure_conflict': structure,'typed_back_to_snapshot':roundtrip}

    def r2(self, page):
        a, b = self.seed('保存旧稿A'), self.seed('保存目标B')
        page.goto(self.front); self.open(page, '保存旧稿A'); self.edit(page, 'A提交快照')
        ready, release = self.hold(page, a, 'PUT')
        page.get_by_role('button', name='保存草稿', exact=True).last.click(); ready()
        self.open(page, '保存目标B'); self.edit(page, 'B独立人工新句，旧稿回执不能确认此句已保存。')
        release(); expect(page.get_by_role('button', name='保存草稿', exact=True).last).to_be_enabled()
        assert self.get(b)['segments'][0]['text'] == '保存目标B'
        expect(page.get_by_text('有未保存的修改，导出的将是上一次保存的版本', exact=True)).to_be_visible()
        assert page.locator('.fe-input').first.input_value() == 'B独立人工新句，旧稿回执不能确认此句已保存。'
        with page.expect_response(lambda r: r.request.method == 'PUT' and r.url.endswith('/'+b)) as saved:
            page.get_by_role('button', name='保存草稿', exact=True).last.click()
        assert saved.value.status == 200
        page.reload(); self.open(page, 'B独立人工新句')
        expect(page.locator('article')).to_contain_text('B独立人工新句')
        page.get_by_role('button', name='S2', exact=True).click(); expect(page.locator('.drawer')).to_contain_text('钩描、刻版、印刷3道工序')
        page.get_by_role('button', name='关闭', exact=True).click()
        page.get_by_role('button', name='.txt 文案正文 逐段改写；依据随改随核 ↗', exact=True).click()
        with page.expect_response(lambda r: r.url.endswith('/export')) as exported, page.expect_download() as download:
            page.get_by_role('button', name='下载', exact=True).click()
        assert exported.value.status == 200
        path = self.output / 'actual-download.txt'; download.value.save_as(path)
        assert path.read_text(encoding='utf-8-sig') == exported.value.json()['content']
        d = self.get(b); assert d['segments'][0]['review_status'] == 'edited_needs_review'
        assert d['segments'][1]['claims'][0]['quotes']
        return {'draft_id': b, 'save_refresh_download': True, 'download_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def submit(self, page, kind, instruction='压缩第二段'):
        if kind == 'save':
            page.get_by_role('button', name='保存草稿', exact=True).last.click()
        else:
            page.locator('.composer-input').fill(instruction)
            page.get_by_role('button', name='发送', exact=True).click()

    def receipt_gate(self, page, id, kind, before_fetch=False):
        return self.hold(page, id+('/refine' if kind=='refine' else ''), 'POST' if kind=='refine' else 'PUT', before_fetch)

    def settled(self, page, kind):
        if kind == 'refine':
            expect(page.locator('.composer-input')).to_be_enabled()
        else:
            expect(page.get_by_role('button', name='保存草稿', exact=True).last).to_be_enabled()

    def failure(self, page, kind):
        marker = kind+'失败回归稿'; id=self.seed(marker)
        page.goto(self.front); self.open(page, marker); self.edit(page, '失败请求已提交的文本')
        before=self.get(id); ready,release=self.receipt_gate(page,id,kind,True)
        self.submit(page,kind,'失败后应保留的追问输入');ready()
        text='请求等待时继续输入，即使失败也不能丢。';self.edit(page,text)
        release(502);self.settled(page,kind)
        assert page.locator('.fe-input').first.input_value()==text
        assert self.get(id)==before
        assert '故障模拟，未确认成功' in page.locator('body').inner_text()
        if kind=='refine':
            assert page.locator('.composer-input').input_value()=='失败后应保留的追问输入'
        with page.expect_response(lambda r:r.request.method==('PUT' if kind=='save' else 'POST') and r.url.endswith('/api/drafts/'+id+('/refine' if kind=='refine' else ''))) as retried:
            self.submit(page,kind,'失败后应保留的追问输入')
        assert retried.value.status==200;self.settled(page,kind)
        if kind=='save': assert self.get(id)['segments'][0]['text']==text
        else: assert any(e['after']==text for e in self.get(id)['history'][-1]['page_edits'])
        return {'draft_id':id,'failed_request_preserved_input':True,'retry_status':200}

    def order(self,page,kind,new_first):
        prefix=kind+('乱序成功' if new_first else '旧失败')
        marker_a,marker_b=prefix+'A',prefix+'B';a,b=self.seed(marker_a),self.seed(marker_b)
        page.goto(self.front);self.open(page,marker_a);self.edit(page,marker_a+'提交')
        ready_a,release_a=self.receipt_gate(page,a,kind,not new_first)
        self.submit(page,kind,'压缩第二段');ready_a()
        self.open(page,marker_b);self.edit(page,marker_b+'提交')
        ready_b,release_b=self.receipt_gate(page,b,kind)
        self.submit(page,kind,'再压缩第二段');ready_b()
        if new_first:
            release_b();self.settled(page,kind)
            header=page.locator('header').inner_text();body=page.locator('article').inner_text()
            release_a()
            assert page.locator('header').inner_text()==header, 'late receipt changed current header'
            assert page.locator('article').inner_text()==body, 'late receipt changed current body'
        else:
            release_a(502)
            # Old catch/finally must not clear the new request's busy/error state.
            if kind=='refine': expect(page.locator('.composer-input')).to_be_disabled()
            else: expect(page.get_by_role('button',name='保存中…',exact=True).last).to_be_disabled()
            assert '故障模拟，未确认成功' not in page.locator('body').inner_text(), 'old error leaked into new view'
            release_b();self.settled(page,kind)
        assert b in page.locator('header').inner_text(), 'active draft changed after old receipt'
        return {'draft_id':b,'kind':kind,'new_reply_first':new_first,'old_receipt_did_not_change_new_view':True}

    def back(self,page,kind):
        marker_a,marker_b=kind+'切回A',kind+'切回B';a,b=self.seed(marker_a),self.seed(marker_b)
        page.goto(self.front);self.open(page,marker_a);self.edit(page,marker_a+'提交')
        ready,release=self.receipt_gate(page,a,kind);self.submit(page,kind);ready()
        self.open(page,marker_b)
        current=self.get(a);self.open(page,marker_a,current['segments'][0]['text'])
        text='切回原草稿后重新输入的人工文字。';self.edit(page,text)
        release();assert page.locator('.fe-input').first.input_value()==text
        expect(page.get_by_text('有未保存的修改，导出的将是上一次保存的版本',exact=True)).to_be_visible()
        with page.expect_response(lambda r:r.request.method=='PUT' and r.url.endswith('/'+a)) as saved:
            self.submit(page,'save')
        assert saved.value.status==200
        assert self.get(a)['segments'][0]['text']==text
        return {'draft_id':a,'new_view_edits_preserved':True}

    def save_later(self,page):
        marker='同稿保存后续编辑';id=self.seed(marker);page.goto(self.front);self.open(page,marker)
        self.edit(page,'本次实际提交的第一句');ready,release=self.receipt_gate(page,id,'save')
        self.submit(page,'save');ready();text='保存提交后继续输入的第二句。';self.edit(page,text);release();self.settled(page,'save')
        assert self.get(id)['segments'][0]['text']=='本次实际提交的第一句'
        assert page.locator('.fe-input').first.input_value()==text
        expect(page.get_by_text('有未保存的修改，导出的将是上一次保存的版本',exact=True)).to_be_visible()
        with page.expect_response(lambda r:r.request.method=='PUT' and r.url.endswith('/'+id)) as saved:self.submit(page,'save')
        assert saved.value.status==200 and self.get(id)['segments'][0]['text']==text
        return {'draft_id':id,'only_submitted_snapshot_acknowledged':True}

    def stop(self,p):
        if p.poll() is None:
            if os.name=='nt':
                subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
            else:p.terminate()
            p.wait(10)

    def run(self, cases):
        backend = self.backend()
        self.start(['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', str(self.front_port), '--strictPort'], ROOT/'frontend', 'frontend', self.front)
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge', headless=False)
            for case in cases:
                page = browser.new_page(viewport={'width': 1600, 'height': 1000})
                page.set_default_timeout(8000)
                try:
                    if case=='r2':result=self.r2(page)
                    elif case in ('r1','structure','roundtrip'):result=self.r1(page,case=='structure',case=='roundtrip')
                    elif case=='save-later':result=self.save_later(page)
                    else:
                        kind,variant=case.split(':')
                        if variant=='failure':result=self.failure(page,kind)
                        elif variant=='back':result=self.back(page,kind)
                        else:result=self.order(page,kind,variant=='new-first')
                    self.results.append({'case': case, 'passed': True, **result})
                except Exception as e:
                    self.results.append({'case': case, 'passed': False, 'error': str(e), 'traceback': traceback.format_exc()})
                page.screenshot(path=str(self.output/(case.replace(':','-')+'.png')), full_page=True); page.close()
            if all(r['passed'] for r in self.results):
                before = {r['draft_id']: self.get(r['draft_id']) for r in self.results}
                self.stop(backend)
                try:httpx.get(self.base+'/api/drafts',timeout=1)
                except httpx.HTTPError:pass
                else:raise AssertionError('old backend still serves; restart not verified')
                restarted = self.backend('backend-restarted')
                after = {id: self.get(id) for id in before}
                assert before == after
                for name,data in [('before-restart',before),('after-restart',after)]:
                    (self.output/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
                view_id=next((r['draft_id'] for r in self.results if r['case']=='r2'),next(iter(after)))
                page=browser.new_page(viewport={'width':1600,'height':1000});page.goto(self.front)
                listing=self.client.get('/api/drafts').json();index=next(i for i,d in enumerate(listing) if d['draft_id']==view_id)
                page.locator('.conv-item:not(.is-new)').nth(index).click()
                expect(page.locator('header')).to_contain_text(view_id)
                expect(page.locator('article')).to_contain_text(after[view_id]['segments'][0]['text'])
                page.get_by_role('button',name='.txt 文案正文 逐段改写；依据随改随核 ↗',exact=True).click()
                with page.expect_response(lambda r:r.url.endswith('/export')) as exported,page.expect_download() as downloaded:
                    page.get_by_role('button',name='下载',exact=True).click()
                assert exported.value.status==200
                actual=self.output/'actual-download-after-restart.txt';downloaded.value.save_as(actual)
                assert actual.read_text(encoding='utf-8-sig')==exported.value.json()['content']
                page.screenshot(path=str(self.output/'after-restart.png'),full_page=True);page.close()
                self.results.append({'case': 'same-db-process-restart', 'passed': True, 'before_pid': backend.pid, 'after_pid': restarted.pid,
                                     'versions': {id:d['version'] for id,d in after.items()},'browser_read_and_actual_download':True,
                                     'download_sha256':hashlib.sha256(actual.read_bytes()).hexdigest()})
            browser.close()

    def close(self):
        for p in reversed(self.processes):
            self.stop(p)
        for log in self.logs: log.close()
        self.client.close()


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--cases', default='r1,r2,structure,roundtrip,save-later,save:failure,refine:failure,save:new-first,refine:new-first,save:old-error,refine:old-error,save:back,refine:back'); parser.add_argument('--output')
    args=parser.parse_args()
    output=Path(args.output).resolve() if args.output else ROOT/'output/playwright'/datetime.now().strftime('async-%Y%m%d-%H%M%S')
    output.mkdir(parents=True, exist_ok=True)
    runner=Runner(output)
    try: runner.run(args.cases.split(','))
    finally:
        runner.close()
        report={'mode':'offline-fixture-NOT-LIVE','results':runner.results}
        (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if runner.results and all(r['passed'] for r in runner.results) else 1


if __name__=='__main__':
    raise SystemExit(main())
