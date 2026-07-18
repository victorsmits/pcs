from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category, RaceDiscipline, RaceFormat, RaceImportance, RaceScope, RaceSeries, RaceSeriesAlias

DEFAULT_ROAD_SERIES_PATH = Path(__file__).resolve().parent / 'seeds' / 'road_series.yaml'
P1_COUNTRIES = ['BE', 'FR', 'IT', 'ES', 'NL', 'GB', 'DE', 'CH', 'DK', 'NO', 'SI', 'PT', 'US', 'AU', 'CO']
P2_COUNTRIES = ['AT', 'CA', 'IE', 'LU', 'PL', 'CZ', 'SK', 'HU', 'SE', 'FI', 'NZ', 'EC', 'ER', 'ZA', 'JP']


@dataclass(frozen=True)
class SeedResult:
    created: int = 0
    updated: int = 0
    aliases_created: int = 0
    aliases_updated: int = 0

    def __add__(self, other: 'SeedResult') -> 'SeedResult':
        return SeedResult(
            self.created + other.created,
            self.updated + other.updated,
            self.aliases_created + other.aliases_created,
            self.aliases_updated + other.aliases_updated,
        )


def load_road_series(path: Path = DEFAULT_ROAD_SERIES_PATH) -> list[dict[str, Any]]:
    # Parser YAML restreint pour le format versionné de ce dépôt. Il évite une
    # dépendance runtime supplémentaire tout en gardant un fichier .yaml lisible.
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_list_key: str | None = None
    for raw_line in path.read_text().splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if stripped.startswith('- ') and not line.startswith('    '):
            if current is not None:
                entries.append(current)
            key, value = stripped[2:].split(': ', 1)
            current = {key: _parse_scalar(value)}
            current_list_key = None
            continue
        if current is None:
            raise ValueError('invalid road series seed')
        if stripped.startswith('- '):
            if current_list_key is None:
                raise ValueError('list item without key')
            current.setdefault(current_list_key, []).append(_parse_scalar(stripped[2:]))
            continue
        key, value = stripped.split(':', 1)
        value = value.strip()
        if value == '':
            current[key] = []
            current_list_key = key
        else:
            current[key] = _parse_scalar(value)
            current_list_key = None
    if current is not None:
        entries.append(current)
    return entries


def _parse_scalar(value: str) -> Any:
    if value == '[]':
        return []
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1].strip()
        return [] if not inner else [item.strip() for item in inner.split(',')]
    if value in {'true', 'false'}:
        return value == 'true'
    return value


def _normalize_alias(name: str) -> str:
    return slugify(name)


def _validate_entry(entry: dict[str, Any]) -> None:
    required = ['slug', 'name', 'category', 'discipline', 'format', 'scope', 'priority']
    missing = [key for key in required if not entry.get(key)]
    if missing:
        raise ValueError(f'missing required seed field(s): {", ".join(missing)}')
    if slugify(entry['slug']) != entry['slug'] and ':' not in entry['slug']:
        raise ValueError(f'invalid slug: {entry["slug"]}')
    if entry['category'] not in Category.values:
        raise ValueError(f'invalid category: {entry["category"]}')
    if entry['discipline'] not in RaceDiscipline.values:
        raise ValueError(f'invalid discipline: {entry["discipline"]}')
    if entry['format'] not in RaceFormat.values:
        raise ValueError(f'invalid format: {entry["format"]}')
    if entry['scope'] not in RaceScope.values:
        raise ValueError(f'invalid scope: {entry["scope"]}')
    if entry['priority'] not in RaceImportance.values:
        raise ValueError(f'invalid priority: {entry["priority"]}')


@transaction.atomic
def seed_road_series(path: Path = DEFAULT_ROAD_SERIES_PATH) -> SeedResult:
    result = SeedResult()
    for entry in load_road_series(path):
        _validate_entry(entry)
        countries = entry.get('countries') or []
        aliases = entry.get('aliases') or []
        series, created = RaceSeries.objects.update_or_create(
            canonical_slug=entry['slug'],
            defaults={
                'current_name': entry['name'],
                'gender_category': entry['category'],
                'discipline': entry['discipline'],
                'format': entry['format'],
                'scope': entry['scope'],
                'primary_country': countries[0] if countries else '',
                'importance': entry['priority'],
                'active': entry.get('active', True),
                'aliases': aliases,
                'metadata': {'seed': 'road_series.yaml', 'countries': countries},
            },
        )
        result += SeedResult(created=int(created), updated=int(not created))
        for alias in [entry['name'], *aliases]:
            _, alias_created = RaceSeriesAlias.objects.update_or_create(
                series=series,
                normalized_name=_normalize_alias(alias),
                valid_from_year=None,
                valid_to_year=None,
                locale='und',
                defaults={'name': alias},
            )
            result += SeedResult(aliases_created=int(alias_created), aliases_updated=int(not alias_created))
    return result


def national_championship_entries() -> list[dict[str, Any]]:
    entries = []
    for priority, countries in [('P1', P1_COUNTRIES), ('P2', P2_COUNTRIES)]:
        for country in countries:
            for category in ['ME', 'WE']:
                entries.append({
                    'slug': f'national-championship:{country}:{category}:road-race',
                    'name': f'National Championship {country} {category} Road Race',
                    'category': category,
                    'discipline': RaceDiscipline.ROAD,
                    'format': RaceFormat.CHAMPIONSHIP_ROAD_RACE,
                    'scope': RaceScope.NATIONAL_CHAMPIONSHIP,
                    'priority': priority,
                    'countries': [country],
                    'aliases': [],
                })
                entries.append({
                    'slug': f'national-championship:{country}:{category}:itt',
                    'name': f'National Championship {country} {category} ITT',
                    'category': category,
                    'discipline': RaceDiscipline.ROAD,
                    'format': RaceFormat.CHAMPIONSHIP_ITT,
                    'scope': RaceScope.NATIONAL_CHAMPIONSHIP,
                    'priority': priority,
                    'countries': [country],
                    'aliases': [],
                })
    return entries


@transaction.atomic
def seed_national_championships() -> SeedResult:
    result = SeedResult()
    for entry in national_championship_entries():
        _validate_entry(entry)
        series, created = RaceSeries.objects.update_or_create(
            canonical_slug=entry['slug'],
            defaults={
                'current_name': entry['name'],
                'gender_category': entry['category'],
                'discipline': entry['discipline'],
                'format': entry['format'],
                'scope': entry['scope'],
                'primary_country': entry['countries'][0],
                'importance': entry['priority'],
                'active': True,
                'aliases': [],
                'metadata': {'seed': 'national_championships', 'countries': entry['countries']},
            },
        )
        _, alias_created = RaceSeriesAlias.objects.update_or_create(
            series=series,
            normalized_name=_normalize_alias(entry['name']),
            valid_from_year=None,
            valid_to_year=None,
            locale='und',
            defaults={'name': entry['name']},
        )
        result += SeedResult(created=int(created), updated=int(not created), aliases_created=int(alias_created), aliases_updated=int(not alias_created))
    return result
