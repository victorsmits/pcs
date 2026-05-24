from datetime import date

from django.db import models
from django.urls import reverse
from django.utils.text import slugify


NATIONALITY_TO_FLAG = {
    # 3-letter ISO → 2-letter ISO
    "AFG": "af", "ALB": "al", "ALG": "dz", "AND": "ad", "ANG": "ao",
    "ARG": "ar", "ARM": "am", "AUS": "au", "AUT": "at", "AZE": "az",
    "BEL": "be", "BEN": "bj", "BLR": "by", "BOL": "bo", "BRA": "br",
    "BUL": "bg", "CAN": "ca", "CHI": "cl", "CHN": "cn", "COL": "co",
    "CRC": "cr", "CRO": "hr", "CUB": "cu", "CYP": "cy", "CZE": "cz",
    "DEN": "dk", "DOM": "do", "ECU": "ec", "EGY": "eg", "ERI": "er",
    "ESP": "es", "EST": "ee", "ETH": "et", "FIN": "fi", "FRA": "fr",
    "GBR": "gb", "GEO": "ge", "GER": "de", "GRE": "gr", "GUA": "gt",
    "HUN": "hu", "INA": "id", "IND": "in", "IRL": "ie", "IRN": "ir",
    "ISL": "is", "ISR": "il", "ITA": "it", "JAM": "jm", "JPN": "jp",
    "KAZ": "kz", "KEN": "ke", "KOR": "kr", "LAT": "lv", "LIB": "lb",
    "LTU": "lt", "LUX": "lu", "MAR": "ma", "MDA": "md", "MEX": "mx",
    "MGL": "mn", "MKD": "mk", "MLT": "mt", "MON": "mc", "MRI": "mu",
    "NAM": "na", "NED": "nl", "NOR": "no", "NZL": "nz", "PAN": "pa",
    "PER": "pe", "PHI": "ph", "POL": "pl", "POR": "pt", "PRK": "kp",
    "PUR": "pr", "ROU": "ro", "RSA": "za", "RUS": "ru", "RWA": "rw",
    "SEN": "sn", "SLO": "si", "SVK": "sk", "SWE": "se", "SWI": "ch",
    "TAN": "tz", "THA": "th", "TUN": "tn", "TUR": "tr", "UAE": "ae",
    "UGA": "ug", "UKR": "ua", "URU": "uy", "USA": "us", "UZB": "uz",
    "VEN": "ve", "VIE": "vn", "ZIM": "zw",
}


class Team(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    year = models.IntegerField()
    status = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ("WorldTeam", "WorldTeam"),
            ("ProTeam", "ProTeam"),
            ("Continental", "Continental"),
            ("Women", "Women"),
        ],
    )
    nationality = models.CharField(max_length=3, blank=True)
    pcs_url = models.URLField(blank=True)

    class Meta:
        unique_together = ("slug", "year")

    def __str__(self):
        return f"{self.name} ({self.year})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"/teams/{self.slug}/{self.year}/"

    @property
    def flag_code(self):
        return NATIONALITY_TO_FLAG.get(self.nationality.upper(), "xx")


