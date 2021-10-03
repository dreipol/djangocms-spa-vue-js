from cms.models import Page
from django.conf import settings
from django.urls import Resolver404, resolve, reverse
from django.utils.encoding import force_text
from menus.menu_pool import menu_pool

from djangocms_spa.content_helpers import (get_frontend_data_dict_for_cms_page, get_frontend_data_dict_for_partials,
                                           get_partial_names_for_template)
from djangocms_spa.utils import get_frontend_component_name_by_template, get_view_from_url
from .router_helpers import get_vue_js_router_name_for_cms_page


def get_vue_js_router(context=None, request=None):
    """
    Returns a list of all routes (CMS pages, projects, team members, etc.) that are in the menu of django CMS. The list
    contains a dict structure that is used by the Vue JS router.
    """
    vue_routes = []
    menu_renderer = get_menu_renderer(context=context, request=request)

    # For the usage of template tags inside our menu modifier we need to make it available on our menu_renderer.
    # The `set_context` method is a monkey patch and no part of the original class.
    menu_renderer.set_context(context)

    menu_nodes = menu_renderer.get_nodes()
    for node in menu_nodes:
        if node.attr.get('vue_js_route'):
            vue_routes.append(node.attr.get('vue_js_route'))

    return {'routes': vue_routes}


def get_menu_renderer(context=None, request=None):
    menu_renderer = None

    if context:
        menu_renderer = context.get('cms_menu_renderer')

    if not menu_renderer:
        menu_renderer = menu_pool.get_renderer(request)

    return menu_renderer


def get_node_template_name(node):
    try:
        view = get_view_from_url(node.get_absolute_url())
    except (AttributeError, Resolver404):
        return settings.DJANGOCMS_SPA_VUE_JS_ERROR_404_TEMPLATE
    if view.__module__ == 'cms.views':
        template = node.attr.get('template')
        if template:
            return template
        else:
            try:
                return node.attr.get('cms_page').get_template()
            except:
                return settings.DJANGOCMS_SPA_VUE_JS_ERROR_404_TEMPLATE
    else:
        try:
            return view.template_name
        except AttributeError:
            return settings.DJANGOCMS_SPA_DEFAULT_TEMPLATE


def get_node_route(request, node, renderer, template=''):
    # Initial data of the route.
    route_data = {
        'api': {},
    }

    if node.attr.get('is_page'):
        route = get_node_route_for_cms_page(request, node, route_data, node.attr.get('router_page'))
    else:
        route = get_node_route_for_app_model(request, node, route_data)

    if not node.attr.get('use_cache', True):
        route['api']['fetch']['useCache'] = False

    if node.selected and node.get_absolute_url() == request.path:
        if not template:
            template = get_node_template_name(node)

        # Static CMS placeholders and other global page elements (e.g. menu) go into the `partials` dict.
        partial_names = get_partial_names_for_template(template=template)
        route['api']['fetched']['response']['partials'] = get_frontend_data_dict_for_partials(
            partials=partial_names,
            request=request,
            editable=request.user.has_perm('cms.edit_static_placeholder'),
            renderer=renderer,
        )

    # Add query params
    template_path = get_node_template_name(node)
    try:
        partials = settings.DJANGOCMS_SPA_TEMPLATES[template_path]['partials']
    except KeyError:
        partials = []
    if partials:
        route_data['api']['fetch'].setdefault('query', {}).update({'partials': partials})

    if node.attr.get('redirect_url'):
        del route_data['api']

    return route


