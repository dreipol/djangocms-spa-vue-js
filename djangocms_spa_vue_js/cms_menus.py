from cms.models import Page, Title
from django.conf import settings
from django.core.urlresolvers import resolve, reverse
from djangocms_spa.content_helpers import (get_frontend_data_dict_for_cms_page, get_frontend_data_dict_for_partials,
                                           get_partial_names_for_template)
from djangocms_spa.utils import get_frontend_component_name_by_template, get_template_path_by_frontend_component_name
from menus.base import Modifier
from menus.menu_pool import menu_pool

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
            if not node.attr.get('nest_route'):
                node_route = self.get_node_route(request, node)
                if node_route:
                    node.attr['vue_js_route'] = node_route
                    router_nodes.append(node)

        # To make sure all properties are available, we parse the nested children in a second step.
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

        if node.selected:
            # Static CMS placeholders and other global page elements (e.g. menu) go into the `partials` dict.
            partial_names = get_partial_names_for_template(template=node.attr.get('template'))
            route['api']['fetched']['partials'] = get_frontend_data_dict_for_partials(
                partials=partial_names,
                request=request,
                include_admin_data=request.user.has_perm('cms.edit_static_placeholder'),
                renderer=self.renderer,
            )

        # Add query params
        template_path = get_template_path_by_frontend_component_name(route['component'])
        try:
            partials = settings.DJANGOCMS_SPA_TEMPLATES[template_path]['partials']
        except KeyError:
            partials = []
        if partials:
            route_data['api'].setdefault('query', {}).update({'partials': partials})

        return route

    def get_node_route_for_cms_page(self, request, node, route_data):
        # Fetch some data from the database.
        try:
            cms_page = Page.objects.get(id=node.id)
            cms_page_title = cms_page.title_set.get(language=request.LANGUAGE_CODE)
        except (Page.DoesNotExist, Title.DoesNotExist):
            return False

        # Update some other values of the node.
        cms_template = cms_page.get_template()
        route_data['component'] = get_frontend_component_name_by_template(cms_template)
        route_data['name'] = get_vue_js_router_name_for_cms_page(cms_page.pk)

        # Add the fetch url
        if not cms_page.application_urls:
            route_data['api']['fetch'] = reverse('api:cms_page_detail', kwargs={'path': cms_page_title.path})
        else:
            # A CMS page with an app hook is most likely a list view and needs to fetch the data from the model API.
            # Because the url names of the list and api view are the same, we can get the reverse url easily by
            # resolving the node url. Because of a strange behaviour we need to make sure we have a trailing slash,
            # otherwise the resolver would not find the page.
            fixed_url = node.url + '/' if node.url[-1] != '/' else node.url
            resolved_url = resolve(fixed_url)
            view_class_module_path = resolved_url._func_path  # e.g. my_app.views.views.MyListView
            app_name = view_class_module_path[:view_class_module_path.index('.')]
            app_slug_setting_variable_name = '{}_URL_PART'.format(app_name.upper())
            app_slug = getattr(settings, app_slug_setting_variable_name)

            route_data['api']['fetch'] = reverse('api:%s' % resolved_url.url_name, kwargs={'app_slug': app_slug})

        # Add initial data for the selected page.
        if node.selected:
            route_data['api']['fetched'] = {
                'data': get_frontend_data_dict_for_cms_page(
                    cms_page=cms_page,
                    cms_page_title=cms_page_title,
                    request=request,
                    include_admin_data=request.user.has_perm('cms.change_page')
                )
            }

        route_data['path'] = '/%s' % cms_page_title.path

        return route_data

    def get_node_route_for_app_model(self, request, node, route_data):
        # Set name and component.
        route_data['component'] = node.attr.get('component')
        route_data['name'] = node.attr.get('vue_js_router_name')

        # Add the link to fetch the data from the API.
        route_data['api']['fetch'] = node.attr.get('fetch_url')

        # We need to prepare the initial structure of the fetched data.
        if request.path == node.attr.get('absolute_url'):
            route_data['api']['fetched'] = {
                'data': {}
            }

        # The sub route is generic. Therefor the frontend router does not know which instance is active. This is why
        # we set the slug as param to the sub route object.
        if request.path == node.attr.get('absolute_url'):
            route_data['params'] = {'slug': node.attr.get('slug')}

        route_data['path'] = '%s' % node.attr.get('slug')
        return route_data

    def get_node_route_children(self, node, request):
        """
        If some of the frontend components can be shared between parent and child, the child node should be nested
        into its parent route.
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

        return children

menu_pool.register_modifier(VueJsMenuModifier)
