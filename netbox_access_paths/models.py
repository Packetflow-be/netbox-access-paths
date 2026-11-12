from urllib.parse import urlsplit

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel

from .choices import AccessMethodChoices, AccessPathStatusChoices, AuthenticationChoices, OriginChoices

__all__ = ('AccessHop', 'AccessPath', 'AccessRoute', 'TARGET_MODELS')

# What a path can lead to: a device, a VM, an application service or an IP address (or a URL, see target_url)
TARGET_MODELS = Q(
    Q(app_label='dcim', model='device') |
    Q(app_label='virtualization', model='virtualmachine') |
    Q(app_label='ipam', model='service') |
    Q(app_label='ipam', model='ipaddress')
)


class AccessRoute(PrimaryModel):
    """
    The MSP-side part of an access path: where sessions start and the hops they take out of the MSP's own network
    (office -> ZTNA -> jump host). Many paths share one route; a route without hops is fine (e.g. "Anywhere").
    """
    name = models.CharField(verbose_name=_('name'), max_length=100, unique=True, db_collation='natural_sort')
    origin = models.CharField(
        verbose_name=_('origin'),
        max_length=30,
        choices=OriginChoices,
        help_text=_('Where sessions on this route start'),
    )
    origin_prefixes = models.ManyToManyField(
        to='ipam.Prefix',
        related_name='access_paths_routes',
        verbose_name=_('origin prefixes'),
        blank=True,
        help_text=_('Networks the sessions start from, e.g. the office VLAN'),
    )
    tenant = models.ForeignKey(
        to='tenancy.Tenant',
        on_delete=models.PROTECT,
        related_name='access_paths_routes',
        verbose_name=_('tenant'),
        blank=True,
        null=True,
        help_text=_("Normally the MSP's own tenant"),
    )

    clone_fields = ('origin', 'tenant')

    class Meta:
        ordering = ('name',)
        verbose_name = _('access route')
        verbose_name_plural = _('access routes')

    def __str__(self):
        return self.name

    def get_origin_color(self):
        return OriginChoices.colors.get(self.origin)


