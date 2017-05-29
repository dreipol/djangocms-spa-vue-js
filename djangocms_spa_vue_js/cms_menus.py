from cms.models import Page
from menus.base import Modifier
from menus.menu_pool import menu_pool

from djangocms_spa_vue_js.menu_helpers import get_node_route, get_node_route_children


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
            if node.attr.get('is_page'):
                node.attr['cms_page'] = Page.objects.get(id=node.id)

            if not node.attr.get('nest_route'):
                node_route = get_node_route(request=request, node=node, renderer=self.renderer)
                if node_route:
                    node.attr['vue_js_route'] = node_route
                    router_nodes.append(node)

        # To make sure all menu modifiers are handled, we parse the nested children in a second step.
        for router_node in router_nodes:
            children = get_node_route_children(node=router_node, request=request, renderer=self.renderer)
            if children:
                router_node.attr['vue_js_route']['children'] = children

        return router_nodes

menu_pool.register_modifier(VueJsMenuModifier)
