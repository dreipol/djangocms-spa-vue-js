from django.core.urlresolvers import reverse


def get_vue_js_link_dict(cms_page=None, project=None, external_link=None):
    if cms_page:
        try:
            slug = cms_page.title_set.first().slug
            return {
                'fetch': reverse('api:cms_page_detail', kwargs={'slug': slug}),
                'name': get_vue_js_router_name_for_cms_page(slug)
            }
        except:
            return {}
    elif project:
        return project.get_vue_js_link_dict()
    elif external_link:
        return {
            'fetch': external_link
        }
    else:
        return {}


def get_vue_js_router_name_for_cms_page(pk):
    return 'cms-page-%d' % pk
