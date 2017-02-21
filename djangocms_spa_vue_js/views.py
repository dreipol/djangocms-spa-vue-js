import json

from cms.utils.page_resolver import get_page_from_request
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, JsonResponse
from django.views.generic import TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.list import MultipleObjectMixin
from rest_framework.views import APIView

from djangocms_spa.content_helpers import (get_frontend_data_dict_for_cms_page, get_frontend_data_dict_for_partials,
                                           get_partial_names_for_template)

from .decorators import cache_view
from .menu_helpers import get_vue_js_router


class VueRouterView(TemplateView):
    fetch_url = None

    @cache_view
    def dispatch(self, request, **kwargs):
        return super(VueRouterView, self).dispatch(request, **kwargs)

    def get_context_data(self, **kwargs):
        return {
            'vue_js_router': self.get_vue_js_router_including_fetched_data()
        }

    def get_vue_js_router_including_fetched_data(self):
        vue_js_router = get_vue_js_router(request=self.request)

        # Put the context data of this view into the active route.
        active_route = self.get_active_route(vue_js_router['routes'])
        if active_route:
            active_route['api']['fetched']['data'].update(
                self.get_fetched_data()
            )

        return vue_js_router

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
            is_active_route = 'fetched' in route['api']
            if is_active_route:
                return route

            if route.get('children'):
                active_route = self.get_active_route(route['children'])
                if active_route:
                    return active_route

        return None

    def get_fetch_url(self):
        if self.fetch_url:
            return self.fetch_url
        else:
            raise ImproperlyConfigured('No fetch URL to get the data. Provide a fetch_url.')


class ObjectPermissionMixin(object):
    model = None
    request = None

    def has_change_permission(self):
        if hasattr(self, 'model'):
            model_permission_code = '%s.change_%s' % (self.model._meta.app_label, self.model._meta.model_name)
            return self.request.user.has_perm(model_permission_code)
        return True


class MetaDataMixin(object):
    def get_meta_data(self):
        return {
            'title': '',
            'description': ''
        }


class MultipleObjectSpaMixin(MetaDataMixin, ObjectPermissionMixin, MultipleObjectMixin):
    list_container_name = settings.DJANGOCMS_SPA_VUE_JS_DEFAULT_LIST_CONTAINER_NAME
    model = None
    queryset = None

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        return super(MultipleObjectSpaMixin, self).get(request, *args, **kwargs)

    def get_fetched_data(self):
        object_list = []
        editable = self.has_change_permission()

        for object in self.object_list:
            if hasattr(object, 'get_frontend_list_data_dict'):
                placeholder_name = 'cms-plugin-{app}-{model}-{pk}'.format(
                    app=object._meta.app_label,
                    model=object._meta.model_name,
                    pk=object.pk
                )
                object_list.append(object.get_frontend_list_data_dict(self.request, editable=editable,
                                                                      placeholder_name=placeholder_name))

        return {
            'containers': {
                self.list_container_name: object_list
            },
            'meta': self.get_meta_data()
        }


class SingleObjectSpaMixin(MetaDataMixin, ObjectPermissionMixin, SingleObjectMixin):
    object = None

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super(SingleObjectSpaMixin, self).get(request, *args, **kwargs)

    def get_fetched_data(self):
        data = {}

        if hasattr(self.object, 'get_frontend_detail_data_dict'):
            data = self.object.get_frontend_detail_data_dict(self.request, editable=self.has_change_permission())

        data['meta'] = self.get_meta_data()
        return data


class VueRouterListView(MultipleObjectSpaMixin, VueRouterView):
    pass


class VueRouterDetailView(SingleObjectSpaMixin, VueRouterView):
    pass


class VueSpaApiView(APIView):
    template_name = None

    @cache_view
    def dispatch(self, request, **kwargs):
        # Take the language from the URL kwarg and set it as request language
        language_code = kwargs.pop('language_code')
        available_languages = [language[0] for language in settings.LANGUAGES]
        request.LANGUAGE_CODE = language_code if language_code in available_languages else settings.LANGUAGES[0][0]
        return super(VueSpaApiView, self).dispatch(request, **kwargs)

    def get(self, *args, **kwargs):
        data = {
            'data': self.get_fetched_data()
        }

        partials = self.get_partials()
        if partials:
            data['partials'] = partials

        return HttpResponse(
            content=json.dumps(data),
            content_type='application/json',
            status=200
        )

    def get_partials(self):
        partial_names = get_partial_names_for_template(template=self.get_template_names(), get_all=False,
                                                       requested_partials=self.request.GET.get('partials'))
        return get_frontend_data_dict_for_partials(
            partials=partial_names,
            request=self.request,
            editable=self.request.user.has_perm('cms.edit_static_placeholder'),
        )

    def get_template_names(self):
        return self.template_name


class VueCmsPageDetailApiView(VueSpaApiView):
    cms_page = None
    cms_page_title = None

    def get(self, request, **kwargs):
        self.cms_page = get_page_from_request(request, use_path=kwargs.get('path'))
        self.cms_page_title = self.cms_page.title_set.get(language=request.LANGUAGE_CODE)

        if not self.cms_page or not self.cms_page_title:
            return JsonResponse(data={}, status=404)

        return super(VueCmsPageDetailApiView, self).get(request, **kwargs)

    def get_fetched_data(self):
        data = {}

        view_data = get_frontend_data_dict_for_cms_page(
            cms_page=self.cms_page,
            cms_page_title=self.cms_page_title,
            request=self.request,
            editable=self.request.user.has_perm('cms.change_page')
        )
        if view_data:
            data.update(view_data)

        return data

    def get_template_names(self):
        return self.cms_page.get_template()


class VueListApiView(MultipleObjectSpaMixin, VueSpaApiView):
    def get_fetched_data(self):
        data = {}

        view_data = super(VueListApiView, self).get_fetched_data()
        if view_data:
            data.update(view_data)

        return data


class VueDetailApiView(SingleObjectSpaMixin, VueSpaApiView):
    def get_fetched_data(self):
        data = {}

        view_data = super(VueDetailApiView, self).get_fetched_data()
        if view_data:
            data.update(view_data)

        return data
