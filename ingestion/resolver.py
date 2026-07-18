from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.text import slugify

from catalog.models import RaceSeries, Rider
from providers.models import Provider, ProviderEntityMapping

from .dto import NormalizedDTO, NormalizedRaceSeries, NormalizedRider


def canonical_model_name(obj_or_model) -> str:
    model = obj_or_model if isinstance(obj_or_model, type) else obj_or_model.__class__
    return f'{model._meta.app_label}.{model._meta.model_name}'


class IdentityResolver:
    def __init__(self, provider: Provider):
        self.provider = provider

    def resolve_mapping(self, entity_type: str, external_id: str):
        mapping = ProviderEntityMapping.objects.filter(
            provider=self.provider, entity_type=entity_type, external_id=external_id
        ).first()
        if not mapping:
            return None
        app_label, model = mapping.canonical_model.split('.', 1)
        model_class = ContentType.objects.get(app_label=app_label, model=model).model_class()
        return model_class.objects.filter(pk=mapping.canonical_id).first()

    def bind(self, dto: NormalizedDTO, canonical_obj):
        return ProviderEntityMapping.objects.update_or_create(
            provider=self.provider,
            entity_type=dto.entity_type.value,
            external_id=dto.source.external_id,
            defaults={
                'external_url': dto.source.external_url,
                'canonical_model': canonical_model_name(canonical_obj),
                'canonical_id': canonical_obj.pk,
                'confidence': dto.source.confidence,
                'source_updated_at': dto.source.source_updated_at,
                'last_seen_at': timezone.now(),
            },
        )[0]

    def resolve_or_create_race_series(self, dto: NormalizedRaceSeries):
        existing = self.resolve_mapping(dto.entity_type.value, dto.source.external_id)
        if existing:
            return existing, False
        obj, created = RaceSeries.objects.get_or_create(
            canonical_slug=dto.canonical_slug,
            defaults={
                'current_name': dto.current_name,
                'gender_category': dto.gender_category,
                'discipline': dto.discipline,
                'format': dto.format,
                'scope': dto.scope,
                'primary_country': dto.primary_country,
                'importance': dto.importance,
                'active': dto.active,
                'aliases': dto.aliases,
                'metadata': dto.metadata,
            },
        )
        self.bind(dto, obj)
        return obj, created

    def resolve_or_create_rider(self, dto: NormalizedRider):
        existing = self.resolve_mapping(dto.entity_type.value, dto.source.external_id)
        if existing:
            return existing, False
        slug = dto.canonical_slug or slugify(dto.full_name)
        obj = Rider.objects.filter(canonical_slug=slug).first()
        created = False
        if not obj and dto.birthdate:
            obj = Rider.objects.filter(normalized_name=dto.normalized_name, birthdate=dto.birthdate, nationality=dto.nationality).first()
        if not obj:
            obj = Rider.objects.create(
                slug=slug,
                canonical_slug=slug,
                name=dto.full_name,
                normalized_name=dto.normalized_name,
                birthdate=dto.birthdate,
                nationality=dto.nationality,
                gender_category=dto.gender_category,
                height=float(dto.height_cm) if dto.height_cm else None,
                weight=float(dto.weight_kg) if dto.weight_kg else None,
                photo_url=dto.photo_url,
                metadata=dto.metadata,
            )
            created = True
        self.bind(dto, obj)
        return obj, created
