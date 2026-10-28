#!/usr/bin/env python3
"""repo-wrapped: your year in git as a shareable poster (SVG) plus the raw stats (JSON).

Stats and verdict ported from sutharsan-311/git-recap (MIT); year window, author default and
multi-repo scan from wheatcore/git-wrapped (MIT). Standard library only, no network.
"""
import argparse, datetime as dt, json, os, re, subprocess, sys
from pathlib import Path

LANGS = dict(js=('JavaScript', '#f7df1e'), mjs=('JavaScript', '#f7df1e'), cjs=('JavaScript', '#f7df1e'), jsx=('JSX', '#61dafb'),
             ts=('TypeScript', '#3178c6'), tsx=('TypeScript', '#41b0ff'), py=('Python', '#3776ab'), pyw=('Python', '#3776ab'),
             ipynb=('Jupyter', '#f37626'), go=('Go', '#00add8'), rs=('Rust', '#dea584'), java=('Java', '#e76f00'), kt=('Kotlin', '#a97bff'),
             kts=('Kotlin', '#a97bff'), rb=('Ruby', '#cc342d'), php=('PHP', '#777bb4'), cs=('C#', '#68217a'), c=('C', '#555555'),
             h=('C', '#555555'), cpp=('C++', '#f34b7d'), cc=('C++', '#f34b7d'), cxx=('C++', '#f34b7d'), hpp=('C++', '#f34b7d'),
             m=('Objective-C', '#438eff'), mm=('Objective-C', '#438eff'), swift=('Swift', '#f05138'), scala=('Scala', '#c22d40'),
             dart=('Dart', '#00b4ab'), lua=('Lua', '#000080'), ex=('Elixir', '#6e4a7e'), exs=('Elixir', '#6e4a7e'), erl=('Erlang', '#b83983'),
             hs=('Haskell', '#5e5086'), ml=('OCaml', '#ef7a08'), clj=('Clojure', '#db5855'), elm=('Elm', '#60b5cc'), r=('R', '#276dc3'),
             jl=('Julia', '#a270ba'), pl=('Perl', '#39457e'), sh=('Shell', '#89e051'), bash=('Shell', '#89e051'), zsh=('Shell', '#89e051'),
             fish=('Shell', '#89e051'), ps1=('PowerShell', '#012456'), vue=('Vue', '#41b883'), svelte=('Svelte', '#ff3e00'),
             astro=('Astro', '#ff5d01'), html=('HTML', '#e34c26'), htm=('HTML', '#e34c26'), css=('CSS', '#563d7c'), scss=('SCSS', '#c6538c'),
             sass=('Sass', '#cc6699'), less=('Less', '#1d365d'), md=('Markdown', '#8da0c7'), mdx=('MDX', '#fcb32c'), json=('JSON', '#cbcb41'),
             jsonc=('JSON', '#cbcb41'), yaml=('YAML', '#cb171e'), yml=('YAML', '#cb171e'), toml=('TOML', '#9c4221'), xml=('XML', '#0060ac'),
             sql=('SQL', '#e38c00'), graphql=('GraphQL', '#e10098'), gql=('GraphQL', '#e10098'), sol=('Solidity', '#8c8c8c'),
             tf=('Terraform', '#7b42bc'), proto=('Protobuf', '#4a88c7'), vim=('Vim Script', '#199f4b'), zig=('Zig', '#f7a41d'),
             nim=('Nim', '#ffe953'), groovy=('Groovy', '#4298b8'), tex=('TeX', '#3d6117'), txt=('Text', '#9aa4b2'))
GENERATED = re.compile(r'(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb|composer\.lock|Cargo\.lock|Gemfile\.lock|poetry\.lock|Pipfile\.lock|go\.sum)$'
                       r'|(^|/)(node_modules|bower_components|vendor|third_party|dist|build|\.next|out)/|\.min\.(js|css)$|\.map$')
