import os, re, shutil, subprocess, sys, tempfile, unittest, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PATCH = os.path.join(ROOT, 'scripts', 'sharp_money_card', 'patch_control_room.py')
INDEX = os.path.join(ROOT, 'sharp-money', 'index.html')
SMNAV = os.path.join(HERE, 'smnav_parse.mjs')


def run(path):
    return subprocess.run([sys.executable, PATCH, '--file', path], capture_output=True, text=True)


def parse_smnav(html):
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as fh:
        fh.write(html)
        path = fh.name
    r = subprocess.run(['node', SMNAV, path], capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError('SmNav eval failed: ' + r.stderr + r.stdout)
    data = json.loads(r.stdout)
    return data['sections'], data['items'], data['arities']


EDGE_ITEM = '["Edge Board","Novig against Pinnacle, biggest +EV",U.createElement(U.Fragment,null,U.createElement("path",{d:"M3 17l6-6 4 4 8-8"}),U.createElement("path",{d:"M15 7h6v6"}))'
NAV_OK_HEAD = EDGE_ITEM + ']]],["System",'
NAV_BROKEN_HEAD = EDGE_ITEM + ']],["System",'
NAV_OK_TAIL = 'rx:1}))]]]];'
NAV_BROKEN_TAIL = 'rx:1}))]]]]];'


class PatchControlRoom(unittest.TestCase):
    def test_idempotent_and_SmNav_has_a_top_level_System_section(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'index.html')
            shutil.copy(INDEX, p)
            first = run(p)
            self.assertEqual(first.returncode, 0, first.stderr)
            once = open(p, encoding='utf-8').read()
            second = run(p)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn('done, 0 change(s)', second.stdout)
            self.assertEqual(once, open(p, encoding='utf-8').read())
            for needle in ('control-room.js?v=1', 'control-room.css?v=1', 'function VaultControlPage',
                           'k.page==="control"', '#control', 'VaultControlPage,{D:o}'):
                self.assertIn(needle, once, needle)
            sections, system_items, arities = parse_smnav(once)
            self.assertIn('Markets', sections)
            self.assertIn('Reads', sections)
            self.assertIn('System', sections)
            self.assertEqual(sections[-1], 'System')
            self.assertIn('Control Room', system_items)
            self.assertEqual(arities['Reads'], 2)
            self.assertEqual(arities['System'], 2)
            self.assertEqual(arities['Markets'], 2)
            js = [x for x in re.findall(r'<script>(.*?)</script>', once, flags=re.S) if 'function VaultControlPage' in x or 'var SmNav=' in x]
            self.assertTrue(js)
            for block in js:
                f = os.path.join(d, 'bundle.js')
                open(f, 'w', encoding='utf-8').write(block)
                r = subprocess.run(['node', '--check', f], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_repairs_a_nested_System_section(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'index.html')
            shutil.copy(INDEX, p)
            text = open(p, encoding='utf-8').read()
            self.assertIn(NAV_OK_HEAD, text)
            self.assertIn(NAV_OK_TAIL, text)
            text = text.replace(NAV_OK_HEAD, NAV_BROKEN_HEAD, 1).replace(NAV_OK_TAIL, NAV_BROKEN_TAIL, 1)
            open(p, 'w', encoding='utf-8').write(text)
            _, _, broken_arities = parse_smnav(text)
            self.assertNotEqual(broken_arities.get('Reads'), 2)
            r = run(p)
            self.assertEqual(r.returncode, 0, r.stderr)
            sections, items, arities = parse_smnav(open(p, encoding='utf-8').read())
            self.assertEqual(arities['Reads'], 2)
            self.assertEqual(arities['System'], 2)
            self.assertIn('Control Room', items)
            self.assertEqual(sections[-1], 'System')

    def test_an_anchor_that_moved_fails_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'index.html')
            open(p, 'w').write('<html><script>var x=1</script></html>')
            r = run(p)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('anchor found 0 times', r.stderr)


if __name__ == '__main__':
    unittest.main()
