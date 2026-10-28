"""Baseline: git-recap's committed example/recap.json for its deterministic demo repo (scripts/make-demo-repo.mjs).
make_demo_repo() is a Python port of that script; analyze() and verdict() must reproduce every number."""
import contextlib, io, json, subprocess, sys, tempfile, unittest, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import repo_wrapped as rw

UPSTREAM = json.loads((ROOT / 'tests' / 'upstream' / 'git-recap-demo-recap.json').read_text(encoding='utf-8'))

class DemoRepo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls.tmp.name) / 'demo-repo'
        cls.n = rw.make_demo_repo(cls.repo)
        cls.commits = rw.read_log(cls.repo)
        cls.stats = rw.analyze(cls.commits, today='2026-10-27')

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_same_commits_as_upstream_generator(self):
        self.assertEqual(self.n, 970); self.assertEqual(len(self.commits), 970)

    def test_every_stat_matches_git_recap(self):
        for key, want in UPSTREAM.items():
            if key in ('repo', 'verdict', 'currentStreak'): continue
            with self.subTest(key=key): self.assertEqual(self.stats[key], want)

    def test_verdict_matches_git_recap(self):
        v = rw.verdict(self.stats)
        for key in ('key', 'score', 'title', 'emoji'): self.assertEqual(v[key], UPSTREAM['verdict'][key])

    def test_author_and_year_filters(self):
        sam = rw.analyze(rw.read_log(self.repo, author='sam@demo.io'))
        self.assertEqual(sam['total'], 304); self.assertEqual(len(sam['authors']), 1)
        y25 = rw.analyze(rw.read_log(self.repo, since='2025-01-01', until='2025-12-31'))
        self.assertEqual(y25['total'], sum(n for m, n in UPSTREAM['monthCounts'].items() if m.startswith('2025')))

    def test_poster_is_valid_svg_with_the_numbers(self):
        v = rw.verdict(self.stats)
        svg = rw.poster(self.stats, v, 'demo-repo', '2024-2026')
        root = ET.fromstring(svg)
        self.assertEqual((root.get('width'), root.get('height')), ('1080', '1350'))
        self.assertIn('970', svg); self.assertIn('The Midnight Architect', svg)

class Units(unittest.TestCase):
    def test_rename_paths(self):
        self.assertEqual(rw.new_path('src/{a.ts => b.ts}'), 'src/b.ts')
        self.assertEqual(rw.new_path('{old => new}/x.py'), 'new/x.py')
        self.assertEqual(rw.new_path('a.md => b.md'), 'b.md')
        self.assertEqual(rw.new_path('plain.py'), 'plain.py')

    def test_mulberry32_matches_js(self):
        # first values of git-recap's mulberry32(42), computed with Node's Math.imul semantics
        r = rw.mulberry32(42)
        self.assertEqual([r() for _ in range(4)], [0.6011037519201636, 0.44829055899754167, 0.8524657934904099, 0.6697340414393693])

    def test_fallback_verdicts(self):
        s = dict(total=150, nightPct=0, earlyPct=0, weekendPct=0, fixPct=0, docsPct=0, lingo=dict(wip=0, fix=0, docs=0),
                 longestStreak=1, firstCommit=dict(date='2026-01-01'), lastCommit=dict(date='2026-12-31'), authors=[{}])
        self.assertEqual(rw.verdict(s)['key'], 'solo')
        self.assertEqual(rw.verdict(dict(s, authors=[{}, {}]))['key'], 'force')

    def test_lockfiles_do_not_count(self):
        c = [dict(hash='h', name='A', email='a@x', day='2026-01-01', hour=10, subject='bump',
                  files=[('package-lock.json', 5000, 0, False), ('src/a.py', 3, 1, False)])]
        s = rw.analyze(c)
        self.assertEqual((s['ins'], s['del'], [l['name'] for l in s['langs']]), (3, 1, ['Python']))

class Cli(unittest.TestCase):
    def test_no_repo_message(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(SystemExit) as e:
            rw.main([d])
        self.assertIn('No git repositories', str(e.exception))

if __name__ == '__main__':
    unittest.main()