SKIP_DIRS = {'node_modules', 'vendor', 'dist', 'build', 'target', 'venv', '.venv', '__pycache__', 'Library', 'snap', 'go', 'AppData'}
# Extended_Pictographic, approximated with the emoji blocks (re has no \p{...})
EMOJI = re.compile('[©®‼⁉™ℹ↔-↪⌚-⏿Ⓜ▪-➿⤴⤵⬅-⭕〰〽㊗㊙\U0001f000-\U0001faff]')
STOP = {'the', 'a', 'an', 'and', 'for', 'with', 'this', 'that', 'to', 'of', 'in', 'on'}

def git(repo, *args):
    r = subprocess.run(['git', '-C', str(repo), '-c', 'core.quotepath=false', *args], capture_output=True, encoding='utf-8', errors='replace')
    if r.returncode: raise SystemExit(f'git {args[0]} failed in {repo}: {r.stderr.strip()}')
    return r.stdout

def is_repo(d):
    g = Path(d, '.git')
    return g.is_file() or (g / 'HEAD').exists()

def find_repos(root, depth=3):
    """Every repo under root, at most depth levels down; a repo is not searched further."""
    found = []
    def walk(d, level):
        if is_repo(d): found.append(d); return
        if level >= depth: return
        try: entries = sorted(os.scandir(d), key=lambda e: e.name)
        except OSError: return
        for e in entries:
            if e.is_dir() and not e.name.startswith('.') and e.name not in SKIP_DIRS: walk(e.path, level + 1)
    walk(str(root), 0)
    return found

def new_path(p):
    """numstat 'path' | 'old => new' | 'dir/{old => new}/file' -> the new path"""
    s = p.strip()
    m = re.match(r'^(.*)\{(.*) => (.*)\}(.*)$', s)
    if m: return (m[1] + m[3] + m[4]).replace('//', '/').strip('"')
    return s.split(' => ')[-1].strip('"')

def read_log(repo, author=None, since=None, until=None, all_branches=False):
    """Commits by AUTHOR date (same field the poster buckets by), window applied here, not by git."""
    args = ['log', '--pretty=format:%x01%H%x02%aN%x03%aE%x04%aI%x05%s', '--numstat', '--no-color']
    if all_branches: args.append('--all')
    if author: args.append(f'--author={author}')
    out = []
    for rec in git(repo, *args).split('\x01'):
        if not rec: continue
        header, _, body = rec.partition('\n')
        parts = re.split('[\x02\x03\x04\x05]', header)
        if len(parts) < 5 or not parts[0] or not parts[3]: continue
        h, name, email, date, subject = parts[:5]
        if since and date[:10] < since or until and date[:10] > until: continue
        files = []
        for line in body.split('\n'):
            m = re.match(r'^(-|\d+)\t(-|\d+)\t(.*)$', line)
            if m: files.append((new_path(m[3]), 0 if m[1] == '-' else int(m[1]), 0 if m[2] == '-' else int(m[2]), m[1] == '-'))
        out.append(dict(hash=h, name=name or 'unknown', email=(email or 'unknown').lower(), day=date[:10],
                        hour=int(date[11:13]) if date[11:13].isdigit() else 0, subject=subject, files=files))
    return out

def ordinal(day): return dt.date.fromisoformat(day).toordinal()

