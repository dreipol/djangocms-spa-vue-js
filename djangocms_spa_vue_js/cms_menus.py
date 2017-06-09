from cms.models import Page
from menus.base import Modifier
from menus.menu_pool import menu_pool

from djangocms_spa_vue_js.menu_helpers import get_node_route


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
        path_patterns = {}

        for node in nodes:
            if node.attr.get('is_page'):
                node.attr['cms_page'] = Page.objects.get(id=node.id)

            node_route = get_node_route(request=request, node=node, renderer=self.renderer)
            if node.attr.get('nest_route'):
                path_pattern = node.attr.get('path_pattern')

                if not path_pattern or path_pattern not in path_patterns.keys():
                    node_route['path'] = '{parent_url}{path_pattern}/'.format(parent_url=node.parent.url,
                                                                              path_pattern=path_pattern)
                    path_patterns[path_pattern] = len(router_nodes)  # Store the index of this route in the list
                elif path_pattern in path_patterns and node.url == request.path:
                    index_of_first_nested_route = path_patterns[path_pattern]
                    router_nodes[index_of_first_nested_route]['vue_js_route']['path'] = path_pattern
                    continue  # Just set a more detailed path on the processed path of the same pattern
                else:
                    continue  # Ignore nested routes with a path pattern that was already processed

            node.attr['vue_js_route'] = node_route
            router_nodes.append(node)

        return router_nodes

menu_pool.register_modifier(VueJsMenuModifier)