def get_node_route_for_cms_page(request, node, route_data, router_page):
    # Set name and component of the route.
    route_data['name'] = get_vue_js_router_name_for_cms_page(router_page.pk)
    if not node.attr.get('redirect_url'):
        try:
            component = get_frontend_component_name_by_template(router_page.template)
        except KeyError:
            component = settings.DJANGOCMS_SPA_TEMPLATES[settings.DJANGOCMS_SPA_DEFAULT_TEMPLATE]['frontend_component_name']
        route_data['component'] = component

    # Add the link to fetch the data from the API.
    if router_page.application_urls not in settings.DJANGOCMS_SPA_VUE_JS_APPHOOKS_WITH_ROOT_URL:
        if not router_page.title_path:  # The home page does not have a path
            if hasattr(settings, 'DJANGOCMS_SPA_USE_SERIALIZERS') and settings.DJANGOCMS_SPA_USE_SERIALIZERS:
                fetch_url = reverse('api:cms_page_detail', kwargs={'path': settings.DJANGOCMS_SPA_HOME_PATH})
            else:
                fetch_url = reverse('api:cms_page_detail_home')
        elif node.attr.get('named_route_path_pattern'):
            # Get the fetch_url of the parent node through the path of the parent node
            parent_node_path = router_page.title_path.replace('/%s' % router_page.title_slug, '')
            fetch_url_of_parent_node = reverse('api:cms_page_detail', kwargs={'path': parent_node_path})
            fetch_url = '{parent_url}{path_pattern}/'.format(parent_url=fetch_url_of_parent_node,
                                                             path_pattern=node.attr.get('named_route_path_pattern'))
        else:
            fetch_url = reverse('api:cms_page_detail', kwargs={'path': router_page.title_path})

        # Add redirect url if available.
        if node.attr.get('redirect_url'):
            route_data['redirect'] = node.attr['redirect_url']

    else:
        # Apphooks use a view that has a custom API URL to fetch data from.
        view = get_view_from_url(node.get_absolute_url())
        fetch_url = force_text(view().get_fetch_url())

    route_data['api']['fetch'] = {
        'url': fetch_url,
    }

    if router_page.reverse_id:
        route_data['meta'] = {
            'id': router_page.reverse_id
        }

    # Add initial data for the selected page.
    if node.selected and node.get_absolute_url() == request.path:
        cms_page = Page.objects.get(pk=router_page.pk)
        if hasattr(settings, 'DJANGOCMS_SPA_USE_SERIALIZERS') and settings.DJANGOCMS_SPA_USE_SERIALIZERS:
            from djangocms_spa.serializers import PageSerializer
            data = PageSerializer(instance=cms_page).data
        else:
            data = get_frontend_data_dict_for_cms_page(
                cms_page=cms_page,
                cms_page_title=cms_page.title_set.get(language=request.LANGUAGE_CODE),
                request=request,
                editable=request.user.has_perm('cms.change_page')
            )

        fetched_data = {
            'response': {
                'data': data
            }
        }
        if node.attr.get('named_route_path_pattern'):
            url_param = node.attr['named_route_path_pattern'].replace(':', '')
            if url_param:
                fetched_data.update({
                    'params': {
                        url_param: router_page.slug
                    }
                })
        route_data['api']['fetched'] = fetched_data

    if settings.DJANGOCMS_SPA_VUE_JS_USE_I18N_PATTERNS:
        route_data['path'] = '/%s/%s' % (request.LANGUAGE_CODE, router_page.title_path)
    else:
        route_data['path'] = '/%s' % router_page.title_path

    return route_data


def get_node_route_for_app_model(request, node, route_data):
    # Set name and component of the route.
    route_data['component'] = node.attr.get('component')
    route_data['name'] = node.attr.get('vue_js_router_name')

    # Add the link to fetch the data from the API.
    route_data['api']['fetch'] = {
        'url': node.attr.get('fetch_url'),
    }

    try:
        request_url_name = resolve(request.path).url_name
        node_url_name = resolve(node.get_absolute_url()).url_name
    except Resolver404:
        resolver_match = False
    else:
        resolver_match = request_url_name == node_url_name

    is_selected_node = request.path == node.get_absolute_url() or resolver_match
    if is_selected_node:
        # We need to prepare the initial structure of the fetched data. The actual data is added by the view.
        route_data['api']['fetched'] = {
            'response': {
                'data': {}
            }
        }
        route_data['params'] = node.attr.get('url_params', {})

    meta_id = node.attr.get('id')
    if meta_id:
        route_data['meta'] = {
            'id': meta_id
        }

    route_data['path'] = node.get_absolute_url()
    return route_data