def analyze(commits, today=None):
    daily, months, authors, files, langs, verbs = {}, {}, {}, {}, {}, {}
    hours, weekdays = [0] * 24, [0] * 7
    lingo = dict(wip=0, final=0, oops=0, fix=0, docs=0, emoji=0, dot=0, revert=0)
    ins = dele = 0; first = last = None; longest, shortest = '', None
    for c in commits:
        d = c['day']; daily[d] = daily.get(d, 0) + 1; hours[c['hour']] += 1
        weekdays[(dt.date.fromisoformat(d).weekday() + 1) % 7] += 1  # 0 = Sunday
        months[d[:7]] = months.get(d[:7], 0) + 1
        a = authors.setdefault(c['email'], dict(name=c['name'], email=c['email'], commits=0)); a['commits'] += 1
        if not first or d < first['day']: first = c
        if not last or d > last['day']: last = c
        s = c['subject'].strip(); low = s.lower()
        if len(s) > len(longest): longest = s
        if s and (shortest is None or len(s) < len(shortest)): shortest = s
        bare = re.sub(r'^\s*(feat|fix|bugfix|hotfix|chore|docs?|refactor|test|style|perf|build|ci)(\(|:)\s*', '', low)
        word = re.sub(r"[^a-z0-9']", '', (re.split(r'[\s(（]+', bare) or [''])[0])
        if word and word != 'merge': verbs[word] = verbs.get(word, 0) + 1
        lingo['fix'] += bool(re.match(r'(fix|bugfix|hotfix|patch)\b', low)); lingo['docs'] += bool(re.match(r'docs?\b', low))
        lingo['wip'] += bool(re.match(r'(wip|draft)\b', s, re.I)); lingo['final'] += bool(re.search(r'\bfinal\b', s, re.I))
        lingo['oops'] += bool(re.search(r'\b(oops|typo|ugh|damn|whoops|oopsie)\b', s, re.I)); lingo['revert'] += bool(re.match(r'revert\b', s, re.I))
        lingo['emoji'] += bool(EMOJI.search(s)); lingo['dot'] += bool(re.fullmatch(r'\.+', s))
        for path, i, de, binary in c['files']:
            if GENERATED.search(path): continue  # lockfiles and vendored code are not lines you wrote
            f = files.setdefault(path, dict(path=path, commits=0, ins=0, **{'del': 0})); f['commits'] += 1; f['ins'] += i; f['del'] += de
            if binary: continue
            ins += i; dele += de
            base = path.rsplit('/', 1)[-1]; ext = base.rsplit('.', 1)[1].lower() if '.' in base[1:] else None
            if ext in LANGS:
                l = langs.setdefault(LANGS[ext][0], dict(name=LANGS[ext][0], color=LANGS[ext][1], ins=0, files=set())); l['ins'] += i; l['files'].add(path)
    days = sorted(daily); streak = run = 0; prev = None
    for d in days:
        run = run + 1 if prev and ordinal(d) - ordinal(prev) == 1 else 1; streak = max(streak, run); prev = d
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat(); current = 0
    if days and ordinal(today) - ordinal(days[-1]) <= 1:
        current = 1
        for a, b in zip(reversed(days[:-1]), reversed(days[1:])):
            if ordinal(b) - ordinal(a) != 1: break
            current += 1
    first_max = lambda d: max(d.items(), key=lambda kv: kv[1]) if d else None  # first key wins ties
    total = len(commits); pct = lambda n: n / total * 100 if total else 0
    ghost_hour = max(range(5), key=lambda h: (hours[h], -h)) if total else 0
    names = {w for a in authors.values() for w in re.split(r"[^a-z0-9']+", a['name'].lower()) if w}
    lang_total = sum(l['ins'] for l in langs.values())
    bd, bm = first_max(daily), first_max(months)
    return dict(total=total, ins=ins, **{'del': dele}, activeDays=len(daily),
                firstCommit=dict(date=first['day'], subject=first['subject']) if first else None,
                lastCommit=dict(date=last['day'], subject=last['subject']) if last else None,
                dailyCounts=daily, hourCounts=hours, weekdayCounts=weekdays, monthCounts=months,
                authors=sorted(authors.values(), key=lambda a: -a['commits']),
                files=sorted(({**f, 'churn': f['ins'] + f['del']} for f in files.values()), key=lambda f: -f['churn'])[:5],
                langs=[dict(name=l['name'], color=l['color'], ins=l['ins'], files=len(l['files']), share=l['ins'] / lang_total if lang_total else 0)
                       for l in sorted(langs.values(), key=lambda l: -l['ins'])],
                longestStreak=streak, currentStreak=current,
                busiestDay=dict(date=bd[0], count=bd[1]) if bd else None, busiestMonth=dict(month=bm[0], count=bm[1]) if bm else None,
                ghostCommits=sum(hours[:5]), ghostHour=ghost_hour,
                nightPct=pct(sum(hours[h] for h in range(24) if h >= 22 or h <= 4)), earlyPct=pct(sum(hours[5:9])),
                weekendPct=pct(weekdays[0] + weekdays[6]), fixPct=pct(lingo['fix']), docsPct=pct(lingo['docs']), lingo=lingo,
                topVerbs=[dict(word=w, n=n) for w, n in sorted(((w, n) for w, n in verbs.items() if len(w) > 1 and n > 1 and w not in names and w not in STOP),
                                                               key=lambda wn: -wn[1])[:5]],
                longestSubject=longest, shortestSubject=shortest or '', avgPerDay=total / len(daily) if daily else 0)

