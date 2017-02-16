import json

from django import template
from django.utils.safestring import mark_safe

from ..menu_helpers import get_vue_js_router

register = template.Library()


@register.simple_tag(takes_context=True)
def vue_js_router(context):
    if 'vue_js_router' in context:
        router = context['vue_js_router']
    else:
        router = get_vue_js_router(context=context)

    router_json = json.dumps(router)
    escaped_router_json = router_json.replace("'", "&#39;")  # Escape apostrophes to prevent JS errors.
    return mark_safe(escaped_router_json)
