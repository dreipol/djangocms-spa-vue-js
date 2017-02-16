from django.conf.urls import url

from .views import VueCmsPageDetailApiView

urlpatterns = [
    url(r'^pages/(?P<path>.*)$', VueCmsPageDetailApiView.as_view(), name='cms_page_detail'),
]