TYPICAL = dict(night=.15, early=.12, weekend=.15, fix=.20, docs=.06, wip=.02, streak=.03)

def verdict(s):
    """git-recap's verdict: the habit this history is most unusual on, vs a typical repo."""
    span = ordinal(s['lastCommit']['date']) - ordinal(s['firstCommit']['date']) + 1 if s['firstCommit'] else 0
    c = []
    def add(key, value, title, emoji, blurb, n=s['total']):
        score = value / TYPICAL[key]
        if n * TYPICAL[key] >= 5 and score > 1: c.append(dict(key=key, score=score, title=title, emoji=emoji, blurb=blurb))
    add('night', s['nightPct'] / 100, 'The Midnight Architect', '🦉', f"{round(s['nightPct'])}% of your commits shipped after 10pm. The best ideas don't sleep, and apparently neither do you.")
    add('early', s['earlyPct'] / 100, 'The Dawn Deployer', '🌅', f"{round(s['earlyPct'])}% of your commits landed before 9am. The early bird gets the merge.")
    add('weekend', s['weekendPct'] / 100, 'The Weekend Warrior', '⚔️', f"{round(s['weekendPct'])}% of your work happened on Saturdays and Sundays.")
    add('fix', s['fixPct'] / 100, 'The Firefighter', '🔥', f"{s['lingo']['fix']} commits started with \"fix\". You don't write bugs, you wrestle them.")
    add('docs', s['docsPct'] / 100, 'The Cartographer', '🗺️', f"{s['lingo']['docs']} documentation commits. The docs you wrote will guide strangers for years.")
    add('wip', s['lingo']['wip'] / max(s['total'], 1), 'The Eternal Draft', '✍️', f"{s['lingo']['wip']} commits literally titled \"wip\".")
    add('streak', s['longestStreak'] / span if span else 0, 'The Marathoner', '🏃', f"{s['longestStreak']} consecutive days of commits.", span)
    if c: return max(c, key=lambda x: x['score'])  # max keeps the first of equal scores, like a stable sort
    if len(s['authors']) == 1 and s['total'] >= 100:
        return dict(key='solo', title='The One-Person Army', emoji='🦾', blurb=f"{s['total']:,} commits, one set of hands. You are the team standup.")
    return dict(key='force', title='The Full-Stack Force', emoji='⚡', blurb='No habit stood out: a fairly typical rhythm. That is most repos, and most repos ship.')

PALETTE = dict(night=('#171A6B', '#F3F0E6', '#FFD166'), early=('#FF7A45', '#2A1204', '#FFFFFF'), weekend=('#0F8A5F', '#F1F8EF', '#FFE45E'),
               fix=('#D92D20', '#FFF2E8', '#FFD43B'), docs=('#1F6FEB', '#EFF6FF', '#FFCB47'), wip=('#8B45E8', '#F7EFFF', '#F7E463'),
               streak=('#0A7D8C', '#E9FBFF', '#FFB347'), solo=('#242424', '#F5F5F0', '#FF6B35'), force=('#2D2A26', '#F5F1E8', '#7CE0B5'))
FONT = "ui-monospace,'SF Mono','Cascadia Mono',Menlo,Consolas,monospace"

def esc(s): return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

