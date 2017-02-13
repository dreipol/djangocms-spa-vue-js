# coding=utf-8
from django.conf.urls import url

from djangocms_spa_vue_js.views import CMSPageDetailAPIView

urlpatterns = [
    url(r'^pages/(?P<path>.*)$', CMSPageDetailAPIView.as_view(), name='cms_page_detail'),
    ]