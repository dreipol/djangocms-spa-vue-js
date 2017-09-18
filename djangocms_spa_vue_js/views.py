from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.views.generic import TemplateView

from djangocms_spa.content_helpers import get_frontend_data_dict_for_partials
from djangocms_spa.decorators import cache_view
from djangocms_spa.views import MultipleObjectSpaMixin, SingleObjectSpaMixin

from .menu_helpers import get_vue_js_router


class VueRouterView(TemplateView):
    fetch_url = None
    add_language_code = len(settings.LANGUAGES) > 1

    @cache_view
    def dispatch(self, request, **kwargs):
        return super(VueRouterView, self).dispatch(request, **kwargs)

    def get_cache_key(self):
        return None

    def get_context_data(self, **kwargs):
        return {
            'vue_js_router': self.get_vue_js_router_including_fetched_data()
        }

    def get_vue_js_router_including_fetched_data(self):
        vue_js_router = self.get_vue_js_router(request=self.request)

        # Put the context data of this view into the active route.
        active_route = self.get_active_route(vue_js_router['routes'])
        if active_route:
            active_route['api']['fetched']['response']['data'].update(
                self.get_fetched_data()
            )

            url_params_for_active_route = self.get_url_params_for_active_route()
            if url_params_for_active_route:
                active_route['api']['fetched']['params'] = url_params_for_active_route

        return vue_js_router

    def get_vue_js_router(self, request):
        return get_vue_js_router(request=request)

    def get_fetched_data(self):
        # Override this method if you need further context data.
        return {}

    def get_view_partials(self, partial_names):
        return get_frontend_data_dict_for_partials(
            partials=partial_names,
            request=self.request,
            editable=self.request.user.has_perm('cms.edit_static_placeholder'),
        )

    def get_active_route(self, routes):
        for route in routes:
            is_active_route = 'api' in route and 'fetched' in route['api']
            if is_active_route:
                return route

        return None

    def get_fetch_url(self):
        if self.fetch_url:
            return self.fetch_url
        else:
            raise ImproperlyConfigured('No fetch URL to get the data. Provide a fetch_url.')

    def get_url_params_for_active_route(self):
        return {}


class VueRouterListView(MultipleObjectSpaMixin, VueRouterView):
    pass


class VueRouterDetailView(SingleObjectSpaMixin, VueRouterView):
    pass