def wrap(text, width):
    lines, cur = [], ''
    for w in text.split():
        if len(cur) + len(w) + 1 > width and cur: lines.append(cur); cur = w
        else: cur = f'{cur} {w}'.strip()
    return lines + [cur] if cur else lines

def poster(s, v, title, label):
    """A 1080x1350 poster: one giant number, the verdict, a 53-week heatmap, power hours, languages."""
    bg, ink, acc = PALETTE[v['key']]
    W, H = 1080, 1350; o = []; t = lambda x, y, txt, size, fill=ink, weight=400, anchor='start', op=1: o.append(
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" opacity="{op}">{esc(txt)}</text>')
    o.append(f'<rect width="{W}" height="{H}" fill="{bg}"/>')
    for i in range(0, W, 40): o.append(f'<rect x="{i}" y="0" width="20" height="20" fill="{ink}" opacity=".08"/><rect x="{i + 20}" y="20" width="20" height="20" fill="{ink}" opacity=".08"/>')
    t(72, 120, title, 34, weight=700); t(W - 72, 120, label, 28, anchor='end', op=.75)
    t(72, 330, f"{s['total']:,}", 200, acc, 800); t(80, 385, 'commits', 40, op=.85)
    t(72, 480, f"{v['emoji']} {v['title']}", 52, weight=800)
    for i, line in enumerate(wrap(v['blurb'], 44)): t(72, 535 + i * 40, line, 30, op=.9)
    # heatmap: last 53 weeks ending at the last commit
    end = dt.date.fromisoformat(s['lastCommit']['date']) if s['lastCommit'] else dt.date.today()
    start = end - dt.timedelta(days=end.weekday() + 1 + 52 * 7); peak = max(s['dailyCounts'].values() or [1]); y0 = 690
    t(72, y0 - 14, 'last 12 months', 24, op=.7)
    for k in range(53 * 7):
        d = start + dt.timedelta(days=k)
        if d > end: break
        n = s['dailyCounts'].get(d.isoformat(), 0)
        o.append(f'<rect x="{72 + (k // 7) * 17.6:.1f}" y="{y0 + (k % 7) * 17.6:.1f}" width="14" height="14" rx="3" fill="{acc if n else ink}" opacity="{(.35 + .65 * n / peak) if n else .1:.2f}"/>')
    # power hours
    y1 = 885; hp = max(s['hourCounts']) or 1
    t(72, y1 - 14, 'when you commit (hour of day)', 24, op=.7)
    for h, n in enumerate(s['hourCounts']):
        bh = 110 * n / hp
        o.append(f'<rect x="{72 + h * 39}" y="{y1 + 110 - bh:.1f}" width="30" height="{max(bh, 2):.1f}" rx="4" fill="{acc}" opacity="{.95 if n == hp else .6}"/>')
        if h % 6 == 0: t(72 + h * 39 + 15, y1 + 140, f'{h:02d}', 20, anchor='middle', op=.6)
    # languages + facts
    y2 = 1095; x = 72
    t(72, y2 - 14, 'languages (lines added)', 24, op=.7)
    for l in s['langs'][:5]:
        w = max(4, 936 * l['share']); o.append(f'<rect x="{x:.1f}" y="{y2}" width="{w:.1f}" height="26" fill="{l["color"]}"/>'); x += w
    for i, l in enumerate(s['langs'][:4]): t(72 + i * 240, y2 + 60, f"{l['name']} {round(l['share'] * 100)}%", 24, op=.85)
    facts = [f"{s['activeDays']} active days", f"longest streak {s['longestStreak']} days",
             f"busiest day {s['busiestDay']['date']} ({s['busiestDay']['count']})" if s['busiestDay'] else '']
    t(72, 1240, ' · '.join(f for f in facts if f), 24, op=.9)
    t(72, 1290, f"{s['lingo']['fix']} fixes · {s['lingo']['wip']} wips · {s['lingo']['oops']} oops · {s['lingo']['final']} finals", 24, op=.7)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" '
            f'aria-label="{esc(title)}: {s["total"]} commits, {esc(v["title"])}">' + ''.join(o) + '</svg>\n')

