from menus.menu_pool import menu_pool


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
