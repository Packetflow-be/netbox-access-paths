import datetime

from django.test import TestCase
from django.utils import timezone

from dcim.models import Interface
from ipam.models import IPAddress, Prefix
from tenancy.models import Contact, ContactGroup, Tenant
from utilities.testing import ChangeLoggedFilterSetTestMixin, create_test_device, create_test_virtualmachine
from vpn.models import Tunnel

from netbox_access_paths.filtersets import AccessHopFilterSet, AccessPathFilterSet, AccessRouteFilterSet
from netbox_access_paths.models import AccessHop, AccessPath, AccessRoute

TODAY = timezone.localdate()
DAY = datetime.timedelta(days=1)


class AccessRouteFilterSetTest(TestCase, ChangeLoggedFilterSetTestMixin):
    queryset = AccessRoute.objects.all()
    filterset = AccessRouteFilterSet
    filter_name_map = {'prefix': 'origin_prefix'}

    @classmethod
    def setUpTestData(cls):
        cls.msp = Tenant.objects.create(name='MSP', slug='msp')
        cls.prefix = Prefix.objects.create(prefix='10.0.10.0/24')
        cls.jump = create_test_device('jump01')
        cls.tunnel = Tunnel.objects.create(name='wg0', status='active', encapsulation='wireguard')
        cls.vm = create_test_virtualmachine('jump02')
        routes = (
            AccessRoute.objects.create(name='Route 1', origin='office', tenant=cls.msp, description='foobar1'),
            AccessRoute.objects.create(name='Route 2', origin='ztna', tenant=cls.msp),
            AccessRoute.objects.create(name='Route 3', origin='internet'),
        )
        routes[0].origin_prefixes.add(cls.prefix)
        AccessHop.objects.create(route=routes[0], position=1, device=cls.jump)
        AccessHop.objects.create(route=routes[1], position=1, tunnel=cls.tunnel)
        AccessHop.objects.create(route=routes[1], position=2, virtual_machine=cls.vm)
        AccessHop.objects.create(route=routes[2], position=1, label='TeamViewer relay')

    def test_q(self):
        self.assertEqual(self.filterset({'q': 'foobar1'}, self.queryset).qs.count(), 1)
        self.assertEqual(self.filterset({'q': 'teamviewer'}, self.queryset).qs.count(), 1)

    def test_name(self):
        self.assertEqual(self.filterset({'name': ['Route 1', 'Route 2']}, self.queryset).qs.count(), 2)

    def test_origin(self):
        self.assertEqual(self.filterset({'origin': ['office', 'ztna']}, self.queryset).qs.count(), 2)

    def test_tenant(self):
        self.assertEqual(self.filterset({'tenant_id': [self.msp.pk]}, self.queryset).qs.count(), 2)

    def test_origin_prefix(self):
        self.assertEqual(self.filterset({'origin_prefix_id': [self.prefix.pk]}, self.queryset).qs.count(), 1)

    def test_hops(self):
        self.assertEqual(self.filterset({'hop_device_id': [self.jump.pk]}, self.queryset).qs.count(), 1)
        self.assertEqual(self.filterset({'hop_virtual_machine_id': [self.vm.pk]}, self.queryset).qs.count(), 1)
        self.assertEqual(self.filterset({'hop_tunnel_id': [self.tunnel.pk]}, self.queryset).qs.count(), 1)


