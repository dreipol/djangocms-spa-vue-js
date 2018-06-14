from appconf import AppConf
from django.core.handlers.wsgi import WSGIRequest
from django.db.models import Model
from django.urls import reverse
from django.utils.translation import override, get_language
from django.views.defaults import ERROR_404_TEMPLATE_NAME

from djangocms_spa.content_helpers import get_frontend_data_dict_for_placeholders, get_global_placeholder_data
from djangocms_spa.models import DjangoCmsMixin


class DjangoCmsSPAVueJSConf(AppConf):
    ERROR_404_TEMPLATE = ERROR_404_TEMPLATE_NAME
    APPHOOKS_WITH_ROOT_URL = []  # list of apphooks that use a custom view on the root url (e.g. "/en/<app_hook_page>/")


class DjangocmsVueJsMixin(DjangoCmsMixin):
    """
    Set up some helper methods to prepare the model for the vue frontend integration.
    This mixin defines the different routes and sets up functions to generate the
    json output for either list or detail view.
    """

    # Configs used to generate vue specific stuff. route_patterns has to be a list
    # with tuples where index 0 matches a parameter from route_parameters and
    # index 1 a vue route pattern like :model to replace.
    vue_config = {
        'router_name': 'app-model',
        'router_component': 'model-detail',
        'route_patterns': [('slug', ':model')],
    }

    # Config dict holding the route groups indexed by group name. Each group contains different
    # view routes, normally there is one for the list view and one for the detail view.
    routes = {
        'api': {'list': 'model_list_api', 'detail': 'model_detail_api'},
        'normal': {'list': 'model_list', 'detail': 'model_detail'},
    }

    # Kwargs that need no be passed to the reverse() function to resolve a specific named route.
    # We assume that views in different groups all need the same route parameters.
    #
    # Possible options:
    #   - None                          -> no kwargs needed
    #   - 'string'                      -> string, meaning that your route parameter and your model field share
    #                                      the same name
    #   - ('parameter', 'attribute')    -> tuple, your model route parameter and field name are different
    #   - ['string', 'string']          -> list with strings, tuples or a mix of both
    route_parameters = {
        'list': None,
        'detail': 'slug',
    }

    class Meta:
        abstract = True

    @property
    def vue_js_link(self) -> dict:
        """ Generate detail api view url so the vue router knows where to fetch this model """
        return {
            'name': self.vue_config['router_name'],
            'fetch': self.url(group='api', view='detail')
        }

    @classmethod
    def menu_node_attributes(cls, view: str = 'detail') -> dict:
        """ Get additional attributes for custom NavigationNode """
        return {
            'component': cls.vue_config['router_component'],
            'vue_js_router_name': cls.vue_config['router_name'],
            'named_route_path_patterns': dict(cls.vue_config['route_patterns']),
            'named_route_path': cls._vue_pattern_url(group='api', view=view),
            'fetch_url': cls._vue_pattern_url(group='normal', view=view),
        }

    def get_frontend_list_data_dict(
        self,
        request: WSGIRequest,
        editable: bool = False,
        placeholder_name: str = ''
    ) -> dict:
        """
        Prepare a base dict for the list view. This should be extended by the model
        to include any additional data. If no custom view is defined in
        views.py this method is not used.
        """
        data = {}

        if editable:
            data.update(self.get_cms_placeholder_json(request=request, placeholder_name=placeholder_name))

        data.update({
            'content': {'id': self.pk, 'link': self.vue_js_link}
        })

        return data

    def get_frontend_detail_data_dict(self, request: WSGIRequest, editable: bool = False) -> dict:
        """
        Same as get_frontend_list_data_dict but for the model detail view. Also takes care of any
        PlaceholderField on the model and renders their plugins.
        """
        data = {}

        # Add all placeholder fields.
        placeholder_field_names = self.get_placeholder_field_names()
        placeholders = [getattr(self, placeholder_field_name) for placeholder_field_name in placeholder_field_names]
        placeholder_frontend_data_dict = get_frontend_data_dict_for_placeholders(
            placeholders=placeholders,
            request=request,
            editable=editable
        )
        global_placeholder_data_dict = get_global_placeholder_data(placeholder_frontend_data_dict)
        data['containers'] = placeholder_frontend_data_dict

        if global_placeholder_data_dict:
            data['global_placeholder_data'] = global_placeholder_data_dict

        return data

    def url(self, group: str, view: str, language: str = None) -> str:
        """
        Acts as a proxy to _static_url with less arguments since this method
        will be called on a model instance and is not static.
        """
        language = language or get_language()

        return self._static_url(group, view, self, language)

    @classmethod
    def _static_url(
        cls,
        group: str,
        view: str,
        model=None,
        language: str = None
    ) -> str:
        """
        Generate reverse() url to route view based on the passed in 'routes' dict. cls.route_parameters and 'model'
        is then used to generate the correct kwargs parameters for reverse().
        """
        language = language or get_language()
        route_name = cls.routes[group][view]

        with override(language):
            return reverse(route_name, kwargs=cls._reverse_kwargs(cls.route_parameters[view], model))

    @classmethod
    def _vue_pattern_url(
        cls,
        group: str = 'normal',
        view: str = 'detail',
        valid: bool = False
    ) -> str:
        """
        Since we don't want to print hundreds of detail model urls in the frontend, we can generate routes à la
        en/api/model/:model A NavigationNode needs a required url parameter and ':model' would not match
        the regex defined in the model route. If we pass in valid = True a string like
        'en/api/model/_replace_slug_' will be returned. Since this NavigationNode is
        only used for the frontend this is an "acceptable hack"™ :)
        """
        replace_strings = []
        for pattern in cls.vue_config['route_patterns']:
            replace_strings.append('_replace_' + pattern[0] + '_')

        url = cls._static_url(group=group, view=view, model=replace_strings)

        if not valid:
            for index, pattern in enumerate(cls.vue_config['route_patterns']):
                url = url.replace(replace_strings[index], pattern[1])

        return url

    @classmethod
    def _reverse_kwargs(cls, route_attributes, model=None) -> dict:
        """
        Generate kwargs vor reverse() based on cls.route_parameters. Basically just get the appropriate
        attribute from our 'model' with a simple exception: if model is a list we're in the process
        of faking a url so we just assign the string to the kwarg parameter.
        """
        return_kwargs = {}

        if not isinstance(route_attributes, list):
            route_attributes = [route_attributes]

        for index, route_attribute in enumerate(route_attributes):
            if isinstance(route_attribute, str):
                parameter = attribute = route_attribute
            else:
                parameter = route_attribute[0]
                attribute = route_attribute[1]

            if isinstance(model, list):
                return_kwargs[parameter] = model[index]
            else:
                return_kwargs[parameter] = getattr(model, attribute)

        return return_kwargs

    def get_absolute_url(self, language: str = None) -> str:
        return self.url(group='normal', view='detail', language=language)
