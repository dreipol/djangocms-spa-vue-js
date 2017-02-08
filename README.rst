====================
djangocms-spa-vue-js
====================

This package prepares your django CMS and Vue.js project to create a single-page application (SPA).


Quickstart
----------

Install djangocms-spa-vue-js::

    pip install djangocms-spa-vue-js

Add it to your `INSTALLED_APPS`:

.. code-block:: python

    INSTALLED_APPS = (
        ...
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


Template tag
------------

Render your Vue.js router in your template::

    {% load router_tags %}
    {% vue_js_router as router %}{{ router|escape_apostrophe }}


Plugin
------

All your plugins need a `render_json_plugin` method::

    class TextPlugin(JsonOnlyPluginBase):
        name = _('Text')
        model = TextPluginModel
        frontend_component_name = 'cmp-text'

        def render_json_plugin(self, **kwargs):
            context = super(TextPlugin, self).render_json_plugin(**kwargs)
            context['content']['text']. = self.instance.text
            return context

    plugin_pool.register_plugin(TextPlugin)


Credits
-------

Tools used in rendering this package:

*  Cookiecutter_
*  `cookiecutter-djangopackage`_

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`cookiecutter-djangopackage`: https://github.com/pydanny/cookiecutter-djangopackage