def terminal(s, v, title):
    bar = lambda n, m: '█' * round(20 * n / m) if m else ''
    top = '\n'.join(f"  {l['name']:<12} {bar(l['share'], 1):<20} {l['share'] * 100:4.0f}%" for l in s['langs'][:3])
    return (f"\n  {title}\n  {s['total']:,} commits on {s['activeDays']} days, {s['ins']:,} lines added\n"
            f"  {v['emoji']}  {v['title']}\n  {v['blurb']}\n\n{top}\n")

# ---- deterministic demo repo: a Python port of git-recap's scripts/make-demo-repo.mjs (same RNG, same commits) ----
def mulberry32(seed=42):
    s = seed
    def rnd():
        nonlocal s
        s = (s + 0x6D2B79F5) & 0xFFFFFFFF
        t = ((s ^ (s >> 15)) * (1 | s)) & 0xFFFFFFFF
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return rnd

def make_demo_repo(target):
    """~970 commits over ~2 years by three authors, written with one `git fast-import` (seconds, not minutes)."""
    target = Path(target); target.mkdir(parents=True, exist_ok=True)
    git(target, 'init', '-q')
    rnd = mulberry32(42); pick = lambda a: a[int(rnd() * len(a))]
    authors = [('Alex Rivera', 'alex@demo.io', True, .55), ('Sam Chen', 'sam@demo.io', False, .3), ('Jules Kim', 'jules@demo.io', False, .15)]
    files = [('src/app.ts', ['feat', 'fix', 'refactor', 'perf']), ('src/engine.ts', ['feat', 'fix', 'perf']), ('src/cli.ts', ['feat', 'fix', 'chore']),
             ('src/utils.ts', ['fix', 'refactor']), ('README.md', ['docs', 'chore', 'docs']), ('docs/architecture.md', ['docs', 'docs']),
             ('package.json', ['chore', 'fix']), ('src/styles.css', ['style', 'fix'])]
    subjects = dict(feat=['add streaming parser', 'implement retry queue', 'add --watch mode', 'support custom themes', 'add incremental indexing', 'wire up plugin hooks'],
                    fix=['fix off-by-one in parser', 'fix race in queue', 'fix broken symlink handling', 'fix crash on empty input', 'fix timezone bug', 'hotfix memory leak', 'fix flaky test'],
                    refactor=['refactor parser core', 'clean up engine', 'extract config module', 'simplify error paths'],
                    wip=['wip', 'wip: middleware', 'draft: new indexer', 'wip (do not review)'],
                    docs=['docs: update readme', 'docs: architecture notes', 'update contributing guide', 'fix typo in docs'],
                    chore=['bump deps', 'chore: release v0.3.0', 'update tooling'], style=['tweak spacing', 'fix hover state'],
                    perf=['speed up indexing 2x', 'cache file stats', 'lazy-load parser'], test=['add parser tests', 'test: cover edge cases'],
                    final=['final', 'FINAL final v2 (for real this time)', 'final fix, promise'], oops=['oops', 'typo', 'ugh fix indent', 'really final this time'])
    rate = dict(wip=.02, oops=.012, final=.008, emoji=.06, dot=.004)
    emoji = ['✨', '🔥', '🐛', '🚀', '💡']
    lines = ['let x = 0;', 'export function step() { return x++; }', '// TODO: make this faster', 'const cache = new Map();', 'if (!ready) return null;']
    content, stream, n = {}, [], 0
    base = dt.datetime(2024, 9, 1, tzinfo=dt.timezone.utc)
    for day in range(700):
        date = base + dt.timedelta(days=day)
        if rnd() < (.62 if date.weekday() >= 5 else .25): continue
        for _ in range(1 + int(rnd() * (6 if rnd() < .15 else 3))):
            r = rnd(); acc = 0; author = authors[0]
            for a in authors:
                acc += a[3]
                if r <= acc: author = a; break
            hour = pick([22, 23, 0, 1, 2, 3, 1, 2, 21, 20] if author[2] else [9, 10, 11, 14, 15, 16, 8, 20])
            minute = int(rnd() * 60)
            when = int((date + dt.timedelta(hours=hour, minutes=minute)).timestamp())
            f, verbs = pick(files); verb = pick(verbs)
            for flavour in ('wip', 'oops', 'final'):
                if rnd() < rate[flavour]: verb = flavour
            subject = pick(subjects.get(verb, ['update']))
            if rnd() < rate['emoji']: subject += ' ' + pick(emoji)
            if rnd() < rate['dot']: subject = '.'
            changed = {f}; content[f] = content.get(f, '') + pick(lines) + '\n'
            if n % 40 == 0: content['README.md'] = content.get('README.md', '') + f'\n## Notes {n}\nChangelog line {n}.\n'; changed.add('README.md')
            msg = subject.encode()
            ident = f'{author[0]} <{author[1]}> {when} +0000'
            stream.append(f'commit refs/heads/main\nauthor {ident}\ncommitter {ident}\ndata {len(msg)}\n'.encode() + msg + b'\n')
            for path in sorted(changed):
                data = content[path].encode(); stream.append(f'M 100644 inline {path}\ndata {len(data)}\n'.encode() + data + b'\n')
            n += 1
    subprocess.run(['git', '-C', str(target), 'fast-import', '--quiet'], input=b''.join(stream), check=True)
    git(target, 'symbolic-ref', 'HEAD', 'refs/heads/main')
    return n

