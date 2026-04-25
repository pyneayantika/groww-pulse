"""
Report builder for groww-pulse project.

Provides pulse note generation, Jinja2 templating, and email composition.
"""

from .pulse_builder import (
    build_pulse_note, 
    render_pulse_note_markdown, 
    WeeklyPulseNote, 
    ThemeSummary,
    count_words,
    truncate_to_250
)
from .email_composer import compose_email

__all__ = [
    'build_pulse_note',
    'render_pulse_note_markdown',
    'WeeklyPulseNote',
    'ThemeSummary',
    'count_words',
    'truncate_to_250',
    'compose_email'
]
