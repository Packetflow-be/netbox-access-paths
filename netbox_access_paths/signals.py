from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete

TARGET_SENDERS = (
    'dcim.Device', 'virtualization.VirtualMachine', 'ipam.Service', 'ipam.IPAddress',
    'ipam.Prefix', 'ipam.VLAN', 'virtualization.Cluster', 'dcim.Site', 'tenancy.Tenant',
)


def clear_deleted_target(sender, instance, **kwargs):
    """
    A deleted target leaves its paths without a target rather than pointing at nothing: the path stays (it is
    documentation someone has to review) and shows up in the review queue as "target missing".
    Saved one by one so the change log records it.
    """
    from .models import AccessPath

    content_type = ContentType.objects.get_for_model(sender)
    for path in AccessPath.objects.filter(target_type=content_type, target_id=instance.pk):
        if hasattr(path, 'snapshot'):
            path.snapshot()
        path.target_type = None
        path.target_id = None
        path.save()


def connect():
    from django.apps import apps

    for label in TARGET_SENDERS:
        post_delete.connect(clear_deleted_target, sender=apps.get_model(label),
                            dispatch_uid=f'netbox_access_paths_clear_target_{label}')
