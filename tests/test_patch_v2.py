import os, re, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PATCH = os.path.join(ROOT, 'scripts', 'sharp_money_card', 'patch_v2.py')
INDEX = os.path.join(ROOT, 'sharp-money', 'index.html')


def run(path):
    return subprocess.run([sys.executable, PATCH, '--file', path], capture_output=True, text=True)


class PatchV2(unittest.TestCase):
    def test_idempotent_and_the_bundle_still_parses(self):
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
            for needle in ('<script src="v2/gates.js">', '<script src="v2-pages.js">', 'window.__smKit=', '["Plays","Prices that clear every gate"', 'k.page==="plays"', '#(plays|signals|record)'):
                self.assertIn(needle, once, needle)
            js = [x for x in re.findall(r'<script>(.*?)</script>', once, flags=re.S) if 'function Kf' in x][0]
            f = os.path.join(d, 'bundle.js')
            open(f, 'w', encoding='utf-8').write(js)
            r = subprocess.run(['node', '--check', f], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_an_anchor_that_moved_fails_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'index.html')
            open(p, 'w').write('<html><script>var x=1</script></html>')
            r = run(p)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('anchor found 0 times', r.stderr)


if __name__ == '__main__':
    unittest.main()
