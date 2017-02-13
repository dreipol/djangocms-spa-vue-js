from django.conf.urls import url

from .views import CMSPageDetailAPIView

urlpatterns = [
    url(r'^pages/(?P<path>.*)$', CMSPageDetailAPIView.as_view(), name='cms_page_detail'),
]
