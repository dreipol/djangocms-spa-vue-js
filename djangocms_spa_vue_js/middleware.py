from django.http import JsonResponse

from djangocms_spa_vue_js.menu_helpers import get_vue_js_router


class RouterDebuggingMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        vue_js_router = get_vue_js_router(request=request)
        return JsonResponse(vue_js_router)