def main(argv=None):
    ap = argparse.ArgumentParser(description='Your year in git as a shareable poster (SVG) and stats (JSON).')
    ap.add_argument('paths', nargs='*', help='repos, or folders with repos (3 levels deep); default: .')
    ap.add_argument('-y', '--year', type=int, help='year to wrap (default: all history)')
    ap.add_argument('--since'); ap.add_argument('--until')
    ap.add_argument('-a', '--author', help='author regex (default: everyone in one repo, you across several)')
    ap.add_argument('--all', action='store_true', help='every author, even across several repos')
    ap.add_argument('--all-branches', action='store_true')
    ap.add_argument('-o', '--out', default='repo-wrapped.svg'); ap.add_argument('--json', action='store_true')
    ap.add_argument('--demo', action='store_true', help="build git-recap's deterministic demo repo in ./demo-repo and wrap it")
    a = ap.parse_args(argv)
    if a.demo:
        if not is_repo('demo-repo'): print(f'demo repo: {make_demo_repo("demo-repo")} commits', file=sys.stderr)
        a.paths = ['demo-repo']
    since, until = a.since, a.until
    if a.year: since, until = since or f'{a.year}-01-01', until or f'{a.year}-12-31'
    repos = [r for p in (a.paths or ['.']) for r in find_repos(Path(p).expanduser())]
    if not repos: raise SystemExit('No git repositories found.')
    author = a.author
    if not author and not a.all and len(repos) > 1:  # profile mode: your own commits, like git-wrapped
        author = re.escape(git(repos[0], 'config', '--get', 'user.email').strip()) or None
    commits = [c for r in repos for c in read_log(r, author, since, until, a.all_branches)]
    if not commits: raise SystemExit('No commits in that range.')
    s = analyze(commits)
    s['repo'] = Path(repos[0]).resolve().name if len(repos) == 1 else f'{len(repos)} repos'
    v = verdict(s); s['verdict'] = v
    if a.json: sys.stdout.buffer.write((json.dumps(s, indent=2, ensure_ascii=False) + '\n').encode('utf-8')); return 0
    label = f'{a.year}' if a.year else f"{s['firstCommit']['date'][:4]}-{s['lastCommit']['date'][:4]}"
    Path(a.out).write_text(poster(s, v, s['repo'], label), encoding='utf-8')
    sys.stdout.buffer.write((terminal(s, v, f"{s['repo']} wrapped, {label}") + f'\n  saved {a.out}\n').encode('utf-8'))
    return 0

if __name__ == '__main__':
    sys.exit(main())
