====================
djangocms-spa-vue-js
====================

This package prepares your django CMS and vue.js project to create a single-page application (SPA). Use it together
with the base package `djangocms-spa`_.

A template tag renders a list of all available routes that are used by vue-router. Contents of other pages are
requested asynchronously and delivered as JSON through a REST-API.

Make sure you read the docs of djangocms-spa.

.. _`djangocms-spa`: https://github.com/dreipol/djangocms-spa/


Quickstart
----------

Install djangocms-spa-vue-js::

    pip install djangocms-spa-vue-js

Add it to your ``INSTALLED_APPS``:

.. code-block:: python

    INSTALLED_APPS = (
        ...
        'djangocms_spa',
        'djangocms_spa_vue_js',
        ...
    )

Add the URL pattern form the API:

.. code-block:: python

    urlpatterns = [
        ...
        url(r'^api/', include('djangocms_spa.urls', namespace='api')),
        ...
    ]

Render your vue.js router in your template::

    {% load router_tags %}
    {% vue_js_router %}



Apphooks
--------

You need to consider a couple of things when using apphooks. Let's assume you have an event model.

.. code-block:: python

    class Event(DjangocmsVueJsMixin):
        name = models.CharField(max_length=255, verbose_name=_('Name'))

        def get_frontend_list_data_dict(self, request, editable=False, placeholder_name=''):
            # Returns the data for your list view.
            data = super(Event, self).get_frontend_list_data_dict(request=request, editable=editable, placeholder_name=placeholder_name)
            data['content'].update({
                'name': self.name,
            })
            return data

        def get_frontend_detail_data_dict(self, request, editable=False):
            # Returns the data for your detail view.
            data = super(Event, self).get_frontend_detail_data_dict(request, editable)

            # Prepare the content of your model instance. We use the same structure like the placeholder data of a CMS page.
            content_container = {
                'type': 'generic',
                'content': {
                    'name': self.name
                }
            }

            # Add support for the CMS frontend editing
            if editable:
                content_container.update(
                    self.get_cms_placeholder_json(request=request, placeholder_name='cms-plugin-events-content')
                )

            # Put the data inside a container like any other CMS placeholder data.
            data['containers']['content'] = content_container

            return data

        def get_absolute_url(self):
            # Return the URL of your detail view.
            return reverse('event_detail', kwargs={'pk': self.pk})

        def get_api_detail_url(self):
            # Return the API URL of your detail view.
            return reverse('event_detail_api', kwargs={'pk': self.pk})

        def get_detail_view_component(self):
            # Return the name of your vue component.
            return 'cmp-event-detail'

        def get_detail_path_pattern(self):
            # Return the path pattern of your nested vue route.
            return 'events/:pk'

        def get_url_params(self):
            # Return the params that are needed to access your nested vue route.
            return {
                'pk': self.pk
            }


All of your views need to be attached to the menu, even if they are not actually rendered in your site navigation. Your ``cms_menus.py`` might looks like this:

.. code-block:: python

    class EventMenu(CMSAttachMenu):
        name = _('Events')

        def get_nodes(self, request):
            nodes = []
            counter = 1
            is_draft = self.instance.publisher_is_draft
            is_edit = hasattr(request, 'toolbar') and request.user.is_staff and request.toolbar.edit_mode

            # We don't want to parse the instance in live and draft mode. Depending on the request user we return the
            # corresponding version.
            if (not is_edit and not is_draft) or (is_edit and is_draft):
                # Let's add the list view
                nodes.append(
                    NavigationNode(
                        title='Event List',
                        url=reverse('event_list'),
                        id=1,
                        attr={
                            'component': 'cmp-event-list',
                            'vue_js_router_name': 'event-list',
                            'fetch_url': reverse('event_list_api'),
                            'absolute_url': reverse('event_list'),
                            'path_pattern': ':pk',  # Used to group routes (dynamic route matching)
                            'nest_route': False
                        }
                    )
                )
                counter += 1

                for event in Event.objects.all():
                    nodes.append(
                        NavigationNode(
                            title=event.name,
                            url=event.get_absolute_url(),
                            id=counter,
                            attr=event.get_cms_menu_node_attributes(),
                            parent_id=1
                        )
                    )
                    counter += 1

            return nodes

    menu_pool.register_menu(EventMenu)


This is an example of a simple template view. Each view that you have needs an API view that returns the JSON data only.

.. code-block:: python

    from djangocms_spa.views import SpaApiView
    from djangocms_spa_vue_js.views import VueRouterView

    class ContentMixin(object):
        template_name = 'index.html'

        def get_fetched_data(self):
            data = {
                'containers': {
                    'content': {
                        'type': 'generic',
                        'content': {
                            'key': 'value'
                        }
                    }
                }
            }
            return data


    class MyTemplateView(ContentMixin, VueRouterView):
        fetch_url = reverse_lazy('content_api')  # URL of the API view.


    class MyTemplateApiView(ContentMixin, SpaApiView):
        pass


Your list view looks like this:

.. code-block:: python

    from djangocms_spa.views import SpaListApiView
    from djangocms_spa_vue_js.views import VueRouterListView

    class EventListView(VueRouterListView):
        fetch_url = reverse_lazy('event_list_api')
        model = Event
        template_name = 'event_list.html'


    class EventListAPIView(SpaListApiView):
        model = Event
        template_name = 'event_list.html'


Your detail view looks like this:

.. code-block:: python

    from djangocms_spa.views import SpaDetailApiView
    from djangocms_spa_vue_js.views import VueRouterDetailView

    class EventDetailView(VueRouterDetailView):
        model = Event
        template_name = 'event_detail.html'

        def get_fetch_url(self):
            return reverse('event_detail_api', kwargs={'pk': self.object.pk})


    class EventDetailAPIView(SpaDetailApiView):
        model = Event
        template_name = 'event_detail.html'


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