class AccessPathFilterSetTest(TestCase, ChangeLoggedFilterSetTestMixin):
    queryset = AccessPath.objects.all()
    filterset = AccessPathFilterSet
    filter_name_map = {'contact': 'holder', 'contact_group': 'holder_group'}

    @classmethod
    def setUpTestData(cls):
        cls.tenants = (
            Tenant.objects.create(name='Acme', slug='acme'),
            Tenant.objects.create(name='Globex', slug='globex'),
        )
        cls.routes = (
            AccessRoute.objects.create(name='Office', origin='office'),
            AccessRoute.objects.create(name='Anywhere', origin='internet'),
        )
        cls.jump = create_test_device('jump01')
        AccessHop.objects.create(route=cls.routes[0], position=1, device=cls.jump)
        cls.dc01 = create_test_device('dc01')
        ip = IPAddress.objects.create(
            address='10.1.0.10/24',
            assigned_object=Interface.objects.create(device=cls.dc01, name='eth0', type='1000base-t'),
        )
        cls.vm = create_test_virtualmachine('app01')
        cls.fw = create_test_device('globex-fw')
        support = ContactGroup.objects.create(name='Support', slug='support')
        cls.tier2 = ContactGroup.objects.create(name='Tier 2', slug='tier-2', parent=support)
        cls.jane = Contact.objects.create(name='Jane')
        cls.jane.groups.add(cls.tier2)
        cls.bob = Contact.objects.create(name='Bob')
        cls.approver = Contact.objects.create(name='Acme IT manager')
        paths = (
            AccessPath.objects.create(
                name='Path 1', tenant=cls.tenants[0], route=cls.routes[0], target=cls.dc01, method='rdp',
                authentication='sso_mfa', approved_by=cls.approver, review_by=TODAY + 30 * DAY,
                credential_ref='Vault: Acme/dc01', description='foobar1',
            ),
            AccessPath.objects.create(
                name='Path 2', tenant=cls.tenants[0], route=cls.routes[0], target=ip, method='ssh',
                authentication='password', review_by=TODAY - DAY,
            ),
            AccessPath.objects.create(
                name='Path 3', tenant=cls.tenants[1], route=cls.routes[1], target=cls.vm, method='vendor_remote',
                authentication='shared_account', status='break_glass', expires=TODAY - DAY,
            ),
            AccessPath.objects.create(
                name='Path 4', tenant=cls.tenants[1], route=cls.routes[1], target_url='https://portal.example.com',
                method='web', authentication='mfa', status='disabled', expires=TODAY - DAY,
            ),
        )
        paths[0].holders.add(cls.bob)
        paths[1].holder_groups.add(support)
        paths[2].holder_groups.add(cls.tier2)
        AccessHop.objects.create(path=paths[3], position=1, device=cls.fw)
        cls.paths = paths

    def count(self, params):
        return self.filterset(params, self.queryset).qs.count()

    def test_q(self):
        self.assertEqual(self.count({'q': 'foobar1'}), 1)
        self.assertEqual(self.count({'q': 'vault: acme'}), 1)
        self.assertEqual(self.count({'q': 'portal.example'}), 1)
        self.assertEqual(self.count({'q': 'globex'}), 2)

    def test_name(self):
        self.assertEqual(self.count({'name': ['Path 1', 'Path 2']}), 2)

    def test_tenant_and_route(self):
        self.assertEqual(self.count({'tenant_id': [self.tenants[0].pk]}), 2)
        self.assertEqual(self.count({'tenant': ['globex']}), 2)
        self.assertEqual(self.count({'route_id': [self.routes[1].pk]}), 2)
        self.assertEqual(self.count({'route': ['Office']}), 2)
        self.assertEqual(self.count({'origin': ['internet']}), 2)

    def test_method_authentication_status(self):
        self.assertEqual(self.count({'method': ['rdp', 'ssh']}), 2)
        self.assertEqual(self.count({'authentication': ['mfa', 'sso_mfa']}), 2)
        self.assertEqual(self.count({'status': ['break_glass']}), 1)

    def test_target(self):
        self.assertEqual(self.count({'target_type': ['dcim.device']}), 1)
        self.assertEqual(self.count({'target_type': ['dcim.device'], 'target_id': [self.dc01.pk]}), 1)
        # Into a device: the device itself and its IP addresses
        self.assertEqual(self.count({'device_id': [self.dc01.pk]}), 2)
        self.assertEqual(self.count({'virtual_machine_id': [self.vm.pk]}), 1)

    def test_runs_through(self):
        self.assertEqual(self.count({'hop_device_id': [self.jump.pk]}), 2)
        self.assertEqual(self.count({'hop_device_id': [self.fw.pk]}), 1)

    def test_holders(self):
        self.assertEqual(self.count({'holder_id': [self.bob.pk]}), 1)
        # Jane is in Tier 2, a sub-group of Support: both group grants reach her
        self.assertEqual(self.count({'holder_id': [self.jane.pk]}), 2)
        self.assertEqual(self.count({'holder_group_id': [self.tier2.pk]}), 1)

    def test_approved_by(self):
        self.assertEqual(self.count({'approved_by_id': [self.approver.pk]}), 1)

    def test_review_flags(self):
        # Disabled paths (Path 4) don't count as expired, due or without MFA
        self.assertEqual(self.count({'expired': True}), 1)
        self.assertEqual(self.count({'expired': False}), 3)
        self.assertEqual(self.count({'review_due': True}), 1)
        self.assertEqual(self.count({'lacks_mfa': True}), 2)
        self.assertEqual(self.count({'break_glass': True}), 1)
        self.assertEqual(self.count({'target_missing': True}), 0)
        self.assertEqual(self.count({'needs_review': True}), 2)
        self.assertEqual(self.count({'needs_review': False}), 2)


class AccessHopFilterSetTest(TestCase, ChangeLoggedFilterSetTestMixin):
    queryset = AccessHop.objects.all()
    filterset = AccessHopFilterSet

    @classmethod
    def setUpTestData(cls):
        cls.route = AccessRoute.objects.create(name='Office', origin='office')
        cls.tenant = Tenant.objects.create(name='Acme', slug='acme')
        cls.path = AccessPath.objects.create(tenant=cls.tenant, route=cls.route, target_url='https://x.example.com',
                                             method='web')
        cls.device = create_test_device('jump01')
        cls.vm = create_test_virtualmachine('jump02')
        cls.tunnel = Tunnel.objects.create(name='wg0', status='active', encapsulation='wireguard')
        AccessHop.objects.create(route=cls.route, position=1, label='NetBird cloud', description='foobar1')
        AccessHop.objects.create(route=cls.route, position=2, device=cls.device)
        AccessHop.objects.create(path=cls.path, position=1, virtual_machine=cls.vm)
        AccessHop.objects.create(path=cls.path, position=2, tunnel=cls.tunnel)

    def count(self, params):
        return self.filterset(params, self.queryset).qs.count()

    def test_q(self):
        self.assertEqual(self.count({'q': 'foobar1'}), 1)
        self.assertEqual(self.count({'q': 'netbird'}), 1)

    def test_parents(self):
        self.assertEqual(self.count({'route_id': [self.route.pk]}), 2)
        self.assertEqual(self.count({'path_id': [self.path.pk]}), 2)
        self.assertEqual(self.count({'tenant_id': [self.tenant.pk]}), 2)
        self.assertEqual(self.count({'on_route': True}), 2)
        self.assertEqual(self.count({'on_route': False}), 2)

    def test_hop(self):
        self.assertEqual(self.count({'device_id': [self.device.pk]}), 1)
        self.assertEqual(self.count({'virtual_machine_id': [self.vm.pk]}), 1)
        self.assertEqual(self.count({'tunnel_id': [self.tunnel.pk]}), 1)
        self.assertEqual(self.count({'label': ['NetBird cloud']}), 1)
        self.assertEqual(self.count({'position': [2]}), 2)
