from django.urls import re_path

from plugins.consortial_billing import views

urlpatterns = [
    re_path(
        r'^$',
        views.supporters,
        name='public_supporter_list',
    ),
    re_path(
        r'^manager/$',
        views.manager,
        name='supporters_manager',
    ),
    re_path(
        r'^site/(?P<page_name>.*)/$',
        views.view_custom_page,
        name='supporters_custom_page',
    ),
    re_path(
        r'^signup/$',
        views.signup,
        name='supporter_signup',
    ),
    re_path(
        r'^search/$',
        views.SupporterList.as_view(),
        name='supporter_list',
    ),
    re_path(
        r'^new-supporter/$',
        views.edit_supporter_band,
        name='new_supporter',
    ),
    re_path(
        r'^edit-supporter-band/(?P<supporter_id>\d+)/$',
        views.edit_supporter_band,
        name='edit_supporter_band',
    ),
]
