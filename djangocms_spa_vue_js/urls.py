from django.conf.urls import url

from .views import VueCmsPageDetailApiView

urlpatterns = [
    url(r'^(?P<language_code>[\w-]+)/pages/$', VueCmsPageDetailApiView.as_view(), name='cms_page_detail_home'),
    url(r'^(?P<language_code>[\w-]+)/pages/(?P<path>.*)/$', VueCmsPageDetailApiView.as_view(), name='cms_page_detail'),
]
