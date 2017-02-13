====================
djangocms-spa-vue-js
====================

This package prepares your django CMS and Vue.js project to create a single-page application (SPA).

The first page request needs to include all available routes. A template tag takes care of rendering a
vue-router list. All other contents like CMS pages or custom views can be requested through a JSON API.


Quickstart
----------

Install djangocms-spa-vue-js::

    pip install djangocms-spa-vue-js

Add it to your `INSTALLED_APPS`:

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'djangocms_spa',
        'djangocms_spa_vue_js',
        ...
    )

Add the URL pattern form the API:

.. code-block:: python

    from django.conf.urls import url

    from djangocms_spa_vue_js.views import CMSPageDetailAPIView


    urlpatterns = [
        ...
        url(r'^api/pages/(?P<path>.*)$', CMSPageDetailAPIView.as_view(), name='cms_page_detail'),
        ...
    ]

Render your Vue.js router in your template::

    {% load router_tags %}
    {% vue_js_router as router %}{{ router|escape_apostrophe }}


Plugin
------

Your plugins don't need a rendering template but a `render_json_plugin` method that returns a dictionary::

    class TextPlugin(JsonOnlyPluginBase):
        name = _('Text')
        model = TextPluginModel
        frontend_component_name = 'cmp-text'

        def render_spa(self, request, context, instance):
            context = super(TextPlugin, self).render_spa(request, context, instance)
            context['content']['text']. = instance.text
            return context

    plugin_pool.register_plugin(TextPlugin)


The router object
-----------------

The server needs to prepare the routes for the frontend. The easiest way to do this is by iterating over the CMS
menu. In order to bring all available routes to the menu, you have to register all your custom URLs as a menu too.
A template tag renders a JS object like this.

.. code-block:: json

    {
        "routes": [
            {
                "api": {
                    "fetch": "/api/pages/",
                    "query": {
                        "partials": ["menu", "footer"]
                    }
                },
                "component": "index",
                "name": "cms-page-1",
                "path": "/"
            },
            {
                "api": {
                    "fetched": {
                        "partials": {
                            "menu": {
                                "type": "generic",
                                "content": {
                                    "menu": [
                                        {
                                            "path": "/",
                                            "label": "Home",
                                            "children": [
                                                {
                                                    "path": "/about",
                                                    "label": "About",
                                                    "children": [
                                                        {
                                                            "path": "/contact",
                                                            "label": "Contact"
                                                        }
                                                    ]
                                                }
                                            ]
                                        }
                                    ]
                                }
                            },
                            "footer": {
                                "type": "cmp-footer",
                                "plugins": [
                                    {
                                        "type": "cmp-footer-text",
                                        "position": 0,
                                        "content": {
                                            "text": "Lorem ipsum dolor sit amet, nam et modus tollit."
                                        }
                                    }
                                ]
                            }
                        },
                        "data": {
                            "meta": {
                                "description": "",
                                "title": "Content-Plugins"
                            },
                            "containers": {
                                "main": {
                                    "type": "cmp-main",
                                    "plugins": [
                                        {
                                            "type": "cmp-text",
                                            "position": 0,
                                            "content": {
                                                "text": "Ex vim saperet habemus, et eum impetus mentitum, cum purto dolores similique ei."
                                            }
                                        }
                                    ]
                                }
                            },
                            "title": "About"
                        }
                    },
                    "query": {
                        "partials": ["menu", "footer"]
                    }
                },
                "component": "content-with-section-navigation",
                "name": "cms-page-2",
                "path": "/about"
            },
            {
                "api": {
                    "fetch": "/api/pages/about/contact",
                    "query": {
                        "partials": ["menu", "meta", "footer"]
                    }
                },
                "component": "content-with-section-navigation",
                "name": "cms-page-3",
                "path": "/about/contact"
            }
        ]
    }


Credits
-------

Tools used in rendering this package:

*  Cookiecutter_
*  `cookiecutter-djangopackage`_

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-djangopackage`: https://github.com/pydanny/cookiecutter-djangopackage
