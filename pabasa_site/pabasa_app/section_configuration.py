"""Canonical, school-owned section configuration."""

SALAWAG_GRADE_TWO_SECTIONS = (
    "AGUINALDO", "ALONZO", "AQUINO", "BALAGTAS", "BALTAZAR", "BONIFACIO",
    "DAGOHOY", "DEL PILAR", "ESCODA", "JACINTO", "LAPU-LAPU", "LUNA",
    "MABINI", "MAGSAYSAY", "MALVAR", "RICARTE", "RIZAL", "SAKAY",
)


def ensure_salawag_grade_two_sections(school, school_calendar):
    """Idempotently configure Salawag's Grade 2 sections for one school year."""
    from .models import Section

    if (
        not school
        or school.name != "Salawag Elementary School"
        or not school_calendar
        or not school_calendar.is_active
    ):
        return

    existing = {
        section.section.upper(): section
        for section in Section.objects.filter(
            school=school,
            school_calendar=school_calendar,
            grade_level__iexact="Grade 2",
        )
    }
    for position, name in enumerate(SALAWAG_GRADE_TWO_SECTIONS, start=1):
        if name in existing:
            continue
        Section.objects.create(
            school=school,
            school_calendar=school_calendar,
            class_code=f"SAL-G2-{position:02d}",
            class_name=f"Grade 2 - {name}",
            subject="Reading",
            grade_level="Grade 2",
            section=name,
            is_active=True,
        )
