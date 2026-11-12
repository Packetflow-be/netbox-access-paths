"""
Demo data: a small fictional MSP with three customers, four routes and seven access paths, so a new user sees
populated tenant, device and contact tabs, a path chain and a review queue within minutes. Everything it creates
is named or described "Access paths demo" (tenants in the tenant group of that name), and --delete removes
exactly that.
"""
import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

PREFIX = 'Access paths demo'
SLUG = 'access-paths-demo'


class Command(BaseCommand):
    help = 'Create (or --delete) a demo MSP with customers, routes and access paths to try the plugin'

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true', help='Remove the demo data instead')

    def handle(self, *args, **options):
        from tenancy.models import TenantGroup

        if options['delete']:
            with transaction.atomic():
                self._delete()
            self.stdout.write(self.style.SUCCESS('Demo data removed'))
            return
        if TenantGroup.objects.filter(slug=SLUG).exists():
            raise CommandError(f'The demo tenant group "{SLUG}" already exists; remove it first with --delete')
        with transaction.atomic():
            self._create()
        self.stdout.write(self.style.SUCCESS(
            'Demo data created: open the tenant "Acme Bakery" and its Access paths tab, the device "msp-jump01" '
            '(everything runs through it), or Access paths > Review queue'))

    def _delete(self):
        from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site
        from ipam.models import IPAddress, Prefix, Service
        from tenancy.models import Contact, ContactGroup, Tenant, TenantGroup
        from virtualization.models import VirtualMachine
        from vpn.models import Tunnel

        from netbox_access_paths.models import AccessPath, AccessRoute

        tenants = Tenant.objects.filter(group__slug=SLUG)
        AccessPath.objects.filter(tenant__in=tenants).delete()
        AccessRoute.objects.filter(description=PREFIX).delete()
        sites = Site.objects.filter(slug__startswith=SLUG)
        devices = Device.objects.filter(site__in=sites)
        vms = VirtualMachine.objects.filter(site__in=sites)
        for asset in list(devices) + list(vms):
            Service.objects.filter(parent_object_id=asset.pk, parent_object_type__model=asset._meta.model_name).delete()
        IPAddress.objects.filter(description=PREFIX).delete()
        Tunnel.objects.filter(description=PREFIX).delete()
        for asset in list(vms) + list(devices):
            asset.delete()
        Prefix.objects.filter(description=PREFIX).delete()
        sites.delete()
        tenants.delete()
        TenantGroup.objects.filter(slug=SLUG).delete()
        Contact.objects.filter(description=PREFIX).delete()
        for group in ContactGroup.objects.filter(description=PREFIX).order_by('-parent_id'):
            group.delete()
        DeviceType.objects.filter(manufacturer__name=PREFIX).delete()
        Manufacturer.objects.filter(name=PREFIX).delete()
        DeviceRole.objects.filter(name__startswith=PREFIX).delete()

    def _create(self):
        from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
        from ipam.models import IPAddress, Prefix, Service
        from tenancy.models import Contact, ContactGroup, Tenant, TenantGroup
        from virtualization.models import VirtualMachine, VMInterface
        from vpn.models import Tunnel

        from netbox_access_paths.models import AccessHop, AccessPath, AccessRoute

        today = timezone.localdate()
        days = datetime.timedelta

        group = TenantGroup.objects.create(name=PREFIX, slug=SLUG)
        tenants = {}
        sites = {}
        for name in ('Demo MSP', 'Acme Bakery', 'Globex Logistics', 'Initech Dental'):
            slug = name.lower().replace(' ', '-')
            tenants[name] = Tenant.objects.create(name=name, slug=f'{SLUG}-{slug}', group=group,
                                                  description=PREFIX)
            sites[name] = Site.objects.create(name=f'{name} ({PREFIX})', slug=f'{SLUG}-{slug}',
                                              tenant=tenants[name], description=PREFIX)

        manufacturer = Manufacturer.objects.create(name=PREFIX, slug=SLUG)
        server_type = DeviceType.objects.create(manufacturer=manufacturer, model='Server', slug=f'{SLUG}-server')
        fw_type = DeviceType.objects.create(manufacturer=manufacturer, model='Firewall', slug=f'{SLUG}-firewall')
        server_role = DeviceRole.objects.create(name=f'{PREFIX} server', slug=f'{SLUG}-server')
        fw_role = DeviceRole.objects.create(name=f'{PREFIX} firewall', slug=f'{SLUG}-firewall')

        def device(name, owner, kind='server', ip=None):
            obj = Device.objects.create(
                name=name, site=sites[owner], tenant=tenants[owner], description=PREFIX,
                device_type=server_type if kind == 'server' else fw_type,
                role=server_role if kind == 'server' else fw_role,
            )
            address = None
            if ip:
                iface = Interface.objects.create(device=obj, name='eth0', type='1000base-t')
                address = IPAddress.objects.create(address=ip, assigned_object=iface, tenant=tenants[owner],
                                                   description=PREFIX)
            return obj, address

        msp_fw, _ = device('msp-fw01', 'Demo MSP', 'firewall')
        msp_jump, _ = device('msp-jump01', 'Demo MSP')
        acme_fw, _ = device('acme-fw01', 'Acme Bakery', 'firewall')
        acme_dc, _ = device('acme-dc01', 'Acme Bakery')
        _, globex_nas_ip = device('globex-nas01', 'Globex Logistics', ip='10.20.0.5/24')
        initech_srv, _ = device('initech-srv01', 'Initech Dental')
        globex_app = VirtualMachine.objects.create(name='globex-app01', site=sites['Globex Logistics'],
                                                   tenant=tenants['Globex Logistics'], description=PREFIX)
        VMInterface.objects.create(virtual_machine=globex_app, name='eth0')
        acme_fw_https = Service.objects.create(parent=acme_fw, name='https', port_mappings=['tcp/443'],
                                               description=PREFIX)
        office_vlan = Prefix.objects.create(prefix='10.99.10.0/24', tenant=tenants['Demo MSP'], description=PREFIX)
        tunnel = Tunnel.objects.create(name='MSP - Acme IPsec', status='active', encapsulation='ipsec-tunnel',
                                       tenant=tenants['Acme Bakery'], description=PREFIX)

        support = ContactGroup.objects.create(name='Demo MSP support', slug=f'{SLUG}-support',
                                              description=PREFIX)
        tier2 = ContactGroup.objects.create(name='Tier 2', slug=f'{SLUG}-tier-2', parent=support, description=PREFIX)

        def contact(name, *groups):
            obj = Contact.objects.create(name=name, description=PREFIX)
            obj.groups.set(groups)
            return obj

        alex = contact('Alex Engineer', tier2)
        sam = contact('Sam Engineer', support)
        vendor = contact('DentalSoft support desk')
        acme_it = contact('Acme Bakery IT contact')
        initech_owner = contact('Initech Dental practice owner')

        def route(name, origin, *hops, prefixes=()):
            obj = AccessRoute.objects.create(name=name, origin=origin, tenant=tenants['Demo MSP'], description=PREFIX)
            obj.origin_prefixes.set(prefixes)
            for i, hop in enumerate(hops, start=1):
                kind = {Device: 'device', Tunnel: 'tunnel'}.get(type(hop), 'label')
                AccessHop.objects.create(route=obj, position=i, **{kind: hop})
            return obj

        office = route('Office -> msp-jump01', 'office', msp_fw, msp_jump, prefixes=[office_vlan])
        ztna = route('ZTNA -> msp-jump01', 'ztna', 'ZTNA cloud', msp_jump)
        anywhere = route('Anywhere (vendor tools)', 'internet')
        on_site = route('On site', 'customer_site')

        def path(customer, via, method, *hops, holders=(), groups=(), **kwargs):
            obj = AccessPath.objects.create(tenant=tenants[customer], route=via, method=method, **kwargs)
            obj.holders.set(holders)
            obj.holder_groups.set(groups)
            for i, hop in enumerate(hops, start=1):
                kind = {Device: 'device', Tunnel: 'tunnel'}.get(type(hop), 'label')
                AccessHop.objects.create(path=obj, position=i, **{kind: hop})
            return obj

        path('Acme Bakery', office, 'rdp', tunnel, acme_fw, target=acme_dc, groups=[support],
             authentication='sso_mfa', credential_ref='Password manager: Acme Bakery / dc01 admin',
             approved_by=acme_it, approved_on=today - days(150), review_by=today + days(30))
        path('Acme Bakery', ztna, 'web', target=acme_fw_https, holders=[alex], authentication='mfa',
             approved_by=acme_it, approved_on=today - days(400), review_by=today - days(35),
             description='Firewall management GUI')
        path('Acme Bakery', anywhere, 'web', name='Microsoft 365 admin center', target_url='https://admin.microsoft.com',
             groups=[support], authentication='sso_mfa', review_by=today + days(120))
        path('Globex Logistics', ztna, 'ssh', target=globex_app, holders=[alex], authentication='key',
             review_by=today + days(200))
        path('Globex Logistics', office, 'web', target=globex_nas_ip, holders=[sam], authentication='password',
             description='NAS web interface, local admin account')
        path('Initech Dental', anywhere, 'vendor_remote', 'TeamViewer cloud', name='DentalSoft vendor support',
             target=initech_srv, holders=[vendor], authentication='shared_account',
             approved_by=initech_owner, approved_on=today - days(60), expires=today - days(5),
             description='Temporary access for the practice software upgrade')
        path('Initech Dental', on_site, 'console', name='Break-glass local admin', target=initech_srv,
             groups=[support], authentication='password', status='break_glass',
             credential_ref='Sealed envelope in the practice safe')
