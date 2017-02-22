from djangocms_spa.content_helpers import get_frontend_data_dict_for_placeholders, get_global_placeholder_data
from djangocms_spa.models import DjangoCmsMixin


class DjangocmsVueJsMixin(DjangoCmsMixin):
    """
    This mixin prepares the data of a model to be ready for the frontend.
    """
    vue_js_router_component = 'topic-detail'

    class Meta:
        abstract = True

    @property
    def vue_js_router_name(self):
        return '%s-%s' % (self._meta.app_label, self._meta.model_name)

    def get_frontend_list_data_dict(self, request, editable=False, placeholder_name=''):
        data = {}

        if editable:
            data.update(self.get_cms_placeholder_json(request=request, placeholder_name=placeholder_name))

        data.update({
            'content': {
                'id': self.pk,
                'link': self.get_vue_js_link_dict(),
            }
        })
        return data

    def get_frontend_detail_data_dict(self, request, editable=False):
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

    def get_vue_js_link_dict(self):
        return {
            'name': self.vue_js_router_name,
            'fetch': self.get_api_detail_url()
        }

    def get_cms_menu_node_attributes(self):
        return {
            'component': self.get_detail_view_component(),
            'vue_js_router_name': self.vue_js_router_name,
            'absolute_url': self.get_absolute_url(),
            'fetch_url': self.get_api_detail_url(),
            'path_pattern': self.get_detail_path_pattern(),
            'url_params': self.get_url_params(),
            'nest_route': True
        }

    def get_absolute_url(self):
        # Override this method in your model.
        return ''

    def get_api_detail_url(self):
        # Override this method in your model.
        return ''

    def get_detail_view_component(self):
        # Override this method in your model.
        return ''

    def get_detail_path_pattern(self):
        # Used to group routes (dynamic route matching). Override this method in your model.
        return ':slug'

    def get_url_params(self):
        # Override this method in your model.
        return {
            'slug': ''
        }
