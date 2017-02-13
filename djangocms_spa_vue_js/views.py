import json

from cms.utils.page_resolver import get_page_from_request
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.generic import View
from django.views.generic.detail import BaseDetailView
from django.views.generic.list import MultipleObjectMixin
from rest_framework.views import APIView

from djangocms_spa.content_helpers import (get_frontend_data_dict_for_cms_page, get_frontend_data_dict_for_partials,
                                           get_partial_names_for_template)

from .decorators import cache_view
from .menu_helpers import get_vue_js_router


class FrontendRouterBase(View):
    app_slug = ''

    def __init__(self):
        super(FrontendRouterBase, self).__init__()
        self.model_name = self.model._meta.model_name

    @staticmethod
    def route_is_active(route):
        return 'fetched' in route['api']

    @cache_view
    def dispatch(self, request, **kwargs):
        # The app slug is needed to find the CMS page of the app hook.
        self.app_slug = kwargs.pop('app_slug', '')
        return super(FrontendRouterBase, self).dispatch(request, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(FrontendRouterBase, self).get_context_data(**kwargs)
        vue_js_router = get_vue_js_router(request=self.request)

        # At this point, the `vue_js_router` on the context includes all menu nodes that are used for the routing. The
        # next step is to put the contents of this very detail view into the router object.
        active_route = self.get_active_route(vue_js_router['routes'])
        active_route['api']['fetched']['data'].update(self.get_router_view_context_data())

        context['vue_js_router'] = vue_js_router

        return context

    def get_router_view_context_data(self):
        # Override this method if you need further context data.
        return {}

    def get_active_route(self, routes):
        for route in routes:
            if self.route_is_active(route):
                return route

            if route.get('children'):
                active_route = self.get_active_route(route['children'])
                if active_route:
                    return active_route

        return None

    def get_view_partials(self):
        partial_names = get_partial_names_for_template(template=self.template_name, get_all=False,
                                                       requested_partials=self.request.GET.get('partials', []))

        return get_frontend_data_dict_for_partials(
            partials=partial_names,
            request=self.request,
            editable=self.request.user.has_perm('cms.edit_static_placeholder'),
        )

    def has_change_permission(self):
        model_permission_code = '%s.change_%s' % (self.model._meta.app_label, self.model._meta.model_name)
        return self.request.user.has_perm(model_permission_code)


class FrontendRouterJsonListMixin(FrontendRouterBase):
    """
    The framework that is used by the frontend has its own routing. We don't want to manage the urls in two separate
    places (front- and backend) and prepare the needed structure here dynamically.
    """
    def get_context_data(self, **kwargs):
        context = super(FrontendRouterJsonListMixin, self).get_context_data(**kwargs)
        context['vue_js_router'] = json.dumps(context['vue_js_router'])
        return context

    def get_router_view_context_data(self):
        data = super(FrontendRouterJsonListMixin, self).get_router_view_context_data()
        object_list = getattr(self, 'object_list', self.get_queryset())

        list_data = []
        for obj in object_list:
            placeholder_name = 'cms-plugin-{app}-{model}-{id}'.format(
                app=obj._meta.app_label,
                model=obj._meta.model_name,
                id=obj.id
            )
            obj_data_dict = obj.get_frontend_list_data_dict(
                request=self.request,
                editable=self.has_change_permission(),
                placeholder_name=placeholder_name
            )
            list_data.append(obj_data_dict)

        data.setdefault('containers', {})[settings.DJANGOCMS_SPA_VUE_JS_DEFAULT_LIST_CONTAINER_NAME] = list_data

        return data


class FrontendRouterJsonDetailMixin(FrontendRouterBase, BaseDetailView):
    def __init__(self):
        super(FrontendRouterJsonDetailMixin, self).__init__()
        self.fetched_data_path = ['subRoutes', self.model.vue_js_router_key, 'api', 'fetched', 'data']

    def get_context_data(self, **kwargs):
        context = super(FrontendRouterJsonDetailMixin, self).get_context_data(**kwargs)
        context['vue_js_router'] = json.dumps(context['vue_js_router'])
        return context

    def get_router_view_context_data(self):
        data = super(FrontendRouterJsonDetailMixin, self).get_router_view_context_data()
        data.update(self.object.get_frontend_detail_data_dict(
            request=self.request,
            editable=self.has_change_permission()
        ))
        return data


class CMSPageDetailAPIView(APIView):
    def get(self, request, **kwargs):
        context = {}
        cms_page = get_page_from_request(request, use_path=kwargs.get('path'))
        if not cms_page:
            return JsonResponse(data={}, status=404)

        cms_page_title = cms_page.title_set.get(language=request.LANGUAGE_CODE)

        data = get_frontend_data_dict_for_cms_page(
            cms_page=cms_page,
            cms_page_title=cms_page_title,
            request=request,
            editable=request.user.has_perm('cms.change_page')
        )
        if data:
            context['data'] = data

        partial_names = get_partial_names_for_template(template=cms_page.get_template(), get_all=False,
                                                       requested_partials=request.GET.get('partials'))
        partials = get_frontend_data_dict_for_partials(
            partials=partial_names,
            request=self.request,
            editable=self.request.user.has_perm('cms.edit_static_placeholder'),
        )
        if partials:
            context['partials'] = partials

        return HttpResponse(
            content=json.dumps(context),
            content_type='application/json',
            status=200
        )


class BaseAPIView(APIView):
    def get_view_partials(self):
        partial_names = get_partial_names_for_template(template=self.template_name, get_all=False,
                                                       requested_partials=self.request.GET.get('partials'))
        return get_frontend_data_dict_for_partials(
            partials=partial_names,
            request=self.request,
            editable=self.request.user.has_perm('cms.edit_static_placeholder'),
        )


class BaseListAPIView(FrontendRouterJsonListMixin, MultipleObjectMixin, BaseAPIView):
    @cache_view
    def dispatch(self, request, **kwargs):
        return super(BaseListAPIView, self).dispatch(request, **kwargs)

    def get(self, request, format=None):
        data = self.get_context_data()

        return HttpResponse(
            content=json.dumps(data),
            content_type='application/json',
            status=200
        )

    def get_context_data(self, **kwargs):
        context = {}

        data = self.get_router_view_context_data()
        if data:
            context['data'] = data

        partials = self.get_view_partials()
        if partials:
            context['partials'] = partials

        return context


class BaseDetailAPIView(FrontendRouterJsonDetailMixin, BaseAPIView):
    @cache_view
    def dispatch(self, request, **kwargs):
        return super(BaseDetailAPIView, self).dispatch(request, **kwargs)

    def get(self, *args, **kwargs):
        self.object = self.get_object()
        data = self.get_context_data()
        return HttpResponse(
            content=json.dumps(data),
            content_type='application/json',
            status=200
        )

    def get_context_data(self, **kwargs):
        context = {}

        data = self.get_router_view_context_data()
        if data:
            context['data'] = data

        partials = self.get_view_partials()
        if partials:
            context['partials'] = partials

        return context
