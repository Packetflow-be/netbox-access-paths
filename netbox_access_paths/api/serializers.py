from django.contrib.contenttypes.models import ContentType
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from dcim.api.serializers import DeviceSerializer
from ipam.api.serializers import PrefixSerializer
from ipam.models import Prefix
from netbox.api.fields import ChoiceField, ContentTypeField, SerializedPKRelatedField
from netbox.api.gfk_fields import GFKSerializerField
from netbox.api.serializers import PrimaryModelSerializer
from tenancy.api.serializers import ContactGroupSerializer, ContactSerializer, TenantSerializer
from tenancy.models import Contact, ContactGroup
from users.api.serializers import UserSerializer
from virtualization.api.serializers import VirtualMachineSerializer
from vpn.api.serializers import TunnelSerializer

from ..choices import AccessMethodChoices, AccessPathStatusChoices, AuthenticationChoices, OriginChoices
from ..models import TARGET_MODELS, AccessHop, AccessPath, AccessRoute

__all__ = ('AccessHopSerializer', 'AccessPathSerializer', 'AccessRouteSerializer')


def _hop_kind(hop):
    if hop.device_id:
        return 'device'
    if hop.virtual_machine_id:
        return 'virtual-machine'
    if hop.tunnel_id:
        return 'tunnel'
    return 'label'


def hops_data(hops, side):
    return [{
        'id': hop.pk,
        'side': side,
        'position': hop.position,
        'kind': _hop_kind(hop),
        'object_id': hop.hop.pk if not hop.label else None,
        'name': hop.label or str(hop.hop),
    } for hop in hops]


class AccessRouteSerializer(PrimaryModelSerializer):
    origin = ChoiceField(choices=OriginChoices)
    origin_prefixes = SerializedPKRelatedField(
        queryset=Prefix.objects.all(), serializer=PrefixSerializer, nested=True, required=False, many=True,
    )
    tenant = TenantSerializer(nested=True, required=False, allow_null=True)
    hops = serializers.SerializerMethodField(read_only=True)
    path_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = AccessRoute
        fields = (
            'id', 'url', 'display_url', 'display', 'name', 'origin', 'origin_prefixes', 'tenant', 'hops',
            'path_count', 'description', 'owner', 'comments', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'origin', 'description')

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_hops(self, obj):
        """The route's hops in order: position, kind (device, virtual-machine, tunnel, label), object id, name."""
        return hops_data(obj.hops.all(), 'route')


class AccessPathSerializer(PrimaryModelSerializer):
    tenant = TenantSerializer(nested=True)
    route = AccessRouteSerializer(nested=True)
    target_type = ContentTypeField(
        queryset=ContentType.objects.filter(TARGET_MODELS), required=False, allow_null=True,
    )
    target = GFKSerializerField(read_only=True)
    method = ChoiceField(choices=AccessMethodChoices)
    holders = SerializedPKRelatedField(
        queryset=Contact.objects.all(), serializer=ContactSerializer, nested=True, required=False, many=True,
    )
    holder_groups = SerializedPKRelatedField(
        queryset=ContactGroup.objects.all(), serializer=ContactGroupSerializer, nested=True, required=False,
        many=True,
    )
    authentication = ChoiceField(choices=AuthenticationChoices, required=False)
    status = ChoiceField(choices=AccessPathStatusChoices, required=False)
    approved_by = ContactSerializer(nested=True, required=False, allow_null=True)
    reviewed_by = UserSerializer(nested=True, required=False, allow_null=True)
    scope = serializers.BooleanField(source='is_scope', read_only=True)
    chain = serializers.SerializerMethodField(read_only=True)
    expired = serializers.BooleanField(source='is_expired', read_only=True)
    review_due = serializers.BooleanField(source='is_review_due', read_only=True)
    lacks_mfa = serializers.BooleanField(read_only=True)
    tenant_mismatch = serializers.BooleanField(read_only=True)

    class Meta:
        model = AccessPath
        fields = (
            'id', 'url', 'display_url', 'display', 'name', 'tenant', 'route', 'target_type', 'target_id', 'target',
            'scope', 'target_url', 'method', 'chain', 'holders', 'holder_groups', 'authentication', 'lacks_mfa',
            'credential_ref', 'status', 'approved_by', 'approved_on', 'reviewed_on', 'reviewed_by', 'review_by',
            'expires', 'expired',
            'review_due', 'tenant_mismatch', 'description', 'owner', 'comments', 'tags', 'custom_fields', 'created',
            'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'method', 'status', 'description')

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_chain(self, obj):
        """Every hop in order: the route's (side "route"), then the path's own (side "path")."""
        return hops_data(obj.route.hops.all(), 'route') + hops_data(obj.hops.all(), 'path')


class AccessHopSerializer(PrimaryModelSerializer):
    route = AccessRouteSerializer(nested=True, required=False, allow_null=True)
    path = AccessPathSerializer(nested=True, required=False, allow_null=True)
    device = DeviceSerializer(nested=True, required=False, allow_null=True)
    virtual_machine = VirtualMachineSerializer(nested=True, required=False, allow_null=True)
    tunnel = TunnelSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = AccessHop
        fields = (
            'id', 'url', 'display_url', 'display', 'route', 'path', 'position', 'device', 'virtual_machine', 'tunnel',
            'label', 'description', 'owner', 'comments', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'position', 'label', 'description')