class Rider(models.Model):
    SPECIALTY_CHOICES = [
        ("climber", "Climber"),
        ("sprinter", "Sprinter"),
        ("tt", "Time Trialist"),
        ("rouleur", "Rouleur"),
        ("puncheur", "Puncheur"),
        ("all_rounder", "All-Rounder"),
        ("classics", "Classics Specialist"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    nationality = models.CharField(max_length=3, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    specialty = models.CharField(max_length=20, choices=SPECIALTY_CHOICES, blank=True)
    is_active = models.BooleanField(default=True)
    current_team = models.ForeignKey(
        Team, null=True, blank=True, on_delete=models.SET_NULL, related_name="riders"
    )
    pcs_rank = models.IntegerField(null=True, blank=True)
    pcs_points = models.IntegerField(default=0)
    uci_rank = models.IntegerField(null=True, blank=True)
    uci_points = models.FloatField(default=0)
    photo_url = models.URLField(blank=True)
    pcs_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"/riders/{self.slug}/"

    @property
    def flag_code(self):
        return NATIONALITY_TO_FLAG.get(self.nationality.upper(), "xx")

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        dob = self.date_of_birth
        return (
            today.year
            - dob.year
            - ((today.month, today.day) < (dob.month, dob.day))
        )


class Race(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    year = models.IntegerField()
    classification = models.CharField(max_length=10, blank=True)
    circuit = models.CharField(max_length=50, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    stages_count = models.IntegerField(default=1)
    is_stage_race = models.BooleanField(default=False)
    is_grand_tour = models.BooleanField(default=False)
    is_monument = models.BooleanField(default=False)
    country = models.CharField(max_length=3, blank=True)
    country_name = models.CharField(max_length=100, blank=True)
    distance = models.FloatField(null=True, blank=True)
    departure_city = models.CharField(max_length=100, blank=True)
    arrival_city = models.CharField(max_length=100, blank=True)
    winner = models.ForeignKey(
        Rider,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="won_races",
    )
    winner_team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="won_races",
    )
    profile_url = models.URLField(blank=True)
    pcs_url = models.URLField(blank=True)
    last_fetched = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("slug", "year")
        indexes = [
            models.Index(fields=["slug", "year"]),
            models.Index(fields=["start_date"]),
            models.Index(fields=["is_grand_tour"]),
            models.Index(fields=["is_monument"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.year})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"/races/{self.slug}/{self.year}/"

    @property
    def flag_code(self):
        return NATIONALITY_TO_FLAG.get(self.country.upper(), "xx")

    @property
    def is_live(self):
        if not self.start_date or not self.end_date:
            return False
        today = date.today()
        return self.start_date <= today <= self.end_date

    @property
    def duration_days(self):
        if not self.start_date or not self.end_date:
            return None
        return (self.end_date - self.start_date).days + 1


class Stage(models.Model):
    STAGE_TYPE_CHOICES = [
        ("flat", "Flat"),
        ("hilly", "Hilly"),
        ("mountain", "Mountain"),
        ("mountain_finish", "Mountain Finish"),
        ("tt", "Time Trial"),
        ("ttt", "Team Time Trial"),
        ("itt", "Individual Time Trial"),
        ("cobbles", "Cobbles"),
        ("prologue", "Prologue"),
    ]

    TYPE_ICONS = {
        "flat": "🟢",
        "hilly": "🟡",
        "mountain": "🔴",
        "mountain_finish": "⛰️",
        "tt": "⏱️",
        "ttt": "👥",
        "itt": "🕐",
        "cobbles": "🪨",
        "prologue": "🏁",
    }

    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name="stages")
    number = models.IntegerField()
    date = models.DateField(null=True, blank=True)
    departure = models.CharField(max_length=100, blank=True)
    arrival = models.CharField(max_length=100, blank=True)
    distance = models.FloatField(null=True, blank=True)
    stage_type = models.CharField(
        max_length=20, choices=STAGE_TYPE_CHOICES, default="flat"
    )
    elevation_gain = models.IntegerField(null=True, blank=True)
    winner = models.ForeignKey(
        Rider,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stage_wins",
    )
    winner_team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stage_wins",
    )
    leader_after = models.ForeignKey(
        Rider,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stages_led",
    )
    profile_url = models.URLField(blank=True)
    pcs_url = models.URLField(blank=True)

    class Meta:
        unique_together = ("race", "number")
        ordering = ["number"]

    def __str__(self):
        return f"{self.race} - Stage {self.number}"

    def get_absolute_url(self):
        return f"/races/{self.race.slug}/{self.race.year}/stages/{self.number}/"

    @property
    def type_icon(self):
        return self.TYPE_ICONS.get(self.stage_type, "")


class RaceResult(models.Model):
    RESULT_TYPE_CHOICES = [
        ("gc", "General Classification"),
        ("stage", "Stage"),
        ("points", "Points Classification"),
        ("kom", "King of the Mountains"),
        ("youth", "Youth Classification"),
        ("team", "Team Classification"),
    ]

    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name="results")
    stage = models.ForeignKey(
        Stage, on_delete=models.CASCADE, null=True, blank=True, related_name="results"
    )
    rider = models.ForeignKey(Rider, on_delete=models.CASCADE, related_name="results")
    team = models.ForeignKey(
        Team, null=True, blank=True, on_delete=models.SET_NULL, related_name="results"
    )
    year = models.IntegerField()
    result_type = models.CharField(
        max_length=10, choices=RESULT_TYPE_CHOICES, default="gc"
    )
    rank = models.IntegerField(null=True, blank=True)
    time_gap = models.CharField(max_length=20, blank=True)
    points = models.FloatField(default=0)
    uci_points = models.FloatField(default=0)
    dnf = models.BooleanField(default=False)
    dns = models.BooleanField(default=False)
    dsq = models.BooleanField(default=False)

    class Meta:
        ordering = ["rank"]
        indexes = [
            models.Index(fields=["race", "stage"]),
            models.Index(fields=["rider", "year"]),
        ]

    def __str__(self):
        return f"{self.rider} - {self.race} ({self.result_type})"

    @property
    def status_display(self):
        if self.dsq:
            return "DSQ"
        if self.dns:
            return "DNS"
        if self.dnf:
            return "DNF"
        if self.rank:
            return str(self.rank)
        return "-"


class StartEntry(models.Model):
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name="start_list")
    rider = models.ForeignKey(
        Rider, on_delete=models.CASCADE, related_name="start_entries"
    )
    team = models.ForeignKey(
        Team,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="start_entries",
    )
    bib_number = models.IntegerField(null=True, blank=True)
    withdrew = models.BooleanField(default=False)

    class Meta:
        unique_together = ("race", "rider")

    def __str__(self):
        return f"{self.rider} @ {self.race} (#{self.bib_number})"