class AccessPath(PrimaryModel):
    """
    One way into one customer system: a route, the customer-side hops, the method and the target; who may use it,
    how they authenticate and where the credential lives (a reference, never the secret); approval, review and
    expiry.
    """
    name = models.CharField(
        verbose_name=_('name'),
        max_length=100,
        db_collation='natural_sort',
        blank=True,
        help_text=_('Left empty, it is made from the target and the method'),
    )
    tenant = models.ForeignKey(
        to='tenancy.Tenant',
        on_delete=models.PROTECT,
        related_name='access_paths',
        verbose_name=_('customer (tenant)'),
    )
    route = models.ForeignKey(
        to=AccessRoute,
        on_delete=models.PROTECT,
        related_name='paths',
        verbose_name=_('route'),
        help_text=_('Where the session starts and the hops on the MSP side'),
    )
    target_type = models.ForeignKey(
        to='contenttypes.ContentType',
        on_delete=models.PROTECT,
        related_name='+',
        limit_choices_to=TARGET_MODELS,
        verbose_name=_('target type'),
        blank=True,
        null=True,
    )
    target_id = models.PositiveBigIntegerField(verbose_name=_('target ID'), blank=True, null=True)
    target = GenericForeignKey(ct_field='target_type', fk_field='target_id')
    target_url = models.URLField(
        verbose_name=_('target URL'),
        blank=True,
        help_text=_('For web portals and cloud consoles; may be given together with a target object'),
    )
    method = models.CharField(
        verbose_name=_('method'),
        max_length=30,
        choices=AccessMethodChoices,
    )
    holders = models.ManyToManyField(
        to='tenancy.Contact',
        related_name='access_paths',
        verbose_name=_('holders'),
        blank=True,
        help_text=_('People who may use this path'),
    )
    holder_groups = models.ManyToManyField(
        to='tenancy.ContactGroup',
        related_name='access_paths',
        verbose_name=_('holder groups'),
        blank=True,
        help_text=_('Groups of people who may use this path (members of sub-groups included)'),
    )
    authentication = models.CharField(
        verbose_name=_('authentication'),
        max_length=30,
        choices=AuthenticationChoices,
        default=AuthenticationChoices.UNKNOWN,
    )
    credential_ref = models.CharField(
        verbose_name=_('credential reference'),
        max_length=200,
        blank=True,
        help_text=_('Where the credential is kept, e.g. "Vault: Acme/dc01 admin". Never paste the secret itself.'),
    )
    status = models.CharField(
        verbose_name=_('status'),
        max_length=30,
        choices=AccessPathStatusChoices,
        default=AccessPathStatusChoices.ACTIVE,
    )
    approved_by = models.ForeignKey(
        to='tenancy.Contact',
        on_delete=models.PROTECT,
        related_name='access_paths_approved',
        verbose_name=_('approved by'),
        blank=True,
        null=True,
        help_text=_('Normally someone at the customer'),
    )
    approved_on = models.DateField(
        verbose_name=_('approved on'),
        blank=True,
        null=True,
        help_text=_('Filled in with today when an approver is set and no date is given'),
    )
    review_by = models.DateField(
        verbose_name=_('review by'),
        blank=True,
        null=True,
        help_text=_('Date by which the path should be reviewed'),
    )
    expires = models.DateField(
        verbose_name=_('expires'),
        blank=True,
        null=True,
        help_text=_('For temporary or vendor access: the path should be gone after this date'),
    )

    clone_fields = ('tenant', 'route', 'method', 'authentication', 'status', 'approved_by', 'review_by')

    class Meta:
        ordering = ('tenant', 'name', 'pk')
        verbose_name = _('access path')
        verbose_name_plural = _('access paths')
        indexes = (
            models.Index(fields=('target_type', 'target_id')),
        )

    def __str__(self):
        return self.name or self.default_name()

    def default_name(self):
        parts = []
        if self.target_type_id and self.target_id:
            try:
                parts.append(str(self.target))
            except ObjectDoesNotExist:
                pass
        if not parts and self.target_url:
            parts.append(urlsplit(self.target_url).hostname or self.target_url)
        if self.method:
            parts.append(str(self.get_method_display()))
        return ' '.join(parts)[:100]

    def clean(self):
        super().clean()
        if bool(self.target_type_id) != bool(self.target_id):
            raise ValidationError({'target_id': _('A target needs both its type and its ID.')})
        if not self.target_type_id and not self.target_url:
            raise ValidationError(_('An access path needs a target object, a target URL or both.'))
        if self.target_type_id:
            allowed = ContentType.objects.filter(TARGET_MODELS)
            if not allowed.filter(pk=self.target_type_id).exists():
                raise ValidationError({'target_type': _('A target is a device, virtual machine, service or IP '
                                                        'address.')})
            if self.target is None:
                raise ValidationError({'target_id': _('The target object does not exist.')})
        if self.approved_on and self.approved_on > timezone.localdate():
            raise ValidationError({'approved_on': _('The approval date is in the future.')})

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = self.default_name()
        # The approval date goes with the approver: a new or different approver without a new date is dated today.
        if self.approved_by_id:
            before = AccessPath.objects.filter(pk=self.pk).values('approved_by', 'approved_on').first() \
                if self.pk else None
            if not self.approved_on:
                self.approved_on = timezone.localdate()
            elif before and before['approved_by'] != self.approved_by_id and before['approved_on'] == self.approved_on:
                self.approved_on = timezone.localdate()
        super().save(*args, **kwargs)

    @property
    def is_live(self):
        """Active, planned and break-glass paths count in reviews; disabled ones don't."""
        return self.status != AccessPathStatusChoices.DISABLED

    @property
    def is_expired(self):
        return self.is_live and bool(self.expires) and self.expires < timezone.localdate()

    @property
    def is_review_due(self):
        return self.is_live and bool(self.review_by) and self.review_by <= timezone.localdate()

    @property
    def lacks_mfa(self):
        return self.authentication in AuthenticationChoices.LACKS_MFA

    @property
    def is_target_missing(self):
        """The target object was deleted and no URL is left."""
        return not self.target_type_id and not self.target_url

    @property
    def target_tenant(self):
        """The target's own tenant (a service has its parent's), or None."""
        target = self.target
        if target is None:
            return None
        if getattr(target, 'tenant_id', None):
            return target.tenant
        parent = getattr(target, 'parent', None)
        if parent is not None and getattr(parent, 'tenant_id', None):
            return parent.tenant
        return None

    @property
    def tenant_mismatch(self):
        """The target belongs to another tenant than the path (shown as a warning, not refused)."""
        target_tenant = self.target_tenant
        return target_tenant is not None and target_tenant.pk != self.tenant_id

    @property
    def target_display(self):
        if self.target_type_id and self.target is not None:
            return str(self.target)
        return self.target_url

    @property
    def all_hops(self):
        """Route hops, then the path's own hops, each in order."""
        return [*self.route.hops.all(), *self.hops.all()]

    def get_method_color(self):
        return AccessMethodChoices.colors.get(self.method)

    def get_authentication_color(self):
        return AuthenticationChoices.colors.get(self.authentication)

    def get_status_color(self):
        return AccessPathStatusChoices.colors.get(self.status)


