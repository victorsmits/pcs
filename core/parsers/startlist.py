"""Parser de la startlist PCS (engagés par équipe)."""
import re

from core.parsers.common import slug_from_href, team_slug_year_from_href

_LEVEL = re.compile(r'\s*\([A-Z]{2,3}\)\s*$')


def parse_startlist(soup):
    """Renvoie [{rider_slug, rider_name, team_slug, team_year, team_name, bib, nat}]."""
    sl = soup.find(class_='startlist_v4') or soup.find(class_=re.compile('startlist'))
    if not sl:
        return []
    out = []
    for li in sl.find_all('li', recursive=False):
        team_link = li.find('a', href=lambda h: h and 'team/' in h)
        if not team_link:
            continue
        team_slug, team_year = team_slug_year_from_href(team_link.get('href'))
        team_name = _LEVEL.sub('', team_link.get_text(' ', strip=True)).strip()

        for rl in li.find_all('a', href=lambda h: h and 'rider/' in h):
            name = rl.get_text(' ', strip=True)
            if not name:
                continue
            par = rl.find_parent(['li', 'tr', 'div', 'span']) or li
            ptext = par.get_text(' ', strip=True)
            bm = re.match(r'\s*(\d+)\b', ptext)
            bib = int(bm.group(1)) if bm else None
            flag = par.find('span', class_='flag')
            nat = ''
            if flag:
                cls = flag.get('class', [])
                nat = next((c for c in cls if c != 'flag' and len(c) == 2), '')
            out.append({
                'rider_slug': slug_from_href(rl.get('href'), 'rider'),
                'rider_name': name,
                'team_slug': team_slug, 'team_year': team_year, 'team_name': team_name,
                'bib': bib, 'nat': nat,
            })
    return out
