import json

from django import template
from django.utils.safestring import mark_safe

from ..menu_helpers import get_vue_js_router

register = template.Library()


@register.simple_tag(takes_context=True)
def vue_js_router(context):
    return mark_safe(json.dumps(get_vue_js_router(context=context)))


@register.filter
def escape_apostrophe(value):
    """
    We need to escape apostrophes to prevent JS errors.
    """
    return mark_safe(value.replace("'", "&#39;"))