class AccessHop(PrimaryModel):
    """
    One step on a route (MSP side) or on a path (customer side), in order: a device, a VM, a tunnel, or a label for
    something that is not in NetBox (a cloud relay, a vendor's portal).
    """
    route = models.ForeignKey(
        to=AccessRoute,
        on_delete=models.CASCADE,
        related_name='hops',
        verbose_name=_('route'),
        blank=True,
        null=True,
    )
    path = models.ForeignKey(
        to=AccessPath,
        on_delete=models.CASCADE,
        related_name='hops',
        verbose_name=_('path'),
        blank=True,
        null=True,
    )
    position = models.PositiveSmallIntegerField(
        verbose_name=_('position'),
        help_text=_('Order along the route or path, starting at 1'),
    )
    device = models.ForeignKey(
        to='dcim.Device',
        on_delete=models.CASCADE,
        related_name='access_paths_hops',
        verbose_name=_('device'),
        blank=True,
        null=True,
    )
    virtual_machine = models.ForeignKey(
        to='virtualization.VirtualMachine',
        on_delete=models.CASCADE,
        related_name='access_paths_hops',
        verbose_name=_('virtual machine'),
        blank=True,
        null=True,
    )
    tunnel = models.ForeignKey(
        to='vpn.Tunnel',
        on_delete=models.CASCADE,
        related_name='access_paths_hops',
        verbose_name=_('tunnel'),
        blank=True,
        null=True,
    )
    label = models.CharField(
        verbose_name=_('label'),
        max_length=100,
        blank=True,
        help_text=_('For a hop that is not in NetBox, e.g. "NetBird cloud" or "TeamViewer relay"'),
    )

    clone_fields = ('route', 'path')

    class Meta:
        ordering = ('route', 'path', 'position')
        verbose_name = _('access hop')
        verbose_name_plural = _('access hops')
        constraints = (
            models.UniqueConstraint(
                fields=('route', 'position'),
                condition=Q(route__isnull=False),
                name='%(app_label)s_%(class)s_unique_route_position',
                violation_error_message=_('This route already has a hop at this position.'),
            ),
            models.UniqueConstraint(
                fields=('path', 'position'),
                condition=Q(path__isnull=False),
                name='%(app_label)s_%(class)s_unique_path_position',
                violation_error_message=_('This path already has a hop at this position.'),
            ),
            models.CheckConstraint(
                condition=Q(route__isnull=False, path__isnull=True) | Q(route__isnull=True, path__isnull=False),
                name='%(app_label)s_%(class)s_route_or_path',
                violation_error_message=_('A hop belongs to exactly one route or one path.'),
            ),
        )

    def __str__(self):
        return f'{self.position}. {self.hop}'

    @property
    def hop(self):
        return self.device or self.virtual_machine or self.tunnel or self.label

    @property
    def parent(self):
        return self.route or self.path

    def clean(self):
        super().clean()
        if bool(self.route_id) == bool(self.path_id):
            raise ValidationError(_('A hop belongs to exactly one route or one path.'))
        if sum(bool(x) for x in (self.device_id, self.virtual_machine_id, self.tunnel_id, self.label)) != 1:
            raise ValidationError(_('A hop is exactly one device, virtual machine, tunnel or label.'))
