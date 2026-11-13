from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from extras.dashboard.utils import register_widget
from extras.dashboard.widgets import DashboardWidget

from . import queries
from .models import AccessPath

__all__ = ('AccessReviewWidget',)


@register_widget
class AccessReviewWidget(DashboardWidget):
    """The review queue's counts on the home screen, each linked to the matching list."""
    default_title = _('Access review')
    description = _('Access paths that need a person: expired, review due, without MFA, break-glass, target missing.')
    template_name = 'netbox_access_paths/widgets/review.html'
    width = 4
    height = 3

    def render(self, request):
        permitted = request.user.has_perm('netbox_access_paths.view_accesspath')
        rows = []
        if permitted:
            visible = AccessPath.objects.restrict(request.user, 'view')
            list_url = reverse('plugins:netbox_access_paths:accesspath_list')
            rows = [
                (title, visible.filter(q()).count(), f'{list_url}?{key}=true')
                for key, title, q, _date_field, _help_text in queries.REVIEW_SECTIONS
            ]
        return render_to_string(self.template_name, {
            'permitted': permitted,
            'rows': rows,
            'review_url': reverse('plugins:netbox_access_paths:review'),
        })
