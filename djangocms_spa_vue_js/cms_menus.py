from cms.models import Page, force_text
from django.conf import settings
from django.core.urlresolvers import reverse
from menus.base import Modifier
from menus.menu_pool import menu_pool

from djangocms_spa.content_helpers import (get_frontend_data_dict_for_cms_page, get_frontend_data_dict_for_partials,
                                           get_partial_names_for_template)
from djangocms_spa.utils import get_frontend_component_name_by_template, get_view_from_url

from .router_helpers import get_vue_js_router_name_for_cms_page


class VueJsMenuModifier(Modifier):
    """
    This menu modifier extends the nodes with data that is needed by the Vue JS route object and by the frontend to
    render all contents. Make sure all your custom models are attached to the CMS menu.

    Expected menu structure:
    - Home
        - Page A
        - Page B
            - Page B1
        - Page C
        - News list (App hook)
            - News detail A
            - News detail B
    """
    @staticmethod
    def get_node_template_name(node):
        view = get_view_from_url(node.url)
        if view.__module__ == 'cms.views':
            return node.attr.get('template')
        else:
            return view.template_name

    def modify(self, request, nodes, namespace, root_id, post_cut, breadcrumb):
        # If the menu is not yet cut, don't do anything.
        if post_cut:
            return nodes

        # Prevent parsing all this again when rendering the menu in a second step.
        if hasattr(self.renderer, 'vue_js_structure_started'):
            return nodes
        else:
            self.renderer.vue_js_structure_started = True

        router_nodes = []

        for node in nodes:
            if node.attr.get('is_page'):
                node.attr['cms_page'] = Page.objects.get(id=node.id)

            if not node.attr.get('nest_route'):
                node_route = self.get_node_route(request, node)
                if node_route:
                    node.attr['vue_js_route'] = node_route
                    router_nodes.append(node)

        # To make sure all menu modifiers are handled, we parse the nested children in a second step.
        for router_node in router_nodes:
            children = self.get_node_route_children(node=router_node, request=request)
            if children:
                router_node.attr['vue_js_route']['children'] = children

        return router_nodes

    def get_node_route(self, request, node):
        # Initial data of the route.
        route_data = {
            'api': {},
        }

        if node.attr.get('is_page'):
            route = self.get_node_route_for_cms_page(request, node, route_data)
        else:
            route = self.get_node_route_for_app_model(request, node, route_data)

        if node.selected and node.url == request.path:
            # Static CMS placeholders and other global page elements (e.g. menu) go into the `partials` dict.
            partial_names = get_partial_names_for_template(template=self.get_node_template_name(node))
            route['api']['fetched']['partials'] = get_frontend_data_dict_for_partials(
                partials=partial_names,
                request=request,
                editable=request.user.has_perm('cms.edit_static_placeholder'),
                renderer=self.renderer,
            )

        # Add query params
        template_path = self.get_node_template_name(node)
        try:
            partials = settings.DJANGOCMS_SPA_TEMPLATES[template_path]['partials']
        except KeyError:
            partials = []
        if partials:
            route_data['api'].setdefault('query', {}).update({'partials': partials})

        return route

    def get_node_route_for_cms_page(self, request, node, route_data):
        cms_page = node.attr['cms_page']
        cms_page_title = cms_page.title_set.get(language=request.LANGUAGE_CODE)
        cms_template = cms_page.get_template()

        # Set name and component of the route.
        route_data['component'] = get_frontend_component_name_by_template(cms_template)
        route_data['name'] = get_vue_js_router_name_for_cms_page(cms_page.pk)

        # Add the link to fetch the data from the API.
        if not cms_page.application_urls:
            if not cms_page_title.path:  # The home page does not have a path
                fetch_url = reverse('api:cms_page_detail_home', kwargs={'language_code': request.LANGUAGE_CODE})
            else:
                fetch_url = reverse('api:cms_page_detail', kwargs={'language_code': request.LANGUAGE_CODE,
                                                                   'path': cms_page_title.path})
            route_data['api']['fetch'] = fetch_url

            # Add redirect url if available.
            if node.attr.get('redirect_url'):
                route_data['redirect'] = node.attr['redirect_url']

        else:
            # Apphooks use a view that has a custom API URL to fetch data from.
            view = get_view_from_url(node.url)
            fetch_url = force_text(view().get_fetch_url())
            route_data['api']['fetch'] = fetch_url

        # Add initial data for the selected page.
        if node.selected and node.url == request.path:
            route_data['api']['fetched'] = {
                'data': get_frontend_data_dict_for_cms_page(
                    cms_page=cms_page,
                    cms_page_title=cms_page_title,
                    request=request,
                    editable=request.user.has_perm('cms.change_page')
                )
            }

        if len(settings.LANGUAGES) > 1:
            route_data['path'] = '/%s/%s' % (request.LANGUAGE_CODE, cms_page_title.path)
        else:
            route_data['path'] = '/%s' % cms_page_title.path

        return route_data

    def get_node_route_for_app_model(self, request, node, route_data):
        # Set name and component of the route.
        route_data['component'] = node.attr.get('component')
        route_data['name'] = node.attr.get('vue_js_router_name')

        # Add the link to fetch the data from the API.
        route_data['api']['fetch'] = node.attr.get('fetch_url')

        # We need to prepare the initial structure of the fetched data. The actual data is added by the view.
        if request.path == node.attr.get('absolute_url'):
            route_data['api']['fetched'] = {
                'data': {}
            }
            route_data['params'] = node.attr.get('url_params', {})

        route_data['path'] = node.url
        return route_data

    def get_node_route_children(self, node, request):
        """
        Child nodes usually share components with each other. Let's assume having a news app. The list view shares
        some components with its detail pages. All detail pages look exactly the same. Using the `nested` feature of
        vue-router, we add one generic route rather than adding all detail pages. Therefor we need to use a generic
        `path` (e.g. `:slug`) that we get from the nodes `path_pattern` property.
        """
        children = []
        children_path_patterns = []
        for child_node in node.children:

            if child_node.attr.get('nest_route'):
                child_path_pattern = child_node.attr.get('path_pattern')

                if not child_path_pattern or child_path_pattern not in children_path_patterns:
                    child_route = self.get_node_route(request, child_node)
                    child_route['path'] = child_path_pattern
                    children.append(child_route)
                    children_path_patterns.append(child_path_pattern)
                elif child_path_pattern in children_path_patterns and child_node.url == request.path:
                    i = child_path_pattern.index(child_path_pattern)
                    children[i] = self.get_node_route(request, child_node)
                    children[i]['path'] = child_path_pattern

        return children

menu_pool.register_modifier(VueJsMenuModifier)
