from django.conf import settings
from django.urls import Resolver404, reverse, resolve
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
        if not template:
            try:
                template = node.attr.get('cms_page').get_template()
            except:
                template = settings.DJANGOCMS_SPA_VUE_JS_ERROR_404_TEMPLATE
        return template
    else:
        return view.template_name


def get_node_route(request, node, renderer):
    # Initial data of the route.
    route_data = {
        'api': {},
    }

    if node.attr.get('is_page'):
        route = get_node_route_for_cms_page(request, node, route_data)
    else:
        route = get_node_route_for_app_model(request, node, route_data)

    if node.selected and node.get_absolute_url() == request.path:
        # Static CMS placeholders and other global page elements (e.g. menu) go into the `partials` dict.
        partial_names = get_partial_names_for_template(template=get_node_template_name(node))
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


def get_node_route_for_cms_page(request, node, route_data):
    cms_page = node.attr['cms_page']
    cms_page_title = cms_page.title_set.get(language=request.LANGUAGE_CODE)
    cms_template = cms_page.get_template()

    # Set name and component of the route.
    route_data['name'] = get_vue_js_router_name_for_cms_page(cms_page.pk)
    if not node.attr.get('redirect_url'):
        route_data['component'] = get_frontend_component_name_by_template(cms_template)

    # Add the link to fetch the data from the API.
    if cms_page.application_urls not in settings.DJANGOCMS_SPA_VUE_JS_APPHOOKS_WITH_ROOT_URL:
        if not cms_page_title.path:  # The home page does not have a path
            fetch_url = reverse('api:cms_page_detail_home')
        elif node.attr.get('named_route_path_pattern'):
            # Get the fetch_url of the parent node through the path of the parent node
            parent_node_path = cms_page_title.path.replace('/%s' % cms_page_title.slug, '')
            fetch_url_of_parent_node = reverse('api:cms_page_detail', kwargs={'path': parent_node_path})
            fetch_url = '{parent_url}{path_pattern}/'.format(parent_url=fetch_url_of_parent_node,
                                                             path_pattern=node.attr.get('named_route_path_pattern'))
        else:
            fetch_url = reverse('api:cms_page_detail', kwargs={'path': cms_page_title.path})

        # Add redirect url if available.
        if node.attr.get('redirect_url'):
            route_data['redirect'] = node.attr['redirect_url']

    else:
        # Apphooks use a view that has a custom API URL to fetch data from.
        view = get_view_from_url(node.get_absolute_url())
        fetch_url = force_text(view().get_fetch_url())

    route_data['api']['fetch'] = {
        'url': fetch_url,
        'cache': bool(node.attr['cache']) if 'cache' in node.attr.keys() else True
    }

    # Add initial data for the selected page.
    if node.selected and node.get_absolute_url() == request.path:
        fetched_data = {
            'response': {
                'data': get_frontend_data_dict_for_cms_page(
                    cms_page=cms_page,
                    cms_page_title=cms_page_title,
                    request=request,
                    editable=request.user.has_perm('cms.change_page')
                )
            }
        }
        if node.attr.get('named_route_path_pattern'):
            url_param = node.attr['named_route_path_pattern'].replace(':', '')
            if url_param:
                fetched_data.update({
                    'params': {
                        url_param: cms_page_title.slug
                    }
                })
        route_data['api']['fetched'] = fetched_data

    if len(settings.LANGUAGES) > 1:
        route_data['path'] = '/%s/%s' % (request.LANGUAGE_CODE, cms_page_title.path)
    else:
        route_data['path'] = '/%s' % cms_page_title.path

    return route_data


def get_node_route_for_app_model(request, node, route_data):
    # Set name and component of the route.
    route_data['component'] = node.attr.get('component')
    route_data['name'] = node.attr.get('vue_js_router_name')

    # Add the link to fetch the data from the API.
    route_data['api']['fetch'] = {
        'url': node.attr.get('fetch_url'),
        'cache': bool(node.attr['cache']) if 'cache' in node.attr.keys() else True
    }

    request_url_name = resolve(request.path).url_name
    node_url_name = resolve(node.get_absolute_url()).url_name
    is_selected_node = request.path == node.get_absolute_url() or request_url_name == node_url_name
    if is_selected_node:
        # We need to prepare the initial structure of the fetched data. The actual data is added by the view.
        route_data['api']['fetched'] = {
            'response': {
                'data': {}
            }
        }
        route_data['params'] = node.attr.get('url_params', {})

    route_data['path'] = node.get_absolute_url()
    return route_data
